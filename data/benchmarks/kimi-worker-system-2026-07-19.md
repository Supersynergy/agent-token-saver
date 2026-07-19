# kimi-worker production lane — system benchmark 2026-07-19

The shipped system behind the [2026-07-19 ADR](../../docs/adr/2026-07-19-simultaneous-fanout-and-kimi-lean-lane.md):
`kimi-worker` (installed to `~/.agent-token-saver/bin` and `~/.local/bin`) is
a lean Kimi child — empty `--skills-dir`, `--quiet` final-message contract,
exit-75 retry, per-worker `KIMI_SHARE_DIR` isolation seeded with
config/credentials. Runtime here: `kimi-cli 1.49.0` (upgraded from the 1.48.0
used in [kimi-lane-2026-07-19](kimi-lane-2026-07-19.md); rollback:
`uv tool install kimi-cli==1.48.0`). Same reproducible fixture and oracle as
all 2026-07 lane benchmarks.

| Arm | Gross input | Uncached | Cache read | Output | Wall | Oracle |
|---|---:|---:|---:|---:|---:|---|
| kimi-worker single lane | 22,268 | 2,300 | 19,968 | 395 | 9.7 s | PASS |
| **kimi-worker team (3x simultaneous)** | **67,514** | **6,842** | 60,672 | 1,160 | **10.8 s** | PASS |
| Kimi built-in swarm (1 parent, 3 `Agent` calls) | 92,803 | 10,627 | 82,176 | 4,503 | 39.1 s | PASS |
| Claude team, 3 cheapest-tier children (same day) | 411,938 | 108 (+149,162 write) | 262,668 | 1,908 | ~13 s | PASS |

## Real savings (measured this session, token volume)

- **Team vs Claude team: −83.6%** gross input (411,938 → 67,514).
- **Team vs Kimi built-in swarm: −27.2%** gross and **3.6x faster** (the
  built-in `Agent` fan-out runs inside one session, re-buys the parent
  conversation per step and burns 3.9x the output tokens).
- **Single lane vs single Claude projection child: −82.8%**
  (129,836 → 22,268), and the single lane covers this whole oracle alone —
  fan out only for genuinely independent lanes, per the protocol.
- 1.48 → 1.49 regression on the lean single lane: +1.0% gross (22,047 →
  22,268) — stable.

Billing caveat: token classes are provider usage fields. Claude runs on an
Anthropic subscription, Kimi on Moonshot membership quota whose
`kimi-for-coding` slug prices as $0 in ccusage-style tools; no cross-provider
dollar claim is made here.

## System contract (production)

1. Controller states one machine oracle and slices independent lanes.
2. Each lane: one `kimi-worker` call, 300–700-token capsule, optional
   `KIMI_WORKER_EVIDENCE` file for full findings, `KIMI_WORKER_SHARE_DIR` for
   per-team accounting.
3. Spawn simultaneously (staggering measured useless; Moonshot cache is
   implicit and write-free — `input_cache_creation` was 0 in every request).
4. Controller sums deterministically and verifies the oracle; escalate a
   failed lane to a Claude child, never the whole team.
5. Retry only exit 75 (retryable per Kimi docs), capped by
   `KIMI_WORKER_RETRIES`.

## Repeat + ledger integration (2026-07-20)

Second team run on the production path (now with `KIMI_WORKER_USAGE_OUT`):
68,474 gross input, oracle PASS, wall 12.3 s — **+1.4%** vs run one, so the
−83.6% figure reproduces. The wrapper now exports one summed
Anthropic-field usage record per run (the ledger reads a source's last
snapshot as cumulative); `agent-token-ledger --usage worker1=... --provider
kimi` reports exactly the wire-log totals (68,474 / 1,247). Contract tests:
`tests/test_kimi_worker.py` (stubbed `kimi-cli`; retry-75, seed, evidence,
lean args, usage export).

One run per arm unless stated; raw JSON: `kimi-worker-system-2026-07-19.json`.
