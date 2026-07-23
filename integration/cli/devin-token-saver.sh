#!/usr/bin/env bash
# devin-token-saver.sh — Devin-specific wrapper around the universal
# agent-token-saver.sh. Devin has no host-native prompt hooks (unlike Codex
# UserPromptSubmit or Claude PreToolUse), so everything is wired via repo
# instructions + shell wrapper + Knowledge Base.
#
# This wrapper:
#   1. Sources the universal agent-token-saver.sh (ats-* functions + goal.sh).
#   2. Exports Devin-specific env (ATS_AGENT_NAME=devin, ATS_ACTIVE_SKILL=…devin).
#   3. Provides thin devin-* backward-compat aliases for existing Devin sessions.
#
# Contract: fail-open · non-destructive · idempotent · no MCP.
# Usage: source scripts/devin-token-saver.sh · Verify: type devin-token-doctor

if [[ -n "${DEVIN_TOKEN_SAVER_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi

# Devin-specific env overrides — picked up by ats-* helpers.
export ATS_AGENT_NAME="${ATS_AGENT_NAME:-devin}"
export ATS_ACTIVE_SKILL="${ATS_ACTIVE_SKILL:-.agents/skills/agent-token-saver-devin/SKILL.md}"

# Source the universal wrapper (provides ats-* + goal-* + aliases).
# Portable script-dir resolution (bash BASH_SOURCE + zsh $0 fallback).
_ats_script="${BASH_SOURCE[0]:-$0}"
_ats_script_dir="${_ats_script%/*}"
[[ "$_ats_script_dir" == "$_ats_script" ]] && _ats_script_dir="."
_universal="$_ats_script_dir/agent-token-saver.sh"
if [[ -f "$_universal" ]]; then
  # shellcheck source=/dev/null
  source "$_universal"
else
  echo "devin-token-saver: agent-token-saver.sh not found at $_universal — universal helpers unavailable" >&2
fi
# Fallback: if universal wrapper was already loaded (guard short-circuited),
# goal.sh may not have been sourced. Ensure goal-* is available.
if [[ -z "${GOAL_SH_LOADED:-}" ]] && [[ -f "$_ats_script_dir/goal.sh" ]]; then
  # shellcheck source=/dev/null
  source "$_ats_script_dir/goal.sh"
fi
unset _universal _ats_script _ats_script_dir

# Devin-specific ingest script default (legacy devin-usage.py location).
export SYNAPSE_ULTRA_INGEST="${SYNAPSE_ULTRA_INGEST:-$HOME/BASE/projects/synapse-memory/crates/synapse-ultra/scripts/ingest/devin-usage.py}"

export DEVIN_TOKEN_SAVER_LOADED=1

# --- Thin backward-compat aliases (devin-* → ats-* / goal-*) ---------------
# Existing Devin sessions call devin-token-ledger, devin-synapse-prime, etc.
# Keep them working as 1-line aliases. New code should call ats-* / goal-*.

devin-token-ledger()       { ats-token-ledger "$@"; }
devin-capsule-template()   { ats-capsule-template "$@"; }
devin-synapse-ingest()     { ats-synapse-ingest "$@"; }
devin-synapse-prime()      { ats-synapse-prime "$@"; }
devin-synapse-remember()   { ats-synapse-remember "$@"; }
devin-token-doctor()       { ats-doctor "$@"; }

# goal-* aliases (also in goal.sh, re-declared here for discoverability).
devin-goal-init()   { goal-init "$@"; }
devin-goal-recall() { goal-recall "$@"; }
devin-goal-check()  { goal-check "$@"; }
devin-goal-close()  { goal-close "$@"; }
devin-goal-spawn()  { goal-spawn "$@"; }
