#!/usr/bin/env python3
"""Kimi K3 vs K2.7 lane benchmark — dated A/B evidence for the kimi-worker lane.

Same reproducible fixture and oracle as the 2026-07-19 lane benchmarks
(``scripts/make_log_fixture.py``: 4,000 lines, 100 ``ERROR`` lines,
``CRITICAL-MARKER`` at 3777; team slices are the exact thirds 1-1333 /
1334-2666 / 2667-4000 = 40/32/28). Every worker arm runs the production
``kimi-worker`` wrapper with an isolated, seeded ``KIMI_SHARE_DIR``; usage is
summed from each session's ``wire.jsonl`` with the same field mapping as the
wrapper's ledger export. The swarm arm invokes ``kimi-cli`` directly and asks
one parent session for three parallel built-in ``Agent`` calls — the same
invocation as the 2026-07-19 built-in swarm arm, now on K3.

Usage:
  uv run python scripts/kimi_k3_lane_benchmark.py                 # all arms once
  uv run python scripts/kimi_k3_lane_benchmark.py --arm k3-single --repeat 2
  uv run python scripts/kimi_k3_lane_benchmark.py --dry-run       # packets only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_log_fixture import ERROR_LINES, MARKER_LINE, TOTAL_LINES, build

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
STAMP = time.strftime("%Y-%m-%d")
OUT_DIR = ROOT / "data" / "benchmarks"
OUT_JSON = OUT_DIR / f"kimi-k3-lane-{STAMP}.json"
OUT_MD = OUT_DIR / f"kimi-k3-lane-{STAMP}.md"

MODEL_K27 = "kimi-code/kimi-for-coding"
MODEL_K3 = "kimi-code/k3"
SLICES = ((1, 1333), (1334, 2666), (2667, 4000))
# Positional subcount: defeats head-only reads and round-number guessing of
# 100 (bench-design review 2026-07-21). Derived from the seeded fixture.
SUBCOUNT_RANGE = (2001, 4000)
TIMEOUT_S = 300

# K3 list prices per million tokens, vendor-published 2026-07-21 — used only
# for labelled list-price estimates, never as an invoice claim.
PRICE_PER_M = {
    "input_other": 3.0,
    "input_cache_read": 0.30,
    "input_cache_creation": 3.0,
    "output": 15.0,
}

# Same-day baseline from the 2026-07-19 system benchmark for drift/savings.
BASELINE_0719 = {
    "k27_single_gross": 22_268,
    "k27_team_gross": 67_514,
    "builtin_swarm_k27_gross": 92_803,
    "claude_team_gross": 411_938,
}

SINGLE_PACKET = (
    "Log file: {fixture} (exactly {total} lines). Using only shell/read tools, "
    "answer for the WHOLE file: how many lines contain the substring ERROR, and "
    "which line number contains CRITICAL-MARKER, and how many of the ERROR lines "
    "fall within lines 2001 to 4000 inclusive. Do not guess; verify by command. "
    "Reply with only compact JSON: "
    '{{"total_errors": <int>, "marker_line": <int>, "errors_2001_4000": <int>}}'
)
SLICE_PACKET = (
    "Log file: {fixture} (exactly {total} lines). Consider ONLY lines {a} to {b} "
    "inclusive. Using only shell/read tools: count lines containing the substring "
    "ERROR inside that range, and check whether the line containing "
    "CRITICAL-MARKER falls inside it. Do not guess; verify by command. Reply with "
    'only compact JSON: {{"errors": <int>, "marker_line": <int or null>}}'
)
SWARM_PACKET = (
    "Log file: {fixture} (exactly {total} lines). Immediately fan out THREE "
    "parallel Agent subagent calls, one per disjoint inclusive line range: "
    "1-1333, 1334-2666, 2667-4000. Each subagent counts lines containing the "
    "substring ERROR in its range and reports whether CRITICAL-MARKER is in its "
    "range (line number if so, else null). Wait for all three, sum the counts, "
    "then run one check yourself: how many ERROR lines fall within lines 2001 to "
    "4000 inclusive. Reply with only compact JSON: "
    '{{"total_errors": <int>, "marker_line": <int>, "errors_2001_4000": <int>}}'
)

USAGE_KEYS = ("input_other", "input_cache_read", "input_cache_creation", "output")
SEED_ITEMS = ("config.toml", "kimi.json", "device_id", "credentials")


@dataclass
class RunResult:
    stdout: str
    returncode: int
    wall_s: float
    usage: dict[str, int]
    requests: list[dict[str, int]] = field(default_factory=list)

    @property
    def gross_input(self) -> int:
        return sum(self.usage[k] for k in USAGE_KEYS[:3])


def kimi_cli_version() -> str:
    try:
        out = subprocess.run(
            ["kimi", "--version"], capture_output=True, text=True, timeout=15
        )
        return out.stdout.strip().replace("kimi, version ", "")
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def resolve_worker() -> Path:
    for candidate in (
        shutil.which("kimi-worker"),
        HOME / ".agent-token-saver/bin/kimi-worker",
        HOME / ".local/bin/kimi-worker",
        ROOT / "integration/cli/kimi-worker",
    ):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise SystemExit("kimi-worker not found on PATH or in install locations")


def parse_wire_usage(share_dir: Path) -> tuple[dict[str, int], list[dict[str, int]]]:
    """Sum token_usage across ALL wire.jsonl under sessions/. Same field mapping
    as kimi-worker's ledger export, but recursive: built-in Agent subagents
    write their own wire.jsonl beside the parent's (verified in kimi-cli
    1.49.0 ``subagents/store.py``), and a fresh share dir belongs to exactly
    one arm, so every wire found is arm usage."""
    wires = sorted(
        share_dir.glob("sessions/**/wire.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )
    total = dict.fromkeys(USAGE_KEYS, 0)
    requests: list[dict[str, int]] = []
    for wire in wires:
        text = wire.read_text(errors="replace")
        for raw in re.findall(r'"token_usage": (\{[^}]*\})', text):
            usage = json.loads(raw)
            row = {k: int(usage.get(k, 0)) for k in USAGE_KEYS}
            requests.append(row)
            for key in USAGE_KEYS:
                total[key] += row[key]
    return total, requests


def subcount_errors() -> int:
    """ERROR lines inside SUBCOUNT_RANGE, derived from the seeded fixture."""
    lines = build().splitlines()
    a, b = SUBCOUNT_RANGE
    return sum("ERROR" in lines[i - 1] for i in range(a, b + 1))


def expected_answer() -> dict:
    return {
        "total_errors": ERROR_LINES,
        "marker_line": MARKER_LINE,
        "errors_2001_4000": subcount_errors(),
    }


def list_price_estimate(usage: dict[str, int]) -> float:
    """K3 list-price estimate in USD — labelled estimate, not an invoice."""
    return round(sum(usage[k] * PRICE_PER_M[k] for k in USAGE_KEYS) / 1_000_000, 4)


def seed_share_dir(share_dir: Path, seed_from: Path) -> None:
    """Mirror the wrapper's seeding: identity in, sessions/accounting isolated."""
    share_dir.mkdir(parents=True, exist_ok=True)
    for item in SEED_ITEMS:
        src = seed_from / item
        dst = share_dir / item
        if not dst.exists() and src.exists():
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)


