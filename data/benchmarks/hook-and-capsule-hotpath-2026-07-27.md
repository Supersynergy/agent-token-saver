# Hook and capsule hot-path benchmark

As of: `2026-07-27T18:28:42.966004+00:00`

Baseline: `cbe3419`. Runs per arm: `7`.
Fresh Python process per sample; baseline and candidate interleaved.
No provider call. Raw wall-time samples and candidate source hashes are in the JSON.

| Case | Baseline p50 | Candidate p50 | p50 change | Baseline bytes | Candidate bytes |
|---|---:|---:|---:|---:|---:|
| trivial | 28.83 ms | 17.21 ms | 40.3% | 0 | 0 |
| token_saver_fast_route | 28.862 ms | 17.362 ms | 39.8% | 509 | 509 |
| generic_router_miss | 100.925 ms | 91.194 ms | 9.6% | 0 | 0 |
| bare_worker | 16.445 ms | 16.925 ms | -2.9% | 1048 | 1048 |
| precontracted_worker | 14.941 ms | 15.553 ms | -4.1% | 1048 | 510 |

Output equality is required except for the intentionally deduplicated
precontracted worker. Its compact output must retain status, evidence and
controller ownership. Times are host-load sensitive; inspect p95 and raw
samples before making a tail-latency claim.

Acceptance: `{"all_exit_codes_zero": true, "bare_worker_same_output": true, "generic_router_miss_same_output": true, "no_forbidden_maintenance_call": true, "precontracted_contract_preserved": true, "precontracted_smaller": true, "token_saver_fast_route_same_output": true, "trivial_same_output": true}`
