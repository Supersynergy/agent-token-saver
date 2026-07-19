# ADR 2026-07-18 — Headroom proxy off/on, first accepted provider A/B

## Status

Accepted, 2026-07-18. Evidence:
[headroom-ab-2026-07-18](../../data/benchmarks/headroom-ab-2026-07-18/result.md).

## Context

Headroom has been an optional provider proxy since v3.0.0, outside Lean
profiles and never as MCP — but it had no provider-usage measurement in this
repository. Every dated token-stack matrix recorded
`headroom_codex_observed: requests 0`. Its dashboard numbers mix in CLI
filtering (RTK) and could not support a routing decision.

## Method

`scripts/headroom_provider_ab.py`: fresh HOME per arm, hooks and rules
disabled in both arms, same fixture and oracle; the only variable is routing
Codex through the local Headroom proxy (`model_providers.headroom`,
`base_url http://127.0.0.1:8787/v1`). The proxy arm ran FIRST, so provider
prompt-cache reuse favors the direct arm — a measured Headroom win survives
that bias. Provider-reported usage is authoritative. Oracle:
`large-git-diff` (12,000-line uncommitted diff, exact answer `ATS_DIFF_OK`,
`git diff` observed in commands, usage > 0).

## Measured result (this run, 2026-07-18)

Command:

```
python3 scripts/headroom_provider_ab.py --live --model gpt-5.6-sol --task large-git-diff
```

Output (verbatim):

```json
{
  "accepted": true,
  "provider_delta": {
    "input_tokens": -24814,
    "uncached_input_tokens": -11758,
    "output_tokens": 206,
    "total_tokens": -24608,
    "input_saved_percent": 55.07,
    "uncached_input_saved_percent": 51.03,
    "total_saved_percent": 54.44
  },
  "proxy_delta": {
    "requests_total": 3,
    "savings_total_tokens": 0
  }
}
```

Per arm (provider usage, codex-cli 0.144.3, headroom 0.31.0):

| Arm | Input | Cached | Uncached | Output | Total | Elapsed |
|---|---:|---:|---:|---:|---:|---:|
| headroom-off | 45,058 | 22,016 | 23,042 | 148 | 45,206 | 16,603 ms |
| headroom-on | 20,244 | 8,960 | 11,284 | 354 | 20,598 | 14,699 ms |

Ledger entries (agent-token-ledger, per arm):
`data/benchmarks/headroom-ab-2026-07-18/ledger-headroom-{off,on}.{json,md}`.

## Attribution caution

The proxy handled 3 requests during the on arm, but its own compression
counter did not move (`savings_total_tokens` delta 0; the dashboard's 16,717
figure is RTK CLI filtering from an unrelated shell session). The saving is
real at the provider level; which proxy layer produced it is not
self-reported. Do not quote Headroom dashboard totals as provider savings.

## Decision

- Record 54.44% provider total saving (−24,608 tokens) for Headroom routing
  on one tool-output-heavy oracle as the first accepted measurement.
- Headroom stays an optional provider proxy outside Lean profiles. One
  accepted pair on one oracle is not a default change: promotion requires a
  repeated ABBA run and at least one low-tool-output task, where compression
  has nothing to remove and proxy overhead could dominate.
- Future Headroom claims must come from `scripts/headroom_provider_ab.py`
  (provider usage + oracle + ledger), never from dashboard aggregates.

## Consequences

The repository gains a reproducible harness for proxy routing decisions and
its first honest Headroom number. The Lean default is unchanged; the
promotion condition is written down and machine-checkable.
