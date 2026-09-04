#!/usr/bin/env python3
"""Reproducible baseline/candidate benchmark for token-saver hooks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROMPT_HOOK = Path("integration/hooks/token-stack-prompt.py")
WORKER_HOOK = Path("integration/hooks/agent-worker-capsule.py")
PROMPT_CASES = {
    "trivial": {"prompt": "danke"},
    "token_saver_fast_route": {"prompt": "Optimize token and context budget for this large log."},
    "generic_router_miss": {
        "prompt": "Inspect the specified local state and report the exact result without edits."
    },
}
WORKER_CASES = {
    "bare_worker": {
        "tool_name": "Agent",
        "session_id": "bench-bare",
        "tool_input": {"prompt": "Find the source function causing the failing test."},
    },
    "precontracted_worker": {
        "tool_name": "Agent",
        "session_id": "bench-precontracted",
        "tool_input": {
            "prompt": (
                "Objective: trace the parser source failure.\n"
                "Scope: src/parser.py and tests/test_parser.py.\n"
                "Oracle: pytest tests/test_parser.py exits 0.\n"
                "Limits: at most 3 tries; do not edit unrelated files.\n"
                "Return: STATUS, evidence path and exit code in <=500 tokens."
            )
        },
    },
}


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def source_at(ref: str, path: Path) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"cannot read {ref}:{path}")
    return result.stdout


def run_source(source: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", source],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=8,
        check=False,
    )
    output = result.stdout.encode()
    return {
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        "exit_code": result.returncode,
        "output_bytes": len(output),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "stdout": result.stdout,
    }


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    times = [float(sample["wall_ms"]) for sample in samples]
    return {
        "runs": len(samples),
        "wall_ms": [sample["wall_ms"] for sample in samples],
        "p50_ms": round(statistics.median(times), 3),
        "p95_ms": round(percentile(times, 0.95), 3),
        "exit_codes": sorted({int(sample["exit_code"]) for sample in samples}),
        "output_bytes": sorted({int(sample["output_bytes"]) for sample in samples}),
        "output_sha256": sorted({str(sample["output_sha256"]) for sample in samples}),
    }


def benchmark_pair(
    baseline: str,
    candidate: str,
    payload: dict[str, Any],
    runs: int,
    env: dict[str, str],
) -> tuple[dict[str, Any], str, str]:
    samples: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
    last_output: dict[str, str] = {}
    for _ in range(runs):
        for label, source in (("baseline", baseline), ("candidate", candidate)):
            sample = run_source(source, payload, env)
            last_output[label] = str(sample.pop("stdout"))
            samples[label].append(sample)
    baseline_summary = summarize(samples["baseline"])
    candidate_summary = summarize(samples["candidate"])
    change = (
        round(
            (1 - candidate_summary["p50_ms"] / baseline_summary["p50_ms"]) * 100,
            1,
        )
        if baseline_summary["p50_ms"]
        else 0.0
    )
    return (
        {
            "baseline": baseline_summary,
            "candidate": candidate_summary,
            "p50_change_percent": change,
        },
        last_output["baseline"],
        last_output["candidate"],
    )


def hook_context(output: str) -> str:
    try:
        value = json.loads(output)
        return str(value["hookSpecificOutput"]["additionalContext"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return ""


def make_report(baseline_ref: str, runs: int) -> dict[str, Any]:
    prompt_baseline = source_at(baseline_ref, PROMPT_HOOK)
    worker_baseline = source_at(baseline_ref, WORKER_HOOK)
    prompt_candidate = (ROOT / PROMPT_HOOK).read_text()
    worker_candidate = (ROOT / WORKER_HOOK).read_text()
    env = os.environ.copy()
    env["ATS_CAPSULE_STATE_DIR"] = "/dev/null"
    cases: dict[str, Any] = {}
    acceptance: dict[str, bool] = {}

    for name, payload in PROMPT_CASES.items():
        case, baseline_out, candidate_out = benchmark_pair(
            prompt_baseline, prompt_candidate, payload, runs, env
        )
        case["output_equal"] = baseline_out == candidate_out
        cases[name] = case
        acceptance[f"{name}_same_output"] = case["output_equal"]

    for name, payload in WORKER_CASES.items():
        case, baseline_out, candidate_out = benchmark_pair(
            worker_baseline, worker_candidate, payload, runs, env
        )
        baseline_context = hook_context(baseline_out)
        candidate_context = hook_context(candidate_out)
        case["baseline_context_bytes"] = len(baseline_context.encode())
        case["candidate_context_bytes"] = len(candidate_context.encode())
        case["output_equal"] = baseline_out == candidate_out
        cases[name] = case
        if name == "bare_worker":
            acceptance["bare_worker_same_output"] = case["output_equal"]
        else:
            acceptance["precontracted_smaller"] = (
                case["candidate_context_bytes"] < case["baseline_context_bytes"]
            )
            acceptance["precontracted_contract_preserved"] = all(
                marker in candidate_context
                for marker in ("capsule accepted", "STATUS:", "EVIDENCE", "controller")
            )

    acceptance["all_exit_codes_zero"] = all(
        arm["exit_codes"] == [0]
        for case in cases.values()
        for arm in (case["baseline"], case["candidate"])
    )
    acceptance["no_forbidden_maintenance_call"] = all(
        "synx doctor" not in source for source in (prompt_candidate, worker_candidate)
    )
    return {
        "schema_version": 1,
        "asof_utc": datetime.now(UTC).isoformat(),
        "baseline_ref": baseline_ref,
        "runs_per_arm": runs,
        "measurement": "fresh_process_interleaved_wall_time_and_output_bytes",
        "not_measured": ["provider tokens", "billing", "model quality"],
        "candidate_sha256": {
            str(PROMPT_HOOK): hashlib.sha256(prompt_candidate.encode()).hexdigest(),
            str(WORKER_HOOK): hashlib.sha256(worker_candidate.encode()).hexdigest(),
        },
        "cases": cases,
        "acceptance": acceptance,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hook and capsule hot-path benchmark",
        "",
        f"As of: `{report['asof_utc']}`",
        "",
        f"Baseline: `{report['baseline_ref']}`. Runs per arm: `{report['runs_per_arm']}`.",
        "Fresh Python process per sample; baseline and candidate interleaved.",
        "No provider call. Raw wall-time samples and candidate source hashes are in the JSON.",
        "",
        "| Case | Baseline p50 | Candidate p50 | p50 change | Baseline bytes | Candidate bytes |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, case in report["cases"].items():
        baseline = case["baseline"]
        candidate = case["candidate"]
        lines.append(
            f"| {name} | {baseline['p50_ms']} ms | {candidate['p50_ms']} ms | "
            f"{case['p50_change_percent']}% | {baseline['output_bytes'][0]} | "
            f"{candidate['output_bytes'][0]} |"
        )
    lines.extend(
        [
            "",
            "Output equality is required except for the intentionally deduplicated",
            "precontracted worker. Its compact output must retain status, evidence and",
            "controller ownership. Times are host-load sensitive; inspect p95 and raw",
            "samples before making a tail-latency claim.",
            "",
            f"Acceptance: `{json.dumps(report['acceptance'], sort_keys=True)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", default="cbe3419")
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--out", type=Path, default=Path("/tmp/ats-hook-hotpath.json"))
    parser.add_argument("--md", type=Path, default=Path("/tmp/ats-hook-hotpath.md"))
    args = parser.parse_args()
    if args.runs < 3:
        parser.error("--runs must be at least 3")
    report = make_report(args.baseline_ref, args.runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, separators=(",", ":")) + "\n")
    args.md.write_text(markdown(report))
    print(json.dumps(report["acceptance"], sort_keys=True))
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
