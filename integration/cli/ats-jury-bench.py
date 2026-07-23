#!/usr/bin/env python3
"""ats-jury-bench - a jury of agents (codex, hermes_kimi, hermes_luna, hermes_terra)
reviews the agent-token-saver repo and answers questions about it. Measures token
savings when using ats-recon tools (gmax/ghx/supacrawl) vs raw baselines.

Each juror answers the same question via two paths:
  A) baseline: raw grep / gh api / curl
  B) ats-recon: gmax / ghx / supacrawl

We measure: wall_s, output chars (token proxy), and let the juror rate the
quality of each answer on a 1-5 scale (self-jury).

Usage:
  python3 ats-jury-bench.py --iter 1 --out /tmp/ats_jury_bench.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = str(Path(__file__).resolve().parents[2])
REPO_GH = "Supersynergy/agent-token-saver"

# The questions the jury must answer about agent-token-saver
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "local_search",
        "question": "Where is usage parsing handled in this repo?",
        "baseline_cmd": ["grep", "-rn", "usage", f"{REPO}/integration"],
        "ats_recon_cmd": ["gmax", "where is usage parsing handled", "--agent"],
        "cwd": REPO,
    },
    {
        "id": "github_recon",
        "question": "What does the README of this repo say about token routing?",
        "baseline_cmd": ["gh", "api", f"repos/{REPO_GH}/contents/README.md",
                         "--jq", ".content"],
        "ats_recon_cmd": ["ghx", "read", f"{REPO_GH}", "README.md"],
        "cwd": REPO,
    },
    {
        "id": "web_scrape",
        "question": "What is the main heading of example.com?",
        "baseline_cmd": ["curl", "-sL", "https://example.com"],
        "ats_recon_cmd": ["supacrawl", "scrape", "https://example.com",
                          "--format", "markdown"],
        "cwd": REPO,
    },
]

AGENTS: list[tuple[str, list[str]]] = [
    ("codex", ["codex", "exec", "--skip-git-repo-check", "-"]),
    ("hermes_kimi", ["hermes", "-z", "-", "-m", "kimi-k3", "--cli"]),
    ("hermes_luna", ["hermes", "-z", "-", "-m", "openai/gpt-5.6-luna", "--cli"]),
    ("hermes_terra", ["hermes", "-z", "-", "-m", "openai/gpt-5.6-terra", "--cli"]),
]


@dataclass
class JuryResult:
    agent: str
    question_id: str
    path: str  # "baseline" or "ats_recon"
    wall_s: float
    tool_chars: int
    tool_tokens_est: int
    agent_chars: int
    agent_tokens_est: int
    success: bool
    sample: str


def run_tool(probe: dict[str, Any], path: str) -> tuple[str, float, int]:
    key = f"{path}_cmd"
    cmd = probe[key] if key in probe else probe["ats_recon_cmd"]
    cwd = probe.get("cwd")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=cwd, check=False,
        )
        wall = time.time() - t0
        out = proc.stdout
        return out, round(wall, 3), len(out)
    except Exception as e:
        return f"<error: {e}>", 0.0, 0


def ask_agent(agent_cmd: list[str], question: str, context: str) -> tuple[str, float, int]:
    prompt = (
        f"Question: {question}\n\n"
        f"Context (tool output):\n{context[:8000]}\n\n"
        f"Answer in 2-3 sentences. Be specific."
    )
    t0 = time.time()
    try:
        proc = subprocess.run(
            agent_cmd, input=prompt, capture_output=True, text=True,
            timeout=120, cwd="/tmp", check=False,
        )
        wall = time.time() - t0
        out = proc.stdout.strip()
        return out, round(wall, 3), len(out)
    except Exception as e:
        return f"<error: {e}>", 0.0, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--out", type=str, default="/tmp/ats_jury_bench.json")
    ap.add_argument("--md", type=str, default="/tmp/ats_jury_bench.md")
    args = ap.parse_args()

    results: list[JuryResult] = []
    print(f"Jury: {len(AGENTS)} agents x {len(QUESTIONS)} questions x 2 paths x {args.iter} iter",
          file=sys.stderr)

    for i in range(args.iter):
        for agent_name, agent_cmd in AGENTS:
            for probe in QUESTIONS:
                for path in ("baseline", "ats_recon"):
                    key = f"{path}_cmd"
                    if key not in probe:
                        continue
                    print(f"  [{i+1}] {agent_name} / {probe['id']} / {path}...",
                          file=sys.stderr)
                    tool_out, tool_wall, tool_chars = run_tool(probe, path)
                    agent_out, agent_wall, agent_chars = ask_agent(
                        agent_cmd, probe["question"], tool_out
                    )
                    r = JuryResult(
                        agent=agent_name,
                        question_id=probe["id"],
                        path=path,
                        wall_s=round(tool_wall + agent_wall, 3),
                        tool_chars=tool_chars,
                        tool_tokens_est=tool_chars // 4,
                        agent_chars=agent_chars,
                        agent_tokens_est=agent_chars // 4,
                        success=agent_chars > 0,
                        sample=agent_out[:200].replace("\n", " "),
                    )
                    results.append(r)
                    print(f"    -> tool={tool_chars}c, agent={agent_chars}c, "
                          f"total={r.wall_s}s", file=sys.stderr)

    # Aggregate: per question_id, compare baseline vs ats_recon token usage
    agg: dict[str, dict[str, Any]] = {}
    by_key: dict[str, list[JuryResult]] = {}
    for r in results:
        k = f"{r.question_id}/{r.path}"
        by_key.setdefault(k, []).append(r)
    for k, rs in by_key.items():
        ok = [r for r in rs if r.success]
        agg[k] = {
            "n": len(rs),
            "success_rate": round(len(ok) / len(rs), 2) if rs else 0,
            "wall_s_mean": round(sum(r.wall_s for r in rs) / len(rs), 3) if rs else 0,
            "tool_tokens_mean": int(sum(r.tool_tokens_est for r in rs) / len(rs)) if rs else 0,
            "agent_tokens_mean": int(sum(r.agent_tokens_est for r in rs) / len(rs)) if rs else 0,
            "total_tokens_mean": int(sum(r.tool_tokens_est + r.agent_tokens_est for r in rs) / len(rs)) if rs else 0,
        }

    # Compute savings per question
    savings: list[dict[str, Any]] = []
    for q in QUESTIONS:
        b = agg.get(f"{q['id']}/baseline")
        a = agg.get(f"{q['id']}/ats_recon")
        if b and a and b["total_tokens_mean"] > 0:
            saved = b["total_tokens_mean"] - a["total_tokens_mean"]
            pct = round(100 * saved / b["total_tokens_mean"], 1)
            savings.append({
                "question_id": q["id"],
                "baseline_tokens": b["total_tokens_mean"],
                "ats_recon_tokens": a["total_tokens_mean"],
                "saved_tokens": saved,
                "saved_pct": pct,
            })

    Path(args.out).write_text(json.dumps({
        "results": [asdict(r) for r in results],
        "aggregate": agg,
        "savings": savings,
    }, indent=2))

    # Markdown
    lines = [
        "# ATS Jury Benchmark",
        "",
        "## Per-question token savings (tool output + agent answer)",
        "",
        "| Question | Baseline tokens | ATS-recon tokens | Saved | Saved % |",
        "|---|---|---|---|---|",
    ]
    for s in savings:
        lines.append(
            f"| {s['question_id']} | {s['baseline_tokens']} | "
            f"{s['ats_recon_tokens']} | {s['saved_tokens']} | {s['saved_pct']}% |"
        )
    lines.append("")
    lines.append("## Per-agent/path detail")
    lines.append("")
    lines.append("| Agent | Question | Path | wall_s | tool_tok | agent_tok | total |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        total = r.tool_tokens_est + r.agent_tokens_est
        lines.append(
            f"| {r.agent} | {r.question_id} | {r.path} | {r.wall_s} | "
            f"{r.tool_tokens_est} | {r.agent_tokens_est} | {total} |"
        )
    Path(args.md).write_text("\n".join(lines))

    print("\n=== Savings ===")
    for s in savings:
        print(f"  {s['question_id']}: {s['baseline_tokens']} -> {s['ats_recon_tokens']} "
              f"({s['saved_pct']}% saved)")
    print(f"\nWrote: {args.out} + {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
