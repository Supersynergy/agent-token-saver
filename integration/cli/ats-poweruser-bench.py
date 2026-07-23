#!/usr/bin/env python3
"""ats-poweruser-bench - 10 real power-user cases for codex + kimi.

Each case is a task the author would actually run today against his systems.
Two paths per case:
  A) baseline: raw grep / gh api / curl / cat / find
  B) ats-recon: gmax / ghx / supacrawl / ats-llm-pipe

Token savings = (baseline_tokens - ats_recon_tokens) / baseline_tokens.
Agent answers via codex + kimi (real CLI, real prompts, real context).

Reproducibility: cases reference the author's repo layout. Set
ATS_BENCH_BASE to point at your own projects directory to adapt the
cases; the agent-token-saver cases auto-detect from this script's path.
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

# Auto-detect: this script lives in <BASE>/agent-token-saver/integration/cli/
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]  # agent-token-saver/
_BASE = os.environ.get("ATS_BENCH_BASE", str(_REPO_ROOT.parent))

# 10 power-user cases — all directly contribute to today's systems
CASES: list[dict[str, Any]] = [
    {
        "id": "01_usage_parsing",
        "question": "Where is usage parsing handled in agent-token-saver?",
        "baseline_cmd": ["grep", "-rn", "usage", f"{_BASE}/agent-token-saver/integration"],
        "ats_recon_cmd": ["gmax", "where is usage parsing handled", "--agent"],
        "cwd": f"{_BASE}/agent-token-saver",
    },
    {
        "id": "02_superweb_readme",
        "question": "What does the superweb README say about PGO?",
        "baseline_cmd": ["gh", "api", "repos/Supersynergy/superweb/contents/README.md",
                         "--jq", ".content"],
        "ats_recon_cmd": ["ghx", "read", "Supersynergy/superweb", "README.md"],
        "cwd": f"{_BASE}/superweb",
    },
    {
        "id": "03_chartlab_quantagent",
        "question": "How does chartlab's QuantAgent Durable Object work?",
        "baseline_cmd": ["grep", "-rn", "QuantAgent", f"{_BASE}/chartlab/src"],
        "ats_recon_cmd": ["gmax", "How does the QuantAgent Durable Object work", "--agent"],
        "cwd": f"{_BASE}/chartlab",
    },
    {
        "id": "04_synapse_fts5",
        "question": "Where is FTS5 search implemented in synapse-memory?",
        "baseline_cmd": ["grep", "-rn", r"FTS5|fts5|ultra_search",
                         f"{_BASE}/synapse-memory/crates"],
        "ats_recon_cmd": ["gmax", "Where is FTS5 search implemented", "--agent"],
        "cwd": f"{_BASE}/synapse-memory",
    },
    {
        "id": "05_codex_pro_providers",
        "question": "Which LLM providers does codex-pro support?",
        "baseline_cmd": ["ls", f"{_BASE}/codex-pro/core/providers"],
        "ats_recon_cmd": ["gmax", "Which LLM providers does codex-pro support", "--agent"],
        "cwd": f"{_BASE}/codex-pro",
    },
    {
        "id": "06_token_cfo_pricing",
        "question": "What are the token-cfo pricing tiers?",
        "baseline_cmd": ["cat", f"{_BASE}/token-cfo/token_cfo/pricing.py"],
        "ats_recon_cmd": ["gmax", "What are the token-cfo pricing tiers", "--agent"],
        "cwd": f"{_BASE}/token-cfo",
    },
    {
        "id": "07_psi_schlafzimmer",
        "question": "What is the PSI Sanctuary product ladder?",
        "baseline_cmd": ["cat", f"{_BASE}/presentum/psi-business-strategie.md"],
        "ats_recon_cmd": ["gmax", "What is the PSI Sanctuary product ladder", "--agent"],
        "cwd": f"{_BASE}/presentum",
    },
    {
        "id": "08_ats_hooks",
        "question": "Which hooks does agent-token-saver install?",
        "baseline_cmd": ["ls", f"{_BASE}/agent-token-saver/integration/hooks"],
        "ats_recon_cmd": ["gmax", "Which hooks does agent-token-saver install", "--agent"],
        "cwd": f"{_BASE}/agent-token-saver",
    },
    {
        "id": "09_example_scrape",
        "question": "What is the main heading of example.com?",
        "baseline_cmd": ["curl", "-sL", "https://example.com"],
        "ats_recon_cmd": ["supacrawl", "scrape", "https://example.com",
                          "--format", "markdown"],
        "cwd": "/tmp",
    },
    {
        "id": "10_ats_recon_router",
        "question": "How does ats-recon auto-route between gmax/ghx/supacrawl?",
        "baseline_cmd": ["grep", "-n", r"ats-recon|ats_auto|route",
                         f"{_BASE}/agent-token-saver/integration/cli/agent-token-saver.sh"],
        "ats_recon_cmd": ["gmax", "How does ats-recon auto-route between tools", "--agent"],
        "cwd": f"{_BASE}/agent-token-saver",
    },
]

AGENTS: list[tuple[str, list[str], str]] = [
    # name, base_cmd, input_mode ("stdin" or "arg")
    ("codex", ["codex", "exec", "--skip-git-repo-check", "-"], "stdin"),
    ("kimi", ["kimi", "--quiet", "--input-format", "text"], "stdin"),
    ("hermes_luna", ["hermes", "-z", "__PROMPT__", "-m",
                     "openai/gpt-5.6-luna", "--cli"], "arg"),
]


@dataclass
class Result:
    agent: str
    case_id: str
    path: str
    wall_s: float
    tool_chars: int
    tool_tokens_est: int
    agent_chars: int
    agent_tokens_est: int
    total_tokens: int
    success: bool
    sample: str


def run_tool(probe: dict[str, Any], path: str) -> tuple[str, float, int, bool]:
    key = f"{path}_cmd"
    cmd = probe[key]
    cwd = probe.get("cwd")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=cwd, check=False,
        )
        wall = time.time() - t0
        out = proc.stdout
        ok = proc.returncode == 0 and len(out) > 0
        return out, round(wall, 3), len(out), ok
    except Exception as e:
        return f"<error: {e}>", 0.0, 0, False


def ask_agent(agent_spec: tuple[str, list[str], str], question: str,
              context: str) -> tuple[str, float, int, bool]:
    agent_name, base_cmd, input_mode = agent_spec
    prompt = (
        f"Question: {question}\n\n"
        f"Context (tool output, may be truncated):\n{context[:8000]}\n\n"
        f"Answer in 2-3 sentences. Be specific and grounded in the context."
    )
    t0 = time.time()
    try:
        if input_mode == "stdin":
            cmd = base_cmd
            proc = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                timeout=180, cwd="/tmp", check=False,
            )
        else:  # arg mode — substitute __PROMPT__ placeholder
            cmd = [prompt if a == "__PROMPT__" else a for a in base_cmd]
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=180, cwd="/tmp", check=False,
            )
        wall = time.time() - t0
        out = proc.stdout.strip()
        ok = proc.returncode == 0 and len(out) > 0
        return out, round(wall, 3), len(out), ok
    except Exception as e:
        return f"<error: {e}>", 0.0, 0, False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--out", type=str, default="/tmp/ats_poweruser_bench.json")
    ap.add_argument("--md", type=str, default="/tmp/ats_poweruser_bench.md")
    args = ap.parse_args()

    # Source kimi env if available so KIMI_API_KEY is set for the kimi agent
    kimi_env = Path.home() / ".config" / "kimi" / "env"
    if kimi_env.exists():
        for line in kimi_env.read_text().splitlines():
            if line.startswith("export KIMI_API_KEY="):
                os.environ["KIMI_API_KEY"] = line.split("=", 1)[1].strip()

    results: list[Result] = []
    print(f"Poweruser bench: {len(AGENTS)} agents x {len(CASES)} cases x 2 paths "
          f"x {args.iter} iter", file=sys.stderr)

    for i in range(args.iter):
        for agent_spec in AGENTS:
            agent_name = agent_spec[0]
            for probe in CASES:
                for path in ("baseline", "ats_recon"):
                    print(f"  [{i+1}] {agent_name} / {probe['id']} / {path}...",
                          file=sys.stderr)
                    tool_out, tool_wall, tool_chars, tool_ok = run_tool(probe, path)
                    agent_out, agent_wall, agent_chars, agent_ok = ask_agent(
                        agent_spec, probe["question"], tool_out
                    )
                    tool_tok = tool_chars // 4
                    agent_tok = agent_chars // 4
                    total = tool_tok + agent_tok
                    r = Result(
                        agent=agent_name,
                        case_id=probe["id"],
                        path=path,
                        wall_s=round(tool_wall + agent_wall, 3),
                        tool_chars=tool_chars,
                        tool_tokens_est=tool_tok,
                        agent_chars=agent_chars,
                        agent_tokens_est=agent_tok,
                        total_tokens=total,
                        success=agent_ok,
                        sample=agent_out[:200].replace("\n", " "),
                    )
                    results.append(r)
                    print(f"    -> tool={tool_tok}t, agent={agent_tok}t, "
                          f"total={total}t, wall={r.wall_s}s "
                          f"({'OK' if r.success else 'FAIL'})", file=sys.stderr)

    # Aggregate per case
    agg: dict[str, dict[str, Any]] = {}
    by_key: dict[str, list[Result]] = {}
    for r in results:
        k = f"{r.case_id}/{r.path}"
        by_key.setdefault(k, []).append(r)
    for k, rs in by_key.items():
        ok = [r for r in rs if r.success]
        agg[k] = {
            "n": len(rs),
            "success_rate": round(len(ok) / len(rs), 2) if rs else 0,
            "wall_s_mean": round(sum(r.wall_s for r in rs) / len(rs), 3) if rs else 0,
            "tool_tokens_mean": int(sum(r.tool_tokens_est for r in rs) / len(rs)) if rs else 0,
            "agent_tokens_mean": int(sum(r.agent_tokens_est for r in rs) / len(rs)) if rs else 0,
            "total_tokens_mean": int(sum(r.total_tokens for r in rs) / len(rs)) if rs else 0,
        }

    # Savings per case
    savings: list[dict[str, Any]] = []
    for c in CASES:
        b = agg.get(f"{c['id']}/baseline")
        a = agg.get(f"{c['id']}/ats_recon")
        if b and a and b["total_tokens_mean"] > 0:
            saved = b["total_tokens_mean"] - a["total_tokens_mean"]
            pct = round(100 * saved / b["total_tokens_mean"], 1)
            savings.append({
                "case_id": c["id"],
                "question": c["question"],
                "baseline_tokens": b["total_tokens_mean"],
                "ats_recon_tokens": a["total_tokens_mean"],
                "saved_tokens": saved,
                "saved_pct": pct,
                "baseline_wall_s": b["wall_s_mean"],
                "ats_recon_wall_s": a["wall_s_mean"],
            })

    # Per-agent savings
    per_agent: dict[str, dict[str, Any]] = {}
    for agent_spec in AGENTS:
        agent_name = agent_spec[0]
        agent_results = [r for r in results if r.agent == agent_name]
        b_tok = sum(r.total_tokens for r in agent_results if r.path == "baseline")
        a_tok = sum(r.total_tokens for r in agent_results if r.path == "ats_recon")
        n = len([r for r in agent_results if r.path == "baseline"])
        per_agent[agent_name] = {
            "n_cases": n,
            "baseline_total_tokens": b_tok,
            "ats_recon_total_tokens": a_tok,
            "saved_tokens": b_tok - a_tok,
            "saved_pct": round(100 * (b_tok - a_tok) / b_tok, 1) if b_tok > 0 else 0,
        }

    Path(args.out).write_text(json.dumps({
        "results": [asdict(r) for r in results],
        "aggregate": agg,
        "savings": savings,
        "per_agent": per_agent,
    }, indent=2))

    # Markdown
    lines = [
        "# ATS Poweruser Benchmark (codex + kimi + hermes_luna, 10 real cases)",
        "",
        "## Per-case token savings",
        "",
        "| Case | Question | Baseline tok | ATS-recon tok | Saved | Saved % | Baseline wall | ATS wall |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in savings:
        lines.append(
            f"| {s['case_id']} | {s['question'][:40]} | {s['baseline_tokens']} | "
            f"{s['ats_recon_tokens']} | {s['saved_tokens']} | {s['saved_pct']}% | "
            f"{s['baseline_wall_s']}s | {s['ats_recon_wall_s']}s |"
        )
    lines.append("")
    lines.append("## Per-agent totals")
    lines.append("")
    lines.append("| Agent | Cases | Baseline tok | ATS-recon tok | Saved | Saved % |")
    lines.append("|---|---|---|---|---|---|")
    for agent_name, stats in per_agent.items():
        lines.append(
            f"| {agent_name} | {stats['n_cases']} | {stats['baseline_total_tokens']} | "
            f"{stats['ats_recon_total_tokens']} | {stats['saved_tokens']} | "
            f"{stats['saved_pct']}% |"
        )
    lines.append("")
    lines.append("## Per-agent/case detail")
    lines.append("")
    lines.append("| Agent | Case | Path | wall_s | tool_tok | agent_tok | total |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r.agent} | {r.case_id} | {r.path} | {r.wall_s} | "
            f"{r.tool_tokens_est} | {r.agent_tokens_est} | {r.total_tokens} |"
        )
    Path(args.md).write_text("\n".join(lines))

    print("\n=== Per-case savings ===")
    for s in savings:
        print(f"  {s['case_id']}: {s['baseline_tokens']} -> {s['ats_recon_tokens']} "
              f"({s['saved_pct']}% saved, {s['ats_recon_wall_s']}s vs {s['baseline_wall_s']}s)")
    print("\n=== Per-agent totals ===")
    for agent_name, stats in per_agent.items():
        print(f"  {agent_name}: {stats['baseline_total_tokens']} -> "
              f"{stats['ats_recon_total_tokens']} ({stats['saved_pct']}% saved)")
    print(f"\nWrote: {args.out} + {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
