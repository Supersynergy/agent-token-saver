#!/usr/bin/env bash
# Rewrite-only RTK hook. Approval and sandbox policy remain owned by the agent.
set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v rtk >/dev/null 2>&1 || exit 0

INPUT=$(</dev/stdin)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -n "$CMD" ] || exit 0

case "$CMD" in
  *";"*|*"|"*|*"&"*) exit 0 ;;
esac
case "$CMD" in
  *$'\n'*|*$'\r'*) exit 0 ;;
esac

TRIMMED_CMD="${CMD#"${CMD%%[![:space:]]*}"}"
case "$TRIMMED_CMD" in
  git\ status*|git\ log*|git\ diff*|git\ show*|git\ grep*|git\ rev-parse*|git\ ls-files*|git\ ls-tree*) ;;
  git\ *) exit 0 ;;
esac

REWRITTEN=$(rtk rewrite "$CMD" 2>/dev/null)
EXIT_CODE=$?
case $EXIT_CODE in
  0|3) ;;
  *) exit 0 ;;
esac
[ "$CMD" != "$REWRITTEN" ] || exit 0

ORIGINAL_INPUT=$(printf '%s' "$INPUT" | jq -c '.tool_input')
UPDATED_INPUT=$(printf '%s' "$ORIGINAL_INPUT" | jq --arg cmd "$REWRITTEN" '.command = $cmd')
jq -n --argjson updated "$UPDATED_INPUT" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "updatedInput": $updated
  }
}'
