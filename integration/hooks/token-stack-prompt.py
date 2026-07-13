#!/usr/bin/env python3
"""Fail-open prompt hook: lazy-load at most three routed skills."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TRIVIAL = re.compile(
    r"^\s*(?:ok|okay|yes|no|ja|nein|thanks|danke|continue|weiter|passt|done|fertig)[.!?\s]*$",
    re.IGNORECASE,
)
LOAD_LINE = re.compile(r"^- ([^:]+): .*\((/[^)]+/SKILL\.md)\)$")


def router_path() -> Path | None:
    candidates = [
        os.environ.get("ATS_ROUTER", ""),
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
    if not router or len(prompt) < 10 or TRIVIAL.fullmatch(prompt):
        return 0
    try:
        result = subprocess.run(
            [sys.executable, str(router), "route", prompt[:2000]],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    selected: list[tuple[str, str]] = []
    for raw_line in result.stdout.splitlines():
        match = LOAD_LINE.match(raw_line.strip())
        if match:
            selected.append((match.group(1).replace(" ★", ""), match.group(2)))
        if len(selected) == 3:
            break
    if selected:
        routes = "; ".join(f"{name}={path}" for name, path in selected)
        emit(
            "<token_stack_route>"
            f"Load only these routed skills: {routes}. "
            "Read each selected SKILL.md completely; max 3. "
            "Use RTK for supported noisy shell output."
            "</token_stack_route>"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
