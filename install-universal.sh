#!/usr/bin/env bash
set -euo pipefail

# Find the newest interpreter that meets the installer's floor. A stock macOS
# resolves `python3` to 3.9 even when a qualifying Homebrew Python sits on the
# same PATH; execing `python3` blindly turned that into the first thing a new
# user saw. Version-manager shims are skipped: they add ~160 ms to every hook
# call, and the installer would otherwise pin one.
MIN_MAJOR=3
MIN_MINOR=11

python_qualifies() {
  "$1" - <<'PY' 2>/dev/null
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

find_python() {
  local candidate resolved
  for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$resolved" ]] || continue
    case "$resolved" in */shims/*) continue ;; esac
    if python_qualifies "$resolved"; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  # A shim is better than nothing; the installer resolves it to a real binary.
  resolved="$(command -v python3 2>/dev/null || true)"
  if [[ -n "$resolved" ]] && python_qualifies "$resolved"; then
    printf '%s\n' "$resolved"
    return 0
  fi
  return 1
}

PYTHON="$(find_python || true)"
if [[ -z "$PYTHON" ]]; then
  found="$(command -v python3 2>/dev/null || echo none)"
  version="$([[ "$found" != none ]] && "$found" --version 2>&1 || echo '')"
  echo "agent-token-saver: Python ${MIN_MAJOR}.${MIN_MINOR}+ is required on PATH under any of" >&2
  echo "  python3.14 python3.13 python3.12 python3.11 python3" >&2
  echo "  found: ${found} ${version}" >&2
  echo "  macOS: brew install python@3.12    Debian/Ubuntu: apt install python3.12" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
LOCAL_INSTALLER="$SCRIPT_DIR/scripts/install_agent_token_saver.py"

if [[ -f "$LOCAL_INSTALLER" ]]; then
  exec "$PYTHON" "$LOCAL_INSTALLER" "$@"
fi

command -v git >/dev/null 2>&1 || {
  echo "agent-token-saver: git is required for the remote bootstrap" >&2
  exit 1
}

TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM
REPO_URL="${ATS_REPO_URL:-https://github.com/Supersynergy/agent-token-saver.git}"
git clone --quiet --depth 1 \
  "$REPO_URL" \
  "$TMP_ROOT/agent-token-saver"
"$PYTHON" "$TMP_ROOT/agent-token-saver/scripts/install_agent_token_saver.py" "$@"
