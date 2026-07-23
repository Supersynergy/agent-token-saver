#!/usr/bin/env bash
# agent-token-saver.sh — universal shell wrapper for hookless AI agents.
# Sources fail-open shell aliases routing noisy commands through `rtk` when present,
# plus the goal-achievement CLI (goal.sh) and SynapseUltra ingest/prime helpers.
#
# Contract: fail-open (missing rtk/si/synx → passthrough, never error) ·
#           non-destructive · idempotent · no MCP.
# Usage: source scripts/agent-token-saver.sh · Verify: type ps · type gitdiff
#
# Agent-specific profiles (e.g. Devin) can wrap this file and add thin
# backward-compat aliases (devin-* → ats-*) for existing sessions.

if [[ -n "${AGENT_TOKEN_SAVER_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi
export AGENT_TOKEN_SAVER_LOADED=1

# --- Adaptive agent detection (v3.7.0) --------------------------------------
# Auto-detects the calling agent from well-known env vars and sets
# ATS_AGENT_NAME + ATS_ACTIVE_SKILL if not already set. Agents can override
# by exporting ATS_AGENT_NAME before sourcing, or by writing their own thin
# wrapper (see claude-token-saver.sh / codex-token-saver.sh / cmux-token-saver.sh).
ats-detect-agent() {
  if [[ -n "${ATS_AGENT_NAME:-}" && -n "${ATS_AGENT_DETECTED:-}" ]]; then
    return 0
  fi
  local detected=""
  # Priority 1: explicit env vars from agent runtimes
  if [[ -n "${DEVIN:-}" || -n "${DEVIN_SESSION:-}" ]]; then
    detected="devin"
  elif [[ -n "${CLAUDECODE:-}" || "${TERM_PROGRAM:-}" == "claude" || -n "${CLAUDE_SESSION_ID:-}" ]]; then
    detected="claude"
  elif [[ -n "${CODEX_AGENT:-}" || -n "${CODEX_SESSION_ID:-}" || -n "${OPENAI_CODEX:-}" ]]; then
    detected="codex"
  elif [[ -n "${CMUX_SESSION:-}" || -n "${CMUX_WORKSPACE:-}" ]]; then
    detected="cmux"
  elif [[ -n "${KIMI_WORKER:-}" || -n "${MOONSHOT_AGENT:-}" ]]; then
    detected="kimi-worker"
  elif [[ -n "${CASCADE_AGENT:-}" || -n "${WINDSURF_AGENT:-}" || "${TERM_PROGRAM:-}" == "windsurf" ]]; then
    detected="cascade"
  # Priority 2: process name heuristic
  else
    local ppid_name=""
    ppid_name=$(ps -o comm= -p $$ 2>/dev/null | tr -d ' ' || true)
    case "$ppid_name" in
      *claude*|*Claude*) detected="claude" ;;
      *codex*|*Codex*) detected="codex" ;;
      *devin*|*Devin*) detected="devin" ;;
      *cmux*) detected="cmux" ;;
      *node*|*vscode*) detected="vscode" ;;
      *) detected="agent" ;;
    esac
  fi
  export ATS_AGENT_NAME="${ATS_AGENT_NAME:-$detected}"
  export ATS_AGENT_DETECTED=1
  # Auto-set ATS_ACTIVE_SKILL if a matching skill profile exists
  if [[ -z "${ATS_ACTIVE_SKILL:-}" ]]; then
    local _ats_script _ats_root
    _ats_script="${BASH_SOURCE[0]:-$0}"
    _ats_root="${_ats_script%/*}/../.."
    [[ -d "$_ats_root" ]] || _ats_root="${ATS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." 2>/dev/null && pwd)}"
    local _skill_candidates=(
      "$_ats_root/skills/agent-token-saver-$ATS_AGENT_NAME/SKILL.md"
      "$_ats_root/.agents/skills/agent-token-saver-$ATS_AGENT_NAME/SKILL.md"
    )
    local _sc
    for _sc in "${_skill_candidates[@]}"; do
      if [[ -f "$_sc" ]]; then
        export ATS_ACTIVE_SKILL="$_sc"
        break
      fi
    done
    unset _sc _skill_candidates _ats_root
  fi
}

ats-detect-agent

# --- Fail-safe wrapper (v3.7.0) ----------------------------------------------
# ats-safe <func> [args...] — calls <func> if defined, else warns + returns 0.
# Lets agents call optional ats-* helpers without knowing whether they're
# installed. Also usable as a guard for subagent-spawn paths.
ats-safe() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: ats-safe <func> [args...]' >&2; return 1
  fi
  local fn="$1"; shift
  if declare -F "$fn" >/dev/null 2>&1; then
    "$fn" "$@"
    return $?
  fi
  echo "ats-safe: $fn not defined — skipping (fail-open)" >&2
  return 0
}

# ats-have <tool> — silent existence check for a CLI tool
ats-have() { command -v "$1" >/dev/null 2>&1; }

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

ats-token-ledger() {
  if ! command -v agent-token-ledger >/dev/null 2>&1; then
    echo "agent-token-saver: agent-token-ledger not on PATH — skipping." >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: ats-token-ledger <parent.jsonl> [child1.jsonl ...]

Wraps agent-token-ledger with sensible defaults: --provider codex,
--expected-workers = (argc - 1), --require-complete-team,
--require-within-guard, project-rules=AGENTS.md,
active-skill=.agents/skills/agent-token-saver/SKILL.md.

Override the active skill via ATS_ACTIVE_SKILL env var (e.g. Devin sessions
set ATS_ACTIVE_SKILL=.agents/skills/agent-token-saver-devin/SKILL.md).
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
  local active_skill="${ATS_ACTIVE_SKILL:-.agents/skills/agent-token-saver/SKILL.md}"
  agent-token-ledger \
    "${usage_args[@]}" \
    --provider codex \
    --expected-workers "$workers" \
    --require-complete-team \
    --require-within-guard \
    --component project-rules=AGENTS.md \
    --component "active-skill=$active_skill" \
    --format markdown \
    --out token-ledger.md
}

