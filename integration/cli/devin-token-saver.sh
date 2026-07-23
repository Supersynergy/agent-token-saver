#!/usr/bin/env bash
# devin-token-saver.sh — hook substitute for Devin (no native prompt hooks).
# Sources fail-open shell aliases routing noisy commands through `rtk` when present.
# Contract: fail-open (missing rtk/si → passthrough, never error) · non-destructive · idempotent · no MCP.
# Usage: source scripts/devin-token-saver.sh · Verify: type ps · type gitdiff

if [[ -n "${DEVIN_TOKEN_SAVER_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi
export DEVIN_TOKEN_SAVER_LOADED=1

# --- RTK routing (noisy shell output) ---------------------------------------

if command -v rtk >/dev/null 2>&1; then
  alias ps='rtk ps'
  alias gitdiff='rtk git diff'
  alias gitlog='rtk git log --oneline -20'
  alias dockerlogs='rtk docker logs'
  alias journalctl='rtk journalctl'
  # `cat *.log` style — only alias `catlog` to avoid breaking `cat` for files.
  alias catlog='rtk cat'
else
  alias ps='ps'; alias gitdiff='git diff'; alias gitlog='git log --oneline -20'
  alias dockerlogs='docker logs'; alias journalctl='journalctl'; alias catlog='cat'
fi

# `si` is invoked explicitly by the agent — no alias, no hook.
# Example: si route "fix failing tests" --max 1 --strict --json

# --- Post-session ledger ----------------------------------------------------

devin-token-ledger() {
  if ! command -v agent-token-ledger >/dev/null 2>&1; then
    echo "agent-token-saver: agent-token-ledger not on PATH — skipping." >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: devin-token-ledger <parent.jsonl> [child1.jsonl ...]

Wraps agent-token-ledger with Devin defaults: --provider codex,
--expected-workers = (argc - 1), --require-complete-team,
--require-within-guard, project-rules=AGENTS.md,
active-skill=.agents/skills/agent-token-saver-devin/SKILL.md.
EOF
    return 0
  fi
  local parent="$1"
  shift
  local workers=$(( $# + 0 ))
  local usage_args=( "--usage" "parent=$parent" )
  local i=1
  for f in "$@"; do
    usage_args+=( "--usage" "child-$i=$f" )
    i=$(( i + 1 ))
  done
  agent-token-ledger \
    "${usage_args[@]}" \
    --provider codex \
    --expected-workers "$workers" \
    --require-complete-team \
    --require-within-guard \
    --component project-rules=AGENTS.md \
    --component active-skill=.agents/skills/agent-token-saver-devin/SKILL.md \
    --format markdown \
    --out token-ledger.md
}

# --- Capsule template helper (see capsule-template.md for full version) -----

devin-capsule-template() {
  cat <<'EOF'
# Delegate capsule (300–700 tokens max)

## Task
<one independent closed objective>

## Paths / hashes
- <file path + git sha or content hash>

## Constraints
- <exact constraints, no ambiguity>

## PASS / FAIL oracle
- <deterministic check, not "schau mal">

## Routed skill (0 or 1)
- <skill name or "none">

## Max attempts
- 3

## Result format
- <=500-token summary pointing to evidence (paths + line ranges)
EOF
}

# --- Synapse Ultra ingest (post-session) ------------------------------------

devin-synapse-ingest() {
  local ultra_bin="${SYNAPSE_ULTRA_BIN:-$HOME/BASE/projects/synapse-memory/target/release/synapse-ultra}"
  local ingest_script="${SYNAPSE_ULTRA_INGEST:-$HOME/BASE/projects/synapse-memory/crates/synapse-ultra/scripts/ingest/devin-usage.py}"
  local db="${SYNAPSE_DB:-$HOME/.synapse/brain.db}"

  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: devin-synapse-ingest <session.jsonl> [--session abc123]

Pipes Devin JSONL through devin-usage.py into ~/.synapse/ingest/devin.jsonl,
then loads events + cost into brain.db via `synapse-ultra ingest --jsonl`.

Env: SYNAPSE_ULTRA_BIN · SYNAPSE_ULTRA_INGEST · SYNAPSE_DB
EOF
    return 0
  fi

  local session_file="$1"; shift
  if [[ ! -f "$session_file" ]]; then
    echo "devin-synapse-ingest: file not found: $session_file" >&2
    return 1
  fi
  if [[ ! -x "$ultra_bin" ]]; then
    echo "devin-synapse-ingest: synapse-ultra binary not found at $ultra_bin" >&2
    echo "  Build: cd ~/BASE/projects/synapse-memory && cargo build -p synapse-ultra --release" >&2
    return 1
  fi
  if [[ ! -f "$ingest_script" ]]; then
    echo "devin-synapse-ingest: devin-usage.py not found at $ingest_script" >&2; return 1
  fi

  python3 "$ingest_script" "$session_file" "$@" || return $?
  local ingest_dir="${SYNAPSE_INGEST_DIR:-$HOME/.synapse/ingest}"
  "$ultra_bin" ingest --db "$db" --jsonl "$ingest_dir/devin.jsonl" || return $?

  echo "devin-synapse-ingest: loaded $session_file into $db"
  echo "  Inspect:  $ultra_bin inspect --db $db"
  echo "  Events:   $ultra_bin events --db $db --agent devin --limit 20"
  echo "  Replay:   $ultra_bin replay --db $db --session $(basename "$session_file" .jsonl)"
}

# --- Synapse hybrid recall (pre-session) ------------------------------------

devin-synapse-prime() {
  if ! command -v synx >/dev/null 2>&1; then
    echo "devin-synapse-prime: synx CLI not on PATH — skipping (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    echo 'Usage: devin-synapse-prime "<topic> devin <repo> decisions"' >&2; return 1
  fi
  synx hybrid "$1" 8
}

devin-synapse-remember() {
  if ! command -v synx >/dev/null 2>&1; then
    echo "devin-synapse-remember: synx CLI not on PATH — skipping (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 2 ]]; then
    echo 'Usage: devin-synapse-remember "<title>" "<decision text>"' >&2; return 1
  fi
  local title="$1"; shift
  echo "$@" | synx put --title "$title"
}

# --- Goal-achievement system (universal goal-* CLI) -------------------------
# Sources integration/cli/goal.sh — 13 functions covering the full omnigoal loop:
#   init / recall / leverage / slice / spawn / check / verify / refute / close /
#   trace / trust / list / doctor
# Built on omnigoal law + 2026 research (AgentLTL, AgentVerify, delegato, Orloj).
# See ~/BASE/docs/goal-system-rework.md for full spec + ADRs.
#
# devin-goal-* are kept as 1-line backward-compat aliases (Devin sessions that
# already use them don't break). New agents should call goal-* directly.

_goal_sh="${BASH_SOURCE[0]%/*}/goal.sh"
if [[ -f "$_goal_sh" ]]; then
  # shellcheck source=/dev/null
  source "$_goal_sh"
else
  echo "devin-token-saver: goal.sh not found at $_goal_sh — goal system unavailable" >&2
fi
unset _goal_sh

# --- Doctor -----------------------------------------------------------------

devin-token-doctor() {
  echo "=== Devin Token-Saver Doctor ==="
  echo "rtk: $(command -v rtk || echo 'MISSING (fail-open pass-through)')"
  echo "si:  $(command -v si || echo 'MISSING (skill routing skipped)')"
  echo "agent-token-ledger: $(command -v agent-token-ledger || echo 'MISSING (post-session ledger unavailable)')"
  echo "agent-token-saver:  $(command -v agent-token-saver || echo 'MISSING (doctor unavailable)')"
  echo "synx: $(command -v synx || echo 'MISSING (synapse hybrid recall unavailable)')"
  local ultra_bin="${SYNAPSE_ULTRA_BIN:-$HOME/BASE/projects/synapse-memory/target/release/synapse-ultra}"
  echo "synapse-ultra: $([[ -x "$ultra_bin" ]] && echo "$ultra_bin" || echo 'MISSING (build: cargo build -p synapse-ultra --release)')"
  echo "duckdb: $(command -v duckdb || echo 'MISSING (DuckLake archive unavailable)')"
  echo "jq:     $(command -v jq || echo 'MISSING (goal system requires jq)')"
  local goals_dir="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
  local n_goals=0
  [[ -d "$goals_dir" ]] && n_goals=$(ls -1 "$goals_dir"/*.json 2>/dev/null | wc -l | tr -d ' ')
  echo "goals:  ${n_goals} in ${goals_dir} (goal-init / goal-check / goal-list)"
  echo "DEVIN_TOKEN_SAVER_LOADED: ${DEVIN_TOKEN_SAVER_LOADED:-0}"
  echo
  echo "Aliases installed:"
  type ps 2>/dev/null | head -1
  type gitdiff 2>/dev/null | head -1
  type gitlog 2>/dev/null | head -1
}
