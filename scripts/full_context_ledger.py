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


def load_usage(path: Path) -> dict[str, int]:
    text = path.read_text(errors="replace")
    records: list[Any] = []
    try:
        records.append(json.loads(text))
    except json.JSONDecodeError:
        for line in text.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    candidates: list[dict[str, Any]] = []
    for record in records:
        candidates.extend(_usage_candidates(record))
    if not candidates:
        raise ValueError(f"no provider usage object found in {path}")
    usage = candidates[-1]
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


def aggregate_usages(usages: list[dict[str, int]]) -> dict[str, int]:
    if not usages:
        raise ValueError("at least one usage source is required")
    return {
        key: sum(usage.get(key, 0) for usage in usages)
        for key in usages[0]
    }


def load_usage_sources(specs: list[str]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        if "=" in spec:
            label, raw_path = spec.split("=", 1)
        else:
            raw_path = spec
            label = Path(raw_path).stem or f"run-{index}"
        path = Path(raw_path).expanduser().resolve()
        if not label.strip() or not path.is_file():
            raise ValueError(f"invalid usage source: {spec}")
        usage = load_usage(path)
        sources.append({"name": label.strip(), "path": str(path), "usage": usage})
    return aggregate_usages([source["usage"] for source in sources]), sources


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
    return {
        "schema_version": 2,
        "provider": provider,
        "provider_usage": usage,
        "usage_sources": usage_sources or [],
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
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        usage, usage_sources = load_usage_sources(args.usage)
        ledger = build_ledger(
            usage,
            load_components(args.component),
            args.provider,
            usage_sources=usage_sources,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    output = (
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else render_markdown(ledger)
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
