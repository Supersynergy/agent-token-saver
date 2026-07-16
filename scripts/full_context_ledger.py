#!/usr/bin/env python3
"""Reconcile provider-reported usage with visible context components.

Provider totals remain authoritative. Local component sizes use the repository's
transparent UTF-8-bytes/4 proxy and expose, rather than hide, unattributed host
context such as system prompts, built-in tools, plugins, history and cache state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
DEFAULT_GUARD_THRESHOLDS = {
    "warn_total_tokens": 10_000_000,
    "checkpoint_total_tokens": 25_000_000,
    "warn_tool_output_bytes": 5_000_000,
    "checkpoint_compactions": 2,
}


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
        "total_input_tokens": total_input,
        "output_tokens": output_tokens,
        "reasoning_output_tokens_subset": _int(usage.get("reasoning_output_tokens")),
        "reported_total_tokens": reported_total,
    }


def _payload_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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


def inspect_usage_file(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    candidates: list[dict[str, Any]] = []
    latest_codex_total: dict[str, Any] | None = None
    metadata = {
        "records": 0,
        "token_count_events": 0,
        "compactions": 0,
        "tool_output_bytes": 0,
        "spawned_workers": 0,
        "shell_exec_calls": 0,
        "rtk_mentions": 0,
    }
    for record in _records(path):
        _update_source_metadata(record, metadata)
        if isinstance(record, dict):
            payload = record.get("payload")
            if (
                record.get("type") == "event_msg"
                and isinstance(payload, dict)
                and payload.get("type") == "token_count"
            ):
                info = payload.get("info")
                if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
                    latest_codex_total = info["total_token_usage"]
        candidates.extend(_usage_candidates(record))
    usage = latest_codex_total or (candidates[-1] if candidates else None)
    if usage is None:
        raise ValueError(f"no provider usage object found in {path}")
    return _normalize_usage(usage), metadata


def load_usage(path: Path) -> dict[str, int]:
    usage, _ = inspect_usage_file(path)
    return usage


def aggregate_usages(usages: list[dict[str, int]]) -> dict[str, int]:
    if not usages:
        raise ValueError("at least one usage source is required")
    return {
        key: sum(usage.get(key, 0) for usage in usages)
        for key in usages[0]
    }


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
        sources.append(
            {"name": label, "path": str(path), "usage": usage, "metadata": metadata}
        )
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
    compactions = sum(
        _int(source.get("metadata", {}).get("compactions")) for source in sources
    )
    tool_output_bytes = sum(
        _int(source.get("metadata", {}).get("tool_output_bytes")) for source in sources
    )
    shell_exec_calls = sum(
        _int(source.get("metadata", {}).get("shell_exec_calls")) for source in sources
    )
    rtk_mentions = sum(
        _int(source.get("metadata", {}).get("rtk_mentions")) for source in sources
    )
    total_tokens = usage["reported_total_tokens"]
    reasons: list[str] = []
    warnings: list[str] = []
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
        },
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
        "method": {
            "provider_total": "authoritative usage reported by the agent/provider",
            "visible_components": "UTF-8 bytes / 4 estimate",
            "unattributed": (
                "provider input minus visible estimates; may include system prompt, built-in "
                "tools, hidden schemas, plugins, history, cache accounting and tokenizer drift"
            ),
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
    parser.add_argument(
        "--format", choices=("json", "json-compact", "markdown"), default="json"
    )
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
