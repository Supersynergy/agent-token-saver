#!/usr/bin/env python3
"""Reconcile provider-reported usage with visible context components.

Provider totals remain authoritative. Local component sizes use the repository's
transparent UTF-8-bytes/4 proxy and expose, rather than hide, unattributed host
context such as system prompts, built-in tools, plugins, history and cache state.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

USAGE_KEYS = {
    "input_tokens",
    "prompt_tokens",
    "total_input_tokens",
    "cached_input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "completion_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}
SPAWN_CALL_RE = re.compile(r"\bspawn_agent\s*\(")
EXEC_CALL_RE = re.compile(r"\bexec_command\s*\(")
RTK_CALL_RE = re.compile(r"(?<![\w-])rtk(?:\s|[\"'])")
# Commands whose exit status is a task oracle: tests, type checks, linters, project gates.
VERIFY_CMD_RE = re.compile(
    r"(?<![\w/.-])(?:pytest|cargo\s+(?:test|check|clippy)|go\s+(?:test|vet)|"
    r"(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:test|check|lint|typecheck)|vitest|"
    r"(?:just|make)\s+(?:test|check|lint|verify)|ruff\s+check|mypy|pyright|tsc)(?![\w-])"
)
EXIT_CODE_RE = re.compile(r"(?:Process exited with code|Exit code:|\"exit_code\":)\s*(\d+)")
MAX_PENDING_VERIFY = 16
DEFAULT_GUARD_THRESHOLDS = {
    "warn_total_tokens": 10_000_000,
    "checkpoint_total_tokens": 25_000_000,
    "warn_tool_output_bytes": 5_000_000,
    "checkpoint_compactions": 2,
}


def _load_cache_economics() -> Any | None:
    """Load the optional cache pricing module without ever raising.

    This file is also executed by path from a fail-open hook and installed as a
    single standalone script, so the sibling ``cache_economics.py`` may simply
    be absent. Only that sibling is loaded, never a same-named module from
    ``sys.path`` or the caller's working directory. Any failure degrades the
    ledger to its previous, cache-unaware behaviour.
    """
    name = "ats_cache_economics"
    try:
        path = Path(__file__).resolve().with_name("cache_economics.py")
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        # Dataclass field resolution needs the module reachable by name.
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            return None
        return module
    except Exception:
        sys.modules.pop(name, None)
        return None


CACHE_ECONOMICS = _load_cache_economics()
CACHE_PRICE_PROFILE = "anthropic"


def build_cache_economics(
    usage: dict[str, int], profile: str | None = None
) -> dict[str, Any] | None:
    """Price the cached prefix, or return None when pricing is unavailable."""
    if CACHE_ECONOMICS is None:
        return None
    try:
        return CACHE_ECONOMICS.build(usage, profile or CACHE_PRICE_PROFILE)
    except Exception:
        return None


def est_tokens(value: bytes) -> int:
    return max(1, len(value) // 4) if value else 0


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _usage_candidates(value: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if USAGE_KEYS.intersection(value):
            candidates.append(value)
        for key, child in value.items():
            if key == "usage" and isinstance(child, dict):
                candidates.append(child)
            elif isinstance(child, (dict, list)):
                candidates.extend(_usage_candidates(child))
    elif isinstance(value, list):
        for child in value:
            candidates.extend(_usage_candidates(child))
    return candidates


def _records(path: Path):
    if path.suffix.lower() == ".jsonl":
        with path.open(errors="replace") as handle:
            for line in handle:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        return
    text = path.read_text(errors="replace")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
        return
    if isinstance(value, list):
        yield from value
    else:
        yield value


def _normalize_usage(usage: dict[str, Any]) -> dict[str, int]:
    input_tokens = _int(usage.get("input_tokens", usage.get("prompt_tokens")))
    cache_creation = _int(usage.get("cache_creation_input_tokens"))
    cache_read = _int(usage.get("cache_read_input_tokens"))
    cached_subset = _int(usage.get("cached_input_tokens"))
    # Codex reports its cache writes as a subset of input_tokens, so this one
    # must not be added to the total the way Anthropic's disjoint field is.
    cache_write_subset = _int(usage.get("cache_write_input_tokens"))
    total_input = _int(usage.get("total_input_tokens"))
    if not total_input:
        total_input = input_tokens + cache_creation + cache_read
    output_tokens = _int(usage.get("output_tokens", usage.get("completion_tokens")))
    reported_total = _int(usage.get("total_tokens")) or total_input + output_tokens
    return {
        "input_tokens": input_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "cached_input_tokens_subset": cached_subset,
        "cache_write_input_tokens": cache_write_subset,
        "total_input_tokens": total_input,
        "output_tokens": output_tokens,
        "reasoning_output_tokens_subset": _int(usage.get("reasoning_output_tokens")),
        "reported_total_tokens": reported_total,
    }


def _payload_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _tool_events(record: dict[str, Any]) -> list[tuple[str, str, str, bool]]:
    """Yield (kind, call_id, text, is_error) for Codex and Claude tool records.

    kind is "call" (text = tool input) or "output" (text = tool output).
    """
    events: list[tuple[str, str, str, bool]] = []
    payload = record.get("payload")
    if isinstance(payload, dict):
        payload_type = str(payload.get("type") or "")
        call_id = str(payload.get("call_id") or "")
        if payload_type in {"function_call", "custom_tool_call"}:
            events.append(
                (
                    "call",
                    call_id,
                    _payload_text(payload.get("input") or payload.get("arguments") or ""),
                    False,
                )
            )
        elif payload_type in {"function_call_output", "custom_tool_call_output"}:
            events.append(("output", call_id, _payload_text(payload.get("output") or ""), False))
        return events
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            events.append(
                ("call", str(block.get("id") or ""), _payload_text(block.get("input") or ""), False)
            )
        elif block.get("type") == "tool_result":
            events.append(
                (
                    "output",
                    str(block.get("tool_use_id") or ""),
                    _payload_text(block.get("content") or ""),
                    bool(block.get("is_error")),
                )
            )
    return events


def _update_verification(record: dict[str, Any], accumulator: dict[str, Any]) -> None:
    """Track the last verification command's exit status; keeps only call ids."""
    metadata = accumulator["metadata"]
    pending: list[str] = accumulator["pending_verify_calls"]
    for kind, call_id, text, is_error in _tool_events(record):
        if not call_id:
            continue
        if kind == "call":
            if VERIFY_CMD_RE.search(text) and call_id not in pending:
                pending.append(call_id)
                del pending[:-MAX_PENDING_VERIFY]
            continue
        if call_id not in pending:
            continue
        pending.remove(call_id)
        match = EXIT_CODE_RE.search(text)
        failed = is_error or (match is not None and int(match.group(1)) != 0)
        metadata["verify_calls"] += 1
        if failed:
            metadata["verify_failures"] += 1
        metadata["last_verify_failed"] = int(failed)


