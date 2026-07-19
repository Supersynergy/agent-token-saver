# Claude staggered-spawn A/B — 2026-07-19

Tests the cache-aware fan-out hypothesis recorded in
[SUBAGENT_CONTEXT_PROTOCOL](../../docs/SUBAGENT_CONTEXT_PROTOCOL.md) after the
2026-07-16 team A/B: *"Stagger the spawn — the expected saving is one cache
write per additional worker."* Same reproducible fixture
(`scripts/make_log_fixture.py`) and oracle (three disjoint awk slices, ground
truth 40/32/28, controller sums to 100 + marker 3777). Children are Claude
Code subagents on the cheapest tier; usage from per-child subagent
transcripts.

| Arm | Uncached | Cache write | Cache read | Gross input | Output | Oracle |
|---|---:|---:|---:|---:|---:|---|
| Simultaneous (3 at once) | 108 | 149,162 | 262,668 | 411,938 | 1,908 | PASS |
| Staggered (1, then 2) | 108 | 142,298 | 269,540 | 411,946 | 1,749 | PASS |

## Verdict: hypothesis refuted on this host

1. **Staggering saved zero gross input** (411,946 vs 411,938) and only 4.6%
   cache write — all of it first-child variance (54.1k vs ~47.4k), not a
   write-to-read conversion.
2. **The shared prefix is already served from cache in both arms.** Every
   child, simultaneous or staggered, read ~89.8k from cache on its first
   request. The 2026-07-16 reading ("four children paid four writes for one
   shared prefix") no longer holds on this harness version.
3. **The ~47k per-child cache write is child-unique suffix** (per-agent
   context, task packet, and the child's own growing conversation re-written
   across its 4 requests). Spawn timing cannot convert it; it is the real
   irreducible cost of a Claude child today.
4. Practical rule replacing the stagger advice: **fan out simultaneously** —
   same tokens, less wall time. Reduce team cost by cutting per-child suffix
   (leaner task packets, fewer requests per lane) or by routing lanes to a
   cheaper runtime, not by scheduling.

Cross-runtime, same day, same fixture and oracle
([kimi-lane-2026-07-19](kimi-lane-2026-07-19.md)): a lean Kimi three-child
team used 66,213 gross input — **16%** of the Claude team's 411,938, with
identical slice answers. Reproducibility check: today's simultaneous Claude
team (411,938) sits within 5.6% of the 2026-07-16 team (390,010).

Addendum, same day: a slice-1 probe through a tool-restricted custom agent
type (read-only investigator profile, cheapest tier) cost 137,338 gross —
identical to the default child. Agent-type restriction does not shrink the
child bootstrap either; runtime choice is the only measured lever.

One run per arm; token classes are provider usage fields, not billing
claims. Raw JSON: `claude-stagger-ab-2026-07-19.json`.
