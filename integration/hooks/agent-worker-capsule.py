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
import re
import sys
import time
from pathlib import Path

CONTRACT = (
    "agent-token-saver worker contract (v4.22.0): give this worker ONE closed "
    "objective and a 300-700 token capsule with exact paths, constraints and a "
    "PASS/FAIL oracle. Never pass the controller's transcript or skill catalog. "
    "Zero or one routed primary skill. Max 3 attempts, result <=500 tokens "
    "pointing at evidence (path/command/exit code). Workers run on Sonnet, the "
    "controller keeps Opus/Fable for planning and verification. Spawn parallel "
    "workers in ONE message. If the check is small or overlaps existing "
    "context, do it inline instead — a spawn costs a full system prompt."
)

RESULT_CONTRACT = (
    " Return compactly: STATUS: PASS|FAIL|BLOCKED; EVIDENCE: exact path or "
    "command+exit; HANDOFF: none or one precise question. Do not chat with "
    "peer workers or repeat their work; the controller may route one targeted "
    "handoff only when HANDOFF is non-none."
)

COMPACT_CONTRACT = (
    "agent-token-saver capsule accepted: preserve its objective, scope and oracle; "
    "never add the parent transcript; use zero or one skill and at most 3 attempts. "
    "Return <=500 tokens with STATUS: PASS|FAIL|BLOCKED, exact EVIDENCE and at most "
    "one HANDOFF. The controller keeps the final decision."
)

CAPSULE_FIELDS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        rf"\b(?:{field})\b[\"']?[ \t]*[:=][ \t]*[\"']?([^\n,}}\"']+)",
        re.IGNORECASE,
    )
    for field in (
        r"objective|goal|ziel",
        r"scope|inputs?",
        r"oracle|dod|definition[ _-]of[ _-]done",
        r"limits?|constraints?",
        r"return|result|output",
    )
)
OBJECTIVE_FIELD = re.compile(
    r"\b(?:objective|goal|ziel)\b[\"']?[ \t]*[:=][ \t]*[\"']?([^\n,}}\"']+)",
    re.IGNORECASE,
)
SCOPE_FIELD = re.compile(
    r"\b(?:scope|inputs?)\b[\"']?[ \t]*[:=][ \t]*[\"']?([^\n,}}\"']+)",
    re.IGNORECASE,
)

# One task-specific hint is cheaper and less error-prone than handing every
# worker a global tool catalog. The hook only suggests a lane; execution stays
# with the worker/controller.
ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:caller|callee|impact|dependency|dependencies|graph)\b", re.I),
        " Tool lane: impact graph. Start `synx ground`; use `graphify query` only "
        "when this repo already has graphify-out/graph.json.",
    ),
    (
        re.compile(r"\b(?:log|stack ?trace|stderr|stdout|noisy output)\b", re.I),
        " Tool lane: noisy output. Bound the command first; use `rtk` for supported "
        "projections and preserve the raw artifact outside prompt context.",
    ),
    (
        re.compile(
            r"\b(?:files?|source|src|code|functions?|tests?|bug|repo|repository|import|symbol)\b",
            re.I,
        ),
        " Tool lane: local source. Start with exact `rg`; for structural symbols or "
        "imports use scoped `tilth --budget 4000` on the concrete project only.",
    ),
    (
        re.compile(
            r"\b(?:fresh|latest|current|documentation|docs|research|recherche|api|package)\b", re.I
        ),
        " Tool lane: fresh external fact. Ask the controller for one bounded primary-source "
        "artifact before making a version, API, price, or policy claim.",
    ),
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


def task_text(payload: dict[object, object]) -> str:
    """Extract bounded Agent input without reflecting a full parent transcript."""
    raw = payload.get("tool_input", {})
    if isinstance(raw, dict):
        parts = []
        for key in (
            "description",
            "prompt",
            "task",
            "instructions",
            "objective",
            "scope",
            "oracle",
            "limits",
            "return",
        ):
            value = raw.get(key)
            if isinstance(value, str):
                parts.append(f"{key}: {value}")
        return "\n".join(parts)[:4_000]
    return raw[:4_000] if isinstance(raw, str) else ""


def has_complete_capsule(payload: dict[object, object]) -> bool:
    """Recognize an explicit five-field capsule; false negatives keep the full contract."""
    text = task_text(payload)
    return bool(text) and all(
        any(match.group(1).strip() for match in pattern.finditer(text))
        for pattern in CAPSULE_FIELDS
    )


def routing_text(payload: dict[object, object]) -> str:
    """Route from objective/scope, not from generic oracle/return vocabulary."""
    text = task_text(payload)
    selected = [
        match.group(1).strip()
        for pattern in (OBJECTIVE_FIELD, SCOPE_FIELD)
        if (match := pattern.search(text)) and match.group(1).strip()
    ]
    return "\n".join(selected) if selected else text


def tool_route(payload: dict[object, object]) -> str:
    """Return at most one compact route, or nothing for an ambiguous task."""
    text = routing_text(payload)
    for pattern, instruction in ROUTES:
        if pattern.search(text):
            return instruction
    return ""


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

    compact = os.environ.get("ATS_CAPSULE_COMPACT_OFF") != "1"
    contract = (
        COMPACT_CONTRACT
        if compact and has_complete_capsule(payload)
        else CONTRACT + RESULT_CONTRACT
    )
    context = contract + tool_route(payload)
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
