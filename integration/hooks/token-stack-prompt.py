#!/usr/bin/env python3
"""Fail-open prompt hook: lazy-load at most one primary routed skill."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

TRIVIAL = re.compile(
    r"^\s*(?:ok|okay|yes|no|ja|nein|thanks|danke|continue|weiter|passt|done|fertig)[.!?\s]*$",
    re.IGNORECASE,
)
ATS_TRIGGER = re.compile(
    r"\b(?:token(?:s)?|context\s+(?:bloat|budget|compression|saving)|"
    r"skill\s+router|mcp\s+schema|noisy\s+(?:log|output)|"
    r"compress\s+(?:logs?|output|context)|rtk|synapse)\b",
    re.IGNORECASE,
)


def router_path() -> Path | None:
    candidates = [
        os.environ.get("ATS_ROUTER", ""),
        "~/.local/bin/si",
        "~/.local/bin/agent-skill-route",
        "~/.codex/skills/agent-token-saver-skill-router/scripts/agent_token_saver.py",
        "~/.claude/skills/agent-token-saver-skill-router/scripts/agent_token_saver.py",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return path
    return None


def emit(context: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        },
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    prompt = str(event.get("prompt") or "").strip()
    router = router_path()
    if len(prompt) < 10 or TRIVIAL.fullmatch(prompt):
        return 0
    if not router:
        fallback = (
            Path.home()
            / ".agent-token-saver"
            / "skills"
            / "agent-token-saver"
            / "SKILL.md"
        )
        if fallback.is_file() and ATS_TRIGGER.search(prompt):
            emit(
                "<token_stack_route>"
                f"Primary skill={fallback}. Read it completely. "
                "Keep raw data outside model context and preserve retrieval pointers."
                "</token_stack_route>"
            )
        return 0
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(router),
                "route",
                prompt[:2000],
                "--max",
                "1",
                "--strict",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        payload = json.loads(result.stdout)
        selected = payload.get("selected") or []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return 0
    if result.returncode != 0 or not isinstance(selected, list) or not selected:
        return 0
    winner = selected[0]
    if not isinstance(winner, dict):
        return 0
    name = str(winner.get("name") or "").strip()
    path = Path(str(winner.get("path") or ""))
    if not name or not path.is_file():
        return 0
    emit(
        f"<skill_route name={quoteattr(name)} path={quoteattr(str(path))}>"
        "Read this SKILL.md completely before acting. "
        "Do not auto-load a second skill."
        "</skill_route>"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
