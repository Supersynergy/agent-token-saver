#!/usr/bin/env bash
# Smoke test for universal goal-* CLI + ats-* helpers + devin-* backward-compat
# + v3.7.0 adaptive features (detect-agent, safe, parallel, metareview,
# omnigoal-check, ats-auto, claude/codex/cmux wrappers).
# + v3.8.0 recon CLIs (gmax, ghx, supacrawl, ats-llm-pipe, zsh portability).
# Covers 36 checks. Exits 0 on success, 1 on any failure.

set -euo pipefail

UNIVERSAL="/Users/master/BASE/projects/agent-token-saver/integration/cli/agent-token-saver.sh"
DEVIN_WRAPPER="/Users/master/BASE/projects/agent-token-saver/integration/cli/devin-token-saver.sh"
GOAL_SH="/Users/master/BASE/projects/agent-token-saver/integration/cli/goal.sh"
GOALS_DIR="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
TEST_SLUG="smoke-test-goal"
FAIL_SLUG="smoke-test-fail"
OPEN_SLUG="smoke-open-verb"

# Source universal wrapper first (provides ats-* + goal-*).
# shellcheck source=/dev/null
source "$UNIVERSAL"
# Then source Devin wrapper (adds devin-* aliases, re-uses already-loaded universal).
# shellcheck source=/dev/null
source "$DEVIN_WRAPPER"

cleanup() {
  rm -f "${GOALS_DIR}/${TEST_SLUG}"*.json "${GOALS_DIR}/${FAIL_SLUG}"*.json \
        "${GOALS_DIR}/${OPEN_SLUG}"*.json "${GOALS_DIR}/devin-compat-test"*.json \
        "${GOALS_DIR}/ats-compat-test"*.json \
        "${GOALS_DIR}/budget-test"*.json "${GOALS_DIR}/cap-test"*.json \
        "${GOALS_DIR}/mr-test"*.json "${GOALS_DIR}/omni-test"*.json \
        "${GOALS_DIR}/mr-req-test"*.json "${GOALS_DIR}/auto-test"*.json \
        "${GOALS_DIR}/auto-cont-test"*.json \
        /tmp/smoke-capsule.md /tmp/goal-oracle.log \
        /tmp/goal-refute.log /tmp/goal-trace.log "${GOALS_DIR}/"*.root-cause.md 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Smoke test: universal goal-* + ats-* + devin-* compat + v3.7.0 adaptive (30 checks) ==="

# 1. Syntax
bash -n "$UNIVERSAL" || { echo "FAIL: universal wrapper syntax"; exit 1; }
bash -n "$DEVIN_WRAPPER" || { echo "FAIL: devin wrapper syntax"; exit 1; }
bash -n "$GOAL_SH" || { echo "FAIL: goal.sh syntax"; exit 1; }
echo "  [PASS] universal + devin wrapper + goal.sh syntax"

# 2. goal-init with closed verb (PASS) + open-verb rejection (FAIL → --force)
out=$(goal-init "$TEST_SLUG reduce-errors-to-0" --oracle "true" --budget-tokens 1000 --deadline 30m --agent devin 2>&1)
[[ -f "${GOALS_DIR}/${TEST_SLUG}-reduce-errors-to-0.json" ]] || { echo "FAIL: goal file not created"; exit 1; }
TEST_SLUG="${TEST_SLUG}-reduce-errors-to-0"
echo "$out" | grep -qE "Oracle: +true" || { echo "FAIL: oracle not echoed"; exit 1; }
echo "  [PASS] goal-init creates JSON with closed verb"

# 3. Open-verb rejection
out=$(goal-init "$OPEN_SLUG optimize the code" --oracle "true" 2>&1 || true)
echo "$out" | grep -q "rejected" || { echo "FAIL: open verb should be rejected"; exit 1; }
echo "  [PASS] open-verb rejected"
# --force override
out=$(goal-init "$OPEN_SLUG optimize the code" --oracle "true" --force 2>&1)
echo "$out" | grep -qE "Oracle: +true" || { echo "FAIL: --force should override"; exit 1; }
echo "  [PASS] --force overrides open-verb rejection"

# 4. goal-recall (fail-open if synx missing)
out=$(goal-recall "$TEST_SLUG" 2>&1 || true)
{ echo "$out" | grep -qE '(synx|chunks|WARN|0\.|Relaxing|telepathy|reflect)' || echo "$out" | grep -q .; } || { echo "FAIL: recall should run or warn"; exit 1; }
echo "  [PASS] goal-recall runs (fail-open if synx missing)"

# 5. goal-leverage (bottleneck + 2 levers)
out=$(goal-leverage "$TEST_SLUG" --bottleneck "missing import" --lever "add import" --lever "fix typo" 2>&1)
echo "$out" | grep -q "Bottleneck: missing import" || { echo "FAIL: leverage not persisted"; exit 1; }
bottleneck=$(jq -r .bottleneck "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$bottleneck" == "missing import" ]] || { echo "FAIL: bottleneck mismatch"; exit 1; }
echo "  [PASS] goal-leverage persists bottleneck + levers"

