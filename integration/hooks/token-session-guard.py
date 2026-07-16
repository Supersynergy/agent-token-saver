#!/usr/bin/env python3
"""Fail-open Codex/Claude Stop hook for cumulative token/context warnings."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

MAX_EVENT_BYTES = 1_000_000
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


def run_ledger(transcript: Path, home: Path) -> dict[str, Any] | None:
    ledger = safe_file(
        os.environ.get(
            "ATS_LEDGER_PATH", str(home / ".agent-token-saver" / "bin" / "agent-token-ledger")
        )
    )
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


def state_dir(home: Path) -> Path:
    path = Path(
        os.environ.get(
            "ATS_GUARD_STATE_DIR", str(home / ".local" / "state" / "agent-token-saver")
        )
    ).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def state_key(event: dict[str, Any], transcript: Path) -> str:
    identity = str(event.get("session_id") or transcript)
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def load_previous(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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


def warning_message(guard: dict[str, Any]) -> str:
    observed = guard.get("observed") if isinstance(guard.get("observed"), dict) else {}
    labels = [*guard.get("reasons", []), *guard.get("warnings", [])]
    action = str(guard.get("action") or "warn")
    next_step = (
        "Write a durable handoff and continue in a fresh session before more work."
        if action == "checkpoint_required"
        else "Check context quality; checkpoint before it reaches the hard limit."
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
    transcript = safe_file(
        event.get("transcript_path"), roots=allowed_transcript_roots(home)
    )
    if transcript is None or transcript.suffix.lower() not in {".json", ".jsonl"}:
        emit()
        return 0
    ledger = run_ledger(transcript, home)
    guard = ledger.get("session_guard") if isinstance(ledger, dict) else None
    if not isinstance(guard, dict):
        emit()
        return 0
    action = str(guard.get("action") or "continue")
    directory = state_dir(home)
    current_path = directory / f"session-guard-{state_key(event, transcript)}.json"
    previous = load_previous(current_path)
    record = {
        "schema_version": 1,
        "timestamp_unix": time.time(),
        "action": action,
        "observed": guard.get("observed", {}),
        "reasons": guard.get("reasons", []),
        "warnings": guard.get("warnings", []),
        "transcript_id": hashlib.sha256(str(transcript).encode()).hexdigest(),
        "transcript_bytes": transcript.stat().st_size,
    }
    atomic_state(current_path, record)
    atomic_state(directory / "session-guard-latest.json", record)
    if ACTION_RANK.get(action, 0) > ACTION_RANK.get(str(previous.get("action")), 0):
        emit({"systemMessage": warning_message(guard)})
    else:
        emit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
