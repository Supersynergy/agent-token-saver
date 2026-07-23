#!/usr/bin/env bash
# codex-token-saver.sh — Codex (OpenAI Codex CLI) wrapper around the universal
# agent-token-saver.sh. Codex has UserPromptSubmit hooks but no native goal
# system; this wrapper provides ats-* + goal-* for Codex sessions.
#
# Usage: source scripts/codex-token-saver.sh · Verify: type codex-token-doctor

if [[ -n "${CODEX_TOKEN_SAVER_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi

export ATS_AGENT_NAME="${ATS_AGENT_NAME:-codex}"
export ATS_ACTIVE_SKILL="${ATS_ACTIVE_SKILL:-.agents/skills/agent-token-saver-codex/SKILL.md}"

_ats_script="${BASH_SOURCE[0]:-$0}"
_ats_script_dir="${_ats_script%/*}"
[[ "$_ats_script_dir" == "$_ats_script" ]] && _ats_script_dir="."
_universal="$_ats_script_dir/agent-token-saver.sh"
if [[ -f "$_universal" ]]; then
  # shellcheck source=/dev/null
  source "$_universal"
else
  echo "codex-token-saver: agent-token-saver.sh not found at $_universal — universal helpers unavailable" >&2
fi
# Fallback: if universal wrapper was already loaded (guard short-circuited),
# goal.sh may not have been sourced. Ensure goal-* is available.
if [[ -z "${GOAL_SH_LOADED:-}" ]] && [[ -f "$_ats_script_dir/goal.sh" ]]; then
  # shellcheck source=/dev/null
  source "$_ats_script_dir/goal.sh"
fi
unset _universal _ats_script _ats_script_dir

export CODEX_TOKEN_SAVER_LOADED=1

codex-token-ledger()       { ats-token-ledger "$@"; }
codex-capsule-template()   { ats-capsule-template "$@"; }
codex-synapse-ingest()     { ats-synapse-ingest "$@"; }
codex-synapse-prime()      { ats-synapse-prime "$@"; }
codex-synapse-remember()   { ats-synapse-remember "$@"; }
codex-token-doctor()       { ats-doctor "$@"; }

codex-goal-init()   { goal-init "$@"; }
codex-goal-recall() { goal-recall "$@"; }
codex-goal-check()  { goal-check "$@"; }
codex-goal-close()  { goal-close "$@"; }
codex-goal-spawn()  { goal-spawn "$@"; }
