#!/usr/bin/env bash
# claude-token-saver.sh — Claude-specific wrapper around the universal
# agent-token-saver.sh. Claude Code has native PreToolUse/PostToolUse hooks
# but no built-in goal-achievement loop; this wrapper wires the universal
# ats-* + goal-* CLI into Claude sessions via /hook or manual sourcing.
#
# This wrapper:
#   1. Exports Claude-specific env (ATS_AGENT_NAME=claude, ATS_ACTIVE_SKILL=…claude).
#   2. Sources the universal agent-token-saver.sh (ats-* + goal-* + aliases).
#   3. Provides thin claude-* aliases mirroring devin-* for consistency.
#
# Contract: fail-open · non-destructive · idempotent · no MCP.
# Usage: source scripts/claude-token-saver.sh · Verify: type claude-token-doctor

if [[ -n "${CLAUDE_TOKEN_SAVER_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi

# Claude-specific env overrides — picked up by ats-* helpers.
export ATS_AGENT_NAME="${ATS_AGENT_NAME:-claude}"
export ATS_ACTIVE_SKILL="${ATS_ACTIVE_SKILL:-.agents/skills/agent-token-saver-claude/SKILL.md}"

# Source the universal wrapper (provides ats-* + goal-* + aliases + ats-detect-agent).
# Portable script-dir resolution (bash BASH_SOURCE + zsh $0 fallback).
_ats_script="${BASH_SOURCE[0]:-$0}"
_ats_script_dir="${_ats_script%/*}"
[[ "$_ats_script_dir" == "$_ats_script" ]] && _ats_script_dir="."
_universal="$_ats_script_dir/agent-token-saver.sh"
if [[ -f "$_universal" ]]; then
  # shellcheck source=/dev/null
  source "$_universal"
else
  echo "claude-token-saver: agent-token-saver.sh not found at $_universal — universal helpers unavailable" >&2
fi
# Fallback: if universal wrapper was already loaded (guard short-circuited),
# goal.sh may not have been sourced. Ensure goal-* is available.
if [[ -z "${GOAL_SH_LOADED:-}" ]] && [[ -f "$_ats_script_dir/goal.sh" ]]; then
  # shellcheck source=/dev/null
  source "$_ats_script_dir/goal.sh"
fi
unset _universal _ats_script _ats_script_dir

export CLAUDE_TOKEN_SAVER_LOADED=1

# --- Thin claude-* aliases (mirror devin-* for cross-agent consistency) ------
claude-token-ledger()       { ats-token-ledger "$@"; }
claude-capsule-template()   { ats-capsule-template "$@"; }
claude-synapse-ingest()     { ats-synapse-ingest "$@"; }
claude-synapse-prime()      { ats-synapse-prime "$@"; }
claude-synapse-remember()   { ats-synapse-remember "$@"; }
claude-token-doctor()       { ats-doctor "$@"; }

# goal-* aliases for discoverability.
claude-goal-init()   { goal-init "$@"; }
claude-goal-recall() { goal-recall "$@"; }
claude-goal-check()  { goal-check "$@"; }
claude-goal-close()  { goal-close "$@"; }
claude-goal-spawn()  { goal-spawn "$@"; }
