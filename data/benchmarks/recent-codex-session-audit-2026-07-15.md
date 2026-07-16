# Recent Codex session audit — 2026-07-15

Scope: the ten most recently modified persisted Codex JSONL sessions at audit
time. Parsed with `agent-token-ledger` v3.2.0, which prefers cumulative
`payload.info.total_token_usage` over the last-request counter.

## Provider and context totals

| Signal | Observed |
|---|---:|
| Sessions | 10 |
| Provider total tokens | 654,720,502 |
| Provider input tokens | 652,769,135 |
| Cached input subset | 633,036,800 (96.98%) |
| Provider output tokens | 1,951,367 |
| Compactions | 32 |
| Captured tool-output bytes | 67,360,659 (64.24 MiB) |
| Shell execution calls | 3,512 |
| Shell calls with an RTK mention | 217 (6.18%, heuristic) |
| Checkpoint-required sessions | 6 |
| Warning sessions | 1 |
| Sessions with missing worker usage | 1 |

Six session totals exceeded 25M tokens or two compactions. One further session
was above the 10M warning threshold. The active implementation task crossed
25M during verification, and the installed Stop guard returned
`checkpoint_required` without automatically continuing or blocking STOP.

## Interpretation

- This is provider-reported cumulative usage, not a character proxy.
- 96.98% cached input is not 96.98% billing or quota savings; cached tokens are
  still provider input and may have different price/quota treatment.
- `rtk gain` reports 97.3% reduction inside commands that RTK actually wrapped.
  That denominator differs from all provider input and cannot prove 97.3% or
  99% session savings.
- Only 6.18% of observed shell-call payloads contained an RTK mention, and the
  classifier does not know which remaining commands were eligible. Treat it as
  a routing signal, not missed-savings proof.
- The valid three-task provider A/B measured 19.67% aggregate reduction after
  replacing automatic full-skill reads with a compact policy. One task still
  regressed 32.16%; 99%+ end-to-end savings is not established.

## Reproduction

```zsh
for file in ~/.codex/sessions/**/*.jsonl(.om[1,10]); do
  agent-token-ledger --usage "parent=$file" --provider codex --format json
done
```

The exact ten-session set is time-dependent because active sessions continue
to append. Re-run before using these totals as a current status report.
