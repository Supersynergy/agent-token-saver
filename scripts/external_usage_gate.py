#!/usr/bin/env python3
"""Gate optional Codex usage auditors against the canonical ATS ledger.

External tools run only when the caller supplies an explicit command. Session
files are copied into a temporary HOME so scanners cannot write through to the
original provider logs. Candidate processes receive a credential-scrubbed
environment. No package is installed or upgraded by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SUPPORTED = {"splitrail", "tokscale", "codeburn", "aiusage"}
CORE_FIELDS = ("input_total", "input_uncached", "cache_read", "output")
DATE_RE = re.compile(r"rollout-(\d{4})-(\d{2})-(\d{2})T")
PIN_RE = re.compile(r"@v?\d")
SAFE_ENV_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "TMP",
    "TEMP",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def canonical_usage(ledger: dict[str, Any]) -> dict[str, int]:
    usage = ledger.get("provider_usage")
    if not isinstance(usage, dict):
        raise ValueError("ledger lacks provider_usage")
    total = _int(usage.get("total_input_tokens"))
    cached_subset = _int(usage.get("cached_input_tokens_subset"))
    cache_read = cached_subset or _int(usage.get("cache_read_input_tokens"))
    cache_write = _int(usage.get("cache_creation_input_tokens"))
    if cached_subset:
        uncached = max(0, total - cached_subset)
    else:
        uncached = _int(usage.get("input_tokens"))
    return {
        "input_total": total,
        "input_uncached": uncached,
        "cache_read": cache_read,
        "cache_write": cache_write,
        "output": _int(usage.get("output_tokens")),
        "reasoning": _int(usage.get("reasoning_output_tokens_subset")),
    }


def normalize_splitrail(data: Any) -> dict[str, int]:
    if not isinstance(data, dict):
        raise ValueError("splitrail output must be an object")
    totals = {"input_uncached": 0, "cache_read": 0, "output": 0, "reasoning": 0}
    matched = False
    for analyzer in data.get("analyzer_stats", []):
        if not isinstance(analyzer, dict):
            continue
        name = str(analyzer.get("analyzer_name", "")).lower()
        if name and "codex" not in name:
            continue
        for day in analyzer.get("daily_stats", {}).values():
            stats = day.get("stats", {}) if isinstance(day, dict) else {}
            if not isinstance(stats, dict):
                continue
            matched = True
            totals["input_uncached"] += _int(stats.get("inputTokens"))
            totals["cache_read"] += _int(stats.get("cachedTokens"))
            totals["output"] += _int(stats.get("outputTokens"))
            totals["reasoning"] += _int(stats.get("reasoningTokens"))
    if not matched:
        raise ValueError("splitrail output lacks Codex daily stats")
    totals["cache_write"] = 0
    totals["input_total"] = totals["input_uncached"] + totals["cache_read"]
    return totals


def normalize_tokscale(data: Any) -> dict[str, int]:
    if not isinstance(data, dict) or "totalInput" not in data:
        raise ValueError("tokscale output lacks totals")
    uncached = _int(data.get("totalInput"))
    cache_read = _int(data.get("totalCacheRead"))
    return {
        "input_total": uncached + cache_read,
        "input_uncached": uncached,
        "cache_read": cache_read,
        "cache_write": _int(data.get("totalCacheWrite")),
        "output": _int(data.get("totalOutput")),
        "reasoning": sum(
            _int(entry.get("reasoning"))
            for entry in data.get("entries", [])
            if isinstance(entry, dict)
        ),
    }


def normalize_codeburn(data: Any) -> dict[str, int | None]:
    if not isinstance(data, dict):
        raise ValueError("codeburn output must be an object")
    overview = data.get("overview")
    tokens = overview.get("tokens") if isinstance(overview, dict) else None
    if not isinstance(tokens, dict):
        raise ValueError("codeburn output lacks overview.tokens")
    uncached = _int(tokens.get("input"))
    cache_read = _int(tokens.get("cacheRead"))
    return {
        "input_total": uncached + cache_read,
        "input_uncached": uncached,
        "cache_read": cache_read,
        "cache_write": _int(tokens.get("cacheWrite")),
        "output": _int(tokens.get("output")),
        "reasoning": None,
    }


def normalize_aiusage(data: Any) -> dict[str, int]:
    if not isinstance(data, list) or not data:
        raise ValueError("aiusage export must be a non-empty record array")
    rows = [row for row in data if isinstance(row, dict) and row.get("tool") == "codex"]
    if not rows:
        raise ValueError("aiusage export lacks Codex records")
    total = sum(_int(row.get("inputTokens")) for row in rows)
    cache_read = sum(_int(row.get("cacheReadTokens")) for row in rows)
    return {
        # aiusage inputTokens already includes cached input. Its native summary
        # adds cache and thinking again; only this normalized export is trusted.
        "input_total": total,
        "input_uncached": max(0, total - cache_read),
        "cache_read": cache_read,
        "cache_write": sum(_int(row.get("cacheWriteTokens")) for row in rows),
        "output": sum(_int(row.get("outputTokens")) for row in rows),
        "reasoning": sum(_int(row.get("thinkingTokens")) for row in rows),
    }


NORMALIZERS = {
    "splitrail": normalize_splitrail,
    "tokscale": normalize_tokscale,
    "codeburn": normalize_codeburn,
    "aiusage": normalize_aiusage,
}


def compare_usage(
    expected: dict[str, int], observed: dict[str, int | None]
) -> dict[str, Any]:
    deltas: dict[str, int | None] = {}
    for field in (*CORE_FIELDS, "cache_write", "reasoning"):
        value = observed.get(field)
        deltas[field] = None if value is None else int(value) - expected[field]
    missing = [field for field in CORE_FIELDS if observed.get(field) is None]
    exact = not missing and all(deltas[field] == 0 for field in CORE_FIELDS)
    if observed.get("reasoning") is not None:
        exact = exact and deltas["reasoning"] == 0
    return {"exact": exact, "missing_core_fields": missing, "delta": deltas}


def policy_verdict(name: str, exact: bool) -> tuple[str, str]:
    if not exact:
        return "reject", "token fields differ from canonical ledger"
    decisions = {
        "splitrail": ("optional", "fast global audit; ledger remains team truth"),
        "tokscale": ("optional", "session/model cross-check"),
        "codeburn": ("optional", "read-only optimizer; savings claims need separate proof"),
        "aiusage": ("normalized-only", "native summary double-counts cache and thinking"),
    }
    return decisions[name]


def parse_named(value: str) -> tuple[str, str]:
    name, separator, payload = value.partition("=")
    if not separator or name not in SUPPORTED or not payload.strip():
        names = ", ".join(sorted(SUPPORTED))
        raise ValueError(f"expected NAME=VALUE with NAME in: {names}")
    return name, payload.strip()


def command_parts(value: str) -> list[str]:
    parts = shlex.split(value)
    if not parts:
        raise ValueError("candidate command is empty")
    if any(token.endswith("@latest") for token in parts):
        raise ValueError("@latest is not reproducible; pin an exact candidate version")
    launcher = Path(parts[0]).name
    if launcher in {"bunx", "npx"} and not any(PIN_RE.search(token) for token in parts[1:]):
        raise ValueError(f"{launcher} candidate commands require an exact package version")
    return parts


def usage_path(spec: str) -> Path:
    raw = spec.split("=", 1)[1] if "=" in spec else spec
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"usage source is not a file: {path}")
    return path


def stage_sessions(specs: list[str], home: Path) -> None:
    for index, spec in enumerate(specs, start=1):
        source = usage_path(spec)
        match = DATE_RE.search(source.name)
        parts = match.groups() if match else ("unknown", "00", "00")
        target_dir = home / ".codex" / "sessions" / Path(*parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if target.exists():
            target = target.with_name(f"{target.stem}-{index}{target.suffix}")
        shutil.copy2(source, target)


def ledger_command() -> list[str]:
    script = Path(__file__).resolve()
    repo_ledger = script.with_name("full_context_ledger.py")
    installed_ledger = script.with_name("agent-token-ledger")
    if repo_ledger.is_file():
        return [sys.executable, str(repo_ledger)]
    if installed_ledger.is_file():
        return [str(installed_ledger)]
    found = shutil.which("agent-token-ledger")
    if found:
        return [found]
    raise ValueError("agent-token-ledger not found beside gate or on PATH")


def load_ledger(specs: list[str], provider: str, timeout: float) -> dict[str, Any]:
    command = [*ledger_command(), "--provider", provider, "--format", "json-compact"]
    for spec in specs:
        command.extend(("--usage", spec))
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"ledger failed ({result.returncode}): {result.stderr.strip()[:500]}")
    return json.loads(result.stdout)


def candidate_invocation(name: str, base: list[str], home: Path) -> list[str]:
    if name == "splitrail":
        return [*base, "stats"]
    if name == "tokscale":
        return [
            *base,
            "--home",
            str(home),
            "--client",
            "codex",
            "--json",
            "--group-by",
            "session,model",
            "--no-spinner",
        ]
    if name == "codeburn":
        return [*base, "report", "--period", "all", "--format", "json"]
    raise ValueError("aiusage execution is unsupported; pass its raw export with --candidate-json")


def first_line(command: list[str], env: dict[str, str], timeout: float) -> str:
    try:
        result = subprocess.run(
            [*command, "--version"],
            capture_output=True,
            text=True,
            timeout=min(timeout, 8),
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0][:200] if output else "unknown"


def candidate_environment(home: Path) -> dict[str, str]:
    """Return the minimum inherited environment, excluding credentials."""
    env = {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ}
    env.update(
        {
            "HOME": str(home),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "CI": "true",
            "NO_COLOR": "1",
            "NO_UPDATE_NOTIFIER": "1",
        }
    )
    return env


def run_candidate(
    name: str, command: str, home: Path, timeout: float, runs: int
) -> tuple[Any, dict[str, Any]]:
    base = command_parts(command)
    env = candidate_environment(home)
    invocation = candidate_invocation(name, base, home)
    samples: list[float] = []
    data: Any = None
    stdout_bytes = 0
    for _ in range(runs):
        started = time.perf_counter()
        result = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        samples.append(round((time.perf_counter() - started) * 1000, 2))
        if result.returncode:
            raise ValueError(
                f"{name} failed ({result.returncode}): "
                f"{(result.stderr or result.stdout).strip()[:500]}"
            )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"{name} did not emit JSON: {error}") from error
        stdout_bytes = len(result.stdout.encode())
    warm = samples[1:] or samples
    display_command = [
        "$ATS_FIXTURE_HOME" if token == str(home) else token for token in invocation
    ]
    return data, {
        "command": display_command,
        "version": first_line(base, env, timeout),
        "runs": runs,
        "cold_wall_ms": samples[0],
        "median_wall_ms": round(statistics.median(samples), 2),
        "warm_median_wall_ms": round(statistics.median(warm), 2),
        "samples_wall_ms": samples,
        "stdout_bytes": stdout_bytes,
    }


def candidate_report(
    name: str,
    data: Any,
    expected: dict[str, int],
    execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = NORMALIZERS[name](data)
    comparison = compare_usage(expected, normalized)
    status, reason = policy_verdict(name, comparison["exact"])
    warnings = []
    if name == "aiusage":
        warnings.append("native summary is not additive; consume normalized raw export only")
    if name == "codeburn":
        warnings.append("reasoning-token coverage unavailable")
    return {
        "name": name,
        "normalized": normalized,
        "comparison": comparison,
        "policy": {"status": status, "reason": reason},
        "warnings": warnings,
        "execution": execution,
    }


def render_markdown(report: dict[str, Any]) -> str:
    expected = report["canonical"]
    lines = [
        "# External usage-auditor gate",
        "",
        "Provider totals come from `agent-token-ledger`. External cost estimates are not an oracle.",
        "",
        f"Canonical input: **{expected['input_total']:,}** total, "
        f"**{expected['input_uncached']:,}** uncached, **{expected['cache_read']:,}** cached.",
        "",
        "| Candidate | Exact token fields | Wall time | Policy |",
        "|---|:---:|---:|---|",
    ]
    for item in report["candidates"]:
        execution = item.get("execution") or {}
        wall = (
            f"{execution['median_wall_ms']:.2f} ms"
            if execution.get("median_wall_ms") is not None
            else "n/a"
        )
        exact = "yes" if item["comparison"]["exact"] else "no"
        lines.append(
            f"| {item['name']} | {exact} | {wall} | {item['policy']['status']}: "
            f"{item['policy']['reason']} |"
        )
    lines.extend(["", f"Gate passed: **{'yes' if report['gate_passed'] else 'no'}**.", ""])
    return "\n".join(lines)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-token-audit")
    parser.add_argument(
        "--usage",
        action="append",
        required=True,
        metavar="[NAME=]PATH",
        help="exact Codex JSONL sources; repeated inputs are summed",
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        metavar="NAME=COMMAND",
        help="run an explicit candidate in an isolated temporary HOME",
    )
    parser.add_argument(
        "--candidate-json",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="compare an existing candidate JSON export without executing it",
    )
    parser.add_argument("--provider", default="codex")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()
    if not args.candidate and not args.candidate_json:
        parser.error("at least one --candidate or --candidate-json is required")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if not 1 <= args.runs <= 20:
        parser.error("--runs must be between 1 and 20")
    try:
        ledger = load_ledger(args.usage, args.provider, args.timeout)
        expected = canonical_usage(ledger)
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        with tempfile.TemporaryDirectory(prefix="agent-token-audit-") as directory:
            fixture_home = Path(directory)
            stage_sessions(args.usage, fixture_home)
            for spec in args.candidate:
                name, command = parse_named(spec)
                if name in seen:
                    raise ValueError(f"duplicate candidate: {name}")
                seen.add(name)
                data, execution = run_candidate(
                    name, command, fixture_home, args.timeout, args.runs
                )
                candidates.append(candidate_report(name, data, expected, execution))
            for spec in args.candidate_json:
                name, raw_path = parse_named(spec)
                if name in seen:
                    raise ValueError(f"duplicate candidate: {name}")
                seen.add(name)
                path = Path(raw_path).expanduser().resolve()
                data = json.loads(path.read_text())
                candidates.append(candidate_report(name, data, expected))
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))
    report = {
        "schema_version": 1,
        "method": "isolated external auditor comparison against agent-token-ledger",
        "provider": args.provider,
        "usage_sources": len(args.usage),
        "canonical": expected,
        "candidates": candidates,
        "gate_passed": all(item["comparison"]["exact"] for item in candidates),
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        write_text(args.json_out, encoded)
    if args.markdown_out:
        write_text(args.markdown_out, render_markdown(report))
    if not args.json_out and not args.markdown_out:
        print(encoded, end="")
    return 0 if report["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