# --- Capsule template helper (see capsule-template.md for full version) -----

ats-capsule-template() {
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

ats-synapse-ingest() {
  local ultra_bin="${SYNAPSE_ULTRA_BIN:-$HOME/projects/synapse-memory/target/release/synapse-ultra}"
  local ingest_script="${SYNAPSE_ULTRA_INGEST:-$HOME/projects/synapse-memory/crates/synapse-ultra/scripts/ingest/agent-usage.py}"
  local db="${SYNAPSE_DB:-$HOME/.synapse/brain.db}"
  local agent_name="${ATS_AGENT_NAME:-agent}"

  if [[ $# -lt 1 ]]; then
    cat <<EOF
Usage: ats-synapse-ingest <session.jsonl> [--session abc123]

Pipes agent JSONL through agent-usage.py into ~/.synapse/ingest/${agent_name}.jsonl,
then loads events + cost into brain.db via \`synapse-ultra ingest --jsonl\`.

Env: SYNAPSE_ULTRA_BIN · SYNAPSE_ULTRA_INGEST · SYNAPSE_DB · ATS_AGENT_NAME
EOF
    return 0
  fi

  local session_file="$1"; shift
  if [[ ! -f "$session_file" ]]; then
    echo "ats-synapse-ingest: file not found: $session_file" >&2
    return 1
  fi
  if [[ ! -x "$ultra_bin" ]]; then
    echo "ats-synapse-ingest: synapse-ultra binary not found at $ultra_bin" >&2
    echo "  Build: clone https://github.com/Supersynergy/synapse-memory && cargo build -p synapse-ultra --release" >&2
    return 1
  fi
  if [[ ! -f "$ingest_script" ]]; then
    echo "ats-synapse-ingest: agent-usage.py not found at $ingest_script" >&2
    echo "  Set SYNAPSE_ULTRA_INGEST to your agent-usage.py path." >&2
    return 1
  fi

  python3 "$ingest_script" "$session_file" "$@" || return $?
  local ingest_dir="${SYNAPSE_INGEST_DIR:-$HOME/.synapse/ingest}"
  "$ultra_bin" ingest --db "$db" --jsonl "$ingest_dir/${agent_name}.jsonl" || return $?

  echo "ats-synapse-ingest: loaded $session_file into $db"
  echo "  Inspect:  $ultra_bin inspect --db $db"
  echo "  Events:   $ultra_bin events --db $db --agent $agent_name --limit 20"
  echo "  Replay:   $ultra_bin replay --db $db --session $(basename "$session_file" .jsonl)"
}

# --- Synapse hybrid recall (pre-session) ------------------------------------

ats-synapse-prime() {
  if ! command -v synx >/dev/null 2>&1; then
    echo "ats-synapse-prime: synx CLI not on PATH — skipping (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    echo 'Usage: ats-synapse-prime "<topic> <repo> decisions"' >&2; return 1
  fi
  synx hybrid "$1" 8
}

ats-synapse-remember() {
  if ! command -v synx >/dev/null 2>&1; then
    echo "ats-synapse-remember: synx CLI not on PATH — skipping (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 2 ]]; then
    echo 'Usage: ats-synapse-remember "<title>" "<decision text>"' >&2; return 1
  fi
  local title="$1"; shift
  echo "$@" | synx put --title "$title"
}

# --- Goal-achievement system (universal goal-* CLI) -------------------------
# Sources integration/cli/goal.sh — 13 functions covering the full omnigoal loop:
#   init / recall / leverage / slice / spawn / check / verify / refute / close /
#   trace / trust / list / doctor
# Built on omnigoal law + 2026 research (AgentLTL, AgentVerify, delegato, Orloj).
# See docs/goal-system-rework.md in the synapse-memory repo for full spec + ADRs.

_ats_script="${BASH_SOURCE[0]:-$0}"
_ats_script_dir="${_ats_script%/*}"
[[ "$_ats_script_dir" == "$_ats_script" ]] && _ats_script_dir="."
_goal_sh="$_ats_script_dir/goal.sh"
if [[ -f "$_goal_sh" ]]; then
  # shellcheck source=/dev/null
  source "$_goal_sh"
else
  echo "agent-token-saver: goal.sh not found at $_goal_sh — goal system unavailable" >&2
fi

# v4.0.0: source ats-token-cfo wrapper (Routing-Audit + Token-CFO-Report).
# Fail-open: missing file → warning, never blocks.
_ats_cfo="$_ats_script_dir/ats-token-cfo"
if [[ -f "$_ats_cfo" ]]; then
  # shellcheck source=/dev/null
  source "$_ats_cfo"
else
  echo "agent-token-saver: ats-token-cfo not found at $_ats_cfo — routing audit unavailable" >&2
fi
unset _goal_sh _ats_cfo _ats_script _ats_script_dir

# --- Speedtuning: parallel prime + init (v3.7.0) -----------------------------
ats-prime-and-init() {
  if [[ $# -lt 2 ]]; then
    echo 'Usage: ats-prime-and-init "<title>" --oracle "<cmd>" [--budget-tokens N] [--deadline T] [--repo P] [--force]'
    return 0
  fi
  local title="$1"; shift
  local recall_tmp=""
  if ats-have synx; then
    recall_tmp=$(mktemp -t ats-recall.XXXXXX)
    ( synx hybrid "$title" 8 >"$recall_tmp" 2>/dev/null ) &
    local recall_pid=$!
    goal-init "$title" "$@"
    local rc=$?
    wait "$recall_pid" 2>/dev/null || true
    local slug
    slug=$(echo -n "$title" | tr -c 'a-zA-Z0-9-' '-' | tr 'A-Z' 'a-z' | sed 's/--*/-/g;s/^-//;s/-$//')
    local goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
    if [[ -f "$goal_file" && -s "$recall_tmp" ]] && ats-have jq; then
      local recall_jq; recall_jq=$(jq -Rs . <"$recall_tmp" 2>/dev/null || echo '""')
      jq --argjson r "$recall_jq" '.evidence.recall = ($r | split("\n") | map(select(length > 0)))' \
        "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    fi
    rm -f "$recall_tmp"
    return $rc
  fi
  goal-init "$title" "$@"
}

ats-parallel() {
  if [[ $# -lt 1 ]]; then echo 'Usage: ats-parallel "<cmd1>" "<cmd2>" ...' >&2; return 1; fi
  local pids=() outs=() rc=0 i=0
  for cmd in "$@"; do
    local tmp; tmp=$(mktemp -t ats-parallel.XXXXXX)
    ( bash -c "$cmd" >"$tmp" 2>&1 ) &
    pids+=($!); outs+=("$tmp")
  done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || rc=1; done
  for tmp in "${outs[@]}"; do i=$((i+1)); echo "--- [$i] ---"; cat "$tmp" 2>/dev/null; rm -f "$tmp"; done
  return $rc
}

# --- Meta-review as hard gate (v3.7.0) ---------------------------------------
ats-metareview() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: ats-metareview <slug> [--via agentmaster|si|grepgod|manual] [--skip-if-missing]'; return 0
  fi
  local slug="$1"; shift
  local via="auto" skip_if_missing=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --via) via="$2"; shift 2 ;;
      --skip-if-missing) skip_if_missing=1; shift ;;
      *) shift ;;
    esac
  done
  local goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
  [[ -f "$goal_file" ]] || { echo "ats-metareview: goal not found: $slug" >&2; return 1; }
  local oracle dod repo
  oracle=$(jq -r .oracle "$goal_file" 2>/dev/null)
  dod=$(jq -r .title "$goal_file" 2>/dev/null)
  repo=$(jq -r .repo "$goal_file" 2>/dev/null)
  local spawn_ts since_date=""
  spawn_ts=$(jq -r '.spawn_ts // empty' "$goal_file" 2>/dev/null)
  if [[ -n "$spawn_ts" ]]; then
    since_date=$(date -u -r "$spawn_ts" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -u -d "@$spawn_ts" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || true)
  fi
  local diff_cmd="git -C '$repo' log --since='$since_date' --oneline 2>/dev/null"
  local prompt
  prompt=$(cat <<EOF
You are a FRESH reviewer agent. You have NO context from the builder.
Widerlege die Definition-of-Done — finde einen konkreten Grund warum DoD NICHT erfüllt ist.
Default verdict: NICHT-ERFÜLLT (only ERFÜLLT if you find concrete proof).

DoD (title): $dod
Oracle (must pass): $oracle
Diff (commits since spawn): $diff_cmd

Antworte: ERFÜLLT oder NICHT-ERFÜLLT + Grund.
EOF
)
  local refute_log="${GOAL_REFUTE_LOG:-/tmp/goal-refute.log}"
  echo "$prompt" >"$refute_log"
  local verdict="SKIPPED" chosen=""
  if [[ "$via" == "auto" || "$via" == "agentmaster" ]] && ats-have agentmaster; then
    chosen="agentmaster"
    agentmaster start --here --name "refute-$slug" 2>/dev/null || true
    agentmaster send "workspace:refute-$slug" "$prompt" 2>/dev/null || true
    verdict="PENDING"
  elif [[ "$via" == "auto" || "$via" == "metareview" ]] && ats-have metareview; then
    chosen="metareview"
    local mr_root="${METAREVIEW_ROOT:-$HOME/.claude/skills/metareview}"
    if [[ -x "$mr_root/run.sh" ]]; then
      "$mr_root/run.sh" "$repo" --since "$since_date" 2>/dev/null && verdict="PASS" || verdict="FAIL"
    else
      metareview "$repo" --since "$since_date" 2>/dev/null && verdict="PASS" || verdict="FAIL"
    fi
  elif [[ "$via" == "auto" || "$via" == "grepgod" ]] && ats-have grepgod; then
    chosen="grepgod"
    grepgod review "$repo" --since "$since_date" 2>/dev/null && verdict="PASS" || verdict="FAIL"
  elif [[ "$via" == "auto" || "$via" == "si" ]] && ats-have si; then
    chosen="si"
    si route "adversarial code review of goal $slug" --max 1 --strict --json 2>/dev/null && verdict="PENDING" || verdict="SKIPPED"
  else
    chosen="manual"
    echo "=== ats-metareview: manual prompt (no automated reviewer available) ==="
    cat "$refute_log"
    verdict="PENDING"
  fi
  if [[ "$skip_if_missing" -eq 1 && "$verdict" == "SKIPPED" ]]; then
    echo "ats-metareview: no reviewer + --skip-if-missing — proceeding"; return 0
  fi
  jq --arg v "$verdict" --arg via "$chosen" \
    '.evidence.refuter = $v | .evidence.refuter_via = $via' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "ats-metareview: verdict=$verdict via=$chosen"
}

# --- DuckLake goal-archive (v4.0.0) ------------------------------------------
# ats-goal-archive <slug> — append the goal JSON to a DuckLake catalog so that
# closed goals become queryable history (time-travel snapshots, branch replay).
# Fail-open: missing duckdb → warning + return 0. Idempotent: re-running on an
# already-archived slug upserts (no duplicate rows).
#
# Env:
#   ATS_GOAL_ARCHIVE_DB — path to DuckLake catalog (default: ~/.synapse/goal-archive.duckdb)
#   ATS_GOAL_ARCHIVE_TABLE — table name (default: goals)
ats-goal-archive() {
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: ats-goal-archive <slug> [--all]

Archives the goal JSON to a DuckLake catalog (default: ~/.synapse/goal-archive.duckdb).
Enables time-travel queries over closed goals: "what did we decide on 2026-07-23?"

Flags:
  --all  — archive every closed goal in SYNAPSE_GOALS_DIR

Env:
  ATS_GOAL_ARCHIVE_DB     — catalog path (default: ~/.synapse/goal-archive.duckdb)
  ATS_GOAL_ARCHIVE_TABLE  — table name (default: goals)

Requires: duckdb CLI on PATH. Fail-open: missing duckdb → warning + return 0.
EOF
    return 0
  fi
  local slug="$1"; shift
  local all=0
  [[ "${1:-}" == "--all" ]] && all=1
  if ! ats-have duckdb; then
    echo "ats-goal-archive: duckdb not on PATH — archive skipped (fail-open)" >&2
    return 0
  fi
  local db="${ATS_GOAL_ARCHIVE_DB:-$HOME/.synapse/goal-archive.duckdb}"
  local table="${ATS_GOAL_ARCHIVE_TABLE:-goals}"
  local goals_dir="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
  mkdir -p "$(dirname "$db")"
  local init_sql="CREATE TABLE IF NOT EXISTS ${table} (slug VARCHAR, state VARCHAR, title VARCHAR, oracle VARCHAR, bottleneck VARCHAR, closed_ts BIGINT, summary VARCHAR, raw JSON, archived_at TIMESTAMP DEFAULT now());"
  duckdb "$db" -c "$init_sql" >/dev/null 2>&1 || { echo "ats-goal-archive: duckdb init failed" >&2; return 0; }
  # Inline archive helper (kept simple — no nested function for shell portability).
  local gf s st ti orc bn ct sm raw
  if [[ "$all" -eq 1 ]]; then
    echo "=== ats-goal-archive --all ==="
    local n=0
    for gf in "$goals_dir"/*.json; do
      [[ -f "$gf" ]] || continue
      s=$(jq -r .id "$gf" 2>/dev/null)
      st=$(jq -r .state "$gf" 2>/dev/null)
      ti=$(jq -r .title "$gf" 2>/dev/null)
      orc=$(jq -r .oracle "$gf" 2>/dev/null)
      bn=$(jq -r '.bottleneck // ""' "$gf" 2>/dev/null)
      ct=$(jq -r '.closed_ts // 0' "$gf" 2>/dev/null)
      sm=$(jq -r '.summary // ""' "$gf" 2>/dev/null)
      raw=$(jq -c . "$gf" 2>/dev/null)
      local s_esc=${s//\'/\'\'}
      duckdb "$db" -c "DELETE FROM ${table} WHERE slug = '$s_esc'; INSERT INTO ${table} (slug, state, title, oracle, bottleneck, closed_ts, summary, raw) VALUES ('$s_esc', '$st', '$(echo "$ti" | sed "s/'/''/g")', '$(echo "$orc" | sed "s/'/''/g")', '$(echo "$bn" | sed "s/'/''/g")', $ct, '$(echo "$sm" | sed "s/'/''/g")', '$(echo "$raw" | sed "s/'/''/g")');" >/dev/null 2>&1 \
        && echo "  [archived] $s ($st)" \
        || echo "  [warn] $s — duckdb insert failed" >&2
      n=$((n+1))
    done
    echo "  Archived $n goal(s) to $db"
  else
    gf="$goals_dir/$slug.json"
    if [[ ! -f "$gf" ]]; then
      echo "ats-goal-archive: goal not found: $slug" >&2; return 1
    fi
    s=$(jq -r .id "$gf" 2>/dev/null)
    st=$(jq -r .state "$gf" 2>/dev/null)
    ti=$(jq -r .title "$gf" 2>/dev/null)
    orc=$(jq -r .oracle "$gf" 2>/dev/null)
    bn=$(jq -r '.bottleneck // ""' "$gf" 2>/dev/null)
    ct=$(jq -r '.closed_ts // 0' "$gf" 2>/dev/null)
    sm=$(jq -r '.summary // ""' "$gf" 2>/dev/null)
    raw=$(jq -c . "$gf" 2>/dev/null)
    local s_esc=${s//\'/\'\'}
    duckdb "$db" -c "DELETE FROM ${table} WHERE slug = '$s_esc'; INSERT INTO ${table} (slug, state, title, oracle, bottleneck, closed_ts, summary, raw) VALUES ('$s_esc', '$st', '$(echo "$ti" | sed "s/'/''/g")', '$(echo "$orc" | sed "s/'/''/g")', '$(echo "$bn" | sed "s/'/''/g")', $ct, '$(echo "$sm" | sed "s/'/''/g")', '$(echo "$raw" | sed "s/'/''/g")');" >/dev/null 2>&1 \
      && echo "  [archived] $s ($st)" \
      || echo "  [warn] $s — duckdb insert failed" >&2
    echo "  Catalog: $db  Table: ${table}"
  fi
}

# --- Omnigoal hard-gate verifier (v3.7.0) ------------------------------------
ats-omnigoal-check() {
  if [[ $# -lt 1 ]]; then echo 'Usage: ats-omnigoal-check <slug>' >&2; return 1; fi
  local slug="$1"
  local goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
  [[ -f "$goal_file" ]] || { echo "ats-omnigoal-check: goal not found: $slug" >&2; return 1; }
  local pass=0 fail=0
  local oracle state bottleneck eval_written commits refuter
  oracle=$(jq -r .oracle "$goal_file" 2>/dev/null)
  state=$(jq -r .state "$goal_file" 2>/dev/null)
  bottleneck=$(jq -r '.bottleneck // empty' "$goal_file" 2>/dev/null)
  eval_written=$(jq -r '.evidence.eval_written // false' "$goal_file" 2>/dev/null)
  commits=$(jq -r '.evidence.commits // [] | length' "$goal_file" 2>/dev/null)
  refuter=$(jq -r '.evidence.refuter // "SKIPPED"' "$goal_file" 2>/dev/null)
  echo "=== Omnigoal Hard Gates: $slug ==="
  if [[ -n "$oracle" && "$oracle" != "null" ]]; then echo "[PASS] 1. Oracle exists: $oracle"; pass=$((pass+1))
  else echo "[FAIL] 1. No machine-checkable oracle"; fail=$((fail+1)); fi
  if [[ "$eval_written" == "true" ]]; then echo "[PASS] 2. Eval written before build (EDD)"; pass=$((pass+1))
  else echo "[FAIL] 2. Eval not written before build"; fail=$((fail+1)); fi
  if [[ -n "$bottleneck" ]]; then echo "[PASS] 3. Bottleneck named: $bottleneck"; pass=$((pass+1))
  else echo "[FAIL] 3. No bottleneck named"; fail=$((fail+1)); fi
  if [[ "$commits" -gt 0 ]]; then echo "[PASS] 4. Commits since spawn: $commits"; pass=$((pass+1))
  else echo "[FAIL] 4. No measured work this session (0 commits)"; fail=$((fail+1)); fi
  if [[ "$refuter" == "PASS" ]]; then echo "[PASS] 5. Metareview: PASS"; pass=$((pass+1))
  elif [[ "$refuter" == "PENDING" ]]; then echo "[WARN] 5. Metareview: PENDING"; fail=$((fail+1))
  else echo "[FAIL] 5. Metareview: $refuter"; fail=$((fail+1)); fi
  local summary; summary=$(jq -r '.summary // empty' "$goal_file" 2>/dev/null)
  if [[ -n "$summary" ]]; then echo "[PASS] 6. Compounding writeback (summary set)"; pass=$((pass+1))
  else echo "[FAIL] 6. No compounding writeback"; fail=$((fail+1)); fi
  local n_att; n_att=$(jq '.attempts | length' "$goal_file" 2>/dev/null)
  if [[ "$state" != "failed" || "$n_att" -lt 3 ]]; then echo "[PASS] 7. No 3-try cap violation"; pass=$((pass+1))
  else echo "[FAIL] 7. 3-try cap reached without root-cause"; fail=$((fail+1)); fi
  echo "--- $pass/$((pass+fail)) gates passed ---"
  [[ "$fail" -eq 0 ]]
}

# --- ats-auto: full omnigoal loop in one call (v3.7.0) -----------------------
ats-auto() {
  if [[ $# -lt 2 ]]; then
    cat <<'EOF'
Usage: ats-auto "<title>" --oracle "<shell cmd>" \
  [--budget-tokens 50000] [--deadline 2h] [--repo <path>] [--skip-metareview]

Runs the full omnigoal loop: recall → contract → leverage → slice →
execute (you) → eval-gate (goal-check + ats-metareview) → learn (goal-close).
Returns after goal-init; you run the work, then call `ats-auto --continue <slug>`
to execute the eval-gate + learn + report steps.
EOF
    return 0
  fi
  local slug=""
  if [[ "${1:-}" == "--continue" ]]; then
    shift; slug="$1"; shift
    local goal_file="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}/$slug.json"
    [[ -f "$goal_file" ]] || { echo "ats-auto: goal not found: $slug" >&2; return 1; }
    local skip_mr=0
    [[ "${1:-}" == "--skip-metareview" ]] && skip_mr=1
    echo "=== ats-auto: EVAL-GATE for $slug ==="
    goal-check "$slug" || { echo "ats-auto: oracle still failing — work not done yet"; return 1; }
    if [[ "$skip_mr" -eq 0 ]]; then
      ats-metareview "$slug" --skip-if-missing
    fi
    ats-omnigoal-check "$slug" || { echo "ats-auto: hard gates not satisfied — not closing"; return 1; }
    echo "=== ats-auto: LEARN + REPORT ==="
    local summary="auto-closed via ats-auto at $(date -u +%FT%TZ)"
    goal-close "$slug" --summary "$summary" --decision "ats-auto loop completed"
    echo "=== ats-auto: REPORT ==="
    goal-list | head -5
    return $?
  fi
  local title="$1"; shift
  local skip_mr=0
  for a in "$@"; do [[ "$a" == "--skip-metareview" ]] && skip_mr=1; done
  echo "=== ats-auto: RECALL + CONTRACT for \"$title\" ==="
  ats-prime-and-init "$title" "$@"
  slug=$(echo -n "$title" | tr -c 'a-zA-Z0-9-' '-' | tr 'A-Z' 'a-z' | sed 's/--*/-/g;s/^-//;s/-$//')
  echo "=== ats-auto: LEVERAGE ==="
  ats-safe goal-leverage "$slug" 2>/dev/null || echo "(goal-leverage not available — skipping)"
  echo "=== ats-auto: SLICE ==="
  ats-safe goal-slice "$slug" 2>/dev/null || echo "(goal-slice not available — skipping)"
  echo ""
  echo "=== ats-auto: EXECUTE (your turn) ==="
  echo "Do the work now. Then run:"
  echo "  ats-auto --continue $slug $([[ $skip_mr -eq 1 ]] && echo --skip-metareview)"
  echo "to execute: goal-check + ats-metareview + ats-omnigoal-check + goal-close."
}

# --- Recon routing: gmax (local semantic) + ghx (GitHub) + supacrawl (web) ---
# v3.8.0 — Three complementary recon CLIs that share the token-saver doctrine:
#   gmax       — persistent semantic index of local codebases (replaces code_search
#                for indexed projects; --agent output is ledger-compatible).
#   ghx        — GitHub reconnaissance sidecar (GraphQL batching, --map 92% token
#                reduction, inspect ranks files by concern).
#   supacrawl  — HTTP-first web scraper (markdown output, map/crawl/batch/search;
#                Ollama-LLM-Extract for structured pulls without API keys).
# All three are fail-open: missing CLI → passthrough, never error.
# MCP servers deliberately NOT used — CLIs keep Cascade/agent context clean.

# gmax (grepmax) — local codebase semantic search.
# Index once per project:   gmax add /path/to/project
# Query from project root:  gmax "<question>" --agent
ats-gmax() {
  if ! ats-have gmax; then
    echo "ats-gmax: gmax not on PATH — install: npm install -g grepmax (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: ats-gmax "<question>" [--agent] [--add <path>] [--trace <symbol>] [--skeleton <file>] [--dead <symbol>]

Wraps grepmax (gmax) for token-efficient local codebase recon.
Default: semantic search with --agent output (single-line hits + score + role tag).

Subcommands:
  gmax add <path>            — index a project once (persistent under ~/.gmax/)
  gmax "<q>" --agent         — semantic search, agent-ready output
  gmax trace <symbol>        — call graph for a symbol
  gmax skeleton <file>       — signatures only (no implementation)
  gmax extract <symbol>      — full function/class body by name
  gmax peek <symbol>         — signature + callers + callees (compact)
  gmax dead <symbol>         — dead-code check (zero inbound calls)
  gmax status                — indexed projects overview
EOF
    return 0
  fi
  gmax "$@"
}

# ghx — GitHub reconnaissance for external repos (uses gh CLI auth).
# Expensive main agents delegate tree/grep/read loops to ghx's GraphQL batch.
ats-ghx() {
  if ! ats-have ghx; then
    echo "ats-ghx: ghx not on PATH — install: npm install -g @gkoreli/ghx (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: ats-ghx <subcommand> [args]

Wraps ghx (GitHub code-recon sidecar) for token-efficient external repo recon.
All subcommands use GraphQL batching (10 files/call) and --map output (~92% token
reduction vs raw file reads).

Common:
  ghx explore <owner/repo>                       — branch + tree + README in 1 call
  ghx read <owner/repo> <file> --map             — token-compressed file read
  ghx read <owner/repo> f1 f2 ... --map          — up to 10 files in 1 call
  ghx inspect <owner/repo> "<concern>"           — rank files/maps/snippets for a concern
  ghx search "<query>" --limit N                 — code search with matching context
  ghx grep <owner/repo> <pattern>                — grep-like search inside one repo
  ghx repos "<topic>" --limit N                  — repo discovery with README preview
  ghx tree <owner/repo>                          — full recursive tree
  ghx skill                                      — print SKILL.md for agent injection

Requires: gh CLI authenticated (gh auth login). No API key needed beyond gh's own.
EOF
    return 0
  fi
  ghx "$@"
}

# supacrawl — HTTP-first web scraper (no API key, Ollama optional for LLM-Extract).
# Complements superweb: lighter for quick scrapes, Python-native, install-skill
# drops a SKILL.md into ~/.claude/skills/ for Cascade-style agents.
ats-supacrawl() {
  if ! ats-have supacrawl; then
    echo "ats-supacrawl: supacrawl not on PATH — install: pip install supacrawl (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: ats-supacrawl <subcommand> [args]

Wraps supacrawl for HTTP-first web scraping. No API key required for scrape/map/
crawl/batch/search. LLM-Extract supports Ollama (local) but currently broken with
schema serialization — use `supacrawl scrape | ollama` directly as workaround.

Common:
  supacrawl scrape <url> --format markdown       — single page → markdown
  supacrawl map <url>                            — discover URLs from a site
  supacrawl crawl <url>                          — deep-crawl from starting URL
  supacrawl batch <file>                         — scrape list of URLs concurrently
  supacrawl search "<query>"                     — multi-provider search (needs key)
  supacrawl cache                                — manage local scrape cache
  supacrawl config get                           — inspect effective settings
  supacrawl install-skill                        — drop SKILL.md for agent injection

Env overrides (SUPACRAWL_<NAME>): engine, headless, only_main_content, ...
For heavy research use superweb research --deep (cited answer, local LLM).
EOF
    return 0
  fi
  supacrawl "$@"
}

# ats-supacrawl-extract — scrape + LLM-extract in one call, using the active
# agent's LLM via the stdio bridge (no Ollama, no API key). Returns JSON.
# Usage: ats-supacrawl-extract <url> "<prompt>" [schema.json]
ats-supacrawl-extract() {
  if ! ats-have supacrawl; then
    echo "ats-supacrawl-extract: supacrawl not on PATH — pip install supacrawl (fail-open)" >&2
    return 0
  fi
  if [[ $# -lt 2 ]]; then
    cat <<'EOF'
Usage: ats-supacrawl-extract <url> "<prompt>" [schema.json]

Scrapes <url> and LLM-extracts structured data using the active agent's LLM
(codex/kimi/claude/llm) via the ats-llm-pipe stdio bridge. No Ollama, no API key.

Env (optional):
  SUPACRAWL_LLM_STDIO_CMD  — override bridge command (default: ats-llm-pipe)
  ATS_LLM_PIPE_CMD         — pin a specific LLM CLI, e.g. "codex exec --skip-git-repo-check -"

Output: JSON with {markdown, llm_extraction, metadata} on stdout.

Examples:
  ats-supacrawl-extract https://example.com "Extract the heading"
  ats-supacrawl-extract https://news.ycombinator.com "Top 3 stories as {stories:[{title,points}]}"
EOF
    return 0
  fi
  local url="$1" prompt="$2" schema="${3:-}"
  # Enable stdio provider for this call if not already set.
  [[ -z "$SUPACRAWL_LLM_PROVIDER" ]] && export SUPACRAWL_LLM_PROVIDER=stdio
  [[ -z "$SUPACRAWL_LLM_MODEL" ]] && export SUPACRAWL_LLM_MODEL=active
  local args=(scrape "$url" --format json --prompt "$prompt")
  [[ -n "$schema" ]] && args+=(--schema "$schema")
  supacrawl "${args[@]}" 2>/dev/null
}

# ats-recon — auto-router that picks the optimal recon tool for a query.
#   - Local codebase question  → gmax (semantic, --agent output)
#   - GitHub repo question      → ghx (inspect/read --map)
#   - URL or "extract from URL" → supacrawl scrape / extract
#   - Web search query          → supacrawl search (if key) or hint to use superweb
# Fails open: if the picked tool is missing, prints a hint and returns 0.
ats-recon() {
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: ats-recon "<question>" [--url <url>] [--repo <owner/repo>] [--extract "<prompt>"]

Auto-routes to the cheapest recon tool that can answer the question:
  1. Local codebase    → gmax "<q>" --agent   (semantic, ledger-compatible)
  2. GitHub repo       → ghx inspect <repo> "<q>"  (GraphQL batch, --map)
  3. URL scrape        → supacrawl scrape <url>     (markdown, no LLM)
  4. URL + extract     → ats-supacrawl-extract <url> "<prompt>"  (LLM JSON)
  5. Web search        → supacrawl search "<q>"      (needs API key)

Flags:
  --url <url>        — target URL for scrape/extract
  --repo <owner/repo> — target GitHub repo
  --extract "<p>"    — LLM extraction prompt (implies --url)
  --json             — force JSON output where supported

Decision heuristic (no flag): if query contains "github.com/<owner>/<repo>" → ghx;
if it starts with http(s):// → supacrawl scrape; else → gmax (local).

Examples:
  ats-recon "where is usage parsing handled"
  ats-recon "what does Supersynergy/agent-token-saver README say"
  ats-recon "extract top 3 stories from https://news.ycombinator.com" --extract "top 3 stories {title,points}"
EOF
    return 0
  fi
  local query="" url="" repo="" extract="" json_out=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url) url="$2"; shift 2 ;;
      --repo) repo="$2"; shift 2 ;;
      --extract) extract="$2"; shift 2 ;;
      --json) json_out=1; shift ;;
      *) query="$1"; shift ;;
    esac
  done

  # Decision tree
  if [[ -n "$extract" && -n "$url" ]]; then
    # URL + LLM extraction
    ats-supacrawl-extract "$url" "$extract"
    return $?
  fi
  if [[ -n "$url" ]]; then
    # Plain scrape
    ats-supacrawl scrape "$url" --format markdown 2>/dev/null
    return $?
  fi
  if [[ -n "$repo" ]]; then
    # GitHub repo
    if ! ats-have ghx; then
      echo "ats-recon: ghx not installed — npm i -g @gkoreli/ghx" >&2
      return 0
    fi
    ghx inspect "$repo" "$query" 2>/dev/null
    return $?
  fi
  # Auto-detect from query
  if [[ "$query" =~ github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+) ]]; then
    repo="${match[1]}"
    if ats-have ghx; then
      ghx inspect "$repo" "$query" 2>/dev/null
      return $?
    fi
  fi
  if [[ "$query" =~ ^https?:// ]]; then
    ats-supacrawl scrape "$query" --format markdown 2>/dev/null
    return $?
  fi
  # Default: local codebase via gmax
  if ats-have gmax; then
    gmax "$query" --agent 2>/dev/null
  else
    echo "ats-recon: gmax not installed — npm i -g grepmax (fail-open)" >&2
    return 0
  fi
}

# ats-recon-doctor — quick health check for the three recon CLIs + stdio bridge.
ats-recon-doctor() {
  echo "=== Recon CLIs (v3.8.0) ==="
  echo "gmax:       $(command -v gmax || echo 'MISSING (npm i -g grepmax)')"
  echo "ghx:        $(command -v ghx || echo 'MISSING (npm i -g @gkoreli/ghx)')"
  echo "supacrawl:  $(command -v supacrawl || echo 'MISSING (pip install supacrawl)')"
  echo "ats-llm-pipe: $(command -v ats-llm-pipe || echo 'MISSING (ln -sf .../ats-llm-pipe ~/.local/bin/)')"
  echo "gh (ghx dep): $(command -v gh || echo 'MISSING (gh auth login)')"
  echo "ollama (legacy): $(command -v ollama || echo 'MISSING (optional, stdio bridge replaces this)')"
  echo
  echo "stdio bridge LLMs detected by ats-llm-pipe:"
  for c in codex kimi claude llm; do
    echo "  $c: $(command -v $c || echo 'not on PATH')"
  done
  echo
  echo "SUPACRAWL_LLM_PROVIDER: ${SUPACRAWL_LLM_PROVIDER:-<unset>}"
  echo "SUPACRAWL_LLM_MODEL:    ${SUPACRAWL_LLM_MODEL:-<unset>}"
  echo "ATS_LLM_PIPE_CMD:       ${ATS_LLM_PIPE_CMD:-<auto>}"
  if ats-have gmax; then
    echo "--- gmax indexed projects ---"
    gmax status 2>/dev/null | head -10
  fi
}

# --- Doctor -----------------------------------------------------------------

ats-doctor() {
  echo "=== Agent Token-Saver Doctor ==="
  echo "rtk: $(command -v rtk || echo 'MISSING (fail-open pass-through)')"
  echo "si:  $(command -v si || echo 'MISSING (skill routing skipped)')"
  echo "agent-token-ledger: $(command -v agent-token-ledger || echo 'MISSING (post-session ledger unavailable)')"
  echo "agent-token-saver:  $(command -v agent-token-saver || echo 'MISSING (doctor unavailable)')"
  echo "synx: $(command -v synx || echo 'MISSING (synapse hybrid recall unavailable)')"
  local ultra_bin="${SYNAPSE_ULTRA_BIN:-$HOME/projects/synapse-memory/target/release/synapse-ultra}"
  echo "synapse-ultra: $([[ -x "$ultra_bin" ]] && echo "$ultra_bin" || echo 'MISSING (build: cargo build -p synapse-ultra --release)')"
  echo "duckdb: $(command -v duckdb || echo 'MISSING (DuckLake archive unavailable)')"
  echo "jq:     $(command -v jq || echo 'MISSING (goal system requires jq)')"
  echo "gmax:       $(command -v gmax || echo 'MISSING (npm i -g grepmax)')"
  echo "ghx:        $(command -v ghx || echo 'MISSING (npm i -g @gkoreli/ghx)')"
  echo "supacrawl:  $(command -v supacrawl || echo 'MISSING (pip install supacrawl)')"
  echo "ats-llm-pipe: $(command -v ats-llm-pipe || echo 'MISSING (ln -sf .../ats-llm-pipe ~/.local/bin/)')"
  echo "ats-token-cfo: $(declare -F ats-token-cfo >/dev/null 2>&1 && echo 'loaded (v4.0.0)' || echo 'MISSING (source ats-token-cfo)')"
  echo "ats-goal-archive: $(declare -F ats-goal-archive >/dev/null 2>&1 && echo 'loaded (v4.0.0)' || echo 'MISSING (v4.0.0)')"
  echo "token-cfo pkg: $([[ -d "${ATS_TOKEN_CFO_DIR:-$HOME/projects/token-cfo}" ]] && echo "${ATS_TOKEN_CFO_DIR:-$HOME/projects/token-cfo}" || echo 'MISSING (set ATS_TOKEN_CFO_DIR)')"
  echo "metareview skill: $([[ -d "${METAREVIEW_ROOT:-$HOME/.claude/skills/metareview}" ]] && echo "${METAREVIEW_ROOT:-$HOME/.claude/skills/metareview}" || echo 'MISSING (optional, --via metareview)')"
  local goals_dir="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
  local n_goals=0
  [[ -d "$goals_dir" ]] && n_goals=$(ls -1 "$goals_dir"/*.json 2>/dev/null | wc -l | tr -d ' ')
  echo "goals:  ${n_goals} in ${goals_dir} (goal-init / goal-check / goal-list)"
  echo "AGENT_TOKEN_SAVER_LOADED: ${AGENT_TOKEN_SAVER_LOADED:-0}"
  echo "ATS_AGENT_NAME: ${ATS_AGENT_NAME:-agent}"
  echo "ATS_AGENT_DETECTED: ${ATS_AGENT_DETECTED:-0}"
  echo "ATS_ACTIVE_SKILL: ${ATS_ACTIVE_SKILL:-none}"
  echo
  echo "Adaptive functions:"
  declare -F ats-detect-agent ats-safe ats-have ats-prime-and-init ats-parallel ats-metareview ats-omnigoal-check ats-auto ats-gmax ats-ghx ats-supacrawl ats-supacrawl-extract ats-recon ats-recon-doctor ats-token-cfo ats-goal-archive 2>/dev/null | awk '{print "  "$3}'
  echo
  echo "Aliases installed:"
  type ps 2>/dev/null | head -1
  type gitdiff 2>/dev/null | head -1
  type gitlog 2>/dev/null | head -1
}
