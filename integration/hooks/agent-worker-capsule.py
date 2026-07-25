#!/usr/bin/env python3
"""PreToolUse hook: enforce the agent-token-saver worker contract on spawns.

Injects the capsule rules from SKILL.md ("Agent teams") into every subagent
spawn and counts spawns per session so the documented default maximum of three
independent workers is visible instead of implicit.

Contract: fail-open · non-destructive · no network · no deps.
Wire it as PreToolUse with matcher "Agent" (Claude Code) — the payload is read
from stdin as JSON, output is a single JSON object on stdout.

Env:
  ATS_TEAM_MAX_WORKERS  — soft cap before the warning fires (default 3)
  ATS_CAPSULE_STATE_DIR — spawn-counter dir (default ~/.agent-token-saver/cache)
  ATS_CAPSULE_OFF=1     — disable entirely

Verify:  echo '{"tool_name":"Agent","session_id":"t"}' | agent-worker-capsule.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

CONTRACT = (
    "agent-token-saver worker contract (v4.21.0): give this worker ONE closed "
    "objective and a 300-700 token capsule with exact paths, constraints and a "
    "PASS/FAIL oracle. Never pass the controller's transcript or skill catalog. "
    "Zero or one routed primary skill. Max 3 attempts, result <=500 tokens "
    "pointing at evidence (path/command/exit code). Workers run on Sonnet, the "
    "controller keeps Opus/Fable for planning and verification. Spawn parallel "
    "workers in ONE message. If the check is small or overlaps existing "
    "context, do it inline instead — a spawn costs a full system prompt."
)


def state_dir() -> Path:
    raw = os.environ.get("ATS_CAPSULE_STATE_DIR") or "~/.agent-token-saver/cache"
    return Path(raw).expanduser()


def bump(session_id: str) -> int:
    """Count spawns for this session. Returns the new count, 0 on any failure."""
    try:
        directory = state_dir()
        directory.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64]
        path = directory / f"spawns-{safe or 'unknown'}.json"
        count, started = 0, time.time()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                count = int(data.get("count", 0))
                started = float(data.get("started", started))
                if time.time() - started > 86400:  # stale session file
                    count, started = 0, time.time()
            except (ValueError, OSError):
                count, started = 0, time.time()
        count += 1
        path.write_text(json.dumps({"count": count, "started": started}), encoding="utf-8")
        return count
    except OSError:
        return 0


def main() -> int:
    if os.environ.get("ATS_CAPSULE_OFF") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") != "Agent":
        return 0

    try:
        max_workers = int(os.environ.get("ATS_TEAM_MAX_WORKERS", "3"))
    except ValueError:
        max_workers = 3

    context = CONTRACT
    count = bump(str(payload.get("session_id", "")))
    if count > max_workers > 0:
        context += (
            f" NOTE: this is spawn #{count} this session, above the measured "
            f"default of {max_workers} independent workers — justify it or "
            "fold the work into an existing worker. Sum parent + children in "
            "`agent-token-ledger` before claiming a saving."
        )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        },
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # fail-open: a hook must never block the agent
        sys.exit(0)
