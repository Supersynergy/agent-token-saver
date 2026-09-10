#!/usr/bin/env bash
# install_stack_tools.sh — thin Bash wrapper around the Python core.
#
# Delegates all logic to install_stack_tools.py so the implementation stays
# testable in the existing pytest suite. This wrapper exists only for
# ``curl | bash`` users and shell-first workflows.
#
# Usage:
#   install_stack_tools.sh                    install all tools, auto-detect hosts
#   install_stack_tools.sh --tool rtk,tilth   install only specified tools
#   install_stack_tools.sh --host claude       wire only to Claude Code
#   install_stack_tools.sh --dry-run           show what would happen
#   install_stack_tools.sh --check             check installed state
#   install_stack_tools.sh --uninstall         remove installed tools
#
# All flags pass through to the Python core.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${ATS_STACK_PYTHON:-python3}"

# Prefer the project's venv if available (same floor as the main installer).
if [[ -f "$SCRIPT_DIR/../.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/../.venv/bin/python"
fi

# The Python core lives next to this wrapper in the source tree, or is
# installed as "install-stack-tools" (no .py extension) in the install home.
# Try both, preferring the .py sibling for dev workflows.
CORE_PY="$SCRIPT_DIR/install_stack_tools.py"
if [[ ! -f "$CORE_PY" ]]; then
  CORE_PY="$SCRIPT_DIR/install-stack-tools"
fi

exec "$PYTHON" "$CORE_PY" "$@"
