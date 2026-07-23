#!/usr/bin/env bash
# cmux-token-saver.sh — cmux (multi-agent workspace) wrapper around the universal
# agent-token-saver.sh. cmux orchestrates multiple agent sessions; this wrapper
# gives each cmux workspace access to ats-* + goal-* for cross-agent coordination
# via the shared ~/.synapse/goals/*.json contract.
#
# Usage: source scripts/cmux-token-saver.sh · Verify: type cmux-token-doctor

if [[ -n "${CMUX_TOKEN_SAVER_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi

export ATS_AGENT_NAME="${ATS_AGENT_NAME:-cmux}"
export ATS_ACTIVE_SKILL="${ATS_ACTIVE_SKILL:-.agents/skills/agent-token-saver-cmux/SKILL.md}"

_ats_script="${BASH_SOURCE[0]:-$0}"
_ats_script_dir="${_ats_script%/*}"
[[ "$_ats_script_dir" == "$_ats_script" ]] && _ats_script_dir="."
_universal="$_ats_script_dir/agent-token-saver.sh"
if [[ -f "$_universal" ]]; then
  # shellcheck source=/dev/null
  source "$_universal"
else
  echo "cmux-token-saver: agent-token-saver.sh not found at $_universal — universal helpers unavailable" >&2
fi
# Fallback: if universal wrapper was already loaded (guard short-circuited),
# goal.sh may not have been sourced. Ensure goal-* is available.
if [[ -z "${GOAL_SH_LOADED:-}" ]] && [[ -f "$_ats_script_dir/goal.sh" ]]; then
  # shellcheck source=/dev/null
  source "$_ats_script_dir/goal.sh"
fi
unset _universal _ats_script _ats_script_dir

export CMUX_TOKEN_SAVER_LOADED=1

cmux-token-ledger()       { ats-token-ledger "$@"; }
cmux-capsule-template()   { ats-capsule-template "$@"; }
cmux-synapse-ingest()     { ats-synapse-ingest "$@"; }
cmux-synapse-prime()      { ats-synapse-prime "$@"; }
cmux-synapse-remember()   { ats-synapse-remember "$@"; }
cmux-token-doctor()       { ats-doctor "$@"; }

cmux-goal-init()   { goal-init "$@"; }
cmux-goal-recall() { goal-recall "$@"; }
cmux-goal-check()  { goal-check "$@"; }
cmux-goal-close()  { goal-close "$@"; }
cmux-goal-spawn()  { goal-spawn "$@"; }
