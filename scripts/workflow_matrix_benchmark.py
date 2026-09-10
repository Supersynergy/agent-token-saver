#!/usr/bin/env python3
"""Reproducible component and worker-shape benchmark for Agent Token Saver.

The offline matrix uses three deterministic fixtures and reports UTF-8/4 token
proxies.  Optional live arms use the installed ``llmadapter ask-v2`` contract
with a machine oracle.  Provider counters are copied only when llmadapter emits
them; local proxies are never labelled as provider usage or billing savings.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKEN_STACK_MATRIX = ROOT / "scripts" / "token_stack_matrix_benchmark.py"
EXPECTED_LIVE = {
    "error_count": 4,
    "last_error_id": "E0377",
    "eu_open_total": 117,
    "failed_test": "test_expected_total",
    "expected": 145,
    "actual": 144,
}
LIVE_PROMPT = """Perform the three independent operations below. No tools.
Return only one JSON object with exactly these keys: error_count,
last_error_id, eu_open_total, failed_test, expected, actual.

INCIDENTS: ERROR ids are E0017, E0099, E0211, E0377 in chronological order.
ORDERS: open EU amounts are 19, 23, 31, 44. Ignore all other orders.
PYTEST: test_expected_total failed because actual 144 != expected 145.
"""


@dataclass(frozen=True)
class OperationFixture:
    name: str
    kind: str
    raw: str
    expected: dict[str, Any]
    source_exit_code: int = 0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    wall_ms: float
    timed_out: bool = False


class ProjectionCache:
    """Small content-addressed cache used only by the deterministic fixture arm."""

    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def get_or_project(self, fixture: OperationFixture) -> tuple[str, bool]:
        key = sha256_text(f"{fixture.kind}\0{fixture.raw}")
        if key in self._items:
            return self._items[key], True
        projected = project_fixture(fixture)
        self._items[key] = projected
        return projected, False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def token_proxy(text: str) -> int:
    """Transparent local proxy. It is never a provider token count."""
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 3)


def incident_fixture() -> OperationFixture:
    error_indices = {17, 99, 211, 377}
    lines = []
    ids: list[str] = []
    for index in range(600):
        event_id = f"E{index:04d}"
        if index in error_indices:
            ids.append(event_id)
            lines.append(
                f"2026-09-08T10:{index % 60:02d}:00Z ERROR id={event_id} "
                f"service=api code=500 request=R{index:06d}"
            )
        else:
            lines.append(
                f"2026-09-08T10:{index % 60:02d}:00Z INFO id=I{index:04d} "
                f"service=api code=200 request=R{index:06d}"
            )
    expected = {
        "error_count": len(ids),
        "last_error_id": ids[-1],
        "last_three_error_ids": ids[-3:],
    }
    return OperationFixture("incident_log", "incident", "\n".join(lines) + "\n", expected)


def orders_fixture() -> OperationFixture:
    rows: list[str] = []
    count = 0
    total = 0
    for index in range(480):
        region = ("EU", "US", "APAC")[index % 3]
        status = "open" if index % 5 in {0, 1} else "closed"
        amount = 10 + (index * 7) % 91
        row = {
            "order_id": f"O{index:05d}",
            "region": region,
            "status": status,
            "amount": amount,
            "note": f"stable-fixture-{index % 19}",
        }
        rows.append(json.dumps(row, separators=(",", ":"), sort_keys=True))
        if region == "EU" and status == "open":
            count += 1
            total += amount
    expected = {"eu_open_count": count, "eu_open_total": total}
    return OperationFixture("orders_jsonl", "orders", "\n".join(rows) + "\n", expected)


def pytest_fixture() -> OperationFixture:
    lines = [
        "============================= test session starts ==============================",
        "platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0",
        "collected 51 items",
        "",
    ]
    lines.extend(f"tests/test_ok.py::test_ok_{index:03d} PASSED" for index in range(50))
    lines.extend(
        [
            "tests/test_workflow.py::test_expected_total FAILED",
            "",
            "=================================== FAILURES ===================================",
            "____________________________ test_expected_total ______________________________",
            "    def test_expected_total():",
            ">       assert calculate_total() == 145",
            "E       assert 144 == 145",
            "tests/test_workflow.py:44: AssertionError",
            "=========================== short test summary info ============================",
            "FAILED tests/test_workflow.py::test_expected_total - assert 144 == 145",
            "========================= 1 failed, 50 passed in 0.42s =========================",
        ]
    )
    expected = {
        "failed": 1,
        "passed": 50,
        "failed_test": "test_expected_total",
        "expected": 145,
        "actual": 144,
    }
    return OperationFixture(
        "pytest_failure", "pytest", "\n".join(lines) + "\n", expected, source_exit_code=1
    )


def build_fixtures() -> tuple[OperationFixture, ...]:
    return incident_fixture(), orders_fixture(), pytest_fixture()


def project_fixture(fixture: OperationFixture) -> str:
    if fixture.kind == "incident":
        ids = re.findall(r"\bERROR id=(E\d{4})\b", fixture.raw)
        value = {
            "error_count": len(ids),
            "last_error_id": ids[-1] if ids else None,
            "last_three_error_ids": ids[-3:],
        }
    elif fixture.kind == "orders":
        selected = []
        for line in fixture.raw.splitlines():
            row = json.loads(line)
            if row["region"] == "EU" and row["status"] == "open":
                selected.append(int(row["amount"]))
        value = {"eu_open_count": len(selected), "eu_open_total": sum(selected)}
    elif fixture.kind == "pytest":
        summary = re.search(r"(\d+) failed, (\d+) passed", fixture.raw)
        comparison = re.search(r"assert (\d+) == (\d+)", fixture.raw)
        failed_test = re.search(r"::(test_[A-Za-z0-9_]+) FAILED", fixture.raw)
        if not summary or not comparison or not failed_test:
            raise ValueError("pytest fixture lacks required failure signals")
        value = {
            "failed": int(summary.group(1)),
            "passed": int(summary.group(2)),
            "failed_test": failed_test.group(1),
            "expected": int(comparison.group(2)),
            "actual": int(comparison.group(1)),
        }
    else:
        raise ValueError(f"unsupported fixture kind: {fixture.kind}")
    return json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n"


def projection_passes(fixture: OperationFixture, output: str) -> bool:
    try:
        return json.loads(output) == fixture.expected
    except json.JSONDecodeError:
        return False


def extract_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def live_oracle(text: str) -> bool:
    value = extract_json_object(text)
    if value is None or set(value) != set(EXPECTED_LIVE):
        return False
    return all(value.get(key) == expected for key, expected in EXPECTED_LIVE.items())


def run_command(
    command: list[str],
    *,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> CommandResult:
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
        return CommandResult(
            process.returncode,
            stdout,
            stderr,
            round((time.perf_counter() - started) * 1000, 3),
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        return CommandResult(
            124,
            stdout,
            stderr,
            round((time.perf_counter() - started) * 1000, 3),
            timed_out=True,
        )


def compact_error(text: str, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", text).strip()[-limit:]


def rtk_projection(fixture: OperationFixture, rtk_path: str | None) -> tuple[str, dict[str, Any]]:
    exact = project_fixture(fixture)
    if fixture.kind != "pytest":
        return exact, {
            "status": "unsupported_for_fixture",
            "adopted": False,
            "wall_ms": 0.0,
            "error": "",
        }
    if not rtk_path:
        return exact, {"status": "unavailable", "adopted": False, "wall_ms": 0.0, "error": ""}
    result = run_command(
        [rtk_path, "pipe", "--filter", "pytest"], input_text=fixture.raw, timeout=30
    )
    required = ("50 passed", "1 failed", "test_expected_total", "assert 144 == 145")
    missing = [signal_text for signal_text in required if signal_text not in result.stdout]
    accepted = result.returncode == 0 and not missing
    smaller = token_proxy(result.stdout) < token_proxy(fixture.raw)
    adopted = accepted and smaller
    return (result.stdout if adopted else exact), {
        "status": "accepted" if adopted else "rejected",
        "adopted": adopted,
        "filter_exit_code": result.returncode,
        "source_exit_code": fixture.source_exit_code,
        "source_exit_preserved_by_harness": True,
        "wall_ms": result.wall_ms,
        "raw_proxy_tokens": token_proxy(fixture.raw),
        "filtered_proxy_tokens": token_proxy(result.stdout),
        "missing_signals": missing,
        "error": compact_error(result.stderr),
    }


def benchmark_shapes(fixtures: tuple[OperationFixture, ...], samples: int) -> dict[str, Any]:
    expected = {fixture.name: project_fixture(fixture) for fixture in fixtures}
    input_tokens = sum(token_proxy(fixture.raw) for fixture in fixtures)
    output_tokens = sum(token_proxy(output) for output in expected.values())

    def team_proxy(workers: int) -> dict[str, Any]:
        return {
            "parent": {
                "calls_started": 0,
                "proxy_tokens": 0,
                "note": "local Python benchmark controller",
            },
            "children": {
                "workers": workers,
                "input_proxy_tokens": input_tokens,
                "output_proxy_tokens": output_tokens,
            },
            "parent_plus_children_proxy_tokens": input_tokens + output_tokens,
            "provider_counter_status": "unavailable_local_proxy_only",
        }

    def sequential() -> dict[str, str]:
        return {fixture.name: project_fixture(fixture) for fixture in fixtures}

    def parallel() -> dict[str, str]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            futures = {pool.submit(project_fixture, fixture): fixture.name for fixture in fixtures}
            return {name: future.result() for future, name in futures.items()}

    def sample(function: Callable[[], dict[str, str]]) -> tuple[list[float], bool]:
        timings = []
        accepted = True
        for _ in range(samples):
            started = time.perf_counter()
            output = function()
            timings.append((time.perf_counter() - started) * 1000)
            accepted = accepted and output == expected
        return timings, accepted

    sequential_ms, sequential_ok = sample(sequential)
    parallel_ms, parallel_ok = sample(parallel)
    return {
        "single_local_worker": {
            "workers": 1,
            "independent_operations": len(fixtures),
            "samples": samples,
            "wall_ms_median": round(statistics.median(sequential_ms), 3),
            "wall_ms_p95": percentile(sequential_ms, 0.95),
            "accepted": sequential_ok,
            "team_tokens": team_proxy(1),
            "retries": 0,
            "errors": [],
        },
        "parallel_local_workers": {
            "workers": len(fixtures),
            "independent_operations": len(fixtures),
            "samples": samples,
            "wall_ms_median": round(statistics.median(parallel_ms), 3),
            "wall_ms_p95": percentile(parallel_ms, 0.95),
            "accepted": parallel_ok,
            "team_tokens": team_proxy(len(fixtures)),
            "retries": 0,
            "errors": [],
            "note": "thread workers; wall-time comparison only, not an agent-token claim",
        },
    }


def command_text(command: list[str], timeout: int = 30) -> CommandResult:
    try:
        return run_command(command, timeout=timeout)
    except OSError as exc:
        return CommandResult(127, "", str(exc), 0.0)


def parse_lane_inventory(output: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    names: dict[str, list[str]] = {}
    total = 0
    for line in output.splitlines():
        match = re.match(r"^(free|cheap|paid|local|cli)\s+(\S+)", line)
        if not match:
            total_match = re.match(r"^total: (\d+) lanes", line)
            if total_match:
                total = int(total_match.group(1))
            continue
        lane_class, name = match.groups()
        counts[lane_class] = counts.get(lane_class, 0) + 1
        names.setdefault(lane_class, []).append(name)
    return {"total": total or sum(counts.values()), "class_counts": counts, "names": names}


def inventory_tools(llmadapter_path: str | None, rtk_path: str | None) -> dict[str, Any]:
    lanes = command_text([llmadapter_path, "lanes"]) if llmadapter_path else None
    doctor = command_text([llmadapter_path, "doctor"]) if llmadapter_path else None
    rtk_version = command_text([rtk_path, "--version"]) if rtk_path else None
    adapter_resolved = Path(llmadapter_path).resolve() if llmadapter_path else None
    token_stack_exists = TOKEN_STACK_MATRIX.is_file()
    return {
        "token_stack_matrix": {
            "path": str(TOKEN_STACK_MATRIX),
            "exists": token_stack_exists,
            "sha256": sha256_file(TOKEN_STACK_MATRIX) if token_stack_exists else None,
        },
        "llmadapter": {
            "path": llmadapter_path,
            "resolved_path": str(adapter_resolved) if adapter_resolved else None,
            "sha256": sha256_file(adapter_resolved) if adapter_resolved else None,
            "lanes_exit_code": lanes.returncode if lanes else None,
            "lanes": parse_lane_inventory(lanes.stdout) if lanes else {},
            "doctor_exit_code": doctor.returncode if doctor else None,
            "doctor_ok": bool(doctor and doctor.returncode == 0),
            "doctor_misses": (
                [line for line in doctor.stdout.splitlines() if line.startswith("MISS")]
                if doctor
                else ["llmadapter unavailable"]
            ),
        },
        "rtk": {
            "path": rtk_path,
            "version": (
                (rtk_version.stdout or rtk_version.stderr).strip() if rtk_version else None
            ),
        },
        "ats_recall": {"path": shutil.which("ats-recall")},
        "agent_token_ledger": {"path": shutil.which("agent-token-ledger")},
    }


def offline_matrix(
    fixtures: tuple[OperationFixture, ...], rtk_path: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    projections: dict[str, str] = {}
    components: list[dict[str, Any]] = []
    for fixture in fixtures:
        started = time.perf_counter()
        projected = project_fixture(fixture)
        wall_ms = round((time.perf_counter() - started) * 1000, 3)
        projections[fixture.name] = projected
        components.append(
            {
                "name": f"exact_projection:{fixture.name}",
                "raw_proxy_tokens": token_proxy(fixture.raw),
                "projected_proxy_tokens": token_proxy(projected),
                "saved_percent": round(
                    (1 - token_proxy(projected) / token_proxy(fixture.raw)) * 100, 2
                ),
                "wall_ms": wall_ms,
                "quality_oracle": "exact_result_equality",
                "accepted": projection_passes(fixture, projected),
                "provider_counters": "unavailable_local_proxy_only",
                "retries": 0,
                "errors": [],
            }
        )

    rtk_contexts: dict[str, str] = {}
    rtk_details: dict[str, Any] = {}
    for fixture in fixtures:
        output, detail = rtk_projection(fixture, rtk_path)
        rtk_contexts[fixture.name] = output
        rtk_details[fixture.name] = detail
    pytest_rtk = next(fixture for fixture in fixtures if fixture.kind == "pytest")
    components.append(
        {
            "name": "rtk_filter:pytest",
            **rtk_details[pytest_rtk.name],
            "quality_oracle": "named_failure_signals_and_source_exit",
            "provider_counters": "unavailable_local_proxy_only",
            "retries": 0,
            "accepted": bool(rtk_details[pytest_rtk.name].get("adopted")) or rtk_path is None,
            "errors": (
                [rtk_details[pytest_rtk.name]["error"]]
                if rtk_details[pytest_rtk.name].get("error")
                else []
            ),
        }
    )

    cache = ProjectionCache()
    started = time.perf_counter()
    cold = [cache.get_or_project(fixture) for fixture in fixtures]
    cold_wall_ms = round((time.perf_counter() - started) * 1000, 3)
    started = time.perf_counter()
    warm = [cache.get_or_project(fixture) for fixture in fixtures]
    warm_wall_ms = round((time.perf_counter() - started) * 1000, 3)
    cache_detail = {
        "cold": {
            "hits": sum(1 for _, hit in cold if hit),
            "misses": sum(1 for _, hit in cold if not hit),
            "calls_started": sum(1 for _, hit in cold if not hit),
            "wall_ms": cold_wall_ms,
            "accepted": all(
                projection_passes(fixture, output)
                for fixture, (output, _) in zip(fixtures, cold, strict=True)
            ),
        },
        "warm": {
            "hits": sum(1 for _, hit in warm if hit),
            "misses": sum(1 for _, hit in warm if not hit),
            "calls_started": sum(1 for _, hit in warm if not hit),
            "wall_ms": warm_wall_ms,
            "accepted": all(
                projection_passes(fixture, output)
                for fixture, (output, _) in zip(fixtures, warm, strict=True)
            ),
        },
        "provider_counters": "unavailable_local_cache_only",
    }
    components.append(
        {
            "name": "deterministic_recall_cache",
            **cache_detail,
            "quality_oracle": "cold_warm_exact_result_equality",
            "wall_ms": {"cold": cold_wall_ms, "warm": warm_wall_ms},
            "accepted": cache_detail["cold"]["accepted"]
            and cache_detail["warm"]["accepted"]
            and cache_detail["cold"]["misses"] == len(fixtures)
            and cache_detail["warm"]["hits"] == len(fixtures),
            "retries": 0,
            "errors": [],
        }
    )

    result_tokens = sum(token_proxy(value) for value in projections.values())

    def matrix_arm(
        name: str,
        contexts: Iterable[str],
        *,
        calls_started: int,
        cache_hits: int,
        accepted: bool,
        note: str,
        wall_ms: float,
    ) -> dict[str, Any]:
        input_tokens = sum(token_proxy(context) for context in contexts if context)
        return {
            "name": name,
            "worker_input_proxy_tokens": input_tokens,
            "worker_output_proxy_tokens": result_tokens,
            "parent_plus_children_proxy_tokens": input_tokens + result_tokens,
            "measurement": "utf8_bytes_div_4_proxy",
            "provider_input_tokens": None,
            "provider_output_tokens": None,
            "provider_counter_status": "unavailable_offline",
            "calls_started": calls_started,
            "cache_hits": cache_hits,
            "wall_ms": wall_ms,
            "retries": 0,
            "errors": [],
            "quality_oracle": "same_exact_results_for_three_operations",
            "accepted": accepted,
            "note": note,
        }

    all_projection_ok = all(
        item["accepted"] for item in components if item["name"].startswith("exact_projection")
    )
    rtk_adopted = bool(rtk_details[pytest_rtk.name].get("adopted"))
    matrix = [
        matrix_arm(
            "baseline_raw",
            (fixture.raw for fixture in fixtures),
            calls_started=len(fixtures),
            cache_hits=0,
            accepted=True,
            note="raw contexts; result oracle computed deterministically",
            wall_ms=0.0,
        ),
        matrix_arm(
            "exact_projection",
            projections.values(),
            calls_started=len(fixtures),
            cache_hits=0,
            accepted=all_projection_ok,
            note="three exact projections before worker context",
            wall_ms=round(
                sum(
                    float(item["wall_ms"])
                    for item in components
                    if item["name"].startswith("exact_projection")
                ),
                3,
            ),
        ),
        matrix_arm(
            "exact_projection_plus_rtk",
            rtk_contexts.values(),
            calls_started=len(fixtures),
            cache_hits=0,
            accepted=all_projection_ok and (rtk_adopted or rtk_path is None),
            note="RTK adopted only for the supported pytest fixture when smaller and complete",
            wall_ms=float(rtk_details[pytest_rtk.name].get("wall_ms") or 0.0),
        ),
        matrix_arm(
            "exact_projection_plus_warm_recall_cache",
            (),
            calls_started=0,
            cache_hits=len(fixtures),
            accepted=bool(components[-1]["accepted"]),
            note="cached exact results returned; no worker call or input context",
            wall_ms=warm_wall_ms,
        ),
    ]
    return components, matrix, rtk_details


def usage_team_totals(accounting: dict[str, Any]) -> dict[str, Any]:
    input_counts = accounting.get("input_tokens") or {}
    output_counts = accounting.get("output_tokens") or {}
    reported = int(input_counts.get("reported") or 0) + int(output_counts.get("reported") or 0)
    estimated = int(input_counts.get("estimated") or 0) + int(output_counts.get("estimated") or 0)
    unknown_calls = max(
        int(input_counts.get("unknown_calls") or 0),
        int(output_counts.get("unknown_calls") or 0),
    )
    if reported and not estimated and not unknown_calls:
        status = "provider_reported"
    elif estimated and not reported and not unknown_calls:
        status = "estimated"
    elif reported or estimated:
        status = "mixed"
    else:
        status = "unavailable" if unknown_calls else "zero_no_calls"
    return {
        "parent": {
            "calls_started": 0,
            "reported_tokens": 0,
            "estimated_tokens": 0,
            "note": "benchmark controller is a local Python process, not a model call",
        },
        "children": {
            "calls_started": int(accounting.get("calls_started") or 0),
            "calls_completed": int(accounting.get("calls_completed") or 0),
            "cache_hits": int(accounting.get("cache_hits") or 0),
            "input_tokens": input_counts,
            "output_tokens": output_counts,
        },
        "parent_plus_children": {
            "reported_tokens": reported,
            "estimated_tokens": estimated,
            "unknown_calls": unknown_calls,
            "counter_status": status,
        },
    }


def summarize_live_result(
    name: str,
    command_result: CommandResult,
    usage_path: Path,
    *,
    expected_workers: int,
    require_first_pass_oracle: bool,
) -> dict[str, Any]:
    try:
        payload = json.loads(command_result.stdout)
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError:
        payload = {}
    try:
        usage = json.loads(usage_path.read_text()) if usage_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        usage = {}
    accounting = payload.get("accounting") if isinstance(payload.get("accounting"), dict) else usage
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    lane_rows = []
    successful_oracles: list[bool] = []
    errors = []
    for result in results:
        if not isinstance(result, dict):
            continue
        answer = result.get("answer") if isinstance(result.get("answer"), str) else ""
        oracle_ok = live_oracle(answer) if result.get("ok") and answer else False
        if result.get("ok"):
            successful_oracles.append(oracle_ok)
        if not result.get("ok") and result.get("terminal") != "pruned":
            errors.append(
                f"{result.get('lane', 'unknown')}:{result.get('error', result.get('terminal'))}"
            )
        lane_rows.append(
            {
                "lane": result.get("lane"),
                "model": result.get("model"),
                "kind": result.get("kind"),
                "class": result.get("class"),
                "terminal": result.get("terminal"),
                "call_started": result.get("call_started"),
                "cached": bool(result.get("cached")),
                "wall_ms": result.get("ms"),
                "token_count_source": result.get("token_count_source"),
                "input_tokens": result.get("input_tokens"),
                "output_tokens": result.get("output_tokens"),
                "answer_sha256": sha256_text(answer) if answer else None,
                "answer_bytes": len(answer.encode("utf-8")),
                "oracle_pass": oracle_ok,
                "error": result.get("error"),
            }
        )
    first_pass = payload.get("first_pass") if isinstance(payload.get("first_pass"), dict) else {}
    all_successful_correct = bool(successful_oracles) and all(successful_oracles)
    if require_first_pass_oracle:
        quality_ok = (
            bool(first_pass.get("oracle"))
            and first_pass.get("winner_oracle_exit") == 0
            and bool(first_pass.get("winner"))
        )
    else:
        quality_ok = all_successful_correct
    complete = (
        command_result.returncode == 0
        and payload.get("status") == "ok"
        and int(payload.get("total") or 0) == expected_workers
        and int(payload.get("ok") or 0) == expected_workers
    )
    if require_first_pass_oracle:
        complete = command_result.returncode == 0 and payload.get("status") in {"ok", "partial"}
    if command_result.stderr:
        stderr_tail = compact_error(command_result.stderr)
        if stderr_tail:
            errors.append(f"stderr:{stderr_tail}")
    return {
        "name": name,
        "command_exit_code": command_result.returncode,
        "wall_ms": command_result.wall_ms,
        "timed_out": command_result.timed_out,
        "status": payload.get("status", "unparseable"),
        "selected_workers": (payload.get("lanes") or {}).get("selected"),
        "ok_workers": payload.get("ok"),
        "terminal_workers": len(lane_rows),
        "quality_oracle": "exact_six_field_json_equality",
        "quality_pass": quality_ok,
        "accepted": complete and quality_ok,
        "first_pass": first_pass,
        "team_tokens": usage_team_totals(accounting if isinstance(accounting, dict) else {}),
        "cost": {
            "estimated_cost_usd": accounting.get("estimated_cost_usd")
            if isinstance(accounting, dict)
            else None,
            "status": accounting.get("cost_status", "unavailable")
            if isinstance(accounting, dict)
            else "unavailable",
            "note": "llmadapter accounting only; no inferred invoice",
        },
        "workers": lane_rows,
        "wrapper_attempts": 1,
        "wrapper_retries": 0,
        "lane_internal_retries": "unavailable_not_emitted",
        "errors": errors,
        "usage_artifact": str(usage_path),
    }


def llmadapter_command(
    llmadapter_path: str,
    usage_path: Path,
    *,
    lanes: str,
    cap: int,
    deadline: int,
    no_cache: bool,
    first_pass_oracle: bool,
    max_tokens: int = 160,
) -> list[str]:
    command = [
        llmadapter_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        lanes,
        "--cap",
        str(cap),
        "--max-tokens",
        str(max_tokens),
        "--budget-tokens",
        "900",
        "--deadline-secs",
        str(deadline),
        "--contract",
        "json",
        "--usage-out",
        str(usage_path),
    ]
    if lanes == "cheap":
        command.extend(["--allow-remote", "--allow-paid"])
    if no_cache:
        command.append("--no-cache")
    if first_pass_oracle:
        oracle = (
            f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} "
            '--oracle-answer "$LLMADAPTER_ANSWER_PATH"'
        )
        command.extend(["--first-pass", "--oracle", oracle])
    return command


def run_live_arms(
    out_dir: Path,
    llmadapter_path: str | None,
    *,
    live_local: bool,
    live_cheap: bool,
    live_first_pass: bool,
    deadline: int,
) -> list[dict[str, Any]]:
    if not (live_local or live_cheap):
        return []
    if not llmadapter_path:
        return [
            {
                "name": "requested_live_arms",
                "accepted": False,
                "errors": ["llmadapter unavailable"],
                "provider_counter_status": "unavailable",
            }
        ]
    arms: list[dict[str, Any]] = []
    if live_local:
        with tempfile.TemporaryDirectory(prefix="workflow-cache-home-", dir=out_dir) as cache_home:
            local_env = os.environ.copy()
            local_env["HOME"] = cache_home
            for label in ("cold", "warm"):
                usage_path = out_dir / f"workflow_matrix_benchmark-usage-local-{label}.json"
                result = run_command(
                    llmadapter_command(
                        llmadapter_path,
                        usage_path,
                        lanes="local",
                        cap=1,
                        deadline=deadline,
                        max_tokens=500,
                        no_cache=False,
                        first_pass_oracle=False,
                    ),
                    input_text=LIVE_PROMPT,
                    env=local_env,
                    timeout=deadline + 15,
                )
                arms.append(
                    summarize_live_result(
                        f"local_single_{label}",
                        result,
                        usage_path,
                        expected_workers=1,
                        require_first_pass_oracle=False,
                    )
                )
    if live_cheap:
        usage_path = out_dir / "workflow_matrix_benchmark-usage-cheap-parallel.json"
        result = run_command(
            llmadapter_command(
                llmadapter_path,
                usage_path,
                lanes="cheap",
                cap=3,
                deadline=deadline,
                max_tokens=160,
                no_cache=True,
                first_pass_oracle=False,
            ),
            input_text=LIVE_PROMPT,
            timeout=deadline + 15,
        )
        arms.append(
            summarize_live_result(
                "cheap_parallel_three",
                result,
                usage_path,
                expected_workers=3,
                require_first_pass_oracle=False,
            )
        )
        if live_first_pass:
            usage_path = out_dir / "workflow_matrix_benchmark-usage-cheap-first-pass.json"
            result = run_command(
                llmadapter_command(
                    llmadapter_path,
                    usage_path,
                    lanes="cheap",
                    cap=3,
                    deadline=deadline,
                    max_tokens=160,
                    no_cache=True,
                    first_pass_oracle=True,
                ),
                input_text=LIVE_PROMPT,
                timeout=deadline + 15,
            )
            arms.append(
                summarize_live_result(
                    "cheap_parallel_oracle_first_pass",
                    result,
                    usage_path,
                    expected_workers=3,
                    require_first_pass_oracle=True,
                )
            )
    return arms


def fixture_manifest(fixtures: tuple[OperationFixture, ...]) -> list[dict[str, Any]]:
    return [
        {
            "name": fixture.name,
            "kind": fixture.kind,
            "bytes": len(fixture.raw.encode("utf-8")),
            "sha256": sha256_text(fixture.raw),
            "expected": fixture.expected,
            "source_exit_code": fixture.source_exit_code,
        }
        for fixture in fixtures
    ]


def write_fixtures(out_dir: Path, fixtures: tuple[OperationFixture, ...]) -> None:
    fixture_dir = out_dir / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    suffixes = {"incident": ".log", "orders": ".jsonl", "pytest": ".txt"}
    for fixture in fixtures:
        (fixture_dir / f"{fixture.name}{suffixes[fixture.kind]}").write_text(fixture.raw)


def git_commit() -> str | None:
    result = command_text(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None


def make_report(
    out_dir: Path,
    *,
    samples: int,
    live_local: bool,
    live_cheap: bool,
    live_first_pass: bool,
    deadline: int,
    llmadapter_path: str | None = None,
    rtk_path: str | None = None,
    reused_live: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fixtures = build_fixtures()
    llmadapter_path = llmadapter_path if llmadapter_path is not None else shutil.which("llmadapter")
    rtk_path = rtk_path if rtk_path is not None else shutil.which("rtk")
    components, matrix, rtk_details = offline_matrix(fixtures, rtk_path)
    new_live = run_live_arms(
        out_dir,
        llmadapter_path,
        live_local=live_local,
        live_cheap=live_cheap,
        live_first_pass=live_first_pass,
        deadline=deadline,
    )
    live_by_name = {
        str(item.get("name")): item for item in (reused_live or []) if isinstance(item, dict)
    }
    live_by_name.update(
        {str(item.get("name")): item for item in new_live if isinstance(item, dict)}
    )
    live = list(live_by_name.values())
    offline_accepted = all(item["accepted"] for item in components) and all(
        item["accepted"] for item in matrix
    )
    live_requested = bool(live)
    live_accepted = bool(live) and all(bool(item.get("accepted")) for item in live)
    return {
        "schema": "agent-token-saver.workflow-matrix-benchmark",
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repo": {"path": str(ROOT), "commit": git_commit()},
        "method": {
            "local_tokens": "ceil(UTF-8 bytes / 4) proxy; not provider billing",
            "provider_tokens": "llmadapter-emitted only; reported, estimated, and unknown separate",
            "wall_time": "perf_counter; deterministic shapes report median and p95",
            "quality": "exact operation results; live six-field JSON equality",
            "cost": "unavailable unless llmadapter emits it; no proxy-to-billing conversion",
        },
        "fixtures": fixture_manifest(fixtures),
        "inventory": inventory_tools(llmadapter_path, rtk_path),
        "components": components,
        "offline_matrix": matrix,
        "worker_shapes": benchmark_shapes(fixtures, samples),
        "rtk": rtk_details,
        "live_arms": live,
        "tier_verify_boundary": {
            "legacy_tier_run": "not_run",
            "reason": "ask-v2 rejects --tier and legacy tier lacks complete aggregate/verifier accounting",
            "real_oracle_run": any(
                item.get("name") == "cheap_parallel_oracle_first_pass" for item in live
            ),
            "oracle": "llmadapter first-pass exact JSON gate",
        },
        "acceptance": {
            "offline_required": True,
            "offline_accepted": offline_accepted,
            "live_requested": live_requested,
            "live_accepted": live_accepted if live_requested else None,
            "overall_accepted": offline_accepted and (live_accepted if live_requested else True),
        },
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Token Saver workflow matrix benchmark",
        "",
        "Three operations. Fixtures and exact answers are deterministic.",
        "An optimized arm passes only when every result survives its oracle; local UTF-8/4 proxies remain separate from provider counters and billing.",
        "",
        "## Offline combinations",
        "",
        "| Arm | Worker input proxy | Worker output proxy | Parent + children | Calls | Cache hits | Accepted |",
        "|---|---:|---:|---:|---:|---:|:--:|",
    ]
    for row in report["offline_matrix"]:
        lines.append(
            f"| {row['name']} | {row['worker_input_proxy_tokens']:,} | "
            f"{row['worker_output_proxy_tokens']:,} | "
            f"{row['parent_plus_children_proxy_tokens']:,} | {row['calls_started']} | "
            f"{row['cache_hits']} | {'yes' if row['accepted'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Components",
            "",
            "| Component | Accepted | Detail |",
            "|---|:--:|---|",
        ]
    )
    for component in report["components"]:
        if component["name"].startswith("exact_projection"):
            detail = (
                f"{component['raw_proxy_tokens']:,} -> {component['projected_proxy_tokens']:,} "
                f"proxy tokens; {component['saved_percent']:.2f}%"
            )
        elif component["name"].startswith("rtk_filter"):
            detail = f"{component['status']}; adopted={component['adopted']}"
        else:
            detail = (
                f"cold {component['cold']['misses']} misses; warm {component['warm']['hits']} hits"
            )
        lines.append(
            f"| {component['name']} | {'yes' if component['accepted'] else 'no'} | {detail} |"
        )
    lines.extend(
        [
            "",
            "## Worker shape",
            "",
            "| Shape | Workers | Median ms | p95 ms | Accepted |",
            "|---|---:|---:|---:|:--:|",
        ]
    )
    for name, row in report["worker_shapes"].items():
        lines.append(
            f"| {name} | {row['workers']} | {row['wall_ms_median']:.3f} | "
            f"{row['wall_ms_p95']:.3f} | {'yes' if row['accepted'] else 'no'} |"
        )
    lines.extend(["", "## Live llmadapter arms", ""])
    if not report["live_arms"]:
        lines.append("Not requested.")
    else:
        lines.extend(
            [
                "| Arm | Workers ok | Wall ms | Reported tokens | Estimated tokens | Unknown calls | Accepted |",
                "|---|---:|---:|---:|---:|---:|:--:|",
            ]
        )
        for arm in report["live_arms"]:
            total = arm.get("team_tokens", {}).get("parent_plus_children", {})
            lines.append(
                f"| {arm['name']} | {arm.get('ok_workers', 0) or 0} | "
                f"{arm.get('wall_ms', 0):.3f} | {total.get('reported_tokens', 0)} | "
                f"{total.get('estimated_tokens', 0)} | {total.get('unknown_calls', 0)} | "
                f"{'yes' if arm.get('accepted') else 'no'} |"
            )
        blocked = [arm for arm in report["live_arms"] if not arm.get("accepted")]
        if blocked:
            lines.extend(["", "## Live blockers", ""])
            for arm in blocked:
                errors = "; ".join(arm.get("errors") or ["unspecified failure"])
                lines.append(f"- `{arm['name']}`: {errors}.")
    inventory = report["inventory"]
    llm = inventory["llmadapter"]
    lines.extend(
        [
            "",
            "## Inventory and boundaries",
            "",
            f"- Existing token-stack matrix: `{inventory['token_stack_matrix']['path']}` "
            f"(sha256 `{inventory['token_stack_matrix']['sha256']}`).",
            f"- llmadapter: {llm['lanes'].get('total', 0)} lanes; doctor exit "
            f"{llm['doctor_exit_code']}; misses: {len(llm['doctor_misses'])}.",
            f"- RTK: `{inventory['rtk']['version'] or 'unavailable'}`.",
            "- Legacy tier not run: ask-v2 rejects it and legacy aggregate/verifier usage is incomplete.",
            "- Parallelism is a wall-time shape. It is not counted as a token or money saving.",
            "- Retries: wrapper retries are zero; provider-internal retries are not emitted.",
            f"- Gate: {'accepted' if report['acceptance']['overall_accepted'] else 'blocked'}.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(out_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "workflow_matrix_benchmark.json"
    md_path = out_dir / "workflow_matrix_benchmark.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    md_path.write_text(markdown(report))
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--live-local", action="store_true")
    parser.add_argument("--live-cheap", action="store_true")
    parser.add_argument("--live-first-pass", action="store_true")
    parser.add_argument("--reuse-live", type=Path)
    parser.add_argument("--deadline-secs", type=int, default=120)
    parser.add_argument("--oracle-answer", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.oracle_answer:
        try:
            answer = args.oracle_answer.read_text()
        except OSError:
            return 1
        return 0 if live_oracle(answer) else 1
    if args.out_dir is None:
        raise SystemExit("--out-dir is required")
    if args.samples < 1 or args.samples > 100:
        raise SystemExit("--samples must be in 1..100")
    if args.deadline_secs < 10 or args.deadline_secs > 600:
        raise SystemExit("--deadline-secs must be in 10..600")
    if args.live_first_pass and not args.live_cheap:
        raise SystemExit("--live-first-pass requires --live-cheap")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    fixtures = build_fixtures()
    write_fixtures(args.out_dir, fixtures)
    reused_live: list[dict[str, Any]] = []
    if args.reuse_live:
        try:
            previous = json.loads(args.reuse_live.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"--reuse-live unreadable: {exc}") from exc
        if previous.get("schema") != "agent-token-saver.workflow-matrix-benchmark":
            raise SystemExit("--reuse-live has the wrong schema")
        reused_live = previous.get("live_arms") or []
        if not isinstance(reused_live, list):
            raise SystemExit("--reuse-live live_arms must be a list")
    report = make_report(
        args.out_dir,
        samples=args.samples,
        live_local=args.live_local,
        live_cheap=args.live_cheap,
        live_first_pass=args.live_first_pass,
        deadline=args.deadline_secs,
        reused_live=reused_live,
    )
    json_path, md_path = write_report(args.out_dir, report)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), **report["acceptance"]}))
    return 0 if report["acceptance"]["overall_accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
