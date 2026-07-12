#!/usr/bin/env python3
"""cts doctor — wire/health audit for Claude Code + ggcoder + CTS layers.

Checks:
  1. settings.json well-formed
  2. every hook command resolves to an existing file
  3. orphan scripts in ~/.claude/hooks/ that are NOT referenced
  4. missing-but-expected events (PreCompact, SubagentStop)
  5. context-mode plugin version (latest vs installed)
  6. ggcoder autopatch last-run status
  7. CTS layers: caveman, RTK, gemma-gate, cache-replay availability

Run:
    python cli/cts_doctor.py            # human checklist
    python cli/cts_doctor.py --json     # machine output

Exit code: 0 all-pass, 1 warnings, 2 critical.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
SETTINGS = HOME / ".claude" / "settings.json"
HOOKS_DIR = HOME / ".claude" / "hooks"
LOG_AUTOPATCH = HOME / ".claude" / "logs" / "ggcoder-autopatch.log"

PLUGIN_MARKETPLACES = HOME / ".claude" / "plugins" / "marketplaces"

# PostCompact is not a Claude Code hook event — post-compact recovery fires as
# SessionStart with source "compact", so we expect SessionEnd instead.
EXPECTED_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "PreCompact",
    "SubagentStop",
    "SessionStart",
    "SessionEnd",
    "Stop",
}


def _plugin_hook_events() -> dict[str, str]:
    """Map hook event -> plugin name for plugin-shipped hooks/hooks.json."""
    events: dict[str, str] = {}
    if not PLUGIN_MARKETPLACES.exists():
        return events
    for plugin in PLUGIN_MARKETPLACES.iterdir():
        hj = plugin / "hooks" / "hooks.json"
        if not hj.exists():
            continue
        try:
            data = json.loads(hj.read_text())
        except Exception:
            continue
        for ev in data.get("hooks", data):
            events.setdefault(ev, plugin.name)
    return events


PATH_RE = re.compile(r'(?:\$HOME|~/\S*|/[^\s"\'`;|&]+\.(?:sh|py|mjs|js))')


def _resolve(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def _extract_path(cmd: str) -> str | None:
    cleaned = cmd.replace('"', " ").replace("'", " ")
    for tok in cleaned.split():
        if "/" in tok and ("." in tok.split("/")[-1]):
            cand = _resolve(tok)
            if cand.startswith("/"):
                return cand
    m = PATH_RE.search(cmd)
    return _resolve(m.group(0)) if m else None


def audit() -> dict:
    report = {"ok": [], "warn": [], "crit": []}
    if not SETTINGS.exists():
        report["crit"].append(f"settings.json missing at {SETTINGS}")
        return report

    try:
        s = json.loads(SETTINGS.read_text())
    except json.JSONDecodeError as e:
        report["crit"].append(f"settings.json invalid JSON: {e}")
        return report
    report["ok"].append("settings.json parses")

    hooks_cfg = s.get("hooks", {})
    referenced = set()
    for event, entries in hooks_cfg.items():
        if not isinstance(entries, list):
            entries = [entries]
        for e in entries:
            for h in e.get("hooks", []) if isinstance(e, dict) else []:
                cmd = h.get("command", "")
                p = _extract_path(cmd)
                if p:
                    referenced.add(os.path.realpath(p))
                    if not os.path.exists(p):
                        report["warn"].append(f"{event}: missing script {os.path.basename(p)}")

    # missing events — plugin-shipped hooks (hooks/hooks.json) count as wired
    plugin_events = _plugin_hook_events()
    missing_events = EXPECTED_EVENTS - hooks_cfg.keys() - plugin_events.keys()
    for ev in missing_events:
        report["warn"].append(f"event not configured: {ev}")
    for ev in ("PreCompact", "SubagentStop"):
        if ev in hooks_cfg:
            report["ok"].append(f"{ev} wired")
        elif ev in plugin_events:
            report["ok"].append(f"{ev} wired (plugin: {plugin_events[ev]})")

    # orphans
    if HOOKS_DIR.exists():
        on_disk = {
            os.path.realpath(str(f))
            for f in HOOKS_DIR.iterdir()
            if f.suffix in (".sh", ".py", ".mjs", ".js") and not f.name.startswith(".")
        }
        orphans = sorted(on_disk - referenced)
        if orphans:
            report["warn"].append(
                f"{len(orphans)} orphan scripts in ~/.claude/hooks (exist but unwired)"
            )

    # context-mode version
    plugin_root = HOME / ".claude" / "plugins" / "cache" / "context-mode" / "context-mode"
    if plugin_root.exists():
        versions = sorted([d.name for d in plugin_root.iterdir() if d.is_dir()])
        if versions:
            installed = versions[-1]
            try:
                latest = subprocess.run(
                    ["npm", "view", "@mksglu/context-mode", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()
                if latest and latest != installed:
                    report["warn"].append(
                        f"context-mode outdated: {installed} → {latest} (run /ctx-upgrade)"
                    )
                else:
                    report["ok"].append(f"context-mode v{installed} current")
            except Exception:
                report["ok"].append(f"context-mode v{installed} (latest check skipped)")

    # ggcoder autopatch
    if LOG_AUTOPATCH.exists():
        age_min = (time.time() - LOG_AUTOPATCH.stat().st_mtime) / 60
        last = LOG_AUTOPATCH.read_text().splitlines()[-3:]
        if age_min < 1440:
            report["ok"].append(f"ggcoder autopatch ran {int(age_min)}m ago")
        if any("FAIL" in l or "ERROR" in l for l in last):
            report["warn"].append("ggcoder autopatch last-run had errors")

    # CTS layers
    for tool in ["caveman", "rtk", "claude"]:
        if shutil.which(tool):
            report["ok"].append(f"{tool} on PATH")
        elif tool == "caveman" and (PLUGIN_MARKETPLACES / "caveman").exists():
            report["ok"].append("caveman plugin installed (marketplace)")
        else:
            report["warn"].append(f"{tool} not on PATH")

    # Headroom dynamic-context proxy
    if shutil.which("headroom"):
        import urllib.request

        try:
            urllib.request.urlopen("http://127.0.0.1:8787/livez", timeout=1)
            report["ok"].append("headroom proxy live on :8787")
        except Exception:
            report["warn"].append("headroom installed but proxy not reachable on :8787")

    cts_root = HOME / "projects" / "claude-token-saver"
    for layer in ["core/gemma-gate.py", "core/cache_replay.py", "core/reflection.py"]:
        if (cts_root / layer).exists():
            report["ok"].append(f"layer present: {layer}")

    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = audit()
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print("# cts doctor\n")
        for tag, items in [("OK", r["ok"]), ("WARN", r["warn"]), ("CRIT", r["crit"])]:
            for i in items:
                mark = {"OK": "[x]", "WARN": "[!]", "CRIT": "[X]"}[tag]
                print(f"  {mark} {i}")
        print(f"\nsummary: ok={len(r['ok'])} warn={len(r['warn'])} crit={len(r['crit'])}")
    sys.exit(2 if r["crit"] else (1 if r["warn"] else 0))


if __name__ == "__main__":
    main()