def run_worker(
    packet: str,
    model: str,
    state_root: Path,
    name: str,
    no_thinking: bool = False,
) -> RunResult:
    share = state_root / name
    env = os.environ.copy()
    env["KIMI_WORKER_SHARE_DIR"] = str(share)
    env["KIMI_WORKER_MODEL"] = model
    if no_thinking:
        env["KIMI_WORKER_NO_THINKING"] = "1"
    else:
        env.pop("KIMI_WORKER_NO_THINKING", None)
    start = time.monotonic()
    proc = subprocess.run(
        [str(run_worker.worker_path), packet],
        capture_output=True,
        text=True,
        env=env,
        timeout=TIMEOUT_S,
    )
    wall = time.monotonic() - start
    usage, requests = parse_wire_usage(share)
    return RunResult(proc.stdout.strip(), proc.returncode, wall, usage, requests)


def run_swarm(packet: str, model: str, state_root: Path, name: str) -> RunResult:
    """One parent session told to fan out three parallel built-in Agent calls."""
    share = state_root / name
    seed_share_dir(share, HOME / ".kimi")
    skills_dir = tempfile.mkdtemp(prefix="kimi-bench-skills-")
    env = os.environ.copy()
    env["KIMI_SHARE_DIR"] = str(share)
    try:
        start = time.monotonic()
        proc = subprocess.run(
            ["kimi-cli", "--quiet", "-y", "--skills-dir", skills_dir,
             "-m", model, "-p", packet],
            capture_output=True,
            text=True,
            env=env,
            timeout=TIMEOUT_S * 3,
        )
        wall = time.monotonic() - start
    finally:
        shutil.rmtree(skills_dir, ignore_errors=True)
    usage, requests = parse_wire_usage(share)
    return RunResult(proc.stdout.strip(), proc.returncode, wall, usage, requests)


