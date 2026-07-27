#!/usr/bin/env python3
"""Measure the visible context cost of routed worker capsules.

This is deliberately a no-provider benchmark: it asks Agent Master for its
model registry and dry-run lane plan, then compares a naive "send every worker
the registry" packet with the one-route worker hook packet.  UTF-8 bytes / 4
is only a reproducible visible-input proxy, never a billing claim.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integration" / "hooks" / "agent-worker-capsule.py"
CASES = {
    "source": "Trace imports for this source function and fix its test.",
    "graph": "Find callers and impact graph for this code symbol.",
    "fresh": "Read the current API documentation for this package.",
}


def est_tokens(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / 4)


def reduction_percent(baseline: int, optimized: int) -> float:
    if baseline <= 0:
        return 0.0
    return round((1 - optimized / baseline) * 100, 1)


def command_text(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    return result.stdout


def precontracted_prompt(prompt: str) -> str:
    return (
        f"Objective: {prompt}\n"
        "Scope: the named evidence only.\n"
        "Oracle: return PASS only with an exact path and exit code.\n"
        "Limits: at most 3 tries; do not edit unrelated files.\n"
        "Return: STATUS, EVIDENCE and at most one HANDOFF in <=500 tokens."
    )


def worker_context(case: str, prompt: str, *, compact: bool) -> str:
    with tempfile.TemporaryDirectory(prefix="ats-swarm-control-") as state:
        env = os.environ.copy()
        env["ATS_CAPSULE_STATE_DIR"] = state
        if not compact:
            env["ATS_CAPSULE_COMPACT_OFF"] = "1"
        event = {
            "tool_name": "Agent",
            "session_id": f"bench-{case}",
            "tool_input": {"description": prompt},
        }
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "worker hook failed")
    try:
        payload = json.loads(result.stdout)
        return str(payload["hookSpecificOutput"]["additionalContext"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("worker hook emitted no context") from error


def make_report(agentmaster: str) -> dict[str, Any]:
    registry_text = command_text([agentmaster, "models", "--json"])
    registry = json.loads(registry_text)
    if not isinstance(registry, list) or not registry:
        raise RuntimeError("Agent Master model registry is empty or invalid")
    dry_plan = command_text(
        [
            agentmaster,
            "swarm",
            "--dry-run",
            "--oracle",
            "true",
            "swarm-control-bench",
            "review this repository and verify its tests",
        ]
    )
    capsules = {name: precontracted_prompt(prompt) for name, prompt in CASES.items()}
    full_contracts = {
        name: worker_context(f"{name}-full", capsules[name], compact=False)
        for name in CASES
    }
    compact_deltas = {
        name: worker_context(f"{name}-compact", capsules[name], compact=True)
        for name in CASES
    }
    registry_tokens = est_tokens(registry_text)
    capsule_tokens = sum(est_tokens(prompt) for prompt in capsules.values())
    full_hook_tokens = sum(est_tokens(context) for context in full_contracts.values())
    compact_hook_tokens = sum(est_tokens(context) for context in compact_deltas.values())
    naive = registry_tokens * len(CASES) + capsule_tokens + full_hook_tokens
    routed_full = capsule_tokens + full_hook_tokens
    routed_compact = capsule_tokens + compact_hook_tokens
    rows = [
        {
            "case": name,
            "task_capsule_tokens": est_tokens(capsules[name]),
            "full_hook_contract_tokens": est_tokens(full_contracts[name]),
            "compact_hook_delta_tokens": est_tokens(compact_deltas[name]),
            "route": compact_deltas[name].split("Tool lane: ", 1)[1].split(".", 1)[0]
            if "Tool lane: " in compact_deltas[name]
            else "missing",
        }
        for name in CASES
    ]
    return {
        "schema_version": 1,
        "asof_utc": datetime.now(UTC).isoformat(),
        "measurement": "utf8_bytes_div_4_visible_input_proxy",
        "not_measured": ["provider billing", "cache tokens", "model quality", "execution latency"],
        "agentmaster": {
            "model_count": len(registry),
            "dry_run_has_lanes": "lanes" in dry_plan.lower(),
        },
        "worker_context": {
            "all_registry_visible_input_tokens": registry_tokens,
            "task_capsules_visible_input_tokens": capsule_tokens,
            "full_hook_contract_tokens": full_hook_tokens,
            "compact_hook_delta_tokens": compact_hook_tokens,
            "naive_registry_plus_capsules_plus_full_hook": naive,
            "routed_capsules_plus_full_hook": routed_full,
            "routed_capsules_plus_compact_hook": routed_compact,
            "routed_full_reduction_vs_naive": reduction_percent(naive, routed_full),
            "routed_compact_reduction_vs_naive": reduction_percent(
                naive, routed_compact
            ),
            "capsule_dedup_avoided_tokens": routed_full - routed_compact,
            "capsule_dedup_packet_reduction_percent": reduction_percent(
                routed_full, routed_compact
            ),
            "rows": rows,
        },
        "acceptance": {
            "agentmaster_models_nonempty": bool(registry),
            "three_task_specific_routes": all(row["route"] != "missing" for row in rows),
            "dry_run_has_lanes": "lanes" in dry_plan.lower(),
            "compact_hook_deltas_smaller": compact_hook_tokens < full_hook_tokens,
            "compact_complete_packets_smaller": routed_compact < routed_full,
        },
    }


def markdown(report: dict[str, Any]) -> str:
    context = report["worker_context"]
    lines = [
        "# Swarm control-plane context benchmark",
        "",
        f"As of: `{report['asof_utc']}`",
        "",
        "No provider call. Tokens are UTF-8 bytes / 4 visible-input proxies.",
        "",
        f"Controller dry run exposed `{report['agentmaster']['model_count']}` model lanes.",
        "",
        "| Worker task | Selected route | Task capsule | Full hook contract | Compact hook delta |",
        "|---|---|---:|---:|---:|",
    ]
    for row in context["rows"]:
        lines.append(
            f"| {row['case']} | {row['route']} | {row['task_capsule_tokens']} | "
            f"{row['full_hook_contract_tokens']} | {row['compact_hook_delta_tokens']} |"
        )
    lines.extend(
        [
            "",
            "| Three-worker packet | Visible input tokens |",
            "|---|---:|",
            f"| Naive: registry + same capsules + full hook | {context['naive_registry_plus_capsules_plus_full_hook']} |",
            f"| Routed: same capsules + full hook | {context['routed_capsules_plus_full_hook']} |",
            f"| Routed: same capsules + compact hook | {context['routed_capsules_plus_compact_hook']} |",
            f"| Routed full reduction vs naive | {context['routed_full_reduction_vs_naive']}% |",
            f"| Routed compact reduction vs naive | {context['routed_compact_reduction_vs_naive']}% |",
            f"| Additional capsule-dedup saving | {context['capsule_dedup_avoided_tokens']} "
            f"({context['capsule_dedup_packet_reduction_percent']}% of complete routed packet) |",
            "",
            "This is a projection-capacity comparison, not a provider-cost or quality claim.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agentmaster", default="agentmaster")
    parser.add_argument("--out", type=Path, default=Path("/tmp/ats-swarm-control.json"))
    parser.add_argument("--md", type=Path, default=Path("/tmp/ats-swarm-control.md"))
    args = parser.parse_args()
    report = make_report(args.agentmaster)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    args.md.write_text(markdown(report))
    print(json.dumps(report["acceptance"], sort_keys=True))
    print(f"wrote: {args.out} + {args.md}")
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
