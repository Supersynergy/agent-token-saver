#!/usr/bin/env bash
# goal.sh — Universal goal-achievement CLI for ALL agents.
# Built on omnigoal law + 2026 research (AgentLTL, AgentVerify, delegato, Orloj, Network-AI, CAPO).
# See ~/BASE/docs/goal-system-rework.md for full spec + ADRs.
#
# 13 functions: init / recall / leverage / slice / spawn / check / verify / refute /
# close / trace / trust / list / doctor. Backward-compat: devin-goal-* are 1-line
# aliases (kept in devin-token-saver.sh).
#
# Fail-open: missing synx/agentmaster/git → skip with warning. Missing jq → hard fail.
# Idempotency: re-sourcing is safe (guard via GOAL_SH_LOADED).

[ -n "${GOAL_SH_LOADED:-}" ] && return 0 2>/dev/null || true
GOAL_SH_LOADED=1

# --- Config ------------------------------------------------------------------
GOAL_GOALS_DIR="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
GOAL_ORACLE_LOG="${GOAL_ORACLE_LOG:-/tmp/goal-oracle.log}"
GOAL_REFUTE_LOG="${GOAL_REFUTE_LOG:-/tmp/goal-refute.log}"
GOAL_TRACE_LOG="${GOAL_TRACE_LOG:-/tmp/goal-trace.log}"

# --- Helpers -----------------------------------------------------------------
_goal_die() { echo "ERR: $*" >&2; exit 1; }
_goal_warn() { echo "WARN: $*" >&2; }
_goal_have() { command -v "$1" >/dev/null 2>&1; }
_goal_slug() {
  echo -n "$1" | tr -c 'a-zA-Z0-9-' '-' | tr 'A-Z' 'a-z' | sed 's/--*/-/g;s/^-//;s/-$//'
}
_goal_file() { echo "${GOAL_GOALS_DIR}/$1.json"; }
_goal_now() { date +%s; }
_goal_ts_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# deadline "2h" -> epoch seconds from now
_goal_deadline_epoch() {
  local d="$1" created="$2"
  local n multi
  n="${d//[!0-9]/}"
  multi="${d//[0-9]/}"
  case "$multi" in
    m|min) multi=60 ;;
    h|hr|hour) multi=3600 ;;
    d|day) multi=86400 ;;
    *) multi=3600 ;;
  esac
  echo $(( created + n * multi ))
}

# closed-verb enforcement (omnigoal anti-pattern: open verbs never converge)
# closed verbs contain measurable condition: "to <N>", "green", "pass <test>", "reach <state>"
_goal_is_open_verb() {
  local t="$1"
  # open verbs that diverge forever
  case "$t" in
    *"optimi"*|*"improve"*|*"polish"*|*"refactor"*|*"clean up"*|*"cleanup"*|*"enhance"*|*"tweak"*|*"streamline"*|*"simplify"*)
      return 0 ;;
  esac
  # no measurable condition → likely open
  if ! echo "$t" | grep -qiE '(to[ _-]?[0-9]+|<n|green|pass(es|ing)?|fail(s|ing)?|reach|reduce|increase[ _-]?by|=[ _-]?[0-9]+|≤|≥|<|>|^[0-9]+ )'; then
    return 0
  fi
  return 1
}

