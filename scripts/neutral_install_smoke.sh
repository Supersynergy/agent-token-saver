#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM

export HOME="$TMP_ROOT/home"
PROJECT="$TMP_ROOT/project"
mkdir -p "$HOME" "$PROJECT/.git"

python3 "$ROOT/scripts/install_agent_token_saver.py" \
  --profile lean --agent all --project "$PROJECT" >/dev/null

REPORT="$TMP_ROOT/doctor.json"
"$HOME/.local/bin/agent-token-saver" doctor --profile lean --json >"$REPORT"

python3 - "$HOME" "$PROJECT" "$REPORT" <<'PY'
import json
import sys
from pathlib import Path

home, project, report_path = map(Path, sys.argv[1:])
report = json.loads(report_path.read_text())
assert report["healthy"] is True, report
assert report["status"] in {"core-ready", "full"}, report
required = [
    home / ".local/bin/agent-token-saver",
    home / ".local/bin/agent-token-ledger",
    home / ".codex/hooks.json",
    home / ".claude/settings.json",
    home / ".hermes/skills/agent-token-saver/SKILL.md",
    home / ".gg/skills/agent-token-saver.md",
    project / ".agents/skills/agent-token-saver/SKILL.md",
]
assert all(path.exists() or path.is_symlink() for path in required), required
print(
    json.dumps(
        {
            "neutral_install": "PASS",
            "status": report["status"],
            "coverage_percent": report["coverage_percent"],
            "missing_optional": report["missing_optional"],
        },
        separators=(",", ":"),
    )
)
PY

"$HOME/.local/bin/agent-token-ledger" --help >/dev/null