def parse_answer(stdout: str) -> dict | None:
    """Last JSON object in the worker's final message, else None."""
    for match in reversed(re.findall(r"\{[^{}]*\}", stdout)):
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    return None


def oracle_single(answer: dict | None) -> bool:
    if not answer:
        return False
    return all(answer.get(k) == v for k, v in expected_answer().items())


def oracle_team(answers: list[dict | None]) -> bool:
    if any(a is None for a in answers):
        return False
    errors = [a.get("errors") for a in answers if a]
    markers = [a.get("marker_line") for a in answers if a and a.get("marker_line")]
    return (
        all(isinstance(e, int) for e in errors)
        and sum(errors) == ERROR_LINES
        and markers == [MARKER_LINE]
    )


def arm_single(
    model: str, fixture: Path, state: Path, no_thinking: bool = False, tag: str = ""
) -> dict:
    packet = SINGLE_PACKET.format(fixture=fixture, total=TOTAL_LINES)
    result = run_worker(packet, model, state, f"single{tag}", no_thinking)
    answer = parse_answer(result.stdout)
    return {
        "invocation": f"kimi-worker -m {model}" + (" --no-thinking" if no_thinking else ""),
        "model": model,
        "thinking": not no_thinking,
        "requests": result.requests,
        "gross_input": result.gross_input,
        "uncached_input": result.usage["input_other"],
        "cache_read": result.usage["input_cache_read"],
        "cache_creation": result.usage["input_cache_creation"],
        "output": result.usage["output"],
        "wall_s": round(result.wall_s, 2),
        "est_cost_usd_list": list_price_estimate(result.usage),
        "answer": answer,
        "oracle": "PASS" if oracle_single(answer) else "FAIL",
        "exit_code": result.returncode,
    }


def arm_team(model: str, fixture: Path, state: Path) -> dict:
    """Three simultaneous workers on the disjoint fixture thirds."""
    import concurrent.futures

    packets = [
        SLICE_PACKET.format(fixture=fixture, total=TOTAL_LINES, a=a, b=b)
        for a, b in SLICES
    ]
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(
                lambda i: run_worker(packets[i], model, state, f"team-w{i + 1}"),
                range(3),
            )
        )
    wall = time.monotonic() - start
    answers = [parse_answer(r.stdout) for r in results]
    total_usage = dict.fromkeys(USAGE_KEYS, 0)
    for r in results:
        for key in USAGE_KEYS:
            total_usage[key] += r.usage[key]
    return {
        "invocation": f"3x kimi-worker simultaneous, -m {model}, disjoint thirds",
        "model": model,
        "children_gross": [r.gross_input for r in results],
        "children_answers": answers,
        "gross_input": sum(total_usage[k] for k in USAGE_KEYS[:3]),
        "uncached_input": total_usage["input_other"],
        "cache_read": total_usage["input_cache_read"],
        "cache_creation": total_usage["input_cache_creation"],
        "output": total_usage["output"],
        "wall_s": round(wall, 2),
        "est_cost_usd_list": list_price_estimate(total_usage),
        "oracle": "PASS" if oracle_team(answers) else "FAIL",
    }


