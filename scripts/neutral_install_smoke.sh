#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM

export HOME="$TMP_ROOT/home"
PROJECT="$TMP_ROOT/project"
mkdir -p "$HOME/.hermes" "$PROJECT/.git"
printf '%s\n' '# Hermes fixture' >"$HOME/.hermes/SOUL.md"

python3 "$ROOT/scripts/install_agent_token_saver.py" \
  --profile lean --agent all --project "$PROJECT" >/dev/null

REPORT="$TMP_ROOT/doctor.json"
"$HOME/.local/bin/agent-token-saver" doctor \
  --profile lean --require-llmadapter --json >"$REPORT"

python3 - "$HOME" "$PROJECT" "$REPORT" <<'PY'
import json
import sys
from pathlib import Path

home, project, report_path = map(Path, sys.argv[1:])
report = json.loads(report_path.read_text())
assert report["healthy"] is True, report
assert report["status"] in {"core-ready", "full"}, report
assert report["llmadapter"]["ready"] is True, report["llmadapter"]
assert report["llmadapter"]["capability"]["schema_version"] == 2
required = [
    home / ".local/bin/agent-token-saver",
    home / ".local/bin/agent-token-ledger",
    home / ".local/bin/agent-token-audit",
    home / ".local/bin/llmadapter",
    home / ".agent-token-saver/skills/agent-token-saver/SKILL.md",
    home / ".agent-token-saver/instructions/compact-default.md",
    home / ".codex/hooks.json",
    home / ".codex/AGENTS.md",
    home / ".claude/settings.json",
    home / ".claude/CLAUDE.md",
    home / ".hermes/skills/agent-token-saver/SKILL.md",
    home / ".hermes/SOUL.md",
    home / ".gg/skills/agent-token-saver.md",
    home / "AGENTS.md",
    project / ".agents/skills/agent-token-saver/SKILL.md",
]
assert all(path.exists() or path.is_symlink() for path in required), required
for path in (
    home / ".codex/AGENTS.md",
    home / ".claude/CLAUDE.md",
    home / ".hermes/SOUL.md",
    home / "AGENTS.md",
):
    text = path.read_text()
    assert text.count("<!-- AGENT-TOKEN-SAVER-DEFAULT:START -->") == 1, path
    assert text.count("<!-- AGENT-TOKEN-SAVER-DEFAULT:END -->") == 1, path
assert not (home / ".codex/skills/agent-token-saver/SKILL.md").exists()
assert not (home / ".claude/skills/agent-token-saver/SKILL.md").exists()
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
"$HOME/.local/bin/agent-token-audit" --help >/dev/null
"$HOME/.local/bin/llmadapter" contract "neutral install smoke" >/dev/null