# --- 1. goal-init ------------------------------------------------------------
goal-init() {
  if [[ $# -lt 2 ]]; then
    cat <<'EOF'
Usage: goal-init "<title>" --oracle "<shell cmd>" \
  [--budget-tokens 50000] [--deadline 2h] [--repo <path>] \
  [--agent devin|codex|claude|cmux|kimi-worker|auto] [--force] [--eval-written]

Creates ~/.synapse/goals/<slug>.json — a machine-checkable goal contract
any agent can pick up. The oracle MUST be a shell command returning 0 on success.

Closed-verb enforcement: title must contain a measurable condition
("reduce X to <N", "make green", "pass <test>"). Open verbs ("optimize",
"improve", "polish") are rejected unless --force is passed.

Examples:
  goal-init "reduce test-runtime to <30s" --oracle "hyperfine --runs 1 cargo test 2>&1 | grep -q '< 30s'"
  goal-init "make ci green" --oracle "just ci 2>&1 | tail -1 | grep -q 'PASS'"
  goal-init "reach 100% type coverage" --oracle "cargo tarpaulin 2>&1 | grep -q '100.00%'"
EOF
    return 0
  fi
  local title="$1"; shift
  local oracle="" budget=50000 deadline="2h" repo="${PWD}" agent="auto" force=0 eval_written=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --oracle) oracle="$2"; shift 2 ;;
      --budget-tokens) budget="$2"; shift 2 ;;
      --deadline) deadline="$2"; shift 2 ;;
      --repo) repo="$2"; shift 2 ;;
      --agent) agent="$2"; shift 2 ;;
      --force) force=1; shift ;;
      --eval-written) eval_written=true; shift ;;
      *) shift ;;
    esac
  done
  if [[ -z "$oracle" ]]; then
    echo "goal-init: --oracle is required" >&2; return 1
  fi
  if [[ "$force" -eq 0 ]] && _goal_is_open_verb "$title"; then
    echo "goal-init: rejected — title uses open verb (optimize/improve/polish/...)." >&2
    echo "  Closed verbs converge; open verbs diverge forever (omnigoal anti-pattern)." >&2
    echo "  Use a measurable condition: 'reduce X to <N', 'make green', 'pass <test>'." >&2
    echo "  Override with --force (exploratory goals only)." >&2
    return 1
  fi
  if ! _goal_have jq; then
    echo "goal-init: jq is required (hard dependency for JSON manipulation)" >&2; return 1
  fi
  mkdir -p "$GOAL_GOALS_DIR"
  local slug; slug=$(_goal_slug "$title")
  local goal_file; goal_file=$(_goal_file "$slug")
  local ts; ts=$(_goal_now)
  # backward-compat: v3.4.0 schema fields + new v3.5.0 fields
  jq -n \
    --arg id "$slug" \
    --arg title "$title" \
    --arg oracle "$oracle" \
    --arg deadline "$deadline" \
    --arg repo "$repo" \
    --arg agent "$agent" \
    --argjson budget "$budget" \
    --argjson ts "$ts" \
    --argjson eval_written "$eval_written" \
    '{id:$id, title:$title, oracle:$oracle, budget_tokens:$budget,
      deadline:$deadline, repo:$repo, agent:$agent, created_ts:$ts,
      state:"open", attempts:[], subagents:[],
      bottleneck:null, levers:[], slice:null, eval_written:$eval_written,
      spawn_ts:null, passed_ts:null, closed_ts:null, summary:"",
      evidence:{commits:[], tests_green:null, refuter:"SKIPPED", trace_compliant:null}}' \
    >"$goal_file"
  echo "$goal_file"
  echo "  Oracle:  $oracle"
  echo "  Budget:  $budget tokens, deadline $deadline"
  echo "  Agent:   $agent"
  echo "  Next:    goal-recall $slug  # synx hybrid pre-session"
  echo "          goal-leverage $slug --bottleneck '<null-term>' --lever '<l1>' --lever '<l2>'"
}

# --- 2. goal-recall ----------------------------------------------------------
goal-recall() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: goal-recall <slug> [--query "<keywords>"]' >&2; return 1
  fi
  local slug="$1"; shift
  local query="$slug"
  [[ ${1:-} == "--query" ]] && { query="${2:-$slug}"; shift 2 2>/dev/null || true; }
  if ! _goal_have synx; then
    _goal_warn "synx not on PATH — recall skipped (fail-open)"
    return 0
  fi
  synx hybrid "$query" 8
}

