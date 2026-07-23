#!/usr/bin/env python3
"""ats-swarm-bench - test ats-llm-pipe + supacrawl extraction across multiple
agent CLIs (codex, kimi, claude, gemini, hermes+luna, hermes+terra).

Measures: wall time, output chars (token proxy), success rate, JSON validity.

Usage:
  python3 ats-swarm-bench.py --iter 2 --out /tmp/ats_swarm_bench.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class SwarmResult:
    agent: str
    iter_idx: int
    wall_s: float
    chars: int
    tokens_est: int
    exit_code: int
    success: bool
    json_valid: bool
    sample: str


# Each agent: (name, command, env_override)
AGENTS: list[tuple[str, list[str], dict[str, str]]] = [
    ("codex",
     ["codex", "exec", "--skip-git-repo-check", "-"],
     {}),
    ("hermes_kimi",
     ["hermes", "-z", "-", "-m", "kimi-k3", "--cli"],
     {}),
    ("hermes_luna",
     ["hermes", "-z", "-", "-m", "openai/gpt-5.6-luna", "--cli"],
     {}),
    ("hermes_terra",
     ["hermes", "-z", "-", "-m", "openai/gpt-5.6-terra", "--cli"],
     {}),
    ("hermes_codex",
     ["hermes", "-z", "-", "-m", "openai-codex:gpt-5.5", "--cli"],
     {}),
]

# The probe: a realistic extraction task
EXTRACT_PROMPT = (
    "Extract product information from this text:\n\n"
    "'Acme Widget Pro — $42.99 — The best widget on the market. "
    "Features: durable, lightweight, eco-friendly. In stock.'\n\n"
    "Return JSON only: {name, price, features:[], in_stock:bool}"
)


def run_agent(agent: tuple[str, list[str], dict[str, str]], iter_idx: int) -> SwarmResult:
    name, cmd, env_override = agent
    env = os.environ.copy()
    env.update(env_override)

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=EXTRACT_PROMPT,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/tmp",
            env=env,
            check=False,
        )
        wall = time.time() - t0
        out = proc.stdout.strip()
        chars = len(out)
        tokens = chars // 4
        success = proc.returncode == 0 and chars > 0

        # Check JSON validity (agents may wrap in fences)
        json_valid = False
        try:
            # Strip code fences if present
            cleaned = out
            if cleaned.startswith("```"):
                cleaned = "\n".join(line for line in cleaned.split("\n")
                                    if not line.startswith("```"))
            # Find first { ... } block
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                json.loads(cleaned[start:end+1])
                json_valid = True
        except Exception:
            json_valid = False

        return SwarmResult(
            agent=name,
            iter_idx=iter_idx,
            wall_s=round(wall, 3),
            chars=chars,
            tokens_est=tokens,
            exit_code=proc.returncode,
            success=success,
            json_valid=json_valid,
            sample=out[:200].replace("\n", " "),
        )
    except subprocess.TimeoutExpired:
        return SwarmResult(name, iter_idx, 120.0, 0, 0, -1, False, False, "<timeout>")
    except FileNotFoundError as e:
        return SwarmResult(name, iter_idx, 0.0, 0, 0, -1, False, False, f"<missing: {e}>")
    except Exception as e:
        return SwarmResult(name, iter_idx, 0.0, 0, 0, -1, False, False, f"<error: {e}>")


def aggregate(results: list[SwarmResult]) -> dict[str, dict[str, Any]]:
    by_agent: dict[str, list[SwarmResult]] = {}
    for r in results:
        by_agent.setdefault(r.agent, []).append(r)
    agg = {}
    for agent, rs in by_agent.items():
        ok = [r for r in rs if r.success]
        json_ok = [r for r in rs if r.json_valid]
        agg[agent] = {
            "n": len(rs),
            "success_rate": round(len(ok) / len(rs), 2),
            "json_valid_rate": round(len(json_ok) / len(rs), 2),
            "wall_s_mean": round(sum(r.wall_s for r in rs) / len(rs), 3),
            "chars_mean": int(sum(r.chars for r in rs) / len(rs)),
            "tokens_est_mean": int(sum(r.tokens_est for r in rs) / len(rs)),
        }
    return agg


def markdown_table(agg: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| Agent | n | success | json_valid | wall_s | chars | tokens~ |",
        "|---|---|---|---|---|---|---|",
    ]
    for agent, s in agg.items():
        lines.append(
            f"| {agent} | {s['n']} | {s['success_rate']} | {s['json_valid_rate']} | "
            f"{s['wall_s_mean']} | {s['chars_mean']} | {s['tokens_est_mean']} |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=2)
    ap.add_argument("--out", type=str, default="/tmp/ats_swarm_bench.json")
    ap.add_argument("--md", type=str, default="/tmp/ats_swarm_bench.md")
    ap.add_argument("--only", type=str, default=None)
    args = ap.parse_args()

    agents = [a for a in AGENTS if args.only is None or args.only in a[0]]
    if not agents:
        print(f"No agents match --only={args.only!r}", file=sys.stderr)
        return 1

    print(f"Running {len(agents)} agents x {args.iter} iter = {len(agents)*args.iter} calls...",
          file=sys.stderr)
    results: list[SwarmResult] = []
    for i in range(args.iter):
        for agent in agents:
            print(f"  [{i+1}/{args.iter}] {agent[0]}...", file=sys.stderr)
            r = run_agent(agent, i)
            results.append(r)
            print(f"    -> {r.wall_s}s, {r.chars} chars, json_valid={r.json_valid}",
                  file=sys.stderr)

    agg = aggregate(results)
    Path(args.out).write_text(json.dumps({"results": [asdict(r) for r in results],
                                          "aggregate": agg}, indent=2))
    Path(args.md).write_text(markdown_table(agg))
    print("\n=== Swarm Aggregate ===")
    print(markdown_table(agg))
    print(f"\nWrote: {args.out} + {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
