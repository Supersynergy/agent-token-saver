#!/usr/bin/env python3
"""ats-recon-bench - benchmark the new recon CLIs (gmax, ghx, supacrawl, ats-llm-pipe)
against baseline approaches to measure real token + latency savings.

Runs N iterations of each probe, records:
  - wall time (s)
  - output chars (proxy for tokens: chars/4 ~ tokens)
  - output lines
  - success (non-empty + exit 0)

Outputs JSON + Markdown table.

Usage:
  python3 ats-recon-bench.py --iter 3 --out /tmp/ats_recon_bench.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProbeResult:
    name: str
    iter_idx: int
    wall_s: float
    chars: int
    lines: int
    exit_code: int
    success: bool
    sample: str  # first 200 chars


PROBES: list[dict[str, Any]] = [
    # --- Local codebase search ---
    {
        "name": "gmax_semantic",
        "cmd": ["gmax", "where is usage parsing handled", "--agent"],
        "cwd": str(Path(__file__).resolve().parents[2]),
    },
    {
        "name": "grep_baseline",
        "cmd": ["grep", "-rn", "usage",
                f"{Path(__file__).resolve().parents[2]}/integration"],
        "cwd": None,
    },
    # --- GitHub repo recon ---
    {
        "name": "ghx_explore",
        "cmd": ["ghx", "explore", "Supersynergy/agent-token-saver"],
        "cwd": None,
    },
    {
        "name": "ghx_inspect",
        "cmd": ["ghx", "inspect", "Supersynergy/agent-token-saver",
                "where is usage parsing handled"],
        "cwd": None,
    },
    {
        "name": "gh_api_baseline",
        "cmd": ["gh", "api", "repos/Supersynergy/agent-token-saver/contents/"],
        "cwd": None,
    },
    # --- Web scrape ---
    {
        "name": "supacrawl_scrape",
        "cmd": ["supacrawl", "scrape", "https://example.com", "--format", "markdown"],
        "cwd": None,
    },
    {
        "name": "curl_baseline",
        "cmd": ["curl", "-sL", "https://example.com"],
        "cwd": None,
    },
    # --- LLM extraction (stdio bridge) ---
    {
        "name": "supacrawl_extract_stdio",
        "cmd": ["supacrawl", "scrape", "https://example.com",
                "--format", "json",
                "--prompt", "Extract the heading and learn-more URL. Return JSON {heading, learn_more_url}"],
        "cwd": None,
        "env": {"SUPACRAWL_LLM_PROVIDER": "stdio", "SUPACRAWL_LLM_MODEL": "active"},
    },
]


def run_probe(probe: dict[str, Any], iter_idx: int) -> ProbeResult:
    cmd = probe["cmd"]
    cwd = probe.get("cwd")
    env_override = probe.get("env", {})
    env = os.environ.copy()
    env.update(env_override)

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=cwd,
            env=env,
            check=False,
        )
        wall = time.time() - t0
        out = proc.stdout
        chars = len(out)
        lines = out.count("\n")
        success = proc.returncode == 0 and chars > 0
        return ProbeResult(
            name=probe["name"],
            iter_idx=iter_idx,
            wall_s=round(wall, 3),
            chars=chars,
            lines=lines,
            exit_code=proc.returncode,
            success=success,
            sample=out[:200].replace("\n", " "),
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(probe["name"], iter_idx, 180.0, 0, 0, -1, False, "<timeout>")
    except FileNotFoundError as e:
        return ProbeResult(probe["name"], iter_idx, 0.0, 0, 0, -1, False, f"<missing: {e}>")
    except Exception as e:
        return ProbeResult(probe["name"], iter_idx, 0.0, 0, 0, -1, False, f"<error: {e}>")


def aggregate(results: list[ProbeResult]) -> dict[str, dict[str, float]]:
    by_name: dict[str, list[ProbeResult]] = {}
    for r in results:
        by_name.setdefault(r.name, []).append(r)
    agg = {}
    for name, rs in by_name.items():
        ok = [r for r in rs if r.success]
        agg[name] = {
            "n": len(rs),
            "success_rate": round(len(ok) / len(rs), 2),
            "wall_s_mean": round(sum(r.wall_s for r in rs) / len(rs), 3),
            "chars_mean": int(sum(r.chars for r in rs) / len(rs)),
            "tokens_est": int(sum(r.chars for r in rs) / len(rs) / 4),
            "lines_mean": int(sum(r.lines for r in rs) / len(rs)),
        }
    return agg


def markdown_table(agg: dict[str, dict[str, float]]) -> str:
    lines = [
        "| Probe | n | success | wall_s | chars | tokens~ | lines |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, s in agg.items():
        lines.append(
            f"| {name} | {s['n']} | {s['success_rate']} | {s['wall_s_mean']} | "
            f"{s['chars_mean']} | {s['tokens_est']} | {s['lines_mean']} |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=3, help="iterations per probe")
    ap.add_argument("--out", type=str, default="/tmp/ats_recon_bench.json",
                    help="JSON output path")
    ap.add_argument("--md", type=str, default="/tmp/ats_recon_bench.md",
                    help="Markdown output path")
    ap.add_argument("--only", type=str, default=None,
                    help="filter probe names by substring")
    args = ap.parse_args()

    probes = [p for p in PROBES if args.only is None or args.only in p["name"]]
    if not probes:
        print(f"No probes match --only={args.only!r}", file=sys.stderr)
        return 1

    print(f"Running {len(probes)} probes × {args.iter} iter = {len(probes)*args.iter} calls...",
          file=sys.stderr)
    results: list[ProbeResult] = []
    for i in range(args.iter):
        for p in probes:
            print(f"  [{i+1}/{args.iter}] {p['name']}...", file=sys.stderr)
            r = run_probe(p, i)
            results.append(r)
            print(f"    → {r.wall_s}s, {r.chars} chars, success={r.success}",
                  file=sys.stderr)

    agg = aggregate(results)
    Path(args.out).write_text(json.dumps({"results": [asdict(r) for r in results],
                                          "aggregate": agg}, indent=2))
    Path(args.md).write_text(markdown_table(agg))
    print("\n=== Aggregate ===")
    print(markdown_table(agg))
    print(f"\nWrote: {args.out} + {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
