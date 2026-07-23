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

# --- Goal-achievement system (omnigoal pattern) -----------------------------
# Every session gets a machine-checkable oracle. Agent stops when oracle PASS
# or budget exhausted. Goals live in ~/.synapse/goals/ as JSON — any agent can
# pick them up, coordinate, and ingest outcomes WITHOUT sharing transcripts.
# Replaces "spawn workers with shared context" (burns tokens) with
# "spawn workers with shared goal contract" (bounded).

devin-goal-init() {
  if [[ $# -lt 2 ]]; then
    cat <<'EOF'
Usage: devin-goal-init "<title>" --oracle "<checkable condition>" \
  [--budget-tokens 50000] [--deadline 2h] [--repo <path>]

Creates ~/.synapse/goals/<slug>.json — a machine-checkable goal contract
any agent can pick up. The oracle MUST be a single shell command that
returns 0 on success. Examples:
  --oracle "cargo test --workspace 2>&1 | tail -1 | grep -q 'test result: ok'"
  --oracle "grep -c 'TODO' src/lib.rs | grep -q '^0$'"
  --oracle "jq -e '.passes > 100' reports/bench.json"
EOF
    return 0
  fi
  local title="$1"; shift
  local oracle="" budget=50000 deadline="2h" repo="${PWD}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --oracle) oracle="$2"; shift 2 ;;
      --budget-tokens) budget="$2"; shift 2 ;;
      --deadline) deadline="$2"; shift 2 ;;
      --repo) repo="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  if [[ -z "$oracle" ]]; then
    echo "devin-goal-init: --oracle is required" >&2; return 1
  fi
  local goals_dir="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
  mkdir -p "$goals_dir"
  local slug
  slug=$(echo -n "$title" | tr -c 'a-zA-Z0-9-' '-' | tr 'A-Z' 'a-z' | sed 's/--*/-/g;s/^-//;s/-$//')
  local goal_file="$goals_dir/${slug}.json"
  local ts; ts=$(date +%s)
  # jq --arg for safe JSON quoting (handles quotes/special chars in oracle/title)
  jq -n \
    --arg id "$slug" \
    --arg title "$title" \
    --arg oracle "$oracle" \
    --arg deadline "$deadline" \
    --arg repo "$repo" \
    --argjson budget "$budget" \
    --argjson ts "$ts" \
    '{id:$id, title:$title, oracle:$oracle, budget_tokens:$budget,
      deadline:$deadline, repo:$repo, created_ts:$ts,
      state:"open", attempts:[], subagents:[]}' >"$goal_file"
  echo "$goal_file"
  echo "  Oracle: $oracle"
  echo "  Budget: $budget tokens, deadline $deadline"
  echo "  Check:  devin-goal-check $slug"
}

devin-goal-check() {
  if [[ $# -lt 1 ]]; then
    local goals_dir="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
    ls -1 "$goals_dir"/*.json 2>/dev/null | while read -r f; do
      jq -r '"\(.id)\t\(.state)\t\(.title)"' "$f" 2>/dev/null
    done
    return 0
  fi
  local slug="$1"
  local goal_file; goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
  if [[ ! -f "$goal_file" ]]; then
    echo "devin-goal-check: goal not found: $slug" >&2; return 1
  fi
  local oracle; oracle=$(jq -r '.oracle' "$goal_file")
  echo "=== Goal: $slug ==="
  echo "Oracle: $oracle"
  echo "--- Running oracle ---"
  if bash -c "$oracle" >/tmp/goal-oracle.log 2>&1; then
    echo "ORACLE: PASS"
    jq '.state = "passed" | .passed_ts = '"$(date +%s)" "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    return 0
  else
    echo "ORACLE: FAIL (exit $?)"
    tail -5 /tmp/goal-oracle.log
    local bottleneck
    bottleneck=$(grep -iE 'error|fail|not found|missing|panic' /tmp/goal-oracle.log | head -1)
    echo "BOTTLENECK: ${bottleneck:-unknown — inspect /tmp/goal-oracle.log}"
    return 1
  fi
}

devin-goal-close() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: devin-goal-close <slug> [--summary "<text>"]' >&2; return 1
  fi
  local slug="$1"; shift
  local summary=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --summary) summary="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  local goal_file; goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
  if [[ ! -f "$goal_file" ]]; then
    echo "devin-goal-close: goal not found: $slug" >&2; return 1
  fi
  if ! devin-goal-check "$slug" >/dev/null 2>&1; then
    echo "devin-goal-close: oracle still failing — close refused" >&2; return 1
  fi
  if [[ -n "$summary" ]] && command -v synx >/dev/null 2>&1; then
    echo "$summary" | synx put --title "goal-close:$slug"
  fi
  # jq --arg for safe summary quoting (handles spaces, quotes)
  jq --arg s "$summary" '.state = "closed" | .closed_ts = '"$(date +%s)"' | .summary = $s' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "CLOSED: $slug"
}

devin-goal-spawn() {
  if [[ $# -lt 2 ]]; then
    echo 'Usage: devin-goal-spawn <slug> --capsule <capsule.md> [--skill <name>]' >&2; return 1
  fi
  local slug="$1"; shift
  local capsule="" skill=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --capsule) capsule="$2"; shift 2 ;;
      --skill) skill="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  local goal_file; goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
  if [[ ! -f "$goal_file" ]]; then
    echo "devin-goal-spawn: goal not found: $slug" >&2; return 1
  fi
  if [[ ! -f "$capsule" ]]; then
    echo "devin-goal-spawn: capsule not found: $capsule" >&2; return 1
  fi
  local sub_id="sub-$(date +%s)-$RANDOM"
  jq '.subagents += [{"id":"'"$sub_id"'","capsule":"'"$capsule"'","skill":"'"${skill:-none}"'","state":"spawned"}]' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "$sub_id"
  echo "  Capsule: $capsule ($(wc -c <"$capsule") bytes, ~$(($(wc -c <"$capsule")/4)) tokens)"
  echo "  Skill:   ${skill:-none}"
  echo "  Goal:    $goal_file"
  echo ""
  echo "Subagent contract: read goal oracle + capsule only. No parent transcript."
  echo "On completion: devin-goal-check $slug && devin-goal-close $slug --summary \"...\""
}

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
  echo "goals:  ${n_goals} in ${goals_dir} (devin-goal-init / devin-goal-check)"
  echo "DEVIN_TOKEN_SAVER_LOADED: ${DEVIN_TOKEN_SAVER_LOADED:-0}"
  echo
  echo "Aliases installed:"
  type ps 2>/dev/null | head -1
  type gitdiff 2>/dev/null | head -1
  type gitlog 2>/dev/null | head -1
}
