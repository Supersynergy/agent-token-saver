# ADR 2026-07-19 — Simultaneous fan-out; Kimi lean child as cheap shell lane

## Status

Accepted (measured on this host; one run per arm).

## Context

The subagent protocol carried an unmeasured hypothesis from 2026-07-16:
staggering child spawn should convert later children's ~44k cache writes into
cache reads. Separately, the engine-lane probe had no Kimi CLI datapoint, and
every Kimi child silently loaded an 86KB user-skills index in its system
prompt.

## Decision

1. **Retire the stagger rule.** A/B on the reproducible log fixture
   (`scripts/make_log_fixture.py`) showed staggered = 411,946 gross input vs
   simultaneous = 411,938 for a three-child Claude team; both arms read the
   shared ~90k prefix from cache and both pay ~47k child-unique cache write.
   Teams fan out simultaneously; savings come from smaller per-child suffix,
   fewer requests per lane, or a cheaper runtime — never from spawn timing.
2. **Add the Kimi CLI lane, lean by default.** Child invocation is
   `kimi-cli --print --output-format stream-json -y --skills-dir <empty-dir>`.
   The empty skills dir removes 83% of the child system prompt and cuts
   uncached input 91% (22.9k → 2.1k; gross 63.8k → 22.0k) with the same
   oracle pass. Usage is read from `~/.kimi/sessions/<proj>/<id>/wire.jsonl`.
3. **Route shell-projection worker lanes to the cheapest passing runtime.**
   Measured same-day, same fixture and oracle: lean Kimi three-child team
   66,213 gross vs Claude team 411,938 (16%). Claude children stay the
   controller/verifier tier; Moonshot's implicit write-free cache means
   simultaneous Kimi fan-out carries no cache penalty.

## Consequences

- `SUBAGENT_CONTEXT_PROTOCOL.md` cache-aware fan-out section rewritten; the
  bootstrap table gains two Kimi rows.
- The stagger claim survives nowhere except as a refuted hypothesis with its
  artifact ([claude-stagger-ab-2026-07-19](../../data/benchmarks/claude-stagger-ab-2026-07-19.md)).
- Open: repeat both A/Bs ABBA on a second day, a real coding lane (not log
  projection) for the Kimi lean child, and whether `--agent` selection trims
  the remaining ~8.7k cached bootstrap further.

Shipped same day as `kimi-worker` (installer-managed CLI); the system
benchmark on kimi-cli 1.49.0 confirms the lane in production shape and beats
Kimi's own built-in `Agent` swarm by 27% gross and 3.6x wall
([kimi-worker-system-2026-07-19](../../data/benchmarks/kimi-worker-system-2026-07-19.md)).

Artifacts: [kimi-lane-2026-07-19](../../data/benchmarks/kimi-lane-2026-07-19.md),
[claude-stagger-ab-2026-07-19](../../data/benchmarks/claude-stagger-ab-2026-07-19.md).
