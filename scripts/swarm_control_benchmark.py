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


def worker_context(case: str, prompt: str) -> str:
    with tempfile.TemporaryDirectory(prefix="ats-swarm-control-") as state:
        env = os.environ.copy()
        env["ATS_CAPSULE_STATE_DIR"] = state
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
    contexts = {name: worker_context(name, prompt) for name, prompt in CASES.items()}
    registry_tokens = est_tokens(registry_text)
    naive = sum(registry_tokens + est_tokens(context) for context in contexts.values())
    routed = sum(est_tokens(context) for context in contexts.values())
    rows = [
        {
            "case": name,
            "routed_visible_input_tokens": est_tokens(context),
            "route": context.split("Tool lane: ", 1)[1].split(".", 1)[0]
            if "Tool lane: " in context
            else "missing",
        }
        for name, context in contexts.items()
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
            "naive_three_workers_registry_plus_contract": naive,
            "routed_three_workers_contract_only": routed,
            "avoided_visible_input_tokens": naive - routed,
            "reduction_percent": reduction_percent(naive, routed),
            "rows": rows,
        },
        "acceptance": {
            "agentmaster_models_nonempty": bool(registry),
            "three_task_specific_routes": all(row["route"] != "missing" for row in rows),
            "dry_run_has_lanes": "lanes" in dry_plan.lower(),
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
        "| Worker task | Selected compact route | Visible input tokens |",
        "|---|---|---:|",
    ]
    for row in context["rows"]:
        lines.append(
            f"| {row['case']} | {row['route']} | {row['routed_visible_input_tokens']} |"
        )
    lines.extend(
        [
            "",
            "| Three-worker packet | Visible input tokens |",
            "|---|---:|",
            f"| Naive: full model registry + contract per worker | {context['naive_three_workers_registry_plus_contract']} |",
            f"| Routed: contract + one task-specific tool hint | {context['routed_three_workers_contract_only']} |",
            f"| Avoided projection | {context['avoided_visible_input_tokens']} ({context['reduction_percent']}%) |",
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