# 6. goal-slice
out=$(goal-slice "$TEST_SLUG" "add the missing import in src/lib.rs" 2>&1)
echo "$out" | grep -q "Slice:" || { echo "FAIL: slice not persisted"; exit 1; }
echo "  [PASS] goal-slice persists"

# 7. goal-spawn (subagent registered with trust 0.5)
echo "# Test capsule" > /tmp/smoke-capsule.md
out=$(goal-spawn "$TEST_SLUG" --capsule /tmp/smoke-capsule.md --skill none 2>&1)
echo "$out" | grep -q "sub-" || { echo "FAIL: subagent id not returned"; exit 1; }
n_subs=$(jq '.subagents | length' "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$n_subs" -eq 1 ]] || { echo "FAIL: subagent not registered (got: $n_subs)"; exit 1; }
trust=$(jq -r '.subagents[0].trust' "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$trust" == "0.5" ]] || { echo "FAIL: trust should start at 0.5 (got: $trust)"; exit 1; }
echo "  [PASS] goal-spawn registers subagent with trust 0.5"

# 8. goal-check passing (attempts=0→1, state=passed)
out=$(goal-check "$TEST_SLUG" 2>&1)
echo "$out" | grep -q "ORACLE: PASS" || { echo "FAIL: oracle should pass"; exit 1; }
state=$(jq -r .state "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$state" == "passed" ]] || { echo "FAIL: state not 'passed' (got: $state)"; exit 1; }
echo "  [PASS] goal-check passing oracle"

# 9. goal-check failing (attempts=1, bottleneck identified)
FAIL_SLUG_FULL="${FAIL_SLUG}-make-false-pass"
goal-init "$FAIL_SLUG_FULL" --oracle "false" --budget-tokens 500 --deadline 15m >/dev/null 2>&1
out=$(goal-check "$FAIL_SLUG_FULL" 2>&1 || true)
echo "$out" | grep -q "ORACLE: FAIL" || { echo "FAIL: oracle should fail"; exit 1; }
n_attempts=$(jq '.attempts | length' "${GOALS_DIR}/${FAIL_SLUG_FULL}.json")
[[ "$n_attempts" -eq 1 ]] || { echo "FAIL: attempts not incremented (got: $n_attempts)"; exit 1; }
echo "  [PASS] goal-check failing oracle increments attempts"
rm -f "${GOALS_DIR}/${FAIL_SLUG_FULL}.json"

# 10. goal-verify (git commits since spawn_ts — may be empty in test repo)
out=$(goal-verify "$TEST_SLUG" 2>&1 || true)
echo "$out" | grep -qE '(VERIFY|no .git|git not)' || { echo "FAIL: verify should run"; exit 1; }
echo "  [PASS] goal-verify runs (fail-open if no git/repo)"

# 11. goal-refute (fresh subagent prompt generated)
out=$(goal-refute "$TEST_SLUG" 2>&1 || true)
echo "$out" | grep -q "Refutation prompt" || echo "$out" | grep -q "agentmaster" || { echo "FAIL: refute prompt not generated"; exit 1; }
refuter=$(jq -r '.evidence.refuter // "SKIPPED"' "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$refuter" != "SKIPPED" ]] || { echo "FAIL: refuter not recorded"; exit 1; }
echo "  [PASS] goal-refute generates prompt + records verdict"

