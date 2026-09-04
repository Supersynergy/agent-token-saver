#!/usr/bin/env python3
"""Run fresh-home Codex baseline/Lean A/B tasks with provider usage gates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cache_economics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_agent_token_saver.py"
DEFAULT_OUT = ROOT / "data" / "benchmarks" / f"codex-provider-ab-{time.strftime('%Y-%m-%d')}"


@dataclass(frozen=True)
class Task:
    name: str
    prompt: str
    expected: str
    command_terms: tuple[str, ...]


TASKS = (
    Task(
        "process-table",
        (
            "Minimize token/context bloat. Inspect the full current process table with a ps "
            "shell command. If its output contains both PID and COMMAND headings, reply exactly "
            "ATS_PS_OK and nothing else."
        ),
        "ATS_PS_OK",
        ("ps",),
    ),
    Task(
        "large-git-diff",
        (
            "Minimize token/context bloat. Inspect the repository's full uncommitted change with "
            "git diff. Confirm exactly 6000 removed lines, 6000 added lines, and the added marker "
            "FIXED-06000. If all are true, reply exactly ATS_DIFF_OK and nothing else."
        ),
        "ATS_DIFF_OK",
        ("git diff",),
    ),
    Task(
        "git-history",
        (
            "Minimize token/context bloat. Inspect the repository history with git log. Confirm "
            "there are exactly 121 commits and the oldest subject is ATS seed. Compute the count "
            "and oldest subject inside the shell command before output reaches the model. If both "
            "are true, reply exactly ATS_HISTORY_OK and nothing else."
        ),
        "ATS_HISTORY_OK",
        ("git log",),
    ),
)


def safe_auth(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    metadata = resolved.stat()
    if not resolved.is_file() or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise ValueError("auth file must be a private regular file owned by the current user")
    return resolved


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, **kwargs)


def create_fixture(path: Path) -> str:
    path.mkdir(parents=True)
    bin_dir = path / "bin"
    bin_dir.mkdir()
    fake_ps = bin_dir / "ps"
    fake_ps.write_text(
        "#!/usr/bin/env python3\n"
        "print('USER PID %CPU %MEM VSZ RSS TT STAT STARTED TIME COMMAND')\n"
        "for index in range(1, 901):\n"
        "    marker = 'critical-worker' if index == 900 else 'fixture-worker'\n"
        "    print(f'user {1000 + index} 0.0 0.1 1000 100 ?? S 00:00 0:00 {marker}-{index:04d}')\n"
    )
    fake_ps.chmod(0o755)
    commands = (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "fixture@example.invalid"],
        ["git", "config", "user.name", "ATS Fixture"],
    )
    for command in commands:
        result = run(command, cwd=path)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "fixture git setup failed")
    payload = path / "payload.txt"
    history = path / "history.txt"
    payload.write_text("".join(f"ORIGINAL-{index:05d}\n" for index in range(1, 6001)))
    history.write_text("seed\n")
    result = run(["git", "add", "payload.txt", "history.txt"], cwd=path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    result = run(["git", "commit", "-q", "-m", "ATS seed"], cwd=path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    for index in range(1, 121):
        history.write_text(history.read_text() + f"history-{index:03d}\n")
        result = run(["git", "add", "history.txt"], cwd=path)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        result = run(["git", "commit", "-q", "-m", f"ATS history {index:03d}"], cwd=path)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
    payload.write_text("".join(f"FIXED-{index:05d}\n" for index in range(1, 6001)))
    result = run(["git", "rev-parse", "HEAD"], cwd=path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def parse_codex_jsonl(text: str) -> tuple[str, dict[str, int], list[str]]:
    answer = ""
    usage: dict[str, int] = {}
    commands: list[str] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "item.completed":
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            if item.get("type") == "agent_message":
                answer = str(item.get("text") or "")
            if "command" in str(item.get("type") or ""):
                command = item.get("command") or item.get("text")
                if isinstance(command, str):
                    commands.append(command)
        elif event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = {key: int(value or 0) for key, value in event["usage"].items()}
    return answer.strip(), usage, commands


def normalize_usage(usage: dict[str, int]) -> dict[str, int]:
    input_tokens = int(usage.get("input_tokens", 0))
    cached = int(usage.get("cached_input_tokens", 0))
    output = int(usage.get("output_tokens", 0))
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "uncached_input_tokens": max(0, input_tokens - cached),
        "output_tokens": output,
        "total_tokens": input_tokens + output,
    }


def command_oracle(commands: list[str], terms: tuple[str, ...]) -> bool:
    joined = "\n".join(commands).lower()
    return all(term.lower() in joined for term in terms)


def prepare_home(home: Path, auth: Path, fixture: Path, arm: str) -> None:
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True)
    target_auth = codex_home / "auth.json"
    shutil.copy2(auth, target_auth)
    target_auth.chmod(stat.S_IRUSR | stat.S_IWUSR)
    if arm == "lean":
        result = run(
            [
                "python3",
                str(INSTALLER),
                "--profile",
                "lean",
                "--agent",
                "codex",
                "--project",
                str(fixture),
            ],
            env={**os.environ, "HOME": str(home), "CODEX_HOME": str(codex_home)},
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Lean install failed")


def run_arm(
    task: Task,
    arm: str,
    *,
    auth: Path,
    fixture: Path,
    model: str,
    timeout: int,
    home_root: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    home = home_root / f"home-{task.name}-{arm}"
    prepare_home(home, auth, fixture, arm)
    codex_home = home / ".codex"
    command = [
        "codex",
        "--enable" if arm == "lean" else "--disable",
        "hooks",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "--dangerously-bypass-hook-trust",
        "--model",
        model,
        "-c",
        'model_reasoning_effort="low"',
        "-C",
        str(fixture),
        "--json",
        "-",
    ]
    started = time.monotonic()
    try:
        run_env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "PATH": f"{fixture / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        result = run(
            command,
            input=task.prompt,
            timeout=timeout,
            env=run_env,
        )
        timed_out = False
    except subprocess.TimeoutExpired as error:
        result = subprocess.CompletedProcess(command, 124, error.stdout or "", error.stderr or "")
        timed_out = True
    elapsed_ms = round((time.monotonic() - started) * 1000)
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    answer, raw_usage, commands = parse_codex_jsonl(stdout)
    usage = normalize_usage(raw_usage)
    accepted = (
        result.returncode == 0
        and answer == task.expected
        and command_oracle(commands, task.command_terms)
        and usage["total_tokens"] > 0
    )
    raw_path = artifact_root / f"{task.name}-{arm}.jsonl"
    raw_path.write_text(stdout)
    return {
        "arm": arm,
        "return_code": result.returncode,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "usage": usage,
        "answer": answer,
        "commands": commands,
        "rtk_observed": any("rtk" in value.lower() for value in commands),
        "accepted": accepted,
        "oracle": {
            "exact_answer": answer == task.expected,
            "command_terms": command_oracle(commands, task.command_terms),
            "provider_usage": usage["total_tokens"] > 0,
        },
        "stderr_tail": stderr[-1000:],
        "raw_jsonl": str(raw_path),
    }


def percent_saved(baseline: int, lean: int) -> float | None:
    if baseline <= 0:
        return None
    return round((1 - lean / baseline) * 100, 2)


WEIGHTED_BASIS = (
    "Weighted numbers are a list-ratio estimate against a no-cache counterfactual, "
    "not an invoice. Raw provider counters stay authoritative."
)


# This harness drives Codex, so it must be priced with Codex ratios rather
# than the Anthropic default. gpt-5.6-terra is the model these runs use.
WEIGHTED_PROFILE = "openai-gpt-5.6-terra"


def weighted_delta(
    baseline: dict[str, int], lean: dict[str, int], accepted: bool
) -> dict[str, Any]:
    """Price the cached prefix instead of counting raw tokens.

    Lean converts fresh input into cache reads, so the raw input sum can rise
    while the bill falls. Both views ship side by side because they disagree.
    """
    comparison = cache_economics.compare(baseline, lean, WEIGHTED_PROFILE)
    base = comparison["baseline"]
    cand = comparison["candidate"]
    return {
        "baseline_weighted_input_tokens": base["weighted_input_tokens"],
        "lean_weighted_input_tokens": cand["weighted_input_tokens"],
        "baseline_weighted_total_tokens": base["weighted_total_tokens"],
        "lean_weighted_total_tokens": cand["weighted_total_tokens"],
        "baseline_cache_hit_rate_percent": base["cache_hit_rate_percent"],
        "lean_cache_hit_rate_percent": cand["cache_hit_rate_percent"],
        "cache_hit_rate_delta": comparison["cache_hit_rate_delta"],
        "input_saved_percent": (comparison["weighted_input_saved_percent"] if accepted else None),
        "total_saved_percent": (comparison["weighted_total_saved_percent"] if accepted else None),
        "profile": comparison["profile"],
        "basis": WEIGHTED_BASIS,
    }


def summarize_pair(task: Task, arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = arms["baseline"]["usage"]
    lean = arms["lean"]["usage"]
    accepted = arms["baseline"]["accepted"] and arms["lean"]["accepted"]
    return {
        "name": task.name,
        "prompt": task.prompt,
        "expected": task.expected,
        "accepted": accepted,
        "arms": arms,
        "provider_delta": {
            "input_tokens": lean["input_tokens"] - baseline["input_tokens"],
            "uncached_input_tokens": (
                lean["uncached_input_tokens"] - baseline["uncached_input_tokens"]
            ),
            "output_tokens": lean["output_tokens"] - baseline["output_tokens"],
            "total_tokens": lean["total_tokens"] - baseline["total_tokens"],
            "input_saved_percent": (
                percent_saved(baseline["input_tokens"], lean["input_tokens"]) if accepted else None
            ),
            "total_saved_percent": (
                percent_saved(baseline["total_tokens"], lean["total_tokens"]) if accepted else None
            ),
        },
        "weighted_delta": weighted_delta(baseline, lean, accepted),
    }


def aggregate(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = all(task["accepted"] for task in tasks)
    baseline = {
        key: sum(task["arms"]["baseline"]["usage"][key] for task in tasks)
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "uncached_input_tokens",
            "output_tokens",
            "total_tokens",
        )
    }
    lean = {key: sum(task["arms"]["lean"]["usage"][key] for task in tasks) for key in baseline}
    weighted = weighted_delta(baseline, lean, accepted)
    return {
        "accepted": accepted,
        "baseline": baseline,
        "lean": lean,
        "weighted": weighted,
        "provider_savings_claim_valid": accepted,
        "input_saved_percent": percent_saved(baseline["input_tokens"], lean["input_tokens"])
        if accepted
        else None,
        "total_saved_percent": percent_saved(baseline["total_tokens"], lean["total_tokens"])
        if accepted
        else None,
        "ninety_nine_percent_provider_saving": (
            accepted
            and percent_saved(baseline["total_tokens"], lean["total_tokens"]) is not None
            and percent_saved(baseline["total_tokens"], lean["total_tokens"]) >= 99
        ),
    }


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Codex provider A/B — {payload['date']}",
        "",
        "Fresh HOME per run; same model, fixture and task oracle. Baseline disables hooks; Lean installs the canonical prompt and Stop hooks. Provider-reported Codex usage is authoritative.",
        "",
        "Raw columns count tokens. Weighted columns price them: Lean turns fresh input into cache reads, so raw and weighted savings can disagree, and a raw regression can still be a cheaper run.",
        "",
        "| Task | Baseline input | Lean input | Input saved (raw) | Input saved (weighted) | Baseline total | Lean total | Total saved (weighted) | Cache hit baseline -> Lean | Accepted | RTK in Lean |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|:--:|:--:|",
    ]
    for task in payload["tasks"]:
        baseline = task["arms"]["baseline"]["usage"]
        lean = task["arms"]["lean"]["usage"]
        delta = task["provider_delta"]
        weighted = task["weighted_delta"]
        lines.append(
            f"| {task['name']} | {baseline['input_tokens']:,} | {lean['input_tokens']:,} | "
            f"{_percent(delta['input_saved_percent'])} | "
            f"{_percent(weighted['input_saved_percent'])} | "
            f"{baseline['total_tokens']:,} | {lean['total_tokens']:,} | "
            f"{_percent(weighted['total_saved_percent'])} | "
            f"{_percent(weighted['baseline_cache_hit_rate_percent'])} -> "
            f"{_percent(weighted['lean_cache_hit_rate_percent'])} | "
            f"{'yes' if task['accepted'] else 'no'} | {'yes' if task['arms']['lean']['rtk_observed'] else 'no'} |"
        )
    aggregate_result = payload["aggregate"]
    weighted = aggregate_result["weighted"]
    profile = weighted["profile"]
    lines.extend(
        [
            "",
            "## Aggregate gate",
            "",
            f"- All task oracles accepted: **{'yes' if aggregate_result['accepted'] else 'no'}**.",
            f"- Baseline provider total (raw): **{aggregate_result['baseline']['total_tokens']:,}**.",
            f"- Lean provider total (raw): **{aggregate_result['lean']['total_tokens']:,}**.",
            f"- Provider total saving (raw): **{aggregate_result['total_saved_percent'] if aggregate_result['total_saved_percent'] is not None else 'not claimable'}%**.",
            f"- 99%+ provider saving proven (raw): **{'yes' if aggregate_result['ninety_nine_percent_provider_saving'] else 'no'}**.",
            "",
            "## Weighted (cache-priced) aggregate",
            "",
            f"- Baseline weighted input (fresh-equivalents): **{weighted['baseline_weighted_input_tokens']:,.0f}**.",
            f"- Lean weighted input (fresh-equivalents): **{weighted['lean_weighted_input_tokens']:,.0f}**.",
            f"- Weighted input saved: **{_percent(weighted['input_saved_percent'])}**.",
            f"- Weighted total saved (incl. output): **{_percent(weighted['total_saved_percent'])}**.",
            f"- Cache hit rate: baseline **{_percent(weighted['baseline_cache_hit_rate_percent'])}**, "
            f"Lean **{_percent(weighted['lean_cache_hit_rate_percent'])}** "
            f"(delta {_percent(weighted['cache_hit_rate_delta'])}).",
            "",
            f"Ratio profile `{profile['name']}` (verified {profile['verified']}): cache read "
            f"{profile['cache_read_ratio']}x, cache write {profile['cache_write_ratio']}x, "
            f"output {profile['output_ratio']}x base input. Source: {profile['source']}.",
            "",
            weighted["basis"],
            "",
            "A failed oracle invalidates the saving claim. One run per arm is fresh evidence, not a statistical confidence interval; repeat ABBA before changing defaults.",
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
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--task",
        action="append",
        choices=tuple(task.name for task in TASKS),
        help="run only this task; repeat to select multiple tasks",
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required because this command consumes provider quota")
    try:
        auth = safe_auth(args.auth)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ats-provider-ab-") as temporary:
        temporary_root = Path(temporary)
        fixture = temporary_root / "fixture"
        fixture_head = create_fixture(fixture)
        run_root = args.out_dir / "runs"
        run_root.mkdir(parents=True, exist_ok=True)
        home_root = temporary_root / "homes"
        home_root.mkdir()
        rows: list[dict[str, Any]] = []
        selected_tasks = [task for task in TASKS if not args.task or task.name in args.task]
        for index, task in enumerate(selected_tasks):
            order = ("baseline", "lean") if index % 2 == 0 else ("lean", "baseline")
            arms = {
                arm: run_arm(
                    task,
                    arm,
                    auth=auth,
                    fixture=fixture,
                    model=args.model,
                    timeout=args.timeout,
                    home_root=home_root,
                    artifact_root=run_root,
                )
                for arm in order
            }
            rows.append(summarize_pair(task, arms))
    version = run(["codex", "--version"]).stdout.strip()
    payload = {
        # 2: adds weighted (cache-priced) deltas alongside the raw ones.
        "schema_version": 2,
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "codex_version": version,
        "model": args.model,
        "fixture_head": fixture_head,
        "order": "alternating AB/BA; fresh HOME and persisted non-ephemeral run per arm",
        "tasks": rows,
        "aggregate": aggregate(rows),
    }
    json_path = args.out_dir / "result.json"
    markdown_path = args.out_dir / "result.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    markdown_path.write_text(render_markdown(payload))
    print(markdown_path)
    print(json.dumps(payload["aggregate"], ensure_ascii=False, indent=2))
    return 0 if payload["aggregate"]["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
