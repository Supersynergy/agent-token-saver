# ADR 2026-07-16 — Cheapest viable team structure

## Status

Accepted, based on measured lanes in
[claude-team-ab-2026-07-16](../../data/benchmarks/claude-team-ab-2026-07-16.md)
and [engine-probe-2026-07-16](../../data/benchmarks/engine-probe-2026-07-16.md).

## Decision

Order lanes by measured marginal cost, cheapest first. A lane is only allowed
to escalate one step after its oracle fails.

```text
0. deterministic projection (rg/awk/jq)     $0, fastest, most correct
1. capsule verification, free-tier API      $0, ~1-2 s, strict-JSON votes
2. free local agent CLI shell lane          $0, ~10 s
3. sandboxed subscription worker (critic)   sub, OS-sandboxed, cross-model
4. in-session child (largest bootstrap)     sub, only when the result must
                                            land in the parent context and
                                            the spawn inequality holds
controller + gate: the expensive model      plans, packets, verification —
                                            never bulk work
```

Local models are not a lane of their own: after deterministic filtering they
saved almost nothing in the component fixtures, and small local models are too
weak for open-ended lanes. Use them only for bounded intake/classification
steps in front of a premium lane, with a machine-checkable oracle on the
classification itself.

## Rules carried over from the subagent protocol

- No self-grading; verify with a deterministic oracle or a different model.
- Stagger spawns that share a prompt prefix; simultaneous fan-out forfeits
  provider cache reuse (measured: four separate ~44k cache writes).
- Workers return ≤500-token capsules pointing at evidence, never raw data.
- The ledger sums parent, children, retries and fallbacks; a missing worker
  ledger fails the done gate.

## Consequences

- Fan-out is for wall time and independent perspectives, never token savings
  (measured team = 3.0x one worker on the same oracle).
- Verification gets cheap and wide: free capsule votes make 3-5 vote
  adversarial gates affordable by default.
- Business-persona council schedulers stay in the strategy domain; coding
  lanes use the ladder above.