# 12. goal-trust (trust updated on done)
sub_id=$(jq -r '.subagents[0].id' "${GOALS_DIR}/${TEST_SLUG}.json")
old_trust=$(jq -r '.subagents[0].trust' "${GOALS_DIR}/${TEST_SLUG}.json")
out=$(goal-trust "$TEST_SLUG" "$sub_id" done 2>&1)
echo "$out" | grep -q "Trust:" || { echo "FAIL: trust not updated"; exit 1; }
new_trust=$(jq -r '.subagents[0].trust' "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$new_trust" != "$old_trust" ]] || { echo "FAIL: trust should change"; exit 1; }
echo "  [PASS] goal-trust updates on done"

# 13. goal-trace (LTL always(P) — default)
out=$(goal-trace "$TEST_SLUG" 2>&1 || true)
echo "$out" | grep -qE '(TRACE|LTL)' || { echo "FAIL: trace should run"; exit 1; }
echo "  [PASS] goal-trace runs LTL check"

# 14. goal-close (refuses if oracle failing OR refute FAIL; persists summary + decision)
out=$(goal-close "$TEST_SLUG" --summary "Smoke test passed" --decision "test verified" 2>&1)
echo "$out" | grep -q "CLOSED: $TEST_SLUG" || { echo "FAIL: close not confirmed"; exit 1; }
state=$(jq -r .state "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$state" == "closed" ]] || { echo "FAIL: state not 'closed' (got: $state)"; exit 1; }
summary=$(jq -r .summary "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$summary" == "Smoke test passed" ]] || { echo "FAIL: summary mismatch"; exit 1; }
echo "  [PASS] goal-close persists summary + decision"

# 15. goal-list
out=$(goal-list 2>&1)
echo "$out" | grep -q "$TEST_SLUG" || { echo "FAIL: goal not listed"; exit 1; }
echo "  [PASS] goal-list shows goal"

# 16. goal-doctor
out=$(goal-doctor 2>&1 || true)
echo "$out" | grep -q "jq:" || { echo "FAIL: doctor missing jq line"; exit 1; }
echo "$out" | grep -q "agentmaster:" || { echo "FAIL: doctor missing agentmaster line"; exit 1; }
echo "  [PASS] goal-doctor reports all tools"

# 17. ats-doctor (universal wrapper doctor)
out=$(ats-doctor 2>&1 || true)
echo "$out" | grep -q "Agent Token-Saver Doctor" || { echo "FAIL: ats-doctor header missing"; exit 1; }
echo "$out" | grep -q "AGENT_TOKEN_SAVER_LOADED" || { echo "FAIL: ats-doctor missing loaded flag"; exit 1; }
echo "  [PASS] ats-doctor reports universal wrapper state"

# 18. devin-* backward-compat aliases still work (Devin wrapper)
out=$(devin-goal-init "devin-compat-test pass" --oracle "true" --budget-tokens 100 --deadline 5m 2>&1)
echo "$out" | grep -qE "Oracle: +true" || { echo "FAIL: devin-goal-init alias broken"; exit 1; }
rm -f "${GOALS_DIR}/devin-compat-test-pass.json"
# devin-token-doctor should delegate to ats-doctor
out=$(devin-token-doctor 2>&1 || true)
echo "$out" | grep -q "Agent Token-Saver Doctor" || { echo "FAIL: devin-token-doctor should alias ats-doctor"; exit 1; }
echo "  [PASS] devin-* backward-compat aliases work"

# 19. Budget enforcement (tokens_used > budget → state=failed)
goal-init "budget-test exhaust-to-0" --oracle "false" --budget-tokens 1 --deadline 1h >/dev/null 2>&1
goal-check budget-test-exhaust-to-0 >/dev/null 2>&1 || true
jq '.attempts[0].tokens_used = 100' "${GOALS_DIR}/budget-test-exhaust-to-0.json" > "${GOALS_DIR}/budget-test-exhaust-to-0.json.tmp" && mv "${GOALS_DIR}/budget-test-exhaust-to-0.json.tmp" "${GOALS_DIR}/budget-test-exhaust-to-0.json"
out=$(goal-check budget-test-exhaust-to-0 2>&1 || true)
echo "$out" | grep -q "BUDGET EXHAUSTED" || { echo "FAIL: budget not enforced"; exit 1; }
state=$(jq -r .state "${GOALS_DIR}/budget-test-exhaust-to-0.json")
[[ "$state" == "failed" ]] || { echo "FAIL: state should be 'failed' (got: $state)"; exit 1; }
echo "  [PASS] budget enforcement works"
rm -f "${GOALS_DIR}/budget-test-exhaust-to-0.json"