def _update_source_metadata(record: Any, metadata: dict[str, int]) -> None:
    if not isinstance(record, dict):
        return
    metadata["records"] += 1
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return
    payload_type = str(payload.get("type") or "")
    if "compact" in payload_type.lower():
        metadata["compactions"] += 1
    if record.get("type") == "event_msg" and payload_type == "token_count":
        metadata["token_count_events"] += 1
    if record.get("type") != "response_item":
        return
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        metadata["tool_output_bytes"] += len(
            _payload_text(payload.get("output") or "").encode("utf-8")
        )
        return
    if payload_type not in {"function_call", "custom_tool_call"}:
        return
    name = str(payload.get("name") or "")
    call_input = _payload_text(payload.get("input") or payload.get("arguments") or "")
    if name.endswith("spawn_agent"):
        metadata["spawned_workers"] += 1
    else:
        metadata["spawned_workers"] += len(SPAWN_CALL_RE.findall(call_input))
    if name.endswith("exec_command"):
        metadata["shell_exec_calls"] += 1
    else:
        metadata["shell_exec_calls"] += len(EXEC_CALL_RE.findall(call_input))
    metadata["rtk_mentions"] += len(RTK_CALL_RE.findall(call_input))


def new_usage_accumulator() -> dict[str, Any]:
    """Return JSON-serializable, content-free state for one usage source."""
    return {
        "latest_codex_total": None,
        "last_usage_candidate": None,
        "pending_verify_calls": [],
        "metadata": {
            "records": 0,
            "token_count_events": 0,
            "compactions": 0,
            "tool_output_bytes": 0,
            "spawned_workers": 0,
            "shell_exec_calls": 0,
            "rtk_mentions": 0,
            "verify_calls": 0,
            "verify_failures": 0,
            "last_verify_failed": 0,
        },
    }


