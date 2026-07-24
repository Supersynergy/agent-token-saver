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
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
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
    cost_usd: float = 0.0


# Each agent: (name, command, env_override).
# "__PROMPT__" in the command switches that lane from stdin to arg mode.
# Lane audit 2026-07-24: kimi-k3 API key dead (401 at api.moonshot.ai) →
# kimi runs via the kimi CLI (Coding Plan OAuth) and via ggcoder --provider
# moonshot (exact usage in JSON events). OpenRouter key is valid but nearly
# out of credits ($0.39) → paid lanes 402; :free models cost $0 and only
# need the valid key (current list: openrouter.ai/api/v1/models, id *:free).
AGENTS: list[tuple[str, list[str], dict[str, str]]] = [
    ("codex", ["codex", "exec", "--skip-git-repo-check", "-"], {}),
    # kimi CLI lane removed 2026-07-24: kimi-awake reads KIMI_API_KEY, which is
    # dead (401 at api.moonshot.ai). Re-add when the key is renewed. Until
    # then ggcoder_kimi (own OAuth) is the working kimi lane.
    ("ggcoder_kimi", ["ggcoder", "--json", "--provider", "moonshot", "__PROMPT__"], {}),
    # paid reference lane (needs OpenRouter credits; honest 402 without)
    ("hermes_luna", ["hermes", "-z", "-", "-m", "openai/gpt-5.6-luna", "--cli"], {}),
    # $0 lanes via OpenRouter :free (rate-limited at peak times — honest 429)
    (
        "hermes_free_gemma4",
        [
            "hermes",
            "-z",
            "-",
            "--provider",
            "openrouter",
            "-m",
            "google/gemma-4-31b-it:free",
            "--cli",
        ],
        {},
    ),
    (
        "hermes_free_ling",
        [
            "hermes",
            "-z",
            "-",
            "--provider",
            "openrouter",
            "-m",
            "inclusionai/ling-3.0-flash:free",
            "--cli",
        ],
        {},
    ),
    # antigravity: Google's VSCode-fork GUI IDE. No headless CLI. Launch via
    # `open -a`. Availability = .app bundle exists. Non-interactive — recorded
    # as success=False with sample="<gui-launch: antigravity>".
    ("antigravity", ["open", "-a", "Antigravity"], {}),
    # Local lanes — no API key, no billing, available whenever installed.
    ("claude", ["claude", "-p"], {}),
    ("ollama_phi4", ["ollama", "run", "phi4-reasoning:plus"], {}),
    ("ollama_dolphin3", ["ollama", "run", "dolphin3:8b"], {}),
]

# stdout error signatures that mean the agent did NOT answer, even with
# exit code 0 (hosted CLIs print HTTP errors to stdout and exit clean).
ERROR_MARKERS = (
    "http 401",
    "http 402",
    "http 403",
    "http 429",
    "http 500",
    "billing or credits",
    "credits exhausted",
    "api key appears to be invalid",
    "invalid api key",
    "rate limit",
    "quota exceeded",
)


def _looks_like_error(out: str) -> bool:
    head = out[:400].lower()
    return any(marker in head for marker in ERROR_MARKERS)


def _parse_ggcoder_json(out: str) -> tuple[str, int]:
    """Collect text_delta events into the answer; return (answer, output_tokens)."""
    answer, out_tokens = [], 0
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "text_delta":
            answer.append(ev.get("text", ""))
        elif ev.get("type") == "agent_done":
            out_tokens = int(ev.get("totalUsage", {}).get("outputTokens", 0))
    return "".join(answer), out_tokens


def _read_usage_cost(path: Path) -> float:
    """estimated_cost_usd from a hermes --usage-file; 0.0 when absent."""
    try:
        cost = json.loads(path.read_text()).get("estimated_cost_usd")
        return float(cost) if cost else 0.0
    except Exception:
        return 0.0


_ANTIGRAVITY_APP_BUNDLE = "/Applications/Antigravity.app"


def _antigravity_available() -> bool:
    return Path(_ANTIGRAVITY_APP_BUNDLE).is_dir()


# The probe: a realistic extraction task
EXTRACT_PROMPT = (
    "Extract product information from this text:\n\n"
    "'Acme Widget Pro — $42.99 — The best widget on the market. "
    "Features: durable, lightweight, eco-friendly. In stock.'\n\n"
    "Return JSON only: {name, price, features:[], in_stock:bool}"
)