# --- 3. goal-leverage --------------------------------------------------------
goal-leverage() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: goal-leverage <slug> --bottleneck "<null-term>" --lever "<l1>" --lever "<l2>"' >&2
    return 1
  fi
  local slug="$1"; shift
  local bottleneck="" levers=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --bottleneck) bottleneck="$2"; shift 2 ;;
      --lever) levers+=("$2"); shift 2 ;;
      *) shift ;;
    esac
  done
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-leverage: goal not found: $slug" >&2; return 1; }
  if [[ -z "$bottleneck" ]]; then
    echo "goal-leverage: --bottleneck is required (omnigoal: no bottleneck = 80% waste)" >&2
    return 1
  fi
  if [[ ${#levers[@]} -lt 2 ]]; then
    echo "goal-leverage: need at least 2 --lever args (omnigoal: min 2 levers)" >&2
    return 1
  fi
  local lever_json; lever_json=$(printf '%s\n' "${levers[@]}" | jq -R . | jq -s .)
  jq --arg b "$bottleneck" --argjson l "$lever_json" \
    '.bottleneck = $b | .levers = $l' "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "Bottleneck: $bottleneck"
  echo "Levers:     ${levers[*]}"
}

# --- 4. goal-slice -----------------------------------------------------------
goal-slice() {
  if [[ $# -lt 2 ]]; then
    echo 'Usage: goal-slice <slug> "<smallest reversible vertical slice>"' >&2; return 1
  fi
  local slug="$1"; shift
  local slice="$*"
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-slice: goal not found: $slug" >&2; return 1; }
  jq --arg s "$slice" '.slice = $s' "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "Slice: $slice"
}

# --- 5. goal-spawn -----------------------------------------------------------
goal-spawn() {
  if [[ $# -lt 2 ]]; then
    cat <<'EOF'
Usage: goal-spawn <slug> --capsule <capsule.md> [--skill <name>] \
  [--agent devin|codex|claude|cmux|kimi-worker] [--via agentmaster]

Registers a bounded subagent in the goal JSON. Subagent sees only capsule +
goal oracle, never the parent transcript. Trust starts at 0.5 (delegato pattern).

--via agentmaster: uses `agentmaster batch` for cmux fleet fan-out (fail-open
to capsule-only if agentmaster missing).
EOF
    return 1
  fi
  local slug="$1"; shift
  local capsule="" skill="" agent="" via=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --capsule) capsule="$2"; shift 2 ;;
      --skill) skill="$2"; shift 2 ;;
      --agent) agent="$2"; shift 2 ;;
      --via) via="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-spawn: goal not found: $slug" >&2; return 1; }
  [[ -f "$capsule" ]] || { echo "goal-spawn: capsule not found: $capsule" >&2; return 1; }
  local sub_id="sub-$(_goal_now)-$RANDOM"
  local spawn_ts; spawn_ts=$(_goal_now)
  # privilege attenuation: subagent inherits reduced permissions (delegato pattern)
  jq \
    --arg id "$sub_id" \
    --arg capsule "$capsule" \
    --arg skill "${skill:-none}" \
    --arg agent "${agent:-auto}" \
    --argjson spawn_ts "$spawn_ts" \
    '.subagents += [{"id":$id, "capsule":$capsule, "skill":$skill, "agent":$agent,
      "state":"spawned", "trust":0.5, "spawn_ts":$spawn_ts, "attempts":0}]' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  # set goal spawn_ts if not already set (for verify-back)
  jq --argjson ts "$spawn_ts" 'if .spawn_ts == null then .spawn_ts = $ts else . end' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "$sub_id"
  echo "  Capsule: $capsule ($(wc -c <"$capsule") bytes, ~$(($(wc -c <"$capsule")/4)) tokens)"
  echo "  Skill:   ${skill:-none}"
  echo "  Agent:   ${agent:-auto}"
  echo "  Trust:   0.5 (initial)"
  if [[ "$via" == "agentmaster" ]]; then
    if _goal_have agentmaster; then
      local am; am=$(command -v agentmaster)
      echo "  via:     agentmaster ($am)"
      local goal_title; goal_title=$(jq -r .title "$goal_file")
      local oracle; oracle=$(jq -r .oracle "$goal_file")
      echo "  # agentmaster batch (fan-out):"
      echo "  $am goal $slug '${goal_title} :: ${oracle}'"
    else
      _goal_warn "agentmaster not on PATH — falling back to capsule-only (fail-open)"
    fi
  fi
  echo ""
  echo "Subagent contract: read goal oracle + capsule only. No parent transcript."
  echo "On completion: goal-check $slug && goal-verify $slug && goal-refute $slug && goal-close $slug --summary \"...\""
}

