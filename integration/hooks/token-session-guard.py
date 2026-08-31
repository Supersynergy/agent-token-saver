#!/usr/bin/env python3
"""Fail-open Codex/Claude Stop hook for cumulative token/context warnings."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

MAX_EVENT_BYTES = 1_000_000
MAX_INCREMENTAL_BYTES = 8_000_000
STATE_MAX_BYTES = 16_384
HASH_WINDOW_BYTES = 4_096
STATE_RETENTION_SECONDS = 14 * 24 * 3_600
ACTION_RANK = {"continue": 0, "warn": 1, "checkpoint_required": 2}


def emit(payload: dict[str, Any] | None = None) -> None:
    json.dump(payload or {}, sys.stdout, ensure_ascii=False, separators=(",", ":"))


def read_event() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
    if len(raw) > MAX_EVENT_BYTES:
        return {}
    try:
        value = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def allowed_transcript_roots(home: Path) -> list[Path]:
    roots = [home / ".codex", home / ".claude"]
    extra = os.environ.get("ATS_TRANSCRIPT_ROOTS", "")
    roots.extend(Path(value).expanduser() for value in extra.split(os.pathsep) if value)
    return [root.resolve() for root in roots if root.exists()]


def safe_file(raw_path: Any, *, roots: list[Path] | None = None) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    try:
        path = Path(raw_path).expanduser().resolve(strict=True)
        metadata = path.stat()
    except OSError:
        return None
    if not path.is_file() or metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
        return None
    if roots is not None and not any(path.is_relative_to(root) for root in roots):
        return None
    return path


def ledger_path(home: Path) -> Path | None:
    return safe_file(
        os.environ.get(
            "ATS_LEDGER_PATH", str(home / ".agent-token-saver" / "bin" / "agent-token-ledger")
        )
    )


def load_ledger_module(ledger: Path) -> Any | None:
    try:
        spec = importlib.util.spec_from_file_location("ats_guard_ledger", ledger)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (ImportError, OSError, ValueError):
        return None
    return module


def run_ledger(transcript: Path, home: Path) -> dict[str, Any] | None:
    ledger = ledger_path(home)
    if ledger is None:
        return None
    provider = "claude" if ".claude" in transcript.parts else "codex"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ledger),
                "--usage",
                f"parent={transcript}",
                "--provider",
                provider,
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        payload = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def file_identity(transcript: Path, metadata: os.stat_result) -> str:
    path_hash = hashlib.sha256(str(transcript).encode()).hexdigest()
    raw = f"{metadata.st_dev}:{metadata.st_ino}:{path_hash}".encode()
    return hashlib.sha256(raw).hexdigest()


def segment_hash(transcript: Path, end: int, *, window: int = HASH_WINDOW_BYTES) -> str | None:
    if end < 0:
        return None
    try:
        with transcript.open("rb") as handle:
            handle.seek(max(0, end - window))
            return hashlib.sha256(handle.read(min(window, end))).hexdigest()
    except OSError:
        return None


def prefix_hash(transcript: Path) -> str | None:
    try:
        with transcript.open("rb") as handle:
            return hashlib.sha256(handle.read(HASH_WINDOW_BYTES)).hexdigest()
    except OSError:
        return None


def stable_stat(transcript: Path) -> os.stat_result | None:
    try:
        metadata = transcript.stat()
    except OSError:
        return None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o022
    ):
        return None
    return metadata


def same_file(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_mode,
        before.st_uid,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_mode,
        after.st_uid,
    )


def valid_cursor_state(state: dict[str, Any], transcript: Path, metadata: os.stat_result) -> bool:
    if state.get("schema_version") != 2:
        return False
    cursor = state.get("cursor")
    if not isinstance(cursor, dict):
        return False
    offset = cursor.get("byte_offset")
    if (
        not isinstance(offset, int)
        or offset < 0
        or offset > metadata.st_size
        or state.get("transcript_bytes") != offset
        or state.get("transcript_fingerprint") != file_identity(transcript, metadata)
        or not isinstance(cursor.get("prefix_sha256"), str)
        or not isinstance(cursor.get("tail_sha256"), str)
    ):
        return False
    return cursor["prefix_sha256"] == prefix_hash(transcript) and cursor[
        "tail_sha256"
    ] == segment_hash(transcript, offset)


def source_from_accumulator(
    module: Any, transcript: Path, accumulator: dict[str, Any]
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    usage, metadata = module.usage_from_accumulator(accumulator)
    return usage, [
        {"name": "parent", "path": str(transcript), "usage": usage, "metadata": metadata}
    ]


def build_full_ledger(
    module: Any, transcript: Path, provider: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    try:
        accumulator = module.inspect_usage_accumulator(transcript)
        usage, sources = source_from_accumulator(module, transcript, accumulator)
        return module.build_ledger(usage, [], provider, usage_sources=sources), accumulator
    except (AttributeError, OSError, ValueError, TypeError):
        return None


def build_incremental_ledger(
    module: Any, transcript: Path, provider: str, state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], int] | None:
    before = stable_stat(transcript)
    if before is None or not valid_cursor_state(state, transcript, before):
        return None
    accumulator = state.get("accumulator")
    if not isinstance(accumulator, dict):
        return None
    offset = state["cursor"]["byte_offset"]
    try:
        if before.st_size == offset:
            module.usage_from_accumulator(accumulator)
            next_accumulator = json.loads(json.dumps(accumulator, separators=(",", ":")))
            next_offset = offset
        else:
            result = module.inspect_usage_suffix(
                transcript, offset, accumulator, max_bytes=MAX_INCREMENTAL_BYTES
            )
            if result is None:
                return None
            next_accumulator, next_offset = result
        after = stable_stat(transcript)
        if after is None or not same_file(before, after) or next_offset != after.st_size:
            return None
        usage, sources = source_from_accumulator(module, transcript, next_accumulator)
        ledger = module.build_ledger(usage, [], provider, usage_sources=sources)
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    return ledger, next_accumulator, next_offset


def state_dir(home: Path) -> Path:
    path = Path(
        os.environ.get("ATS_GUARD_STATE_DIR", str(home / ".local" / "state" / "agent-token-saver"))
    ).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def state_key(event: dict[str, Any], transcript: Path) -> str:
    identity = str(event.get("session_id") or transcript)
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def load_previous(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_mode & 0o077:
            return {}
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def guard_record(
    transcript: Path,
    metadata: os.stat_result,
    guard: dict[str, Any],
    accumulator: dict[str, Any],
) -> dict[str, Any] | None:
    cursor = {
        "byte_offset": metadata.st_size,
        "prefix_sha256": prefix_hash(transcript),
        "tail_sha256": segment_hash(transcript, metadata.st_size),
    }
    if not cursor["prefix_sha256"] or not cursor["tail_sha256"]:
        return None
    record = {
        "schema_version": 2,
        "timestamp_unix": time.time(),
        "action": str(guard.get("action") or "continue"),
        "observed": guard.get("observed", {}),
        "reasons": guard.get("reasons", []),
        "warnings": guard.get("warnings", []),
        "transcript_id": hashlib.sha256(str(transcript).encode()).hexdigest(),
        "transcript_bytes": metadata.st_size,
        "transcript_fingerprint": file_identity(transcript, metadata),
        "cursor": cursor,
        "accumulator": accumulator,
    }
    try:
        serialized = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode()
    except (TypeError, ValueError):
        return None
    return record if len(serialized) <= STATE_MAX_BYTES else None


def fallback_record(
    transcript: Path, metadata: os.stat_result, guard: dict[str, Any]
) -> dict[str, Any] | None:
    """Persist the pre-v2 guard contract when the local module cannot load."""
    record = {
        "schema_version": 1,
        "timestamp_unix": time.time(),
        "action": str(guard.get("action") or "continue"),
        "observed": guard.get("observed", {}),
        "reasons": guard.get("reasons", []),
        "warnings": guard.get("warnings", []),
        "transcript_id": hashlib.sha256(str(transcript).encode()).hexdigest(),
        "transcript_bytes": metadata.st_size,
    }
    try:
        serialized = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode()
    except (TypeError, ValueError):
        return None
    return record if len(serialized) <= STATE_MAX_BYTES else None


def atomic_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def prune_state(directory: Path, keep: set[str]) -> None:
    """Drop per-session guard files the next run can no longer resume from.

    One state file per session with no expiry path grows without bound for the
    lifetime of the installation.
    """
    cutoff = time.time() - STATE_RETENTION_SECONDS
    try:
        entries = list(directory.glob("session-guard-*.json"))
    except OSError:
        return
    for entry in entries:
        if entry.name in keep:
            continue
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
            entry.unlink()
        except OSError:
            continue


def warning_message(guard: dict[str, Any]) -> str:
    observed = guard.get("observed") if isinstance(guard.get("observed"), dict) else {}
    labels = [*guard.get("reasons", []), *guard.get("warnings", [])]
    action = str(guard.get("action") or "warn")
    next_step = (
        "Invoke warm-handoff when installed; write one reference-only 300-700-token "
        "handoff with decisions, running state, next action, oracle and test checklist, "
        "then continue in a fresh session."
        if action == "checkpoint_required"
        else "Keep model and effort stable; prepare the bounded handoff before the hard "
        "limit or any pause beyond the host cache TTL."
    )
    return (
        f"agent-token-saver context guard: {action}; "
        f"provider_total={int(observed.get('provider_total_tokens', 0)):,}, "
        f"compactions={int(observed.get('compactions', 0))}, "
        f"tool_output_bytes={int(observed.get('tool_output_bytes', 0)):,}; "
        f"signals={','.join(str(item) for item in labels) or 'threshold'}. "
        f"{next_step} This hook warns only; it never auto-continues or blocks STOP."
    )


def main() -> int:
    event = read_event()
    home = Path.home().resolve()
    transcript = safe_file(event.get("transcript_path"), roots=allowed_transcript_roots(home))
    if transcript is None or transcript.suffix.lower() not in {".json", ".jsonl"}:
        emit()
        return 0
    provider = "claude" if ".claude" in transcript.parts else "codex"
    directory = state_dir(home)
    current_path = directory / f"session-guard-{state_key(event, transcript)}.json"
    previous = load_previous(current_path)
    module = None
    path = ledger_path(home)
    if path is not None:
        module = load_ledger_module(path)
    incremental = (
        build_incremental_ledger(module, transcript, provider, previous)
        if module is not None
        else None
    )
    if incremental is not None:
        ledger, accumulator, _ = incremental
    else:
        full = build_full_ledger(module, transcript, provider) if module is not None else None
        if full is not None:
            ledger, accumulator = full
        else:
            ledger = run_ledger(transcript, home)
            accumulator = None
    guard = ledger.get("session_guard") if isinstance(ledger, dict) else None
    if not isinstance(guard, dict):
        emit()
        return 0
    metadata = stable_stat(transcript)
    if metadata is None:
        emit()
        return 0
    record = (
        guard_record(transcript, metadata, guard, accumulator)
        if isinstance(accumulator, dict)
        else fallback_record(transcript, metadata, guard)
    )
    if record is None:
        emit()
        return 0
    atomic_state(current_path, record)
    atomic_state(directory / "session-guard-latest.json", record)
    prune_state(directory, keep={current_path.name, "session-guard-latest.json"})
    action = record["action"]
    if ACTION_RANK.get(action, 0) > ACTION_RANK.get(str(previous.get("action")), 0):
        emit({"systemMessage": warning_message(guard)})
    else:
        emit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
