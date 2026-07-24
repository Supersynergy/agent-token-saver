#!/usr/bin/env python3
"""Ingest local agent-CLI conversation logs into the Synapse corpus sidecar.

Closes the recall gap deja-vu names: Codex/Claude Code/aider/opencode write
every session to local JSONL files that Synapse never indexed. This walks
those logs, extracts the user+assistant turns, and BULK-imports one JSONL via
`synx import` (seconds; 6700 per-session calls would take hours on DB/index
overhead). Sessions land under the `cli-log://` uri prefix, searchable through
the normal recall path (synxp / ats-recall).

Lean + fail-open: unknown line shapes are skipped, not fatal. Idempotent via a
state file of already-imported paths.

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


def bulk_import(rows: list[dict], db: str | None) -> int:
    """Write one JSONL and do a single `synx import` — 6700 per-call add-text
    invocations each pay ~20s of DB/index overhead (hours total); one bulk
    import is seconds. Rows use the export schema: {title, text, uri, ts}."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        path = fh.name
    cmd = ["synx", "import", path]
    if db:
        cmd = ["synx", "import", "-f", db, path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        Path(path).unlink(missing_ok=True)
        return 0 if r.returncode == 0 else -1
    except Exception:
        Path(path).unlink(missing_ok=True)
        return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=float, default=None, help="only files modified within N days")
    ap.add_argument("--limit", type=int, default=None, help="max sessions to ingest this run")
    ap.add_argument("--sources", type=str, default="codex,claude,aider,opencode")
    ap.add_argument(
        "--db",
        type=str,
        default=str(HOME / ".synapse" / "brain.db"),
        help="target Synapse db (default ~/.synapse/brain.db)",
    )
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

    print(f"{len(files)} new session logs to scan", file=sys.stderr)
    rows: list[dict] = []
    now = int(time.time())
    for src, p in files:
        turns = extract_turns(p)
        digest = "\n".join(turns)
        if len(digest) < MIN_CHARS:
            done.add(str(p))
            continue
        rows.append(
            {
                "title": f"cli-log:{src}:{p.stem[:40]}",
                "text": digest[:20000],
                "uri": f"cli-log://{src}/{p.stem}",
                "ts": now,
                "meta": json.dumps({"source": src, "kind": "cli-session"}),
            }
        )
        done.add(str(p))

    if args.dry_run:
        for r in rows[:10]:
            print(f"would import {r['title']} ({len(r['text'])} chars)")
        print(f"total {len(rows)} sessions ready for bulk import", file=sys.stderr)
        return 0

    if not rows:
        print("nothing new to ingest", file=sys.stderr)
        return 0
    print(f"bulk-importing {len(rows)} sessions into {args.db} …", file=sys.stderr)
    rc = bulk_import(rows, args.db)
    if rc == 0:
        save_state(done)
        print(f"imported {len(rows)} CLI sessions (uri prefix cli-log://)", file=sys.stderr)
    else:
        print("bulk import failed — state not advanced", file=sys.stderr)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
