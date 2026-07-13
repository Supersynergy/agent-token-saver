#!/usr/bin/env python3
"""Reproducible local + optional live benchmark for the Codex token stack.

Local cases use real installed CLIs/MCP schemas and UTF-8 bytes / 4 as the
same transparent token proxy used by the existing benchmark.  --live-codex
adds two Ponytail A/B tasks and records provider-reported usage.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
STAMP = time.strftime("%Y-%m-%d")
OUT_DIR = ROOT / "data" / "benchmarks"
OUT_JSON = OUT_DIR / f"token-stack-matrix-{STAMP}.json"
OUT_MD = OUT_DIR / f"token-stack-matrix-{STAMP}.md"
ROUTER = HOME / ".codex/skills/agent-token-saver-skill-router/scripts/agent_token_saver.py"
PROMPT_HOOK = HOME / ".codex/hooks/token-stack-prompt.py"
PONYTAIL = HOME / ".claude/skills/superskills/ponytail/SKILL.md"
LIVE_TASKS = [
    {
        "name": "ttl-cache",
        "prompt": (
            "Do not use tools. Return only the answer. Implement a thread-safe Python "
            "in-memory TTL cache with maxsize, get, set, invalidate, monotonic time, "
            "and a compact runnable self-check. No external dependencies."
        ),
        "required": [["maxsize"], ["invalidate"], ["monotonic"], ["assert"], ["lock"]],
    },
    {
        "name": "jsonl-cli-design",
        "prompt": (
            "Do not use tools. Return only the answer. Propose a local CLI that streams "
            "JSONL, filters by key/value, and emits JSONL. Include command syntax, failure "
            "exit codes, streaming behavior, and one test. No implementation."
        ),
        "required": [
            ["exit", "`0`: success", "0: success"],
            ["one line at a time", "line-by-line", "never buffers"],
            ["test"],
            ["jsonl"],
        ],
    },
]


def est_tokens(value: str | bytes | object) -> int:
    if not isinstance(value, (str, bytes)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, str):
        value = value.encode("utf-8", errors="ignore")
    return max(1, len(value) // 4)


def run(
    cmd: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 60,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str, int]:
    started = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        elapsed = round((time.perf_counter() - started) * 1000)
        return result.returncode, result.stdout, result.stderr, elapsed
    except (OSError, subprocess.TimeoutExpired) as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        return 124, "", str(exc), elapsed


@dataclass
class Component:
    name: str
    baseline_tokens: int
    optimized_tokens: int
    baseline_ms: int
    optimized_ms: int
    accepted: bool
    detail: str

    @property
    def saved_pct(self) -> float:
        return round((1 - self.optimized_tokens / self.baseline_tokens) * 100, 2)


def mcp_exchange(
    command: list[str],
    *,
    call: tuple[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int, str]:
    messages: list[dict[str, Any]] = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "token-stack-bench", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    if call:
        messages.append(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": call[0], "arguments": call[1]},
            }
        )
    clean_env = os.environ.copy()
    clean_env.pop("CODEX_THREAD_ID", None)
    clean_env.pop("CODEX_CI", None)
    payload = "\n".join(json.dumps(message) for message in messages) + "\n"
    rc, stdout, stderr, elapsed = run(
        command, cwd=ROOT, timeout=40, input_text=payload, env=clean_env
    )
    responses: dict[int, dict[str, Any]] = {}
    for line in stdout.splitlines():
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed.get("id"), int):
            responses[parsed["id"]] = parsed
    tools = responses.get(2, {}).get("result", {}).get("tools", [])
    result = responses.get(3, {}).get("result")
    error = stderr if rc else ""
    return tools, result, elapsed, error


def headroom_codex_savings() -> dict[str, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", 8787, timeout=8)
    connection.request("GET", "/stats")
    response = connection.getresponse()
    stats = json.loads(response.read())
    connection.close()
    codex = next(
        agent for agent in stats["agent_usage"]["agents"] if agent["agent"] == "codex"
    )
    tool_search = stats["savings"]["by_layer"]["tool_search"]
    return {
        "requests": codex["requests"],
        "before_tokens": codex["before_tokens"],
        "after_tokens": codex["after_tokens"],
        "tokens_saved": codex["tokens_saved"],
        "savings_percent": codex["savings_percent"],
        "tool_search_tokens_saved": tool_search["tokens_saved"],
        "tool_search_requests": tool_search["requests"],
    }


def parse_codex_jsonl(stdout: str) -> tuple[str, dict[str, int]]:
    answer = ""
    usage: dict[str, int] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                answer = item.get("text", "")
        elif event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    return answer, usage


def assess_answer(answer: str, task: dict[str, Any]) -> list[str]:
    lowered = answer.lower()
    return [
        "|".join(group)
        for group in task["required"]
        if not any(term in lowered for term in group)
    ]


def live_ponytail_cases() -> list[dict[str, Any]]:
    policy = PONYTAIL.read_text(errors="ignore")
    cases: list[dict[str, Any]] = []
    for task in LIVE_TASKS:
        arms = {
            "baseline": task["prompt"],
            "ponytail_full": policy + "\n\nTASK\n" + task["prompt"],
        }
        row: dict[str, Any] = {"name": task["name"], "arms": {}}
        for arm, prompt in arms.items():
            cmd = [
                "codex",
                "--disable",
                "hooks",
                "-c",
                'model_reasoning_effort="low"',
                "exec",
                "--skip-git-repo-check",
                "--json",
                "-",
            ]
            rc, stdout, stderr, elapsed = run(cmd, timeout=120, input_text=prompt)
            answer, usage = parse_codex_jsonl(stdout)
            missing = assess_answer(answer, task)
            row["arms"][arm] = {
                "rc": rc,
                "elapsed_ms": elapsed,
                "usage": usage,
                "answer_est_tokens": est_tokens(answer),
                "answer_chars": len(answer),
                "accepted": rc == 0 and not missing,
                "missing": missing,
                "answer": answer,
                "stderr": stderr[-500:],
            }
        cases.append(row)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-codex", action="store_true")
    parser.add_argument("--reuse-live", type=Path)
    args = parser.parse_args()
    components: list[Component] = []

    # Skill catalog vs adaptive router.
    rc, router_out, router_err, router_ms = run(
        [
            "python3",
            str(ROUTER),
            "bench",
            "Benchmark Ponytail context-mode Headroom RTK Tilth",
            "--max",
            "3",
        ]
    )
    router = json.loads(router_out) if rc == 0 else {}
    components.append(
        Component(
            "skill-routing",
            router.get("full_est_tokens", 1),
            router.get("router_est_tokens", 1),
            0,
            router_ms,
            rc == 0 and len(router.get("selected", [])) == 3,
            f"{router.get('skills_scanned', 0)} skills -> 3 selected",
        )
    )

    # Shell output filtering.
    rc_raw, raw_ps, raw_ps_err, raw_ps_ms = run(["ps", "aux"], cwd=HOME, timeout=20)
    rc_rtk, rtk_ps, rtk_ps_err, rtk_ps_ms = run(
        ["rtk", "ps", "aux"], cwd=HOME, timeout=30
    )
    ps_raw_tokens = est_tokens(raw_ps + raw_ps_err)
    ps_rtk_tokens = est_tokens(rtk_ps + rtk_ps_err)
    components.append(
        Component(
            "rtk-ps",
            ps_raw_tokens,
            ps_rtk_tokens,
            raw_ps_ms,
            rtk_ps_ms,
            rc_raw == 0 and rc_rtk == 0,
            "Real process table, raw vs RTK.",
        )
    )

    # Structural read.
    document = ROOT / "README.md"
    raw_document = document.read_text(errors="ignore")
    rc_tilth, tilth_out, tilth_err, tilth_ms = run(
        ["tilth", str(document), "--budget", "800", "--scope", str(ROOT)], timeout=30
    )
    document_raw_tokens = est_tokens(raw_document)
    document_tilth_tokens = est_tokens(tilth_out + tilth_err)
    components.append(
        Component(
            "tilth-read",
            document_raw_tokens,
            document_tilth_tokens,
            0,
            tilth_ms,
            rc_tilth == 0 and bool(tilth_out.strip()),
            "Full README vs 800-token structural budget.",
        )
    )

    # Exact large-log projection, native vs context-mode.
    with tempfile.TemporaryDirectory(prefix=".token-stack-bench-", dir=ROOT) as tmp:
        log_path = Path(tmp) / "events.log"
        expected_ids: list[str] = []
        with log_path.open("w") as handle:
            for index in range(20_000):
                if index % 137 == 0:
                    event_id = f"E{index:05d}"
                    expected_ids.append(event_id)
                    handle.write(
                        f"2026-07-13T12:00:00Z ERROR id={event_id} service=api code=500 request failed\n"
                    )
                else:
                    handle.write(
                        f"2026-07-13T12:00:00Z INFO id=I{index:05d} service=api code=200 ok\n"
                    )
        raw_log = log_path.read_text()
        log_raw_tokens = est_tokens(raw_log)
        started = time.perf_counter()
        errors = [line for line in raw_log.splitlines() if " ERROR " in line]
        native_summary = f"errors={len(errors)}\n" + "\n".join(errors[-10:]) + "\n"
        native_ms = round((time.perf_counter() - started) * 1000)
        native_tokens = est_tokens(native_summary)
        native_ok = (
            f"errors={len(expected_ids)}" in native_summary
            and all(event_id in native_summary for event_id in expected_ids[-10:])
        )

        js_code = (
            "const e=FILE_CONTENT.split('\\n').filter(x=>x.includes(' ERROR '));"
            "console.log('errors='+e.length);console.log(e.slice(-10).join('\\n'));"
        )
        ctx_tools, ctx_result, ctx_ms, ctx_error = mcp_exchange(
            ["context-mode"],
            call=(
                "ctx_execute_file",
                {"path": str(log_path), "language": "javascript", "code": js_code},
            ),
        )
        ctx_result = ctx_result or {"error": ctx_error}
        ctx_text = "\n".join(
            item.get("text", "")
            for item in ctx_result.get("content", [])
            if item.get("type") == "text"
        )
        context_tokens = est_tokens(ctx_result)
        context_ok = (
            not ctx_result.get("isError")
            and f"errors={len(expected_ids)}" in ctx_text
            and all(event_id in ctx_text for event_id in expected_ids[-10:])
        )
        components.append(
            Component(
                "native-log-projection",
                log_raw_tokens,
                native_tokens,
                0,
                native_ms,
                native_ok,
                "20k-line log -> exact error count + last 10 errors.",
            )
        )
        components.append(
            Component(
                "context-mode-log",
                log_raw_tokens,
                context_tokens,
                0,
                ctx_ms,
                context_ok,
                "Same exact oracle through ctx_execute_file; excludes schema overhead.",
            )
        )

    # Real MCP schemas, not synthetic proxies.
    tilth_tools, _, tilth_schema_ms, tilth_schema_error = mcp_exchange(
        ["tilth", "--mcp", "--budget", "4000"]
    )
    if not ctx_tools:
        ctx_tools, _, _, _ = mcp_exchange(["context-mode"])
    tilth_schema_tokens = est_tokens(tilth_tools)
    context_schema_tokens = est_tokens(ctx_tools)

    # Current compact prompt hook cost.
    hook_event = json.dumps(
        {
            "prompt": "Benchmark Ponytail context-mode Headroom RTK Tilth",
            "session_id": "token-stack-benchmark",
        }
    )
    rc_hook, hook_out, hook_err, hook_ms = run(
        ["python3", str(PROMPT_HOOK)], input_text=hook_event, timeout=10
    )
    hook_tokens = est_tokens(hook_out + hook_err)

    # Headroom can remain an optional provider/proxy, but it is not a Lean
    # profile component or MCP. Its observations are not applied to profile totals.
    headroom = {
        "counted_in_profiles": False,
        "requests": 0,
        "before_tokens": 0,
        "after_tokens": 0,
        "tokens_saved": 0,
        "savings_percent": 0.0,
        "tool_search_tokens_saved": 0,
        "tool_search_requests": 0,
    }
    headroom_ratio = 1.0
    ponytail_skill_tokens = est_tokens(PONYTAIL.read_text(errors="ignore"))
    live = live_ponytail_cases() if args.live_codex else []
    if args.reuse_live:
        previous = json.loads(args.reuse_live.read_text())
        live = previous.get("ponytail", {}).get("live_cases", [])
        tasks_by_name = {task["name"]: task for task in LIVE_TASKS}
        for case in live:
            task = tasks_by_name[case["name"]]
            for arm in case["arms"].values():
                missing = assess_answer(arm.get("answer", ""), task)
                arm["missing"] = missing
                arm["accepted"] = arm.get("rc") == 0 and not missing
    baseline_output_tokens = 0
    ponytail_output_tokens = 0
    baseline_live_accepted = True
    ponytail_live_accepted = True
    if live:
        baseline_output_tokens = round(
            sum(case["arms"]["baseline"]["usage"].get("output_tokens", 0) for case in live)
            / len(live)
        )
        ponytail_output_tokens = round(
            sum(case["arms"]["ponytail_full"]["usage"].get("output_tokens", 0) for case in live)
            / len(live)
        )
        baseline_live_accepted = all(case["arms"]["baseline"]["accepted"] for case in live)
        ponytail_live_accepted = all(case["arms"]["ponytail_full"]["accepted"] for case in live)

    raw_catalog = components[0].baseline_tokens
    routed_catalog = components[0].optimized_tokens
    raw_total = raw_catalog + ps_raw_tokens + document_raw_tokens + log_raw_tokens
    current_input = hook_tokens + ps_rtk_tokens + document_tilth_tokens + native_tokens + tilth_schema_tokens
    cli_input = routed_catalog + ps_rtk_tokens + document_tilth_tokens + native_tokens
    context_input = routed_catalog + ps_rtk_tokens + document_tilth_tokens + context_tokens + context_schema_tokens
    max_input = (
        hook_tokens
        + ps_rtk_tokens
        + document_tilth_tokens
        + context_tokens
        + tilth_schema_tokens
        + context_schema_tokens
        + ponytail_skill_tokens
    )

    def matrix_row(
        name: str,
        input_tokens: int,
        output_tokens: int,
        *,
        apply_headroom: bool,
        accepted: bool,
        note: str,
    ) -> dict[str, Any]:
        provider_input = round(input_tokens * headroom_ratio) if apply_headroom else input_tokens
        total = provider_input + output_tokens
        return {
            "name": name,
            "workload_input_tokens": input_tokens,
            "provider_input_tokens": provider_input,
            "output_tokens": output_tokens,
            "total_tokens": total,
            "accepted": accepted,
            "cost_index_vs_none": 0.0,
            "note": note,
        }

    all_components_ok = all(component.accepted for component in components)
    matrix = [
        matrix_row(
            "none/raw",
            raw_total,
            baseline_output_tokens,
            apply_headroom=False,
            accepted=all_components_ok and baseline_live_accepted,
            note="Full skill catalog + raw shell/file/log; no schema overhead.",
        ),
        matrix_row(
            "cli-selective",
            cli_input,
            baseline_output_tokens,
            apply_headroom=False,
            accepted=all_components_ok and baseline_live_accepted,
            note="Router + RTK + Tilth CLI + native projection; zero MCP schema.",
        ),
        matrix_row(
            "current-lean",
            current_input,
            baseline_output_tokens,
            apply_headroom=False,
            accepted=all_components_ok and baseline_live_accepted and rc_hook == 0,
            note="Prompt hook + RTK + Tilth MCP + native projection; no Headroom.",
        ),
        matrix_row(
            "context-on-demand",
            context_input,
            baseline_output_tokens,
            apply_headroom=False,
            accepted=all_components_ok and baseline_live_accepted,
            note="Router + RTK + Tilth CLI + context-mode schema/call; no Headroom.",
        ),
        matrix_row(
            "max-all+ponytail",
            max_input,
            ponytail_output_tokens,
            apply_headroom=False,
            accepted=all_components_ok and ponytail_live_accepted,
            note="Current + context-mode MCP + full Ponytail skill; cold-schema cost.",
        ),
    ]
    none_total = matrix[0]["total_tokens"] or 1
    for row in matrix:
        row["cost_index_vs_none"] = round(row["total_tokens"] / none_total * 100, 2)
    accepted_matrix = sorted(
        (row for row in matrix if row["accepted"]), key=lambda row: row["total_tokens"]
    )

    payload = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "method": "local real CLIs/MCP schemas; bytes/4 token proxy; optional Codex provider usage for Ponytail A/B",
        "versions": {
            "context_mode": "1.0.169",
            "headroom": "0.31.0",
            "rtk": "0.43.0",
            "tilth": "0.9.0",
            "codex": "0.144.0-alpha.4",
        },
        "headroom_codex_observed": headroom,
        "schemas": {
            "tilth": {"tools": len(tilth_tools), "tokens": tilth_schema_tokens, "ms": tilth_schema_ms, "error": tilth_schema_error},
            "context_mode": {"tools": len(ctx_tools), "tokens": context_schema_tokens},
        },
        "ponytail": {
            "type": "behavior/output shaper skill, not a lossless compressor",
            "full_skill_tokens": ponytail_skill_tokens,
            "live_cases": live,
            "baseline_avg_output_tokens": baseline_output_tokens,
            "ponytail_avg_output_tokens": ponytail_output_tokens,
        },
        "components": [
            {**asdict(component), "saved_pct": component.saved_pct}
            for component in components
        ],
        "matrix": matrix,
        "top3": [row["name"] for row in accepted_matrix[:3]],
        "monetary_cost": {
            "marginal_eur": 0,
            "reason": "Codex uses subscription/OAuth quota and gpt-5.6-sol has no public list price in Headroom stats.",
            "comparison": "cost_index_vs_none is the measured token/quota index; none/raw = 100.",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    lines = [
        f"# Token Stack Matrix — {STAMP}",
        "",
        "Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.",
        "",
        "## Stack ranking",
        "",
        "| Stack | Input tok | Provider input | Output tok | Total | Cost index | Accepted |",
        "|---|---:|---:|---:|---:|---:|:--:|",
    ]
    for row in sorted(matrix, key=lambda item: item["total_tokens"]):
        lines.append(
            f"| {row['name']} | {row['workload_input_tokens']:,} | {row['provider_input_tokens']:,} | "
            f"{row['output_tokens']:,} | {row['total_tokens']:,} | {row['cost_index_vs_none']:.2f} | "
            f"{'yes' if row['accepted'] else 'no'} |"
        )
    lines += [
        "",
        "## Components",
        "",
        "| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |",
        "|---|---:|---:|---:|---:|---:|:--:|",
    ]
    for component in components:
        lines.append(
            f"| {component.name} | {component.baseline_tokens:,} | {component.optimized_tokens:,} | "
            f"{component.saved_pct:.2f}% | {component.baseline_ms} | {component.optimized_ms} | "
            f"{'yes' if component.accepted else 'no'} |"
        )
    lines += [
        "",
        "## Fixed overhead and observed runtime",
        "",
        f"- Tilth MCP: {len(tilth_tools)} tools / {tilth_schema_tokens:,} tokens.",
        f"- context-mode MCP: {len(ctx_tools)} tools / {context_schema_tokens:,} tokens.",
        f"- Ponytail full skill: {ponytail_skill_tokens:,} input tokens.",
        "- Headroom: optional provider/proxy; excluded from Lean totals and never loaded as MCP.",
        "- Monetary marginal cost: EUR 0 inside the current subscription; cost index measures quota/token load.",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- **{row['name']}**: {row['note']}" for row in matrix)
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(OUT_MD)
    print(json.dumps({"top3": payload["top3"], "matrix": matrix, "schemas": payload["schemas"], "headroom": headroom, "ponytail": payload["ponytail"]}, ensure_ascii=False, indent=2))
    return 0 if accepted_matrix else 1


if __name__ == "__main__":
    raise SystemExit(main())