def arm_swarm(model: str, fixture: Path, state: Path) -> dict:
    packet = SWARM_PACKET.format(fixture=fixture, total=TOTAL_LINES)
    result = run_swarm(packet, model, state, "swarm")
    answer = parse_answer(result.stdout)
    return {
        "invocation": f"single kimi-cli parent -m {model}, 3 parallel built-in Agent calls",
        "model": model,
        "requests": len(result.requests),
        "gross_input": result.gross_input,
        "uncached_input": result.usage["input_other"],
        "cache_read": result.usage["input_cache_read"],
        "cache_creation": result.usage["input_cache_creation"],
        "output": result.usage["output"],
        "wall_s": round(result.wall_s, 2),
        "est_cost_usd_list": list_price_estimate(result.usage),
        "answer": answer,
        "oracle": "PASS" if oracle_single(answer) else "FAIL",
        "exit_code": result.returncode,
    }


ARMS = {
    "k27-single": lambda f, s: arm_single(MODEL_K27, f, s, tag="-k27"),
    "k3-single": lambda f, s: arm_single(MODEL_K3, f, s),
    "k3-single-nothink": lambda f, s: arm_single(
        MODEL_K3, f, s, no_thinking=True, tag="-nothink"
    ),
    "k3-team": lambda f, s: arm_team(MODEL_K3, f, s),
    "k3-swarm": lambda f, s: arm_swarm(MODEL_K3, f, s),
}


def pct(delta: float) -> str:
    return f"{'-' if delta < 0 else '+'}{abs(delta):.1f}%"


