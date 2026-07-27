"""Executable contract for the Claude Agent pre-tool worker capsule hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integration" / "hooks" / "agent-worker-capsule.py"


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
            "tool_input": {"description": "Trace imports for this source function and fix its test."},
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
