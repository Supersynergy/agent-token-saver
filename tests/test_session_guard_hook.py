from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integration" / "hooks" / "token-session-guard.py"
LEDGER = ROOT / "scripts" / "full_context_ledger.py"


def run_hook_for_transcript(tmp_path: Path, transcript: Path, *, ledger: Path = LEDGER):
    home = tmp_path / "home"
    state = tmp_path / "state"
    event = {
        "hook_event_name": "Stop",
        "session_id": "fixture-session",
        "transcript_path": str(transcript),
    }
    env = {
        **os.environ,
        "HOME": str(home),
        "ATS_LEDGER_PATH": str(ledger),
        "ATS_GUARD_STATE_DIR": str(state),
    }
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result, state


def run_hook(tmp_path: Path, records: list[dict], *, transcript_mode: int = 0o600):
    home = tmp_path / "home"
    transcript = home / ".codex" / "sessions" / "run.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    transcript.chmod(transcript_mode)
    return run_hook_for_transcript(tmp_path, transcript)


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
    saved = json.loads(latest.read_text())
    assert saved["schema_version"] == 2
    assert saved["cursor"]["byte_offset"] > 0
    assert "run.jsonl" not in latest.read_text()
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
    assert "warm-handoff" in payload["systemMessage"]
    assert "300-700-token" in payload["systemMessage"]
    assert "test checklist" in payload["systemMessage"]
    assert "decision" not in payload
    assert "continue" not in payload
    assert json.loads((state / "session-guard-latest.json").read_text())["action"] == (
        "checkpoint_required"
    )


def test_guard_incremental_append_matches_full_replay(tmp_path: Path) -> None:
    home = tmp_path / "home"
    transcript = home / ".codex" / "sessions" / "run.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(token_record(1_000)) + "\n")
    transcript.chmod(0o600)
    first, state = run_hook_for_transcript(tmp_path, transcript)
    assert first.returncode == 0

    with transcript.open("a") as handle:
        handle.write(json.dumps(token_record(10_000_001)) + "\n")
    second, _ = run_hook_for_transcript(tmp_path, transcript)

    assert "context guard: warn" in json.loads(second.stdout)["systemMessage"]
    saved = json.loads((state / "session-guard-latest.json").read_text())
    assert saved["action"] == "warn"
    assert saved["accumulator"]["latest_codex_total"]["reported_total_tokens"] == 10_000_001


def test_guard_truncation_falls_back_and_rewrites_cursor(tmp_path: Path) -> None:
    home = tmp_path / "home"
    transcript = home / ".codex" / "sessions" / "run.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(token_record(10_000_001)) + "\n")
    transcript.chmod(0o600)
    _, state = run_hook_for_transcript(tmp_path, transcript)
    transcript.write_text(json.dumps(token_record(1_000)) + "\n")

    result, _ = run_hook_for_transcript(tmp_path, transcript)

    assert result.returncode == 0
    saved = json.loads((state / "session-guard-latest.json").read_text())
    assert saved["action"] == "continue"
    assert saved["cursor"]["byte_offset"] == transcript.stat().st_size


def test_guard_import_failure_uses_subprocess_action_and_v1_state(tmp_path: Path) -> None:
    home = tmp_path / "home"
    transcript = home / ".codex" / "sessions" / "run.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(token_record(10_000_001)) + "\n")
    transcript.chmod(0o600)
    executable_ledger = tmp_path / "agent-token-ledger"
    executable_ledger.write_bytes(LEDGER.read_bytes())
    executable_ledger.chmod(0o600)

    result, state = run_hook_for_transcript(tmp_path, transcript, ledger=executable_ledger)

    assert result.returncode == 0
    assert "context guard: warn" in json.loads(result.stdout)["systemMessage"]
    saved = json.loads((state / "session-guard-latest.json").read_text())
    assert saved["schema_version"] == 1
    assert saved["action"] == "warn"
    assert "cursor" not in saved
    assert "accumulator" not in saved


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
        [sys.executable, str(HOOK)],
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


def test_guard_prunes_stale_session_state_but_keeps_recent(tmp_path: Path) -> None:
    """One state file per session with no expiry fills the user's home."""
    state = tmp_path / "state"
    state.mkdir()
    stale = state / "session-guard-old.json"
    recent = state / "session-guard-new.json"
    unrelated = state / "hook-events.jsonl"
    for path in (stale, recent, unrelated):
        path.write_text("{}")
    old = time.time() - 30 * 24 * 3_600
    os.utime(stale, (old, old))
    os.utime(unrelated, (old, old))

    result, _ = run_hook(tmp_path, [token_record(1_000)])

    assert result.returncode == 0
    assert not stale.exists()
    assert recent.exists()
    assert unrelated.exists()
    assert (state / "session-guard-latest.json").exists()
