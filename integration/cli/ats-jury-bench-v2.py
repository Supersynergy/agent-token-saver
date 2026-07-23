#!/usr/bin/env python3
"""ats-jury-bench-v2 - jury of agents with ABBA-adaptive ordering + metareview score.

Extends v1 (ats-jury-bench.py) with:
  1. Broader jury: codex, claude, kimi, gemini, fable (any subset available on PATH).
  2. ABBA-adaptive ordering: each (agent, question) pair runs baseline/ats_recon
     in ABBA or BAAB order (counter-balanced) so warmup/fatigue bias cancels.
  3. Metareview score: a second pass where a different agent (the "reviewer")
     rates the answer 1-5 without seeing which path produced it (blind review).
     The mean reviewer score per path is the "quality" metric.

Each juror answers the same question via two paths:
  A) baseline: raw grep / gh api / curl
  B) ats-recon: gmax / ghx / supacrawl

We measure: wall_s, output chars (token proxy), blind reviewer quality (1-5).

Usage:
  python3 ats-jury-bench-v2.py --iter 1 --out /tmp/ats_jury_bench_v2.json
  python3 ats-jury-bench-v2.py --agents codex,claude,kimi --abba --reviewer gemini
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = str(Path(__file__).resolve().parents[2])
REPO_GH = "Supersynergy/agent-token-saver"

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

# v2: broader jury. Each entry: (name, cmd, available_check).
# Agents are auto-filtered to those available on PATH.
AGENT_CANDIDATES: list[tuple[str, list[str]]] = [
    ("codex", ["codex", "exec", "--skip-git-repo-check", "-"]),
    ("claude", ["claude", "--print"]),
    ("kimi", ["kimi", "--print"]),
    ("gemini", ["gemini", "--print"]),
    ("fable", ["fable", "--print"]),
    # hermes variants from v1 kept for backward-compat
    ("hermes_kimi", ["hermes", "-z", "-", "-m", "kimi-k3", "--cli"]),
    ("hermes_luna", ["hermes", "-z", "-", "-m", "openai/gpt-5.6-luna", "--cli"]),
    ("hermes_terra", ["hermes", "-z", "-", "-m", "openai/gpt-5.6-terra", "--cli"]),
]


@dataclass
class JuryResultV2:
    agent: str
    question_id: str
    path: str  # "baseline" or "ats_recon"
    order_pos: int  # 1-based position within the ABBA round
    wall_s: float
    tool_chars: int
    tool_tokens_est: int
    agent_chars: int
    agent_tokens_est: int
    success: bool
    reviewer: str
    reviewer_score: float  # 0 if not reviewed
    sample: str


def agents_available(requested: str | None) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for name, cmd in AGENT_CANDIDATES:
        if requested and name not in requested:
            continue
        if shutil.which(cmd[0]):
            out.append((name, cmd))
    return out


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


def blind_review(reviewer_cmd: list[str], question: str, answer: str) -> float:
    """Ask a reviewer agent to rate the answer 1-5 without knowing the path."""
    if not reviewer_cmd or not shutil.which(reviewer_cmd[0]):
        return 0.0
    prompt = (
        f"You are a blind reviewer. Rate the following answer to the question "
        f"on a 1-5 scale (5 = excellent, 1 = wrong). Reply with ONLY the number.\n\n"
        f"Question: {question}\n"
        f"Answer: {answer[:2000]}\n"
    )
    try:
        proc = subprocess.run(
            reviewer_cmd, input=prompt, capture_output=True, text=True,
            timeout=60, cwd="/tmp", check=False,
        )
        txt = proc.stdout.strip()
        # Take the first digit found.
        for ch in txt:
            if ch in "12345":
                return float(ch)
        return 0.0
    except Exception:
        return 0.0


def abba_sequence(n_rounds: int) -> list[str]:
    """Return a list of 'baseline'/'ats_recon' in ABBA order per round."""
    seq: list[str] = []
    for _ in range(n_rounds):
        seq.extend(["baseline", "ats_recon", "ats_recon", "baseline"])
    return seq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1, help="ABBA rounds per (agent, question)")
    ap.add_argument("--out", type=str, default="/tmp/ats_jury_bench_v2.json")
    ap.add_argument("--md", type=str, default="/tmp/ats_jury_bench_v2.md")
    ap.add_argument("--agents", type=str, default="",
                    help="Comma-separated agent names (default: all available)")
    ap.add_argument("--reviewer", type=str, default="",
                    help="Reviewer agent name (default: first available non-juror)")
    ap.add_argument("--no-abba", action="store_true",
                    help="Disable ABBA ordering, use simple alternating")
    args = ap.parse_args()

    agents = agents_available(args.agents or None)
    if not agents:
        print("No agents available on PATH. Install codex/claude/kimi/gemini/fable.", file=sys.stderr)
        return 1

    # Pick reviewer: first agent not in the jury, or fall back to jury[0].
    reviewer_cmd: list[str] = []
    for name, cmd in AGENT_CANDIDATES:
        if args.reviewer and name != args.reviewer:
            continue
        if not args.reviewer and any(name == a[0] for a in agents):
            continue
        if shutil.which(cmd[0]):
            reviewer_cmd = cmd
            break
    if not reviewer_cmd and agents:
        reviewer_cmd = agents[0][1]
    reviewer_name = ""
    for name, cmd in AGENT_CANDIDATES:
        if cmd == reviewer_cmd:
            reviewer_name = name
            break

    results: list[JuryResultV2] = []
    print(f"Jury v2: {len(agents)} agents x {len(QUESTIONS)} questions x "
          f"{'ABBA' if not args.no_abba else 'alt'} x {args.iter} rounds",
          file=sys.stderr)
    print(f"Reviewer: {reviewer_name or 'none'}", file=sys.stderr)

    for agent_name, agent_cmd in agents:
        for probe in QUESTIONS:
            if args.no_abba:
                order = ["baseline", "ats_recon"] * args.iter
            else:
                order = abba_sequence(args.iter)
            for pos, path in enumerate(order, start=1):
                print(f"  {agent_name} / {probe['id']} / {path} [{pos}]...",
                      file=sys.stderr)
                tool_out, tool_wall, tool_chars = run_tool(probe, path)
                agent_out, agent_wall, agent_chars = ask_agent(
                    agent_cmd, probe["question"], tool_out
                )
                score = blind_review(reviewer_cmd, probe["question"], agent_out) if reviewer_cmd else 0.0
                r = JuryResultV2(
                    agent=agent_name,
                    question_id=probe["id"],
                    path=path,
                    order_pos=pos,
                    wall_s=round(tool_wall + agent_wall, 3),
                    tool_chars=tool_chars,
                    tool_tokens_est=tool_chars // 4,
                    agent_chars=agent_chars,
                    agent_tokens_est=agent_chars // 4,
                    success=agent_chars > 0,
                    reviewer=reviewer_name,
                    reviewer_score=score,
                    sample=agent_out[:200].replace("\n", " "),
                )
                results.append(r)
                print(f"    -> tool={tool_chars}c, agent={agent_chars}c, "
                      f"score={score}, total={r.wall_s}s", file=sys.stderr)

    # Aggregate
    agg: dict[str, dict[str, Any]] = {}
    by_key: dict[str, list[JuryResultV2]] = {}
    for r in results:
        k = f"{r.question_id}/{r.path}"
        by_key.setdefault(k, []).append(r)
    for k, rs in by_key.items():
        ok = [r for r in rs if r.success]
        scored = [r for r in rs if r.reviewer_score > 0]
        agg[k] = {
            "n": len(rs),
            "success_rate": round(len(ok) / len(rs), 2) if rs else 0,
            "wall_s_mean": round(sum(r.wall_s for r in rs) / len(rs), 3) if rs else 0,
            "tool_tokens_mean": int(sum(r.tool_tokens_est for r in rs) / len(rs)) if rs else 0,
            "agent_tokens_mean": int(sum(r.agent_tokens_est for r in rs) / len(rs)) if rs else 0,
            "total_tokens_mean": int(sum(r.tool_tokens_est + r.agent_tokens_est for r in rs) / len(rs)) if rs else 0,
            "reviewer_score_mean": round(sum(r.reviewer_score for r in scored) / len(scored), 2) if scored else 0,
        }

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
                "baseline_reviewer": b["reviewer_score_mean"],
                "ats_recon_reviewer": a["reviewer_score_mean"],
            })

    Path(args.out).write_text(json.dumps({
        "version": "v2",
        "agents": [a[0] for a in agents],
        "reviewer": reviewer_name,
        "abba": not args.no_abba,
        "results": [asdict(r) for r in results],
        "aggregate": agg,
        "savings": savings,
    }, indent=2))

    # Markdown
    lines = [
        "# ATS Jury Benchmark v2 (ABBA + blind metareview)",
        "",
        f"- Agents: {', '.join(a[0] for a in agents)}",
        f"- Reviewer: {reviewer_name or 'none'}",
        f"- Ordering: {'ABBA' if not args.no_abba else 'alternating'}",
        "",
        "## Per-question token savings + reviewer quality",
        "",
        "| Question | Baseline tok | ATS tok | Saved % | Baseline ★ | ATS ★ |",
        "|---|---|---|---|---|---|",
    ]
    for s in savings:
        lines.append(
            f"| {s['question_id']} | {s['baseline_tokens']} | "
            f"{s['ats_recon_tokens']} | {s['saved_pct']}% | "
            f"{s['baseline_reviewer']} | {s['ats_recon_reviewer']} |"
        )
    lines.append("")
    lines.append("## Per-agent/path detail")
    lines.append("")
    lines.append("| Agent | Question | Path | Pos | wall_s | tool_tok | agent_tok | ★ |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r.agent} | {r.question_id} | {r.path} | {r.order_pos} | "
            f"{r.wall_s} | {r.tool_tokens_est} | {r.agent_tokens_est} | "
            f"{r.reviewer_score} |"
        )
    Path(args.md).write_text("\n".join(lines))

    print("\n=== Savings (v2) ===")
    for s in savings:
        print(f"  {s['question_id']}: {s['baseline_tokens']} -> {s['ats_recon_tokens']} "
              f"({s['saved_pct']}% saved, ★ {s['baseline_reviewer']} vs {s['ats_recon_reviewer']})")
    print(f"\nWrote: {args.out} + {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
