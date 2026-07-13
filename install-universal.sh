#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
LOCAL_INSTALLER="$SCRIPT_DIR/scripts/install_agent_token_saver.py"

if [[ -f "$LOCAL_INSTALLER" ]]; then
  exec python3 "$LOCAL_INSTALLER" "$@"
fi

command -v git >/dev/null 2>&1 || {
  echo "agent-token-saver: git is required for the remote bootstrap" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "agent-token-saver: Python 3.11+ is required" >&2
  exit 1
}

TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM
REPO_URL="${ATS_REPO_URL:-https://github.com/Supersynergy/agent-token-saver.git}"
git clone --quiet --depth 1 \
  "$REPO_URL" \
  "$TMP_ROOT/agent-token-saver"
python3 "$TMP_ROOT/agent-token-saver/scripts/install_agent_token_saver.py" "$@"