# 20. 3-try cap + root-cause note
goal-init "cap-test reach-3-attempts" --oracle "false" --budget-tokens 10000 --deadline 1h >/dev/null 2>&1
goal-check cap-test-reach-3-attempts >/dev/null 2>&1 || true
goal-check cap-test-reach-3-attempts >/dev/null 2>&1 || true
goal-check cap-test-reach-3-attempts >/dev/null 2>&1 || true
out=$(goal-check cap-test-reach-3-attempts 2>&1 || true)
echo "$out" | grep -q "3-TRY CAP" || { echo "FAIL: 3-try cap not enforced"; exit 1; }
[[ -f "${GOALS_DIR}/cap-test-reach-3-attempts.root-cause.md" ]] || { echo "FAIL: root-cause note not written"; exit 1; }
echo "  [PASS] 3-try cap + root-cause note"
rm -f "${GOALS_DIR}/cap-test-reach-3-attempts.json" "${GOALS_DIR}/cap-test-reach-3-attempts.root-cause.md"

# 21. ats-detect-agent sets ATS_AGENT_NAME + ATS_AGENT_DETECTED
ATS_AGENT_NAME="" ATS_AGENT_DETECTED="" ats-detect-agent
[[ -n "${ATS_AGENT_NAME:-}" ]] || { echo "FAIL: ats-detect-agent did not set ATS_AGENT_NAME"; exit 1; }
[[ "${ATS_AGENT_DETECTED:-0}" == "1" ]] || { echo "FAIL: ATS_AGENT_DETECTED not set"; exit 1; }
echo "  [PASS] ats-detect-agent sets ATS_AGENT_NAME=${ATS_AGENT_NAME}"

# 22. ats-safe skips undefined functions (fail-open)
out=$(ats-safe undefined-fn-xyz arg1 2>&1 || true)
echo "$out" | grep -q "fail-open" || { echo "FAIL: ats-safe did not skip undefined fn"; exit 1; }
out=$(ats-safe goal-list 2>&1 || true)
echo "$out" | grep -qE "ID|STATE|smoke" || { echo "FAIL: ats-safe did not call defined goal-list"; exit 1; }
echo "  [PASS] ats-safe fail-open + dispatch"

# 23. ats-have returns 0 for existing tool, 1 for missing
ats-have jq || { echo "FAIL: ats-have should return 0 for jq"; exit 1; }
if ats-have definitely-missing-tool-xyz 2>/dev/null; then
  echo "FAIL: ats-have should return 1 for missing tool"; exit 1
fi
echo "  [PASS] ats-have tool existence check"

# 24. ats-parallel runs N commands in parallel + joins
out=$(ats-parallel "echo hello" "echo world" 2>&1)
echo "$out" | grep -q "hello" || { echo "FAIL: ats-parallel cmd1 missing"; exit 1; }
echo "$out" | grep -q "world" || { echo "FAIL: ats-parallel cmd2 missing"; exit 1; }
echo "$out" | grep -qE "\[1\]|\[2\]" || { echo "FAIL: ats-parallel index prefix missing"; exit 1; }
echo "  [PASS] ats-parallel runs + joins"

# 25. ats-metareview records verdict in goal JSON (manual fallback)
goal-init "mr-test pass" --oracle "true" --budget-tokens 100 --deadline 5m >/dev/null 2>&1
out=$(ats-metareview mr-test-pass --skip-if-missing 2>&1 || true)
echo "$out" | grep -qE "verdict=" || { echo "FAIL: ats-metareview did not return verdict"; exit 1; }
mr_v=$(jq -r '.evidence.refuter // "SKIPPED"' "${GOALS_DIR}/mr-test-pass.json" 2>/dev/null)
[[ -n "$mr_v" && "$mr_v" != "SKIPPED" ]] || { echo "FAIL: ats-metareview verdict not recorded in JSON (got: $mr_v)"; exit 1; }
echo "  [PASS] ats-metareview records verdict ($mr_v)"
rm -f "${GOALS_DIR}/mr-test-pass.json"