# --- 6. goal-check (oracle + 3-try cap + budget/deadline enforcement) --------
goal-check() {
  if [[ $# -lt 1 ]]; then
    # list mode
    ls -1 "$GOAL_GOALS_DIR"/*.json 2>/dev/null | while read -r f; do
      jq -r '"\(.id)\t\(.state)\t\(.title)"' "$f" 2>/dev/null
    done
    return 0
  fi
  local slug="$1"
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-check: goal not found: $slug" >&2; return 1; }
  if ! _goal_have jq; then
    echo "goal-check: jq is required" >&2; return 1
  fi

  # budget + deadline enforcement (ADR-6)
  local budget created deadline tokens_used now deadline_epoch
  budget=$(jq -r .budget_tokens "$goal_file")
  created=$(jq -r .created_ts "$goal_file")
  deadline=$(jq -r .deadline "$goal_file")
  tokens_used=$(jq '[.attempts[].tokens_used] | add // 0' "$goal_file")
  now=$(_goal_now)
  deadline_epoch=$(_goal_deadline_epoch "$deadline" "$created")
  if [[ "$tokens_used" -gt "$budget" ]]; then
    jq --argjson ts "$now" '.state = "failed" | .failed_ts = $ts | .failure_reason = "budget_exhausted"' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    echo "BUDGET EXHAUSTED: $tokens_used > $budget tokens — state=failed" >&2
    return 1
  fi
  if [[ "$now" -gt "$deadline_epoch" ]]; then
    jq --argjson ts "$now" '.state = "failed" | .failed_ts = $ts | .failure_reason = "deadline_exceeded"' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    echo "DEADLINE EXCEEDED: now=$now > deadline_epoch=$deadline_epoch — state=failed" >&2
    return 1
  fi

  # 3-try cap (ADR-3)
  local n_attempts
  n_attempts=$(jq '.attempts | length' "$goal_file")
  if [[ "$n_attempts" -ge 3 ]]; then
    local rc="$GOAL_GOALS_DIR/${slug}.root-cause.md"
    if [[ ! -f "$rc" ]]; then
      cat >"$rc" <<EOF
# Root-cause analysis: $slug

3-try cap reached at $(_goal_ts_iso). Further attempts refused until root-cause
is addressed. Inspect the oracle log at $GOAL_ORACLE_LOG and the attempts below.

## Attempts
$(jq -r '.attempts[] | "- ts=\(.ts) exit=\(.exit_code) bottleneck=\(.bottleneck) tokens=\(.tokens_used)"' "$goal_file")

## Bottleneck (last identified)
$(jq -r '.bottleneck // "unknown"' "$goal_file")

## Next step
Fix the root cause, then either:
  goal-init --force "< revised title >" --oracle "< revised oracle >"
  # or manually reset: jq '.attempts = []' < $goal_file > $goal_file.tmp && mv $goal_file.tmp $goal_file
EOF
    fi
    echo "3-TRY CAP reached — root-cause note at $rc" >&2
    echo "Further checks refused until root-cause is addressed." >&2
    return 1
  fi

  local oracle; oracle=$(jq -r .oracle "$goal_file")
  echo "=== Goal: $slug ==="
  echo "Oracle: $oracle"
  echo "Attempt: $((n_attempts + 1))/3  |  Budget: $tokens_used/$budget tokens  |  Deadline: $deadline"
  echo "--- Running oracle ---"
  local exit_code=0 tokens_this=0
  if bash -c "$oracle" >"$GOAL_ORACLE_LOG" 2>&1; then
    echo "ORACLE: PASS"
    tokens_this=$(wc -c <"$GOAL_ORACLE_LOG" 2>/dev/null | awk '{print int($1/4)}')
    jq --argjson ts "$now" --argjson tokens "$tokens_this" \
      '.state = "passed" | .passed_ts = $ts | .attempts += [{"ts":$ts, "exit_code":0, "bottleneck":null, "tokens_used":$tokens}] | .evidence.tests_green = true' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    return 0
  else
    exit_code=$?
    echo "ORACLE: FAIL (exit $exit_code)"
    tail -5 "$GOAL_ORACLE_LOG" 2>/dev/null
    local bottleneck
    bottleneck=$(grep -iE 'error|fail|not found|missing|panic' "$GOAL_ORACLE_LOG" 2>/dev/null | head -1)
    echo "BOTTLENECK: ${bottleneck:-unknown — inspect $GOAL_ORACLE_LOG}"
    tokens_this=$(wc -c <"$GOAL_ORACLE_LOG" 2>/dev/null | awk '{print int($1/4)}')
    jq --argjson ts "$now" --argjson exit_code "$exit_code" \
       --arg b "${bottleneck:-unknown}" --argjson tokens "$tokens_this" \
      '.state = "failed" | .attempts += [{"ts":$ts, "exit_code":$exit_code, "bottleneck":$b, "tokens_used":$tokens}]' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    return 1
  fi
}

# --- 7. goal-verify (verify-back via git commits since spawn_ts) -------------
goal-verify() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: goal-verify <slug>' >&2; return 1
  fi
  local slug="$1"
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-verify: goal not found: $slug" >&2; return 1; }
  local repo spawn_ts
  repo=$(jq -r .repo "$goal_file")
  spawn_ts=$(jq -r '.spawn_ts // empty' "$goal_file")
  if [[ -z "$spawn_ts" ]]; then
    echo "goal-verify: no spawn_ts set — run goal-spawn first" >&2; return 1
  fi
  if [[ ! -d "$repo/.git" ]]; then
    _goal_warn "repo has no .git: $repo — verify-back skipped (fail-open)"
    return 0
  fi
  if ! _goal_have git; then
    _goal_warn "git not on PATH — verify-back skipped (fail-open)"
    return 0
  fi
  local since_date commits_json
  since_date=$(date -u -r "$spawn_ts" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -u -d "@$spawn_ts" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null)
  # real work = commits, not mtime (agent-loop principle)
  local commits
  commits=$(git -C "$repo" log --since="$since_date" --pretty=format:'%H' 2>/dev/null || true)
  commits_json=$(printf '%s\n' "$commits" | grep -c '^' | xargs -I{} echo "[]" 2>/dev/null)
  if [[ -z "$commits" ]]; then
    echo "VERIFY: NO COMMITS since $since_date — no real work detected"
    jq '.evidence.commits = [] | .evidence.tests_green = (.evidence.tests_green // false)' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    return 1
  fi
  local n_commits
  n_commits=$(echo "$commits" | wc -l | tr -d ' ')
  echo "VERIFY: $n_commits commit(s) since $since_date"
  echo "$commits" | head -5 | while read -r sha; do echo "  $sha"; done
  local commits_jq
  commits_jq=$(printf '%s\n' "$commits" | jq -R . | jq -s .)
  jq --argjson c "$commits_jq" '.evidence.commits = $c' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  return 0
}

# --- 8. goal-refute (fresh subagent, no parent context) ----------------------
goal-refute() {
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: goal-refute <slug> [--via agentmaster|--manual]

Spawns a FRESH subagent (no parent transcript) to refute the DoD. Default
verdict = "NICHT-ERFÜLLT". Catches honesty-bugs at the last inch.

--via agentmaster: uses `agentmaster send` to a fresh workspace.
--manual: prints the refutation prompt for manual use (default if no runtime).
EOF
    return 1
  fi
  local slug="$1"; shift
  local via="manual"
  [[ "${1:-}" == "--via" ]] && { via="${2:-manual}"; shift 2 2>/dev/null || true; }
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-refute: goal not found: $slug" >&2; return 1; }
  local oracle repo dod diff_cmd
  oracle=$(jq -r .oracle "$goal_file")
  repo=$(jq -r .repo "$goal_file")
  dod=$(jq -r .title "$goal_file")
  local spawn_ts; spawn_ts=$(jq -r '.spawn_ts // empty' "$goal_file")
  local since_date=""
  if [[ -n "$spawn_ts" ]]; then
    since_date=$(date -u -r "$spawn_ts" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -u -d "@$spawn_ts" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || true)
  fi
  diff_cmd="git -C '$repo' log --since='$since_date' --oneline 2>/dev/null"
  local prompt
  prompt=$(cat <<EOF
You are a FRESH reviewer agent. You have NO context from the builder.
Widerlege die Definition-of-Done — finde einen konkreten Grund warum DoD NICHT erfüllt ist.
Default verdict: NICHT-ERFÜLLT (only ERFÜLLT if you find concrete proof).

DoD (title): $dod
Oracle (must pass): $oracle
Diff (commits since spawn): $diff_cmd

Antworte: ERFÜLLT oder NICHT-ERFÜLLT + Grund.
Vorsicht mit Zustimmung — Standard sollte NICHT-ERFÜLLT sein bei Unsicherheit.
EOF
)
  echo "$prompt" >"$GOAL_REFUTE_LOG"
  local verdict="SKIPPED"
  if [[ "$via" == "agentmaster" ]] && _goal_have agentmaster; then
    local am; am=$(command -v agentmaster)
    # spawn fresh workspace + send refute prompt
    "$am" start --here --name "refute-$slug" 2>/dev/null || true
    "$am" send "workspace:refute-$slug" "$prompt" 2>/dev/null || true
    echo "Refutation prompt sent to agentmaster workspace:refute-$slug"
    echo "Review verdict there. Mark with: goal-trust $slug <sub_id> refuted|done"
    verdict="PENDING"
  else
    echo "=== Refutation prompt (manual) ==="
    cat "$GOAL_REFUTE_LOG"
    echo ""
    echo "Run this in a FRESH agent session. Then record verdict:"
    echo "  jq --arg v 'PASS|FAIL' '.evidence.refuter = \$v' $goal_file > $goal_file.tmp && mv $goal_file.tmp $goal_file"
    verdict="PENDING"
  fi
  jq --arg v "$verdict" '.evidence.refuter = $v' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
}

# --- 9. goal-close (refuses if oracle failing OR refute found a hole) --------
goal-close() {
  if [[ $# -lt 1 ]]; then
    echo 'Usage: goal-close <slug> --summary "<text>" [--decision "<rationale>"] [--skip-refute] [--require-metareview]' >&2
    return 1
  fi
  local slug="$1"; shift
  local summary="" decision="" skip_refute=0 require_mr=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --summary) summary="$2"; shift 2 ;;
      --decision) decision="$2"; shift 2 ;;
      --skip-refute) skip_refute=1; shift ;;
      --require-metareview) require_mr=1; shift ;;
      *) shift ;;
    esac
  done
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-close: goal not found: $slug" >&2; return 1; }
  # refuse if oracle failing
  if ! goal-check "$slug" >/dev/null 2>&1; then
    echo "goal-close: oracle still failing — close refused" >&2; return 1
  fi
  # refuse if refute found a hole (unless --skip-refute)
  local refuter
  refuter=$(jq -r '.evidence.refuter // "SKIPPED"' "$goal_file")
  if [[ "$skip_refute" -eq 0 && "$refuter" == "FAIL" ]]; then
    echo "goal-close: refuter found a hole (FAIL) — close refused. Use --skip-refute to override." >&2
    return 1
  fi
  # --require-metareview: refuse if no foreign reviewer was ever run (omnigoal hard gate #5)
  if [[ "$require_mr" -eq 1 && "$refuter" == "SKIPPED" ]]; then
    echo "goal-close: --require-metareview set and no metareview recorded — close refused." >&2
    echo "  Run: ats-metareview $slug   (or goal-refute $slug --via agentmaster)" >&2
    return 1
  fi
  local now; now=$(_goal_now)
  # compounding writeback (ADR-10): synx put summary + decision
  if _goal_have synx; then
    [[ -n "$summary" ]] && echo "$summary" | synx put --title "goal-close:$slug"
    if [[ -n "$decision" ]]; then
      local bottleneck levers
      bottleneck=$(jq -r '.bottleneck // "unknown"' "$goal_file")
      levers=$(jq -r '.levers | join(", ")' "$goal_file")
      {
        echo "Decision: $decision"
        echo "Bottleneck: $bottleneck"
        echo "Levers: $levers"
        echo "Verify: $(jq -r .oracle "$goal_file")"
      } | synx put --title "decision:goal-$slug-$(date +%F)"
    fi
  fi
  jq --arg s "$summary" --argjson ts "$now" \
    '.state = "closed" | .closed_ts = $ts | .summary = $s' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "CLOSED: $slug"
  echo "  Summary: $summary"
  [[ -n "$decision" ]] && echo "  Decision: $decision (written to synx)"
}

# --- 10. goal-trace (LTL-style procedural compliance) ------------------------
goal-trace() {
  if [[ $# -lt 1 ]]; then
    cat <<'EOF'
Usage: goal-trace <slug> --ltl "<expr>"

Checks LTL-style procedural compliance over the execution trace.
Supported operators:
  always(P)       — P holds in every state
  eventually(P)   — P holds in some future state
  P before Q      — P occurs before Q
  P until Q       — P holds until Q

P is a shell command returning 0 on success. Trace source: git log + test runs.
Default: always(test_green before commit)

Example:
  goal-trace mygoal --ltl "always(just ci 2>&1 | grep -q PASS) before(git log --oneline | head -1 | grep -q .)"
EOF
    return 1
  fi
  local slug="$1"; shift
  local ltl=""
  [[ "${1:-}" == "--ltl" ]] && { ltl="${2:-}"; shift 2 2>/dev/null || true; }
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-trace: goal not found: $slug" >&2; return 1; }
  if [[ -z "$ltl" ]]; then ltl="always(test_green before commit)"; fi
  echo "=== Trace check: $slug ==="
  echo "LTL: $ltl"
  # parse simple always(P) before(Q) pattern
  local compliant=true
  if echo "$ltl" | grep -qE 'always\(.*before\('; then
    local p q
    p=$(echo "$ltl" | sed -nE 's/.*always\((.*)\) before\(.*/\1/p')
    q=$(echo "$ltl" | sed -nE 's/.*before\((.*)\).*/\1/p')
    # check: every commit has a passing test before it
    local repo; repo=$(jq -r .repo "$goal_file")
    if [[ -d "$repo/.git" ]]; then
      local commits
      commits=$(git -C "$repo" log --pretty=format:'%H' 2>/dev/null | head -10)
      for sha in $commits; do
        if ! bash -c "$p" >"$GOAL_TRACE_LOG" 2>&1; then
          echo "  VIOLATION at $sha: P failed"
          compliant=false
          break
        fi
      done
    fi
  elif echo "$ltl" | grep -qE 'always\('; then
    local p
    p=$(echo "$ltl" | sed -nE 's/.*always\((.*)\).*/\1/p')
    if ! bash -c "$p" >"$GOAL_TRACE_LOG" 2>&1; then
      echo "  VIOLATION: always(P) failed"
      compliant=false
    fi
  fi
  if $compliant; then
    echo "TRACE: COMPLIANT"
    jq --argjson c true '.evidence.trace_compliant = $c' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    return 0
  else
    echo "TRACE: NON-COMPLIANT"
    tail -5 "$GOAL_TRACE_LOG" 2>/dev/null
    jq --argjson c false '.evidence.trace_compliant = $c' \
      "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
    return 1
  fi
}

# --- 11. goal-trust (per-subagent trust scoring + circuit breaker) -----------
goal-trust() {
  if [[ $# -lt 3 ]]; then
    cat <<'EOF'
Usage: goal-trust <slug> <sub_id> <outcome>

Outcome: done | failed | refuted
Updates trust: +0.05 on done, -0.15 on failed, -0.30 on refuted (asymmetric).
Circuit breaker: if |trust_today - trust_before| > 0.3 → subagent paused.
EOF
    return 1
  fi
  local slug="$1" sub_id="$2" outcome="$3"
  local goal_file; goal_file=$(_goal_file "$slug")
  [[ -f "$goal_file" ]] || { echo "goal-trust: goal not found: $slug" >&2; return 1; }
  local delta
  case "$outcome" in
    done) delta=0.05 ;;
    failed) delta=-0.15 ;;
    refuted) delta=-0.30 ;;
    *) echo "goal-trust: invalid outcome: $outcome (use done|failed|refuted)" >&2; return 1 ;;
  esac
  local old_trust new_trust
  old_trust=$(jq --arg id "$sub_id" -r '(.subagents[] | select(.id == $id) | .trust) // 0.5' "$goal_file")
  new_trust=$(awk -v o="$old_trust" -v d="$delta" 'BEGIN { t = o + d; if (t < 0) t = 0; if (t > 1) t = 1; printf "%.3f", t }')
  local circuit=0
  if awk -v o="$old_trust" -v n="$new_trust" 'BEGIN { exit !( (o - n) > 0.3 || (n - o) > 0.3 ) }'; then
    circuit=1
  fi
  jq --arg id "$sub_id" --argjson t "$new_trust" --argjson circuit "$circuit" --arg state "$outcome" \
    '(.subagents[] | select(.id == $id) | .trust) = $t |
     ((.subagents[] | select(.id == $id) | .state) = $state) |
     (if $circuit == 1 then (.subagents[] | select(.id == $id) | .circuit_breaker = true) else . end)' \
    "$goal_file" >"${goal_file}.tmp" && mv "${goal_file}.tmp" "$goal_file"
  echo "Trust: $old_trust → $new_trust ($outcome)"
  if [[ "$circuit" -eq 1 ]]; then
    echo "CIRCUIT BREAKER fired (Δtrust > 0.3) — subagent $sub_id paused"
  fi
}

