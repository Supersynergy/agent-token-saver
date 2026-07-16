#!/usr/bin/env python3
"""Fail-open prompt hook: lazy-load at most one primary routed skill."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from xml.sax.saxutils import quoteattr

TRIVIAL = re.compile(
    r"^\s*(?:ok|okay|yes|no|ja|nein|thanks|danke|continue|weiter|passt|done|fertig)[.!?\s]*$",
    re.IGNORECASE,
)
ATS_TRIGGER = re.compile(
    r"\b(?:token(?:s)?|context\s+(?:bloat|budget|compression|saving)|"
    r"skill\s+router|mcp\s+schema|noisy\s+(?:log|output)|"
    r"compress\s+(?:logs?|output|context)|rtk)\b",
    re.IGNORECASE,
)
EXPLICIT_SKILL = re.compile(r"\$[a-z0-9][a-z0-9_.-]*", re.IGNORECASE)
FRONTMATTER_NAME = re.compile(r"^name:\s*['\"]?([^'\"\s]+)", re.MULTILINE)


def audit(event: str, reason: str, name: str = "") -> None:
    """Write rejection telemetry without prompts, commands or routed paths."""
    try:
        state = Path.home() / ".local" / "state" / "agent-token-saver"
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        state.chmod(0o700)
        path = state / "hook-events.jsonl"
        payload = json.dumps(
            {"ts": int(time.time()), "event": event, "reason": reason, "name": name},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            os.write(descriptor, (payload + "\n").encode("utf-8"))
        finally:
            os.close(descriptor)
    except OSError:
        pass


def owned_nonwritable_file(path: Path) -> bool:
    try:
        metadata = path.stat()
    except OSError:
        return False
    return path.is_file() and metadata.st_uid == os.getuid() and not metadata.st_mode & 0o022


def allowed_skill_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".agent-token-saver" / "skills",
        home / ".agents" / "skills",
        home / ".codex" / "skills",
        home / ".claude" / "skills",
        home / ".claude" / "cts" / "skills",
        home / ".hermes" / "skills",
        home / ".gg" / "skills",
        Path.cwd() / ".agents" / "skills",
    ]
    roots.extend(
        Path(value).expanduser()
        for value in os.environ.get("ATS_SKILL_ROOTS", "").split(os.pathsep)
        if value
    )
    resolved: list[Path] = []
    for root in roots:
        try:
            candidate = root.resolve()
        except OSError:
            continue
        if candidate not in resolved:
            resolved.append(candidate)
    return resolved


def routed_skill(name: str, raw_path: str) -> Path | None:
    candidate = Path(raw_path).expanduser()
    if candidate.name != "SKILL.md":
        audit("route_rejected", "not_skill_md", name)
        return None
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        audit("route_rejected", "missing_path", name)
        return None
    if not any(resolved.is_relative_to(root) for root in allowed_skill_roots()):
        audit("route_rejected", "outside_allowed_roots", name)
        return None
    if not owned_nonwritable_file(resolved):
        audit("route_rejected", "unsafe_owner_or_mode", name)
        return None
    try:
        header = resolved.read_text(errors="replace")[:4096]
    except OSError:
        audit("route_rejected", "unreadable", name)
        return None
    lines = header.splitlines()
    frontmatter = ""
    if lines and lines[0].strip() == "---":
        try:
            closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
            frontmatter = "\n".join(lines[1:closing])
        except StopIteration:
            pass
    match = FRONTMATTER_NAME.search(frontmatter)
    if not match or match.group(1) != name:
        audit("route_rejected", "frontmatter_name_mismatch", name)
        return None
    return resolved


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
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if owned_nonwritable_file(resolved) and (
            resolved.is_relative_to(Path.home().resolve())
            or resolved.is_relative_to(Path.cwd().resolve())
        ):
            return resolved
        audit("router_rejected", "unsafe_owner_mode_or_root")
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


def emit_token_saver_fallback(*, load_skill: bool = False) -> bool:
    fallback = (
        Path.home()
        / ".agent-token-saver"
        / "skills"
        / "agent-token-saver"
        / "SKILL.md"
    )
    fallback = routed_skill("agent-token-saver", str(fallback))
    if fallback is None:
        return False
    if load_skill:
        emit(
            "<token_stack_route>"
            f"Primary skill={fallback}. Read it completely. "
            "Keep raw data outside model context and preserve retrieval pointers."
            "</token_stack_route>"
        )
    else:
        emit(
            f"<token_stack_policy canonical={quoteattr(str(fallback))}>"
            "Automatic compact policy; do not read SKILL.md for this route. "
            "Put filtering or aggregation in the first command so noisy raw output never enters "
            "context; use exact local search, deterministic projection, or rtk for a supported "
            "noisy command; keep raw data outside model context; preserve the task oracle."
            "</token_stack_policy>"
        )
    return True


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    prompt = str(event.get("prompt") or "").strip()
    if len(prompt) < 10 or TRIVIAL.fullmatch(prompt):
        return 0
    explicit_skill = bool(EXPLICIT_SKILL.search(prompt))
    explicit_token_saver = bool(
        re.search(r"\$agent-token-saver\b", prompt, re.IGNORECASE)
    )
    if ATS_TRIGGER.search(prompt) and not explicit_skill and emit_token_saver_fallback():
        return 0
    router = router_path()
    if not router:
        if ATS_TRIGGER.search(prompt):
            emit_token_saver_fallback(load_skill=explicit_token_saver)
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
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        audit("router_failed", type(error).__name__)
        return 0
    if result.returncode == 0 and isinstance(selected, list) and selected:
        winner = selected[0]
        if isinstance(winner, dict):
            name = str(winner.get("name") or "").strip()
            if name == "agent-token-saver" and emit_token_saver_fallback(
                load_skill=explicit_token_saver
            ):
                return 0
            path = routed_skill(name, str(winner.get("path") or "")) if name else None
            if path is not None:
                emit(
                    f"<skill_route name={quoteattr(name)} path={quoteattr(str(path))}>"
                    "Read this SKILL.md completely before acting. "
                    "Do not auto-load a second skill."
                    "</skill_route>"
                )
                return 0
    if ATS_TRIGGER.search(prompt) and not explicit_skill:
        emit_token_saver_fallback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
