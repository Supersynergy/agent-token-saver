from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integration" / "hooks" / "token-session-guard.py"
LEDGER = ROOT / "scripts" / "full_context_ledger.py"


def run_hook(tmp_path: Path, records: list[dict], *, transcript_mode: int = 0o600):
    home = tmp_path / "home"
    transcript = home / ".codex" / "sessions" / "run.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    transcript.chmod(transcript_mode)
    state = tmp_path / "state"
    event = {
        "hook_event_name": "Stop",
        "session_id": "fixture-session",
        "transcript_path": str(transcript),
    }
    env = {
        **os.environ,
        "HOME": str(home),
        "ATS_LEDGER_PATH": str(LEDGER),
        "ATS_GUARD_STATE_DIR": str(state),
    }
    result = subprocess.run(
        ["python3", str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result, state


def token_record(total: int) -> dict:
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": total - 100,
                    "cached_input_tokens": 0,
                    "output_tokens": 100,
                    "total_tokens": total,
                }
            },
        },
    }


def test_guard_is_silent_and_persists_private_state_below_threshold(tmp_path: Path) -> None:
    result, state = run_hook(tmp_path, [token_record(1_000)])

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
    latest = state / "session-guard-latest.json"
    assert json.loads(latest.read_text())["action"] == "continue"
    assert latest.stat().st_mode & 0o077 == 0
    assert state.stat().st_mode & 0o077 == 0


def test_guard_warns_once_per_session_and_never_auto_continues(tmp_path: Path) -> None:
    first, _ = run_hook(tmp_path, [token_record(10_000_001)])
    second, _ = run_hook(tmp_path, [token_record(10_000_001)])

    payload = json.loads(first.stdout)
    assert "context guard: warn" in payload["systemMessage"]
    assert "decision" not in payload
    assert json.loads(second.stdout) == {}


def test_guard_escalates_to_checkpoint_without_blocking_stop(tmp_path: Path) -> None:
    records = [
        token_record(25_000_001),
        {"type": "response_item", "payload": {"type": "compaction"}},
        {"type": "response_item", "payload": {"type": "compaction"}},
    ]
    result, state = run_hook(tmp_path, records)

    payload = json.loads(result.stdout)
    assert "checkpoint_required" in payload["systemMessage"]
    assert "decision" not in payload
    assert "continue" not in payload
    assert json.loads((state / "session-guard-latest.json").read_text())["action"] == (
        "checkpoint_required"
    )


def test_guard_rejects_world_writable_transcript(tmp_path: Path) -> None:
    result, state = run_hook(tmp_path, [token_record(25_000_001)], transcript_mode=0o666)

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
    assert not state.exists()


def test_guard_rejects_symlink_escape(tmp_path: Path) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "outside.jsonl"
    outside.write_text(json.dumps(token_record(25_000_001)) + "\n")
    outside.chmod(0o600)
    link = home / ".codex" / "sessions" / "escape.jsonl"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    event = {"session_id": "escape", "transcript_path": str(link)}
    result = subprocess.run(
        ["python3", str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "ATS_LEDGER_PATH": str(LEDGER),
            "ATS_GUARD_STATE_DIR": str(tmp_path / "state"),
        },
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
    assert not (tmp_path / "state").exists()