# --- 12. goal-list -----------------------------------------------------------
goal-list() {
  echo "ID	STATE	ATTEMPTS	BUDGET	DEADLINE	BOTTLENECK	TRUST	TITLE"
  ls -1 "$GOAL_GOALS_DIR"/*.json 2>/dev/null | while read -r f; do
    jq -r --argjson now "$(_goal_now)" \
      '[(.id), (.state), (.attempts | length), "\([.attempts[].tokens_used] | add // 0)/\(.budget_tokens)",
        (.deadline), (.bottleneck // "—"),
        ([.subagents[].trust] | if length == 0 then "—" else (add / length * 100 | round / 100 | tostring) end),
        (.title)] | @tsv' "$f" 2>/dev/null
  done | column -t -s $'\t'
}

# --- 13. goal-doctor ---------------------------------------------------------
goal-doctor() {
  echo "=== Goal-System Doctor ==="
  echo "jq:           $(command -v jq || echo 'MISSING (hard dependency — goal system requires jq)')"
  echo "git:          $(command -v git || echo 'MISSING (verify-back skipped)')"
  echo "synx:         $(command -v synx || echo 'MISSING (recall/remember skipped)')"
  echo "agentmaster:  $(command -v agentmaster || echo 'MISSING (cmux fan-out skipped)')"
  echo "rtk:          $(command -v rtk || echo 'MISSING (fail-open pass-through)')"
  echo "si:           $(command -v si || echo 'MISSING (skill routing skipped)')"
  local ultra_bin="${SYNAPSE_ULTRA_BIN:-$HOME/BASE/projects/synapse-memory/target/release/synapse-ultra}"
  echo "synapse-ultra: $([[ -x "$ultra_bin" ]] && echo "$ultra_bin" || echo 'MISSING')"
  echo "duckdb:       $(command -v duckdb || echo 'MISSING (DuckLake archive unavailable)')"
  local n_goals=0
  [[ -d "$GOAL_GOALS_DIR" ]] && n_goals=$(ls -1 "$GOAL_GOALS_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
  echo "goals:        ${n_goals} in ${GOAL_GOALS_DIR}"
  echo "GOAL_SH_LOADED: ${GOAL_SH_LOADED:-0}"
}

# --- Backward-compat aliases (Devin-specific names → universal goal-*) -------
# These are defined here so that any agent sourcing goal.sh gets both names.
devin-goal-init()   { goal-init "$@"; }
devin-goal-check()  { goal-check "$@"; }
devin-goal-close()  { goal-close "$@"; }
devin-goal-spawn()  { goal-spawn "$@"; }
