#!/bin/bash
# Proves the llmadapter PII shield actually holds at the egress boundary.
#
# The probe is a fake CLI lane that writes whatever it was handed to a file and
# answers with a fixed string. That file IS the wire: whatever lands there is
# what a real provider would have received. No network, no API keys.
#
# Test values follow the ggadapter convention of obviously-synthetic sentinels
# (DE00TESTIBAN…, example.test) so no realistic PII sits in the repo.
#
# Runs against a throwaway HOME so the real cache, ledger and local-lanes.json
# are untouched.
#
#   bash tests/test_llmadapter_pii_shield.sh
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADAPTER="$REPO/scripts/llmadapter.ts"
SHIELD="${ATS_SHIELD_PATH:-$HOME/BASE/ggprojects/ggadapter/adapter/dsgvo-shield.mjs}"

if [ ! -f "$SHIELD" ]; then
  echo "SKIP: shield not found at $SHIELD"
  exit 0
fi

FAILED=0
pass() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n     %s\n' "$1" "${2:-}"; FAILED=$((FAILED + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP"
mkdir -p "$TMP/.agent-token-saver"

WIRE="$TMP/wire.txt"
cat > "$TMP/.agent-token-saver/local-lanes.json" <<EOF
{ "llmadapter": [ {
  "name": "egress-probe",
  "kind": "cli",
  "class": "cli",
  "cmd": ["/bin/sh", "-c", "printf '%s' \"\$1\" > $WIRE; printf 'Ich habe die Anfrage von __PROMPT__ geprueft.'", "sh", "__PROMPT__"]
} ] }
EOF
chmod 600 "$TMP/.agent-token-saver/local-lanes.json"

# Shaped like a real German customer request; values are sentinels.
NAME="Frau Test Person"
ACCOUNT="DE00TESTIBAN0000000000"
MAIL="pii.test@example.test"
PROMPT="Kundenanfrage pruefen. Kunde: $NAME, IBAN $ACCOUNT, Mail $MAIL. Ist die Zahlung plausibel?"

run_probe() { # $@: extra env assignments
  rm -f "$WIRE"
  env "$@" ATS_SHIELD_PATH="$SHIELD" bun "$ADAPTER" ask "$PROMPT" \
    --lanes egress-probe --no-cache --json 2>"$TMP/err.txt"
}

echo
echo "llmadapter PII shield"
echo

# 1 — shield on: nothing identifying may appear on the wire.
OUT="$(run_probe X=1)"
if [ ! -f "$WIRE" ]; then
  fail "probe lane ran" "$(head -3 "$TMP/err.txt")"
else
  SENT="$(cat "$WIRE")"
  for secret in "$NAME" "$ACCOUNT" "$MAIL"; do
    if printf '%s' "$SENT" | grep -qF "$secret"; then
      fail "no '$secret' on the wire" "sent: ${SENT:0:160}"
    else
      pass "masked on the wire: $secret"
    fi
  done
  if printf '%s' "$SENT" | grep -q 'GGD_'; then
    pass "wire carries [[GGD_*]] tokens instead"
  else
    fail "wire carries pseudonym tokens" "sent: ${SENT:0:160}"
  fi
fi

# 2 — the caller still gets real values back: tokens restored in the answer.
if printf '%s' "$OUT" | grep -qF "$NAME"; then
  pass "answer restored to real values"
elif printf '%s' "$OUT" | grep -q 'GGD_'; then
  fail "answer restored to real values" "answer still contains tokens"
else
  fail "answer restored to real values" "answer: $(printf '%s' "$OUT" | head -c 200)"
fi

# 3 — explicit opt-out must actually opt out, otherwise the flag is a lie.
run_probe ATS_PII_SHIELD=0 >/dev/null
if [ -f "$WIRE" ] && grep -qF "$ACCOUNT" "$WIRE"; then
  pass "ATS_PII_SHIELD=0 sends unmasked (opt-out works)"
else
  fail "ATS_PII_SHIELD=0 sends unmasked" "sentinel not found on wire"
fi

# 4 — shield missing must fail closed, never fall back to plaintext.
rm -f "$WIRE"
env ATS_SHIELD_PATH="$TMP/does-not-exist.mjs" bun "$ADAPTER" ask "$PROMPT" \
  --lanes egress-probe --no-cache --json >/dev/null 2>&1
if [ -f "$WIRE" ]; then
  fail "fails closed when shield is missing" "data reached the wire: $(head -c 120 "$WIRE")"
else
  pass "fails closed when shield is missing"
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "  all checks passed"
  exit 0
fi
echo "  $FAILED check(s) failed"
exit 1