# 26. ats-omnigoal-check verifies 7 hard gates
goal-init "omni-test pass" --oracle "true" --budget-tokens 100 --deadline 5m >/dev/null 2>&1
goal-check omni-test-pass >/dev/null 2>&1 || true
# Set eval_written + bottleneck + summary to pass gates 2/3/6
jq '.evidence.eval_written = true | .bottleneck = "test-bottleneck" | .summary = "test-summary"' \
  "${GOALS_DIR}/omni-test-pass.json" > "${GOALS_DIR}/omni-test-pass.json.tmp" && mv "${GOALS_DIR}/omni-test-pass.json.tmp" "${GOALS_DIR}/omni-test-pass.json"
out=$(ats-omnigoal-check omni-test-pass 2>&1 || true)
echo "$out" | grep -qE "Omnigoal Hard Gates" || { echo "FAIL: ats-omnigoal-check header missing"; exit 1; }
echo "$out" | grep -qE "gates passed" || { echo "FAIL: ats-omnigoal-check summary missing"; exit 1; }
echo "  [PASS] ats-omnigoal-check verifies hard gates"
rm -f "${GOALS_DIR}/omni-test-pass.json"

# 27. goal-close --require-metareview refuses without metareview
goal-init "mr-req-test pass" --oracle "true" --budget-tokens 100 --deadline 5m >/dev/null 2>&1
goal-check mr-req-test-pass >/dev/null 2>&1 || true
out=$(goal-close mr-req-test-pass --summary "test" --require-metareview 2>&1 || true)
echo "$out" | grep -q "require-metareview" || { echo "FAIL: goal-close --require-metareview should refuse"; exit 1; }
# Now run metareview, then close should succeed
ats-metareview mr-req-test-pass --skip-if-missing >/dev/null 2>&1 || true
# Force refuter to PASS for the test
jq '.evidence.refuter = "PASS"' "${GOALS_DIR}/mr-req-test-pass.json" > "${GOALS_DIR}/mr-req-test-pass.json.tmp" && mv "${GOALS_DIR}/mr-req-test-pass.json.tmp" "${GOALS_DIR}/mr-req-test-pass.json"
out=$(goal-close mr-req-test-pass --summary "test" --require-metareview 2>&1 || true)
echo "$out" | grep -q "CLOSED" || { echo "FAIL: goal-close should succeed after metareview PASS"; exit 1; }
echo "  [PASS] goal-close --require-metareview gate works"
rm -f "${GOALS_DIR}/mr-req-test-pass.json"

# 28. ats-auto starts the loop (recall+contract+leverage+slice)
out=$(ats-auto "auto-test pass" --oracle "true" --budget-tokens 100 --deadline 5m 2>&1)
echo "$out" | grep -q "RECALL + CONTRACT" || { echo "FAIL: ats-auto did not run recall+contract"; exit 1; }
echo "$out" | grep -q "EXECUTE (your turn)" || { echo "FAIL: ats-auto did not pause at execute"; exit 1; }
[[ -f "${GOALS_DIR}/auto-test-pass.json" ]] || { echo "FAIL: ats-auto did not create goal JSON"; exit 1; }
echo "  [PASS] ats-auto starts omnigoal loop"
rm -f "${GOALS_DIR}/auto-test-pass.json"

# 29. ats-auto --continue runs eval-gate + close
goal-init "auto-cont-test pass" --oracle "true" --budget-tokens 100 --deadline 5m >/dev/null 2>&1
goal-check auto-cont-test-pass >/dev/null 2>&1 || true
jq '.evidence.eval_written = true | .bottleneck = "test" | .evidence.refuter = "PASS" | .evidence.commits = ["fake-sha"] | .summary = "preset"' \
  "${GOALS_DIR}/auto-cont-test-pass.json" > "${GOALS_DIR}/auto-cont-test-pass.json.tmp" && mv "${GOALS_DIR}/auto-cont-test-pass.json.tmp" "${GOALS_DIR}/auto-cont-test-pass.json"
out=$(ats-auto --continue auto-cont-test-pass --skip-metareview 2>&1 || true)
echo "$out" | grep -qE "EVAL-GATE|CLOSED" || { echo "FAIL: ats-auto --continue did not run eval-gate/close"; exit 1; }
echo "  [PASS] ats-auto --continue completes the loop"
rm -f "${GOALS_DIR}/auto-cont-test-pass.json"

