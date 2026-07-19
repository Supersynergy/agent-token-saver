#!/usr/bin/env python3
"""Run a fresh-home Codex A/B with the Headroom proxy off/on on one oracle task.

Both arms disable hooks and rules; the only variable is whether Codex routes
through the local Headroom proxy. The proxy arm runs FIRST so any provider
prompt-cache reuse favors the direct arm — a measured Headroom win survives
that bias. Provider-reported usage is authoritative; the proxy /stats delta is
supporting evidence only.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import codex_provider_ab as base  # noqa: E402

DEFAULT_OUT = ROOT / "data" / "benchmarks" / f"headroom-ab-{time.strftime('%Y-%m-%d')}"
DEFAULT_TASK = "large-git-diff"

PROXY_CONFIG_TEMPLATE = """model_provider = "headroom"

[model_providers.headroom]
name = "OpenAI via Headroom proxy"
base_url = "http://127.0.0.1:{port}/v1"
supports_websockets = true
"""


def proxy_get(port: int, path: str) -> dict[str, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    connection.request("GET", path)
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    return payload


def proxy_snapshot(port: int) -> dict[str, Any]:
    stats = proxy_get(port, "/stats")
    savings = stats.get("savings", {})
    return {
        "requests_total": stats.get("requests", {}).get("total", 0),
        "requests_by_provider": stats.get("requests", {}).get("by_provider", {}),
        "savings_total_tokens": savings.get("total_tokens", 0),
        "savings_by_layer": savings.get("by_layer", {}),
    }


def prepare_home(home: Path, auth: Path, arm: str, port: int) -> Path:
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True)
    target_auth = codex_home / "auth.json"
    shutil.copy2(auth, target_auth)
    target_auth.chmod(0o600)
    if arm == "on":
        (codex_home / "config.toml").write_text(PROXY_CONFIG_TEMPLATE.format(port=port))
    return codex_home


def run_arm(
    task: base.Task,
    arm: str,
    *,
    auth: Path,
    fixture: Path,
    model: str,
    timeout: int,
    port: int,
    home_root: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    home = home_root / f"home-{task.name}-{arm}"
    codex_home = prepare_home(home, auth, arm, port)
    command = [
        "codex",
        "--disable",
        "hooks",
        "exec",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "-c",
        'model_reasoning_effort="low"',
        "-C",
        str(fixture),
        "--json",
        "-",
    ]
    run_env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(codex_home),
    }
    started = time.monotonic()
    try:
        result = base.run(command, input=task.prompt, timeout=timeout, env=run_env)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        result = subprocess.CompletedProcess(command, 124, error.stdout or "", error.stderr or "")
        timed_out = True
    elapsed_ms = round((time.monotonic() - started) * 1000)
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    answer, raw_usage, commands = base.parse_codex_jsonl(stdout)
    usage = base.normalize_usage(raw_usage)
    accepted = (
        result.returncode == 0
        and answer == task.expected
        and base.command_oracle(commands, task.command_terms)
        and usage["total_tokens"] > 0
    )
    raw_path = artifact_root / f"{task.name}-headroom-{arm}.jsonl"
    raw_path.write_text(stdout)
    return {
        "arm": arm,
        "command": " ".join(command),
        "return_code": result.returncode,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "usage": usage,
        "answer": answer,
        "commands": commands,
        "accepted": accepted,
        "oracle": {
            "exact_answer": answer == task.expected,
            "command_terms": base.command_oracle(commands, task.command_terms),
            "provider_usage": usage["total_tokens"] > 0,
        },
        "stderr_tail": stderr[-1000:],
        "raw_jsonl": str(raw_path),
    }


def write_ledgers(out_dir: Path, arms: dict[str, dict[str, Any]]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for arm, row in arms.items():
        for fmt, suffix in (("json-compact", "json"), ("markdown", "md")):
            ledger_path = out_dir / f"ledger-headroom-{arm}.{suffix}"
            result = base.run(
                [
                    "agent-token-ledger",
                    "--usage",
                    f"headroom-{arm}={row['raw_jsonl']}",
                    "--provider",
                    "openai",
                    "--format",
                    fmt,
                    "--out",
                    str(ledger_path),
                ]
            )
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or f"ledger failed for arm {arm}")
            paths[f"{arm}-{suffix}"] = str(ledger_path)
    return paths


def summarize(task: base.Task, arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    off = arms["off"]["usage"]
    on = arms["on"]["usage"]
    accepted = arms["off"]["accepted"] and arms["on"]["accepted"]
    return {
        "name": task.name,
        "prompt": task.prompt,
        "expected": task.expected,
        "accepted": accepted,
        "arms": arms,
        "provider_delta": {
            "input_tokens": on["input_tokens"] - off["input_tokens"],
            "uncached_input_tokens": on["uncached_input_tokens"] - off["uncached_input_tokens"],
            "output_tokens": on["output_tokens"] - off["output_tokens"],
            "total_tokens": on["total_tokens"] - off["total_tokens"],
            "input_saved_percent": (
                base.percent_saved(off["input_tokens"], on["input_tokens"]) if accepted else None
            ),
            "uncached_input_saved_percent": (
                base.percent_saved(off["uncached_input_tokens"], on["uncached_input_tokens"])
                if accepted
                else None
            ),
            "total_saved_percent": (
                base.percent_saved(off["total_tokens"], on["total_tokens"]) if accepted else None
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["task"]
    delta = summary["provider_delta"]
    proxy = payload["proxy_delta"]

    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.2f}%"

    lines = [
        f"# Headroom proxy A/B — {payload['date']}",
        "",
        "Fresh HOME per arm; same model, fixture and oracle. Both arms disable hooks and",
        "rules; the only variable is routing through the local Headroom proxy. The proxy",
        "arm ran first, so provider prompt-cache reuse favors the direct arm.",
        "",
        f"- Task: `{summary['name']}`, expected `{summary['expected']}`",
        f"- Model: `{payload['model']}`, codex `{payload['codex_version']}`, headroom `{payload['headroom_version']}`",
        "",
        "| Arm | Input | Cached | Uncached | Output | Total | Elapsed | Accepted |",
        "|---|---:|---:|---:|---:|---:|---:|:--:|",
    ]
    for arm_name in ("off", "on"):
        arm = summary["arms"][arm_name]
        usage = arm["usage"]
        lines.append(
            f"| headroom-{arm_name} | {usage['input_tokens']:,} | {usage['cached_input_tokens']:,} | "
            f"{usage['uncached_input_tokens']:,} | {usage['output_tokens']:,} | "
            f"{usage['total_tokens']:,} | {arm['elapsed_ms']:,} ms | {'yes' if arm['accepted'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Delta (on vs off)",
            "",
            f"- Input saved: **{pct(delta['input_saved_percent'])}** ({delta['input_tokens']:+,})",
            f"- Uncached input saved: **{pct(delta['uncached_input_saved_percent'])}** ({delta['uncached_input_tokens']:+,})",
            f"- Total saved: **{pct(delta['total_saved_percent'])}** ({delta['total_tokens']:+,})",
            f"- Oracle accepted in both arms: **{'yes' if summary['accepted'] else 'no'}**",
            "",
            "## Proxy-side evidence (supporting only)",
            "",
            f"- Proxy requests during on-arm: **{proxy['requests_total']}**",
            f"- Proxy-claimed tokens saved during on-arm: **{proxy['savings_total_tokens']:,}**",
            "",
            "A failed oracle invalidates the saving claim. One run per arm is fresh",
            "evidence, not a statistical confidence interval; repeat ABBA before changing",
            "defaults.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live", action="store_true", help="required acknowledgement for provider calls"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--auth", type=Path, default=Path.home() / ".codex" / "auth.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--task", choices=tuple(t.name for t in base.TASKS), default=DEFAULT_TASK)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required because this command consumes provider quota")
    try:
        auth = base.safe_auth(args.auth)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    try:
        health = proxy_get(args.port, "/health")
    except OSError:
        parser.error(
            f"Headroom proxy not reachable on 127.0.0.1:{args.port}; start it with: headroom proxy"
        )
    task = next(t for t in base.TASKS if t.name == args.task)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_root = args.out_dir / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ats-headroom-ab-") as temporary:
        temporary_root = Path(temporary)
        fixture = temporary_root / "fixture"
        fixture_head = base.create_fixture(fixture)
        home_root = temporary_root / "homes"
        home_root.mkdir()
        before = proxy_snapshot(args.port)
        arms: dict[str, dict[str, Any]] = {}
        for arm in ("on", "off"):
            arms[arm] = run_arm(
                task,
                arm,
                auth=auth,
                fixture=fixture,
                model=args.model,
                timeout=args.timeout,
                port=args.port,
                home_root=home_root,
                artifact_root=run_root,
            )
            if arm == "on":
                after_on = proxy_snapshot(args.port)
    proxy_delta = {
        "requests_total": after_on["requests_total"] - before["requests_total"],
        "savings_total_tokens": after_on["savings_total_tokens"] - before["savings_total_tokens"],
        "before": before,
        "after_on_arm": after_on,
    }
    summary = summarize(task, arms)
    payload = {
        "schema_version": 1,
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "codex_version": base.run(["codex", "--version"]).stdout.strip(),
        "headroom_version": str(health.get("version", "unknown")),
        "model": args.model,
        "fixture_head": fixture_head,
        "order": "on first, then off; fresh HOME per arm; provider cache reuse favors off",
        "task": summary,
        "proxy_delta": proxy_delta,
    }
    payload["ledgers"] = write_ledgers(args.out_dir, arms)
    json_path = args.out_dir / "result.json"
    markdown_path = args.out_dir / "result.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    markdown_path.write_text(render_markdown(payload))
    print(markdown_path)
    print(
        json.dumps(
            {
                "accepted": summary["accepted"],
                "provider_delta": summary["provider_delta"],
                "proxy_delta": {
                    k: proxy_delta[k] for k in ("requests_total", "savings_total_tokens")
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
