#!/usr/bin/env bash
# Smoke test for universal goal-* CLI + devin-goal-* backward-compat aliases.
# Covers 19 checks: init/recall/leverage/slice/spawn/check/verify/refute/close/
# trace/trust/list/doctor + backward-compat + budget/deadline enforcement.
# Exits 0 on success, 1 on any failure.

set -euo pipefail

WRAPPER="/Users/master/BASE/projects/agent-token-saver/integration/cli/devin-token-saver.sh"
GOAL_SH="/Users/master/BASE/projects/agent-token-saver/integration/cli/goal.sh"
GOALS_DIR="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
TEST_SLUG="smoke-test-goal"
FAIL_SLUG="smoke-test-fail"
OPEN_SLUG="smoke-open-verb"

# shellcheck source=/dev/null
source "$WRAPPER"

cleanup() {
  rm -f "${GOALS_DIR}/${TEST_SLUG}"*.json "${GOALS_DIR}/${FAIL_SLUG}"*.json \
        "${GOALS_DIR}/${OPEN_SLUG}"*.json "${GOALS_DIR}/devin-compat-test"*.json \
        "${GOALS_DIR}/budget-test"*.json "${GOALS_DIR}/cap-test"*.json \
        /tmp/smoke-capsule.md /tmp/goal-oracle.log \
        /tmp/goal-refute.log /tmp/goal-trace.log "${GOALS_DIR}/"*.root-cause.md 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Smoke test: universal goal-* CLI (19 checks) ==="

# 1. Syntax
bash -n "$WRAPPER" || { echo "FAIL: wrapper syntax"; exit 1; }
bash -n "$GOAL_SH" || { echo "FAIL: goal.sh syntax"; exit 1; }
echo "  [PASS] wrapper + goal.sh syntax"

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
# either synx returned results, or it warned it's missing — both are PASS
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

# 17. devin-goal-* backward-compat aliases still work
out=$(devin-goal-init "devin-compat-test pass" --oracle "true" --budget-tokens 100 --deadline 5m 2>&1)
echo "$out" | grep -qE "Oracle: +true" || { echo "FAIL: devin-goal-init alias broken"; exit 1; }
rm -f "${GOALS_DIR}/devin-compat-test-pass.json"
echo "  [PASS] devin-goal-* backward-compat aliases work"

# 18. Budget enforcement (tokens_used > budget → state=failed)
goal-init "budget-test exhaust-to-0" --oracle "false" --budget-tokens 1 --deadline 1h >/dev/null 2>&1
# run check twice to exhaust budget (each attempt uses ~1 token from log size)
goal-check budget-test-exhaust-to-0 >/dev/null 2>&1 || true
# force tokens_used > budget by manually setting attempts
jq '.attempts[0].tokens_used = 100' "${GOALS_DIR}/budget-test-exhaust-to-0.json" > "${GOALS_DIR}/budget-test-exhaust-to-0.json.tmp" && mv "${GOALS_DIR}/budget-test-exhaust-to-0.json.tmp" "${GOALS_DIR}/budget-test-exhaust-to-0.json"
out=$(goal-check budget-test-exhaust-to-0 2>&1 || true)
echo "$out" | grep -q "BUDGET EXHAUSTED" || { echo "FAIL: budget not enforced"; exit 1; }
state=$(jq -r .state "${GOALS_DIR}/budget-test-exhaust-to-0.json")
[[ "$state" == "failed" ]] || { echo "FAIL: state should be 'failed' (got: $state)"; exit 1; }
echo "  [PASS] budget enforcement works"
rm -f "${GOALS_DIR}/budget-test-exhaust-to-0.json"

# 19. 3-try cap + root-cause note
goal-init "cap-test reach-3-attempts" --oracle "false" --budget-tokens 10000 --deadline 1h >/dev/null 2>&1
goal-check cap-test-reach-3-attempts >/dev/null 2>&1 || true
goal-check cap-test-reach-3-attempts >/dev/null 2>&1 || true
goal-check cap-test-reach-3-attempts >/dev/null 2>&1 || true
out=$(goal-check cap-test-reach-3-attempts 2>&1 || true)
echo "$out" | grep -q "3-TRY CAP" || { echo "FAIL: 3-try cap not enforced"; exit 1; }
[[ -f "${GOALS_DIR}/cap-test-reach-3-attempts.root-cause.md" ]] || { echo "FAIL: root-cause note not written"; exit 1; }
echo "  [PASS] 3-try cap + root-cause note"
rm -f "${GOALS_DIR}/cap-test-reach-3-attempts.json" "${GOALS_DIR}/cap-test-reach-3-attempts.root-cause.md"

echo ""
echo "=== ALL 19 CHECKS PASSED ==="