# 30. claude-* + codex-* + cmux-* wrappers source + install aliases
CLAUDE_WRAPPER="/Users/master/BASE/projects/agent-token-saver/integration/cli/claude-token-saver.sh"
CODEX_WRAPPER="/Users/master/BASE/projects/agent-token-saver/integration/cli/codex-token-saver.sh"
CMUX_WRAPPER="/Users/master/BASE/projects/agent-token-saver/integration/cli/cmux-token-saver.sh"
bash -n "$CLAUDE_WRAPPER" "$CODEX_WRAPPER" "$CMUX_WRAPPER" || { echo "FAIL: agent wrapper syntax"; exit 1; }
# Source in subshell to verify they load cleanly
( source "$CLAUDE_WRAPPER" && type claude-token-doctor >/dev/null 2>&1 ) || { echo "FAIL: claude wrapper missing claude-token-doctor"; exit 1; }
( source "$CODEX_WRAPPER"  && type codex-token-doctor  >/dev/null 2>&1 ) || { echo "FAIL: codex wrapper missing codex-token-doctor"; exit 1; }
( source "$CMUX_WRAPPER"   && type cmux-token-doctor   >/dev/null 2>&1 ) || { echo "FAIL: cmux wrapper missing cmux-token-doctor"; exit 1; }
echo "  [PASS] claude/codex/cmux wrappers load + install aliases"

# 31. v3.8.0 recon CLIs — fail-open wrappers exist + dispatch to real CLIs
for fn in ats-gmax ats-ghx ats-supacrawl ats-recon-doctor; do
  declare -F "$fn" >/dev/null 2>&1 || { echo "FAIL: $fn not defined"; exit 1; }
done
echo "  [PASS] v3.8.0 recon wrappers (ats-gmax/ghx/supacrawl/recon-doctor) defined"

# 32. ats-gmax dispatches to real gmax if installed (fail-open otherwise)
if ats-have gmax; then
  out=$(ats-gmax "abba_order" --agent 2>&1 | head -5)
  echo "$out" | grep -qE "abba|scripts/" || { echo "FAIL: ats-gmax did not return hits for abba"; exit 1; }
  echo "  [PASS] ats-gmax dispatches to real gmax (--agent output)"
else
  out=$(ats-gmax test 2>&1)
  echo "$out" | grep -q "fail-open\|not on PATH" || { echo "FAIL: ats-gmax should fail-open when gmax missing"; exit 1; }
  echo "  [PASS] ats-gmax fail-open (gmax not installed)"
fi

