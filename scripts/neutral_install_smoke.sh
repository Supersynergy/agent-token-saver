#!/usr/bin/env bash
set -euo pipefail

# Proves the promise in the README: a machine with nothing but Python 3 and git
# gets a healthy portable core. Bun is only needed by the optional llmadapter,
# so it must never gate this run — it is exercised separately below when the
# host happens to have it.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM

export HOME="$TMP_ROOT/home"
PROJECT="$TMP_ROOT/project"
mkdir -p "$HOME/.hermes" "$PROJECT/.git"
printf '%s\n' '# Hermes fixture' >"$HOME/.hermes/SOUL.md"

python3 "$ROOT/scripts/install_agent_token_saver.py" \
  --profile lean --agent all --project "$PROJECT" >/dev/null

if command -v bun >/dev/null 2>&1; then
  HAS_BUN=yes
else
  HAS_BUN=no
fi

# Never swallow the diagnosis: with --json redirected to a file, a failing
# doctor exits silently, which is unactionable for both users and CI.
run_doctor() {
  local out="$1"
  shift
  if ! "$HOME/.local/bin/agent-token-saver" doctor --profile lean --json "$@" >"$out"; then
    echo "neutral install FAILED: 'agent-token-saver doctor $*' reported an unhealthy stack" >&2
    cat "$out" >&2 || true
    exit 1
  fi
}

REPORT="$TMP_ROOT/doctor.json"
run_doctor "$REPORT"

python3 - "$HOME" "$PROJECT" "$REPORT" "$HAS_BUN" <<'PY'
import json
import sys
from pathlib import Path

home, project, report_path = map(Path, sys.argv[1:4])
has_bun = sys.argv[4] == "yes"
report = json.loads(report_path.read_text())
assert report["healthy"] is True, report
assert report["status"] in {"core-ready", "full"}, report

adapter = report["llmadapter"]
if has_bun:
    assert adapter["ready"] is True, adapter
    assert adapter["capability"]["schema_version"] == 2, adapter
else:
    # Documented contract: the core stays healthy and the adapter names the one
    # missing runtime instead of failing the install.
    assert adapter["ready"] is False, adapter
    assert adapter["error"] == "bun_missing", adapter

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
missing = [str(path) for path in required if not (path.exists() or path.is_symlink())]
assert not missing, missing
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
            "bun": has_bun,
        },
        separators=(",", ":"),
    )
)
PY

"$HOME/.local/bin/agent-token-ledger" --help >/dev/null
"$HOME/.local/bin/agent-token-audit" --help >/dev/null

# Optional adapter lane: only meaningful where its runtime exists.
if [ "$HAS_BUN" = yes ]; then
  run_doctor "$TMP_ROOT/doctor-strict.json" --require-llmadapter
  "$HOME/.local/bin/llmadapter" contract "neutral install smoke" >/dev/null
  printf '%s\n' '{"llmadapter_lane":"PASS"}'
else
  printf '%s\n' '{"llmadapter_lane":"SKIPPED","reason":"bun not installed"}'
fi
