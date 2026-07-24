#!/usr/bin/env python3
"""Ingest local agent-CLI conversation logs into the Synapse corpus sidecar.

Closes the recall gap deja-vu names: Codex/Claude Code/aider/opencode write
every session to local JSONL files that Synapse never indexed. This walks
those logs, extracts the user+assistant turns, and pipes a compact digest per
session to `synx corpus add-text`, so past solutions become searchable.

Lean + fail-open: unknown line shapes are skipped, not fatal. Idempotent-ish
via a state file of already-ingested paths. Corpus (not verified memory) is the
right tier — raw history, promote later.

Usage:
  synapse-ingest-cli-logs.py [--since DAYS] [--limit N] [--dry-run] [--sources codex,claude,aider,opencode]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".agent-token-saver" / "cli-log-ingest.state"
SOURCES = {
    "codex": HOME / ".codex" / "sessions",
    "claude": HOME / ".claude" / "projects",
    "aider": HOME / ".aider",
    "opencode": HOME / ".local" / "share" / "opencode" / "log",
}
MIN_CHARS = 200  # skip trivial/empty sessions


def _text_from_content(content) -> str:
    """Flatten a message 'content' (str or list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or "")
            elif isinstance(b, str):
                parts.append(b)
        return " ".join(p for p in parts if p)
    return ""


def extract_turns(path: Path) -> list[str]:
    """Pull user/assistant turns from a session JSONL, tolerant of formats."""
    turns: list[str] = []
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            # codex: {type: event_msg, payload: {type, message/content, role}}
            payload = d.get("payload", d)
            role = payload.get("role") or d.get("role") or ""
            msg = payload.get("message") or payload.get("content") or d.get("message")
            if isinstance(msg, dict):
                role = role or msg.get("role", "")
                msg = msg.get("content")
            text = _text_from_content(msg).strip()
            if text and role in ("user", "assistant"):
                turns.append(f"{role}: {text[:1500]}")
    except Exception:
        return []
    return turns


def load_state() -> set[str]:
    try:
        return set(STATE.read_text().splitlines())
    except FileNotFoundError:
        return set()


def save_state(done: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("\n".join(sorted(done)))


def ingest_text(title: str, ext_id: str, uri: str, text: str) -> bool:
    try:
        r = subprocess.run(
            [
                "synx",
                "corpus",
                "add-text",
                "--title",
                title,
                "--source-uri",
                uri,
                "--external-id",
                ext_id,
                "--embed",
            ],
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
        )
        return r.returncode == 0
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=float, default=None, help="only files modified within N days")
    ap.add_argument("--limit", type=int, default=None, help="max sessions to ingest this run")
    ap.add_argument("--sources", type=str, default="codex,claude,aider,opencode")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wanted = set(args.sources.split(","))
    done = load_state()
    cutoff = time.time() - args.since * 86400 if args.since else None
    files: list[tuple[str, Path]] = []

    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    for name, root in SOURCES.items():
        if name not in wanted or not root.exists():
            continue
        for p in root.rglob("*.jsonl"):
            mt = mtime(p)
            if cutoff and mt < cutoff:
                continue
            if mt and str(p) not in done:
                files.append((name, p))
    files.sort(key=lambda x: mtime(x[1]), reverse=True)
    if args.limit:
        files = files[: args.limit]

    print(f"{len(files)} new session logs to ingest", file=sys.stderr)
    ingested = 0
    for src, p in files:
        turns = extract_turns(p)
        digest = "\n".join(turns)
        if len(digest) < MIN_CHARS:
            done.add(str(p))
            continue
        title = f"cli-log:{src}:{p.stem[:40]}"
        if args.dry_run:
            print(f"would ingest {title} ({len(digest)} chars, {len(turns)} turns)")
        else:
            if ingest_text(title, f"{src}:{p.stem}", f"file://{p}", digest[:20000]):
                ingested += 1
            done.add(str(p))
        if not args.dry_run and ingested % 25 == 0 and ingested:
            save_state(done)
    if not args.dry_run:
        save_state(done)
    print(f"ingested {ingested} session logs into Synapse corpus", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