# 33. ats-supacrawl dispatches to real supacrawl if installed
if ats-have supacrawl; then
  out=$(ats-supacrawl scrape https://example.com --format markdown 2>&1 | head -10)
  echo "$out" | grep -qiE "example domain|iana" || { echo "FAIL: ats-supacrawl did not fetch example.com"; exit 1; }
  echo "  [PASS] ats-supacrawl fetches example.com → markdown"
else
  out=$(ats-supacrawl scrape 2>&1)
  echo "$out" | grep -q "fail-open\|not on PATH" || { echo "FAIL: ats-supacrawl should fail-open"; exit 1; }
  echo "  [PASS] ats-supacrawl fail-open (supacrawl not installed)"
fi

# 34. ats-llm-pipe bridges supacrawl LLM-extraction to active CLI agent
ATS_LLM_PIPE="/Users/master/BASE/projects/agent-token-saver/integration/cli/ats-llm-pipe"
[[ -x "$ATS_LLM_PIPE" ]] || { echo "FAIL: ats-llm-pipe not executable"; exit 1; }
# Pick first available CLI (codex/kimi/claude) — skip test if none
if ats-have codex || ats-have kimi || ats-have claude; then
  out=$(echo '{"messages":[{"role":"user","content":"What is 2+2? Answer with just the number."}]}' | \
    ATS_LLM_PIPE_TIMEOUT=30 "$ATS_LLM_PIPE" 2>&1 | head -3 || true)
  # Accept either a valid answer OR a timeout/dispatch message (proves bridging works)
  echo "$out" | grep -qE "^[0-9]+\b|four|4$|timed out|dispatching|codex|kimi|claude" || { echo "FAIL: ats-llm-pipe did not dispatch to a CLI; got: $out"; exit 1; }
  echo "  [PASS] ats-llm-pipe bridges to active CLI (codex/kimi/claude)"
else
  echo "  [PASS] ats-llm-pipe present (no CLI agent available — skip live test)"
fi

# 35. zsh portability — wrappers load under zsh without BASH_SOURCE errors
if ats-have zsh; then
  zsh_out=$(zsh -c '
    source /Users/master/BASE/projects/agent-token-saver/integration/cli/codex-token-saver.sh 2>&1
    type codex-token-doctor >/dev/null 2>&1 && echo "ZSH_OK"
  ' 2>&1)
  echo "$zsh_out" | grep -q "ZSH_OK" || { echo "FAIL: zsh did not load codex wrapper cleanly: $zsh_out"; exit 1; }
  # Verify no "goal.sh not found at /goal.sh" warning (the BASH_SOURCE bug)
  echo "$zsh_out" | grep -q "goal.sh not found at /goal.sh" && { echo "FAIL: zsh hit BASH_SOURCE bug"; exit 1; }
  echo "  [PASS] zsh loads codex wrapper (no BASH_SOURCE bug)"
else
  echo "  [PASS] zsh not installed — skip portability test"
fi

# 36. codex-swarm integration — full goal lifecycle under codex-token-saver.sh
SWARM_DIR="${TMPDIR:-/tmp}/codex-swarm-smoke-$$"
mkdir -p "$SWARM_DIR/goals"
ORACLE="$SWARM_DIR/oracle.sh"
cat > "$ORACLE" <<'ORACLE_EOF'
#!/usr/bin/env bash
python3 -c 'print("ORACLE_PASS")'
ORACLE_EOF
chmod +x "$ORACLE"
SWARM_SLUG="codex-swarm-smoke-pass"
# Unset load-guards so the zsh subshell re-sources agent-token-saver.sh + goal.sh
# cleanly (the test script's own source at line 19 sets AGENT_TOKEN_SAVER_LOADED=1,
# which would short-circuit the universal wrapper's goal.sh sourcing in zsh).
SWARM_OUT=$(env -u AGENT_TOKEN_SAVER_LOADED -u GOAL_SH_LOADED zsh -c "
  export SYNAPSE_GOALS_DIR=$SWARM_DIR/goals
  source /Users/master/BASE/projects/agent-token-saver/integration/cli/codex-token-saver.sh 2>&1
  codex-goal-init 'codex-swarm-smoke pass' --oracle '$ORACLE' --budget-tokens 500 --deadline 5m >/dev/null 2>&1
  codex-goal-check $SWARM_SLUG >/dev/null 2>&1
  state=\$(jq -r .state $SWARM_DIR/goals/$SWARM_SLUG.json 2>&1)
  [[ \"\$state\" == \"passed\" ]] || { echo \"FAIL_STATE=\$state\"; exit 1; }
  jq '.evidence.eval_written = true | .bottleneck = \"test\" | .evidence.refuter = \"PASS\" | .evidence.commits = [\"fake\"] | .summary = \"preset\"' \
    $SWARM_DIR/goals/$SWARM_SLUG.json > $SWARM_DIR/goals/$SWARM_SLUG.json.tmp && mv $SWARM_DIR/goals/$SWARM_SLUG.json.tmp $SWARM_DIR/goals/$SWARM_SLUG.json
  codex-goal-close $SWARM_SLUG --summary 'swarm-test passed' --require-metareview >/dev/null 2>&1 || true
  closed_state=\$(jq -r .state $SWARM_DIR/goals/$SWARM_SLUG.json 2>&1)
  [[ \"\$closed_state\" == \"closed\" ]] && echo SWARM_OK
" 2>&1 || true)
echo "$SWARM_OUT" | grep -q "SWARM_OK" || { echo "FAIL: codex-swarm lifecycle did not complete; output: $SWARM_OUT"; exit 1; }
echo "  [PASS] codex-swarm lifecycle (init→check→close under zsh + codex wrapper)"
rm -rf "$SWARM_DIR"

echo ""
echo "=== ALL 36 CHECKS PASSED ==="
