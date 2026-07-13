#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT INT TERM

cp "$ROOT/install-universal.sh" "$TMP_ROOT/install-universal.sh"
mkdir -p "$TMP_ROOT/home" "$TMP_ROOT/project/.git"

HOME="$TMP_ROOT/home" ATS_REPO_URL="$ROOT" \
  bash "$TMP_ROOT/install-universal.sh" \
  --profile lean --agent repo --project "$TMP_ROOT/project" >/dev/null

test -x "$TMP_ROOT/home/.agent-token-saver/bin/agent-token-saver"
test -x "$TMP_ROOT/home/.agent-token-saver/bin/agent-token-ledger"
test -f "$TMP_ROOT/project/.agents/skills/agent-token-saver/SKILL.md"
printf '%s\n' '{"remote_bootstrap":"PASS"}'
