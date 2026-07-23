#!/usr/bin/env bash
# Smoke test for devin-goal-* functions.
# Runs: init → check → spawn → close → list → cleanup
# Exits 0 on success, 1 on any failure.

set -euo pipefail

WRAPPER="/Users/master/BASE/projects/agent-token-saver/integration/cli/devin-token-saver.sh"
GOALS_DIR="${SYNAPSE_GOALS_DIR:-$HOME/.synapse/goals}"
TEST_SLUG="smoke-test-goal"

# shellcheck source=/dev/null
source "$WRAPPER"

cleanup() {
  rm -f "${GOALS_DIR}/${TEST_SLUG}.json" /tmp/smoke-capsule.md /tmp/goal-oracle.log
}
trap cleanup EXIT

echo "=== Smoke test: devin-goal-* ==="

# 1. Syntax
bash -n "$WRAPPER" || { echo "FAIL: syntax"; exit 1; }
echo "  [PASS] wrapper syntax"

# 2. goal-init (passing oracle)
out=$(devin-goal-init "$TEST_SLUG" --oracle "true" --budget-tokens 1000 --deadline 30m 2>&1)
[[ -f "${GOALS_DIR}/${TEST_SLUG}.json" ]] || { echo "FAIL: goal file not created"; exit 1; }
echo "$out" | grep -q "Oracle: true" || { echo "FAIL: oracle not echoed"; exit 1; }
echo "  [PASS] goal-init creates JSON"

# 3. goal-check (passing)
out=$(devin-goal-check "$TEST_SLUG" 2>&1)
echo "$out" | grep -q "ORACLE: PASS" || { echo "FAIL: oracle should pass"; exit 1; }
state=$(jq -r .state "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$state" == "passed" ]] || { echo "FAIL: state not 'passed' (got: $state)"; exit 1; }
echo "  [PASS] goal-check passing oracle"

# 4. goal-spawn
echo "# Test capsule" > /tmp/smoke-capsule.md
out=$(devin-goal-spawn "$TEST_SLUG" --capsule /tmp/smoke-capsule.md --skill none 2>&1)
echo "$out" | grep -q "sub-" || { echo "FAIL: subagent id not returned"; exit 1; }
n_subs=$(jq '.subagents | length' "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$n_subs" -eq 1 ]] || { echo "FAIL: subagent not registered (got: $n_subs)"; exit 1; }
echo "  [PASS] goal-spawn registers subagent"

# 5. goal-close
out=$(devin-goal-close "$TEST_SLUG" --summary "Smoke test passed" 2>&1)
echo "$out" | grep -q "CLOSED: $TEST_SLUG" || { echo "FAIL: close not confirmed"; exit 1; }
state=$(jq -r .state "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$state" == "closed" ]] || { echo "FAIL: state not 'closed' (got: $state)"; exit 1; }
summary=$(jq -r .summary "${GOALS_DIR}/${TEST_SLUG}.json")
[[ "$summary" == "Smoke test passed" ]] || { echo "FAIL: summary mismatch (got: $summary)"; exit 1; }
echo "  [PASS] goal-close persists summary"

# 6. goal-list
out=$(devin-goal-check 2>&1)
echo "$out" | grep -q "$TEST_SLUG" || { echo "FAIL: goal not listed"; exit 1; }
echo "  [PASS] goal-list shows goal"

# 7. Failing oracle (separate goal)
FAIL_SLUG="smoke-test-fail"
devin-goal-init "$FAIL_SLUG" --oracle "false" --budget-tokens 500 --deadline 15m >/dev/null 2>&1
out=$(devin-goal-check "$FAIL_SLUG" 2>&1 || true)
echo "$out" | grep -q "ORACLE: FAIL" || { echo "FAIL: oracle should fail"; exit 1; }
echo "  [PASS] goal-check failing oracle"
rm -f "${GOALS_DIR}/${FAIL_SLUG}.json"

# 8. Doctor shows goals count (doctor may return non-zero if aliases missing, use || true)
out=$(devin-token-doctor 2>&1 || true)
echo "$out" | grep -q "goals:" || { echo "FAIL: doctor missing goals line"; exit 1; }
echo "  [PASS] doctor reports goals"

# 9. synx rename verification
out=$(devin-token-doctor 2>&1 || true)
echo "$out" | grep -q "synx:" || { echo "FAIL: doctor missing synx line"; exit 1; }
echo "$out" | grep -qE '^syn: ' && { echo "FAIL: doctor still shows 'syn:' line"; exit 1; } || true
echo "  [PASS] doctor uses synx (not syn)"

echo ""
echo "=== ALL 9 CHECKS PASSED ==="
