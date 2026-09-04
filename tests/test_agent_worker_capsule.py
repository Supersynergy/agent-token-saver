"""Executable contract for the Claude Agent pre-tool worker capsule hook."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integration" / "hooks" / "agent-worker-capsule.py"
# Read the canonical version instead of hardcoding it; test_skill_doc_drift
# already proves every release site agrees, so a bump stays a one-line change.
VERSION = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)
CONTRACT = f"worker contract (v{VERSION})"


def run_hook(tmp_path: Path, payload: dict[object, object]) -> dict[object, object]:
    env = os.environ.copy()
    env["ATS_CAPSULE_STATE_DIR"] = str(tmp_path / "state")
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout else {}


def context(output: dict[object, object]) -> str:
    return str(output["hookSpecificOutput"]["additionalContext"])


def test_source_worker_gets_one_scoped_tool_hint_and_handoff_contract(tmp_path: Path) -> None:
    output = run_hook(
        tmp_path,
        {
            "tool_name": "Agent",
            "session_id": "source-route",
            "tool_input": {
                "description": "Trace imports for this source function and fix its test."
            },
        },
    )

    message = context(output)
    assert "Tool lane: local source" in message
    assert "scoped `tilth --budget 4000`" in message
    assert "STATUS: PASS|FAIL|BLOCKED" in message
    assert "HANDOFF: none" in message
    assert "fresh external fact" not in message


def test_graph_route_wins_over_generic_source_terms(tmp_path: Path) -> None:
    output = run_hook(
        tmp_path,
        {
            "tool_name": "Agent",
            "session_id": "graph-route",
            "tool_input": {"prompt": "Find callers and impact graph for this code symbol."},
        },
    )

    message = context(output)
    assert "Tool lane: impact graph" in message
    assert "graphify query" in message
    assert "Tool lane: local source" not in message


def test_precontracted_capsule_gets_only_compact_delta(tmp_path: Path) -> None:
    output = run_hook(
        tmp_path,
        {
            "tool_name": "Agent",
            "session_id": "precontracted",
            "tool_input": {
                "prompt": (
                    "Objective: trace the parser failure.\n"
                    "Scope: src/parser.py and tests/test_parser.py.\n"
                    "Oracle: pytest tests/test_parser.py exits 0.\n"
                    "Limits: at most 3 tries; do not edit unrelated files.\n"
                    "Return: STATUS, exact evidence path and exit code in <=500 tokens."
                )
            },
        },
    )

    message = context(output)
    assert "capsule accepted" in message
    assert "preserve its objective, scope and oracle" in message
    assert CONTRACT not in message
    assert "Tool lane: local source" in message
    assert len(message.encode("utf-8")) < 700


def test_incomplete_capsule_keeps_full_contract(tmp_path: Path) -> None:
    output = run_hook(
        tmp_path,
        {
            "tool_name": "Agent",
            "session_id": "incomplete",
            "tool_input": {"prompt": "Objective: inspect this source file. Scope: src/parser.py."},
        },
    )

    message = context(output)
    assert CONTRACT in message
    assert "STATUS: PASS|FAIL|BLOCKED" in message


def test_empty_capsule_fields_keep_full_contract(tmp_path: Path) -> None:
    output = run_hook(
        tmp_path,
        {
            "tool_name": "Agent",
            "session_id": "empty-fields",
            "tool_input": {
                "prompt": (
                    "Objective: inspect the parser.\n"
                    "Scope:\n"
                    "Oracle: pytest exits 0.\n"
                    "Limits: at most 3 tries.\n"
                    "Return: STATUS and evidence."
                )
            },
        },
    )

    message = context(output)
    assert CONTRACT in message
    assert "capsule accepted" not in message


def test_capsule_contract_words_do_not_override_objective_route(tmp_path: Path) -> None:
    output = run_hook(
        tmp_path,
        {
            "tool_name": "Agent",
            "session_id": "fresh-capsule",
            "tool_input": {
                "prompt": (
                    "Objective: read the current API documentation for this package.\n"
                    "Scope: official package documentation.\n"
                    "Oracle: return the exact version and command exit code.\n"
                    "Limits: at most 3 tries.\n"
                    "Return: STATUS and evidence in <=500 tokens."
                )
            },
        },
    )

    message = context(output)
    assert "Tool lane: fresh external fact" in message
    assert "Tool lane: local source" not in message


def test_non_agent_emits_nothing(tmp_path: Path) -> None:
    assert run_hook(tmp_path, {"tool_name": "Bash", "session_id": "other"}) == {}


def test_fourth_spawn_keeps_route_and_warns(tmp_path: Path) -> None:
    payload = {
        "tool_name": "Agent",
        "session_id": "fourth",
        "tool_input": {"task": "Read the current API documentation."},
    }
    for _ in range(3):
        run_hook(tmp_path, payload)
    message = context(run_hook(tmp_path, payload))

    assert "Tool lane: fresh external fact" in message
    assert "primary-source artifact" in message
    assert "superweb" not in message
    assert "spawn #4" in message