def savings(arms: dict[str, dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    k27, k3 = arms.get("k27-single"), arms.get("k3-single")
    if k27 and k3:
        out["k3_vs_k27_single_gross"] = pct(
            (k3["gross_input"] - k27["gross_input"]) / k27["gross_input"] * 100
        ) + f" ({k27['gross_input']:,} -> {k3['gross_input']:,})"
    team, swarm = arms.get("k3-team"), arms.get("k3-swarm")
    if team and swarm:
        out["k3_team_vs_k3_swarm_gross"] = pct(
            (team["gross_input"] - swarm["gross_input"]) / swarm["gross_input"] * 100
        ) + f" ({swarm['gross_input']:,} -> {team['gross_input']:,})"
    if team:
        out["k3_team_vs_claude_team_0719"] = pct(
            (team["gross_input"] - BASELINE_0719["claude_team_gross"])
            / BASELINE_0719["claude_team_gross"] * 100
        ) + f" ({BASELINE_0719['claude_team_gross']:,} -> {team['gross_input']:,})"
    think = arms.get("k3-single-nothink")
    if k3 and think:
        out["k3_nothink_vs_think_output"] = pct(
            (think["output"] - k3["output"]) / max(k3["output"], 1) * 100
        ) + f" output ({k3['output']:,} -> {think['output']:,})"
    if k27:
        drift = (k27["gross_input"] - BASELINE_0719["k27_single_gross"]) / BASELINE_0719[
            "k27_single_gross"
        ] * 100
        out["k27_single_drift_vs_0719"] = pct(drift) + (
            f" ({BASELINE_0719['k27_single_gross']:,} -> {k27['gross_input']:,})"
        )
    return out


def render_md(report: dict) -> str:
    rows = []
    for name, arm in report["arms"].items():
        rows.append(
            f"| {name} | {arm['gross_input']:,} | {arm['uncached_input']:,} | "
            f"{arm['cache_read']:,} | {arm['output']:,} | "
            f"${arm.get('est_cost_usd_list', 0):.4f} | {arm['wall_s']} s | "
            f"{arm['oracle']} |"
        )
    lines = [
        f"# Kimi K3 lane A/B — {report['date']}",
        "",
        f"Host: {report['host']}. Same fixture and oracle as "
        "[kimi-worker-system-2026-07-19](kimi-worker-system-2026-07-19.md) "
        f"({report['fixture']}). Usage summed from each isolated share dir's "
        "`wire.jsonl`, same field mapping as the wrapper's ledger export.",
        "",
        "| Arm | Gross input | Uncached | Cache read | Output | Est. $ (list) | Wall | Oracle |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
        *rows,
        "",
        "## Measured deltas",
        "",
        *[f"- **{k}**: {v}" for k, v in report["real_savings"].items()],
        "",
        "Oracle hardening vs 2026-07-19: single/swarm arms must also report "
        "`errors_2001_4000` = 44 (positional subcount; defeats head-only reads "
        "and round-number guessing). Packets never contain the expected values.",
        "",
        "Headless-swarm note: K3's PARL-trained **Swarm Max** is app-only "
        "(kimi.com/agent-swarm, paid tiers) with no documented API/CLI access as "
        "of today; the `k3-swarm` arm measures the CLI's built-in `Agent` tool "
        "(prompt-templated subagents) running on K3 — the honest headless "
        "comparand.",
        "",
        "Billing caveat: token classes are provider usage fields. Claude runs on an "
        "Anthropic subscription, Kimi on Moonshot membership quota; the Est. $ "
        "column applies vendor-published K3 list prices ($3/$15 per M, $0.30 "
        "cache hit) — **list-price estimate, not an invoice**. Arms run "
        "sequentially in the listed order, each on a fresh isolated share dir; "
        "Moonshot caching is implicit and write-free (`input_cache_creation` = 0), "
        "so warming appears as a class shift between uncached and cache-read, "
        "never as hidden savings.",
        "",
        f"Reproduce: `uv run python scripts/kimi_k3_lane_benchmark.py`. "
        f"Raw JSON: `{OUT_JSON.name}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", choices=sorted(ARMS), default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-state", type=Path, default=None)
    args = parser.parse_args()

    selected = args.arm or list(ARMS)
    fixture = Path(tempfile.mkdtemp(prefix="kimi-bench-")) / "fixture.log"
    fixture.write_text(build())

    if args.dry_run:
        print(SINGLE_PACKET.format(fixture=fixture, total=TOTAL_LINES), end="\n\n")
        a, b = SLICES[0]
        print(SLICE_PACKET.format(fixture=fixture, total=TOTAL_LINES, a=a, b=b), end="\n\n")
        print(SWARM_PACKET.format(fixture=fixture, total=TOTAL_LINES))
        return

    run_worker.worker_path = resolve_worker()  # type: ignore[attr-defined]
    state = args.keep_state or Path(tempfile.mkdtemp(prefix="kimi-bench-state-"))
    version = kimi_cli_version()
    report = {
        "date": STAMP,
        "host": f"{platform.system().lower()} {platform.release()}, "
        f"kimi-cli {version}, models {MODEL_K27} / {MODEL_K3}",
        "fixture": "scripts/make_log_fixture.py (4000 lines, 100 ERROR, "
        "CRITICAL-MARKER at 3777; team slices 1-1333/1334-2666/2667-4000 = 40/32/28)",
        "oracle": "single/swarm: total_errors=100, marker_line=3777 and "
        f"errors_2001_4000={subcount_errors()}; team: slice counts sum to 100 "
        "and exactly one slice reports 3777",
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "packets": {
            "single": SINGLE_PACKET.format(fixture="<fixture>", total=TOTAL_LINES),
            "slice": SLICE_PACKET.format(
                fixture="<fixture>", total=TOTAL_LINES, a=SLICES[0][0], b=SLICES[0][1]
            ),
            "swarm": SWARM_PACKET.format(fixture="<fixture>", total=TOTAL_LINES),
        },
        "usage_source": "wire.jsonl token_usage per request, fresh isolated "
        "KIMI_SHARE_DIR per worker (seeded identity, isolated sessions)",
        "baselines_2026_07_19": BASELINE_0719,
        "arms": {},
    }
    run_order = 0
    for name in selected:
        for rep in range(1, args.repeat + 1):
            key = name if args.repeat == 1 else f"{name}-run{rep}"
            print(f"[bench] {key} ...", flush=True)
            run_order += 1
            report["arms"][key] = ARMS[name](fixture, state)
            report["arms"][key]["run_order"] = run_order
            arm = report["arms"][key]
            print(
                f"[bench] {key}: gross={arm['gross_input']:,} "
                f"wall={arm['wall_s']}s oracle={arm['oracle']}",
                flush=True,
            )
    report["real_savings"] = savings(report["arms"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=1) + "\n")
    OUT_MD.write_text(render_md(report))
    print(f"[bench] wrote {OUT_JSON}")
    print(f"[bench] wrote {OUT_MD}")
    failed = [k for k, a in report["arms"].items() if a["oracle"] != "PASS"]
    if failed:
        print(f"[bench] ORACLE FAIL: {', '.join(failed)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