def run_agent(
    agent: tuple[str, list[str], dict[str, str]], iter_idx: int, timeout: int = 120
) -> SwarmResult:
    name, cmd, env_override = agent
    env = os.environ.copy()
    env.update(env_override)

    # antigravity: GUI IDE, no headless stdin/stdout. Launch the app and
    # record a marker. success=False, json_valid=False — honest.
    if cmd[:2] == ["open", "-a"] and "Antigravity" in cmd:
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd="/tmp",
                env=env,
                check=False,
            )
            wall = time.time() - t0
            return SwarmResult(
                agent=name,
                iter_idx=iter_idx,
                wall_s=round(wall, 3),
                chars=0,
                tokens_est=0,
                exit_code=proc.returncode,
                success=False,
                json_valid=False,
                sample="<gui-launch: antigravity>",
            )
        except Exception as e:
            return SwarmResult(name, iter_idx, 0.0, 0, 0, -1, False, False, f"<gui-error: {e}>")

    # arg mode: "__PROMPT__" placeholder gets the prompt, stdin stays empty.
    arg_mode = any("__PROMPT__" in part for part in cmd)
    if arg_mode:
        cmd = [part.replace("__PROMPT__", EXTRACT_PROMPT) for part in cmd]
    # hermes lanes: capture per-call cost via --usage-file.
    usage_file: Path | None = None
    if cmd[0] == "hermes":
        usage_file = Path(f"/tmp/ats-swarm-usage-{name}-{iter_idx}-{os.getpid()}.json")
        cmd = [*cmd, "--usage-file", str(usage_file)]

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=None if arg_mode else EXTRACT_PROMPT,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env=env,
            check=False,
        )
        wall = time.time() - t0
        out = proc.stdout.strip()
        cost = 0.0
        if usage_file is not None:
            cost = _read_usage_cost(usage_file)
            usage_file.unlink(missing_ok=True)
        if name.startswith("ggcoder"):
            answer, out_tokens = _parse_ggcoder_json(out)
            if answer:
                out = answer
        chars = len(out)
        tokens = chars // 4
        # exit 0 + non-empty is not enough: hosted CLIs print HTTP/billing
        # errors to stdout and exit clean — that is a failure, not an answer.
        success = proc.returncode == 0 and chars > 0 and not _looks_like_error(out)

        # Check JSON validity (agents may wrap in fences)
        json_valid = False
        try:
            # Strip code fences if present
            cleaned = out
            if cleaned.startswith("```"):
                cleaned = "\n".join(
                    line for line in cleaned.split("\n") if not line.startswith("```")
                )
            # Find first { ... } block
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                json.loads(cleaned[start : end + 1])
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
            cost_usd=round(cost, 6),
        )
    except subprocess.TimeoutExpired:
        return SwarmResult(name, iter_idx, float(timeout), 0, 0, -1, False, False, "<timeout>")
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
            "cost_usd_sum": round(sum(r.cost_usd for r in rs), 6),
        }
    return agg


def markdown_table(agg: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| Agent | n | success | json_valid | wall_s | chars | tokens~ | cost_usd |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for agent, s in agg.items():
        lines.append(
            f"| {agent} | {s['n']} | {s['success_rate']} | {s['json_valid_rate']} | "
            f"{s['wall_s_mean']} | {s['chars_mean']} | {s['tokens_est_mean']} | "
            f"{s.get('cost_usd_sum', 0.0)} |"
        )
    total = sum(s.get("cost_usd_sum", 0.0) for s in agg.values())
    free_ok = sum(
        s["n"] * s["success_rate"]
        for a, s in agg.items()
        if s.get("cost_usd_sum", 0.0) == 0 and a != "antigravity"
    )
    lines.append("")
    lines.append(
        f"Total credits spent: ${total:.4f} — successful $0-lane calls: {int(free_ok)} "
        "(subscription/local/free lanes; each would cost real credits on a paid lane)"
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=2)
    ap.add_argument("--out", type=str, default="/tmp/ats_swarm_bench.json")
    ap.add_argument("--md", type=str, default="/tmp/ats_swarm_bench.md")
    ap.add_argument("--only", type=str, default=None)
    ap.add_argument("--timeout", type=int, default=120, help="per-call timeout in seconds")
    ap.add_argument("--workers", type=int, default=0, help="parallel workers (0 = min(8, calls))")
    ap.add_argument("--sequential", action="store_true", help="disable parallel execution")
    args = ap.parse_args()

    agents = [a for a in AGENTS if args.only is None or args.only in a[0]]
    # Filter antigravity by app-bundle presence (GUI, not on PATH).
    agents = [a for a in agents if a[0] != "antigravity" or _antigravity_available()]
    # Skip CLIs that are not installed — a swarm bench should report the
    # missing lane once, not burn a slot on FileNotFoundError per iteration.
    missing = [a[0] for a in agents if a[0] != "antigravity" and not shutil.which(a[1][0])]
    if missing:
        print(f"skipping (not on PATH): {', '.join(missing)}", file=sys.stderr)
        agents = [a for a in agents if a[0] not in missing]
    if not agents:
        print(f"No agents match --only={args.only!r}", file=sys.stderr)
        return 1

    print(
        f"Running {len(agents)} agents x {args.iter} iter = {len(agents) * args.iter} calls...",
        file=sys.stderr,
    )
    calls = [(i, agent) for i in range(args.iter) for agent in agents]
    results: list[SwarmResult] = []
    if args.sequential:
        for i, agent in calls:
            print(f"  [{i + 1}/{args.iter}] {agent[0]}...", file=sys.stderr)
            results.append(run_agent(agent, i, args.timeout))
    else:
        # A swarm is parallel by definition: wall-clock = slowest agent,
        # not the sum. Threads are fine — the work is subprocess-bound.
        workers = args.workers or min(8, len(calls))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(run_agent, agent, i, args.timeout): (i, agent[0]) for i, agent in calls
            }
            for future in as_completed(futures):
                r = future.result()
                results.append(r)
                print(
                    f"  {r.agent} [{r.iter_idx + 1}/{args.iter}] -> {r.wall_s}s, "
                    f"{r.chars} chars, ok={r.success}",
                    file=sys.stderr,
                )
    # Deterministic report order regardless of completion order.
    order = {name: idx for idx, (name, _, _) in enumerate(AGENTS)}
    results.sort(key=lambda r: (order.get(r.agent, 99), r.iter_idx))

    agg = aggregate(results)
    Path(args.out).write_text(
        json.dumps({"results": [asdict(r) for r in results], "aggregate": agg}, indent=2)
    )
    Path(args.md).write_text(markdown_table(agg))
    print("\n=== Swarm Aggregate ===")
    print(markdown_table(agg))
    print(f"\nWrote: {args.out} + {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