def _accumulator_metadata(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        return None
    required = {
        "records",
        "token_count_events",
        "compactions",
        "tool_output_bytes",
        "spawned_workers",
        "shell_exec_calls",
        "rtk_mentions",
        "verify_calls",
        "verify_failures",
        "last_verify_failed",
    }
    if set(metadata) != required or any(
        not isinstance(metadata[key], int) or metadata[key] < 0 for key in required
    ):
        return None
    pending = value.get("pending_verify_calls")
    if (
        not isinstance(pending, list)
        or len(pending) > MAX_PENDING_VERIFY
        or any(not isinstance(item, str) for item in pending)
    ):
        return None
    for key in ("latest_codex_total", "last_usage_candidate"):
        candidate = value.get(key)
        if candidate is not None and (
            not isinstance(candidate, dict)
            or set(candidate)
            != {
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "cached_input_tokens_subset",
                "cache_write_input_tokens",
                "total_input_tokens",
                "output_tokens",
                "reasoning_output_tokens_subset",
                "reported_total_tokens",
            }
            or any(not isinstance(item, int) or item < 0 for item in candidate.values())
        ):
            return None
    return metadata


def update_usage_accumulator(record: Any, accumulator: dict[str, Any]) -> None:
    """Apply one record with the same usage precedence as a full replay."""
    metadata = _accumulator_metadata(accumulator)
    if metadata is None:
        raise ValueError("invalid usage accumulator")
    _update_source_metadata(record, metadata)
    if not isinstance(record, dict):
        return
    _update_verification(record, accumulator)
    payload = record.get("payload")
    if (
        record.get("type") == "event_msg"
        and isinstance(payload, dict)
        and payload.get("type") == "token_count"
    ):
        info = payload.get("info")
        if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
            accumulator["latest_codex_total"] = _normalize_usage(info["total_token_usage"])
    for candidate in _usage_candidates(record):
        accumulator["last_usage_candidate"] = _normalize_usage(candidate)


def usage_from_accumulator(accumulator: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    metadata = _accumulator_metadata(accumulator)
    if metadata is None:
        raise ValueError("invalid usage accumulator")
    usage = accumulator.get("latest_codex_total") or accumulator.get("last_usage_candidate")
    if not isinstance(usage, dict):
        raise ValueError("no provider usage object found")
    return dict(usage), dict(metadata)


def inspect_usage_accumulator(path: Path) -> dict[str, Any]:
    accumulator = new_usage_accumulator()
    for record in _records(path):
        update_usage_accumulator(record, accumulator)
    usage_from_accumulator(accumulator)
    return accumulator


def inspect_usage_suffix(
    path: Path, offset: int, accumulator: dict[str, Any], *, max_bytes: int = 8_000_000
) -> tuple[dict[str, Any], int] | None:
    """Parse only complete JSONL records after a trusted byte cursor.

    Returning ``None`` tells callers to perform a complete replay.  The caller
    owns cursor/file identity validation; this function refuses partial lines
    and never retains record text.
    """
    if path.suffix.lower() != ".jsonl" or offset < 0 or max_bytes < 0:
        return None
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            if offset > size or size - offset > max_bytes:
                return None
            handle.seek(offset)
            suffix = handle.read(max_bytes + 1)
    except OSError:
        return None
    if len(suffix) > max_bytes or (suffix and not suffix.endswith(b"\n")):
        return None
    try:
        next_accumulator = json.loads(json.dumps(accumulator, separators=(",", ":")))
        for raw_line in suffix.splitlines():
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            update_usage_accumulator(record, next_accumulator)
        usage_from_accumulator(next_accumulator)
    except (TypeError, ValueError):
        return None
    return next_accumulator, offset + len(suffix)


def inspect_usage_file(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    accumulator = inspect_usage_accumulator(path)
    return usage_from_accumulator(accumulator)


def load_usage(path: Path) -> dict[str, int]:
    usage, _ = inspect_usage_file(path)
    return usage


def aggregate_usages(usages: list[dict[str, int]]) -> dict[str, int]:
    if not usages:
        raise ValueError("at least one usage source is required")
    return {key: sum(usage.get(key, 0) for usage in usages) for key in usages[0]}


def load_usage_sources(specs: list[str]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    seen_labels: set[str] = set()
    for index, spec in enumerate(specs, start=1):
        if "=" in spec:
            label, raw_path = spec.split("=", 1)
        else:
            raw_path = spec
            label = Path(raw_path).stem or f"run-{index}"
        path = Path(raw_path).expanduser().resolve()
        label = label.strip()
        if not label or not path.is_file():
            raise ValueError(f"invalid usage source: {spec}")
        if path in seen_paths:
            raise ValueError(f"duplicate usage source path: {path}")
        if label in seen_labels:
            raise ValueError(f"duplicate usage source label: {label}")
        seen_paths.add(path)
        seen_labels.add(label)
        usage, metadata = inspect_usage_file(path)
        sources.append({"name": label, "path": str(path), "usage": usage, "metadata": metadata})
    return aggregate_usages([source["usage"] for source in sources]), sources


def build_team_accounting(
    usage_sources: list[dict[str, Any]] | None,
    expected_workers: int | None = None,
) -> dict[str, Any]:
    sources = usage_sources or []
    detected_workers = sum(
        _int(source.get("metadata", {}).get("spawned_workers")) for source in sources
    )
    required_workers = max(detected_workers, _int(expected_workers))
    observed_sources = len(sources) or 1
    expected_sources = 1 + required_workers
    missing_sources = max(0, expected_sources - observed_sources)
    return {
        "observed_usage_sources": observed_sources,
        "detected_spawned_workers": detected_workers,
        "expected_usage_sources": expected_sources,
        "missing_usage_sources": missing_sources,
        "complete": missing_sources == 0,
    }


def build_session_guard(
    usage: dict[str, int],
    usage_sources: list[dict[str, Any]] | None,
    thresholds: dict[str, int] | None = None,
) -> dict[str, Any]:
    limits = {**DEFAULT_GUARD_THRESHOLDS, **(thresholds or {})}
    sources = usage_sources or []
    compactions = sum(_int(source.get("metadata", {}).get("compactions")) for source in sources)
    tool_output_bytes = sum(
        _int(source.get("metadata", {}).get("tool_output_bytes")) for source in sources
    )
    shell_exec_calls = sum(
        _int(source.get("metadata", {}).get("shell_exec_calls")) for source in sources
    )
    rtk_mentions = sum(_int(source.get("metadata", {}).get("rtk_mentions")) for source in sources)
    verify_calls = sum(_int(source.get("metadata", {}).get("verify_calls")) for source in sources)
    verify_failures = sum(
        _int(source.get("metadata", {}).get("verify_failures")) for source in sources
    )
    last_verify_failed = any(
        _int(source.get("metadata", {}).get("last_verify_failed")) for source in sources
    )
    total_tokens = usage["reported_total_tokens"]
    reasons: list[str] = []
    warnings: list[str] = []
    if last_verify_failed:
        warnings.append("last_verification_failed")
    if total_tokens >= limits["checkpoint_total_tokens"]:
        reasons.append(f"provider_total_tokens>={limits['checkpoint_total_tokens']}")
    elif total_tokens >= limits["warn_total_tokens"]:
        warnings.append(f"provider_total_tokens>={limits['warn_total_tokens']}")
    if compactions >= limits["checkpoint_compactions"]:
        reasons.append(f"compactions>={limits['checkpoint_compactions']}")
    if tool_output_bytes >= limits["warn_tool_output_bytes"]:
        warnings.append(f"tool_output_bytes>={limits['warn_tool_output_bytes']}")
    action = "checkpoint_required" if reasons else ("warn" if warnings else "continue")
    return {
        "action": action,
        "reasons": reasons,
        "warnings": warnings,
        "thresholds": limits,
        "observed": {
            "provider_total_tokens": total_tokens,
            "compactions": compactions,
            "tool_output_bytes": tool_output_bytes,
            "shell_exec_calls": shell_exec_calls,
            "rtk_mentions": rtk_mentions,
            "rtk_signal_percent": (
                round(rtk_mentions / shell_exec_calls * 100, 2) if shell_exec_calls else 0.0
            ),
            "verify_calls": verify_calls,
            "verify_failures": verify_failures,
            "verify_status": (
                "none" if not verify_calls else ("red" if last_verify_failed else "green")
            ),
        },
        "verify_note": "exit status of test/lint/typecheck commands; red means the saving is unproven",
        "rtk_note": "heuristic signal only; denominator is not an eligibility classifier",
    }


def load_components(specs: list[str]) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"component must be NAME=PATH: {spec}")
        name, raw_path = spec.split("=", 1)
        path = Path(raw_path).expanduser().resolve()
        if not name.strip() or not path.is_file():
            raise ValueError(f"invalid component: {spec}")
        payload = path.read_bytes()
        components.append(
            {
                "name": name.strip(),
                "path": str(path),
                "bytes": len(payload),
                "estimated_tokens": est_tokens(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return components


def build_ledger(
    usage: dict[str, int],
    components: list[dict[str, Any]],
    provider: str,
    usage_sources: list[dict[str, Any]] | None = None,
    expected_workers: int | None = None,
    guard_thresholds: dict[str, int] | None = None,
) -> dict[str, Any]:
    known_input = sum(item["estimated_tokens"] for item in components)
    reported_input = usage["total_input_tokens"]
    unattributed = max(0, reported_input - known_input)
    over_attributed = max(0, known_input - reported_input)
    coverage = round(known_input / reported_input * 100, 2) if reported_input else 0.0
    seen_hashes: set[str] = set()
    duplicate_visible = 0
    for item in components:
        digest = item.get("sha256", "")
        if digest in seen_hashes:
            duplicate_visible += item["estimated_tokens"]
        else:
            seen_hashes.add(digest)
    team_accounting = build_team_accounting(usage_sources, expected_workers)
    session_guard = build_session_guard(usage, usage_sources, guard_thresholds)
    cache_economics = build_cache_economics(usage)
    if not team_accounting["complete"]:
        session_guard["action"] = "checkpoint_required"
        session_guard["reasons"].append("team_usage_incomplete")
    return {
        "schema_version": 3,
        "provider": provider,
        "provider_usage": usage,
        "usage_sources": usage_sources or [],
        "team_accounting": team_accounting,
        "session_guard": session_guard,
        "visible_input_components": components,
        "estimated_visible_input_tokens": known_input,
        "duplicate_visible_input_tokens": duplicate_visible,
        "unique_visible_input_tokens": max(0, known_input - duplicate_visible),
        "unattributed_input_tokens": unattributed,
        "over_attributed_tokens": over_attributed,
        "attribution_coverage_percent": coverage,
        **({"cache_economics": cache_economics} if cache_economics else {}),
        "method": {
            "provider_total": "authoritative usage reported by the agent/provider",
            "visible_components": "UTF-8 bytes / 4 estimate",
            "unattributed": (
                "provider input minus visible estimates; may include system prompt, built-in "
                "tools, hidden schemas, plugins, history, cache accounting and tokenizer drift"
            ),
            **({"cache_economics": cache_economics["basis"]} if cache_economics else {}),
        },
    }


def render_markdown(ledger: dict[str, Any]) -> str:
    usage = ledger["provider_usage"]
    lines = [
        f"# Full Context Token Ledger — {ledger['provider']}",
        "",
        "Provider totals are authoritative; component rows are transparent bytes/4 estimates.",
        "",
        "| Layer | Tokens | Measurement |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| {item['name']} | {item['estimated_tokens']:,} | local estimate |"
        for item in ledger["visible_input_components"]
    )
    team = ledger["team_accounting"]
    guard = ledger["session_guard"]
    lines.extend(
        [
            "",
            "## Team accounting and context guard",
            "",
            f"- Team accounting complete: **{'yes' if team['complete'] else 'no'}**.",
            f"- Usage sources: **{team['observed_usage_sources']} / {team['expected_usage_sources']}**.",
            f"- Detected spawned workers: **{team['detected_spawned_workers']}**.",
            f"- Guard action: **{guard['action']}**.",
            f"- Compactions: **{guard['observed']['compactions']}**.",
            f"- Tool output bytes: **{guard['observed']['tool_output_bytes']:,}**.",
            f"- RTK signal: **{guard['observed']['rtk_mentions']} / {guard['observed']['shell_exec_calls']}** shell calls (heuristic).",
            f"- Verification: **{guard['observed']['verify_status']}** ({guard['observed']['verify_failures']} / {guard['observed']['verify_calls']} test/lint runs failed; red = saving unproven).",
        ]
    )
    if guard["reasons"]:
        lines.append(f"- Blocking reasons: **{', '.join(guard['reasons'])}**.")
    if guard["warnings"]:
        lines.append(f"- Warnings: **{', '.join(guard['warnings'])}**.")
    lines.extend(
        [
            f"| **Visible input subtotal** | **{ledger['estimated_visible_input_tokens']:,}** | estimate |",
            f"| **Unattributed host input** | **{ledger['unattributed_input_tokens']:,}** | reconciled difference |",
            f"| **Provider input total** | **{usage['total_input_tokens']:,}** | reported |",
            f"| Provider output | {usage['output_tokens']:,} | reported |",
            f"| **Provider total** | **{usage['reported_total_tokens']:,}** | reported |",
        ]
    )
    cache = ledger.get("cache_economics")
    if cache:
        hit_rate = cache["cache_hit_rate_percent"]
        saving = cache["cache_saving_percent"]
        # A sibling pricer older than this renderer still produces a ledger.
        diagnosis = cache.get("diagnosis") or {"verdict": "n/a", "detail": "pricer too old"}
        lines.extend(
            [
                f"| — input served from cache | {cache['cache_read_tokens']:,} | reported |",
                f"| — input written to cache | {cache['cache_write_tokens']:,} | reported |",
                f"| — fresh input | {cache['uncached_input_tokens']:,} | reported |",
                f"| Cache hit rate | {'n/a' if hit_rate is None else f'{hit_rate:.2f}%'} | reported ratio |",
                f"| Weighted input (fresh-equivalents) | {cache['weighted_input_tokens']:,.0f} | list-ratio estimate |",
                f"| Same stream with no cache | {cache['nocache_input_tokens']:,.0f} | counterfactual |",
                f"| Input saved by cache | {'n/a' if saving is None else f'{saving:.2f}%'} | list-ratio estimate |",
                f"| Weighted total (incl. output) | {cache['weighted_total_tokens']:,.0f} | list-ratio estimate |",
                f"| Cache verdict | {diagnosis['verdict']} | {diagnosis['detail']} |",
            ]
        )
    if ledger["usage_sources"]:
        lines.extend(
            [
                "",
                "## Provider usage sources",
                "",
                "| Run | Input | Output | Total |",
                "|---|---:|---:|---:|",
            ]
        )
        lines.extend(
            f"| {source['name']} | {source['usage']['total_input_tokens']:,} | "
            f"{source['usage']['output_tokens']:,} | {source['usage']['reported_total_tokens']:,} |"
            for source in ledger["usage_sources"]
        )
    lines.extend(
        [
            "",
            f"Attribution coverage: **{ledger['attribution_coverage_percent']:.2f}%**.",
            f"Duplicate visible input: **{ledger['duplicate_visible_input_tokens']:,} tokens**.",
            "",
            "Unattributed input can include the host system prompt, built-in tool schemas, plugins,",
            "conversation history, cache accounting and tokenizer differences. It is a measurement",
            "target, not a claimed saving.",
        ]
    )
    if cache:
        profile = cache["profile"]
        lines.extend(
            [
                "",
                f"Cache ratios: read {profile['cache_read_ratio']}x, write "
                f"{profile['cache_write_ratio']}x, output {profile['output_ratio']}x base input "
                f"(profile `{profile['name']}`, verified {profile['verified']}).",
                cache["basis"],
            ]
        )
    return "\n".join(lines) + "\n"


def serialize_ledger(ledger: dict[str, Any], output_format: str) -> str:
    if output_format == "markdown":
        return render_markdown(ledger)
    if output_format == "json-compact":
        return json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n"
    return json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-token-ledger")
    parser.add_argument(
        "--usage",
        action="append",
        required=True,
        metavar="[NAME=]PATH",
        help="provider/agent JSON or JSONL; repeat for parent and child runs",
    )
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="visible input component; repeat for rules, schemas, hooks, history or task",
    )
    parser.add_argument("--provider", default="unknown")
    parser.add_argument("--expected-workers", type=int, default=None)
    parser.add_argument("--require-complete-team", action="store_true")
    parser.add_argument("--require-within-guard", action="store_true")
    parser.add_argument("--warn-total-tokens", type=int, default=10_000_000)
    parser.add_argument("--checkpoint-total-tokens", type=int, default=25_000_000)
    parser.add_argument("--warn-tool-output-bytes", type=int, default=5_000_000)
    parser.add_argument("--checkpoint-compactions", type=int, default=2)
    parser.add_argument("--format", choices=("json", "json-compact", "markdown"), default="json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        usage, usage_sources = load_usage_sources(args.usage)
        ledger = build_ledger(
            usage,
            load_components(args.component),
            args.provider,
            usage_sources=usage_sources,
            expected_workers=args.expected_workers,
            guard_thresholds={
                "warn_total_tokens": args.warn_total_tokens,
                "checkpoint_total_tokens": args.checkpoint_total_tokens,
                "warn_tool_output_bytes": args.warn_tool_output_bytes,
                "checkpoint_compactions": args.checkpoint_compactions,
            },
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    output = serialize_ledger(ledger, args.format)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    else:
        print(output, end="")
    if args.require_complete_team and not ledger["team_accounting"]["complete"]:
        return 2
    if args.require_within_guard and ledger["session_guard"]["action"] == "checkpoint_required":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
