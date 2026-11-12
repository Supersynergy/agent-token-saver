# Claude hook-matrix A/B — 2026-09-13 23:31:13 CEST

Every arm runs `--setting-sources` isolation in the real HOME plus its own `--settings` hook fragment; baseline carries none. Usage is summed from the session transcript (authoritative); `modelUsage` and `total_cost_usd` cross-check. Weighted columns price cache classes via the Anthropic ratios.

| Task | Model | Arm | Input | Total | Input saved (raw) | Input saved (weighted) | Total saved (weighted) | Cache hit | Cost | Accepted |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| multi-edit | opus | baseline | 180,955 | 183,175 | — | — | — | — | $0.1727 | yes |
| multi-edit | opus | cap | 111,170 | 112,490 | 38.56% | 18.81% | 23.71% | 84.47% | $0.1534 | yes |
| multi-edit | opus | cap-grepai | 69,347 | 70,279 | 61.68% | 46.30% | 48.94% | 83.01% | $0.1154 | yes |

## Aggregate vs baseline

- Baseline total (raw): **183,175**, cost **$0.1727**.
- **cap**: raw total 112,490 (saved 38.59%), weighted total saved 23.71%, cost $0.1534 (saved 11.16%), oracles yes.
- **cap-grepai**: raw total 70,279 (saved 61.63%), weighted total saved 48.94%, cost $0.1154 (saved 33.19%), oracles yes.

Ratio profile `anthropic` (verified 2026-08-25): cache read 0.1x, cache write 1.25x, output 5.0x base input. Source: https://platform.claude.com/docs/en/build-with-claude/prompt-caching.

Weighted numbers are a list-ratio estimate against a no-cache counterfactual, not an invoice. Raw provider counters stay authoritative.

A failed oracle invalidates that arm's saving claim. Single runs are fresh evidence, not confidence intervals — repeat with --reps before changing defaults.
