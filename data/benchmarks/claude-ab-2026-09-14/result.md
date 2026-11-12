# Claude hook-matrix A/B — 2026-09-14 21:53:21 CEST

Every arm runs `--setting-sources` isolation in the real HOME plus its own `--settings` hook fragment; baseline carries none. Usage is summed from the session transcript (authoritative); `modelUsage` and `total_cost_usd` cross-check. Weighted columns price cache classes via the Anthropic ratios.

| Task | Model | Arm | Input | Total | Input saved (raw) | Input saved (weighted) | Total saved (weighted) | Cache hit | Cost | Accepted |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| multi-edit | haiku | baseline | 622,418 | 644,665 | — | — | — | — | $0.0622 | yes |
| multi-edit | haiku | cap-budget | 465,738 | 490,132 | 25.17% | 10.90% | 1.61% | 86.23% | $0.0398 | yes |
| multi-edit | haiku | cap-graperoot | 631,056 | 646,013 | -1.39% | 24.38% | 28.17% | 94.62% | $0.0563 | yes |

## Aggregate vs baseline

- Baseline total (raw): **644,665**, cost **$0.0622**.
- **cap-budget**: raw total 490,132 (saved 23.97%), weighted total saved 1.61%, cost $0.0398 (saved 35.92%), oracles yes.
- **cap-graperoot**: raw total 646,013 (saved -0.21%), weighted total saved 28.17%, cost $0.0563 (saved 9.46%), oracles yes.

Ratio profile `anthropic` (verified 2026-08-25): cache read 0.1x, cache write 1.25x, output 5.0x base input. Source: https://platform.claude.com/docs/en/build-with-claude/prompt-caching.

Weighted numbers are a list-ratio estimate against a no-cache counterfactual, not an invoice. Raw provider counters stay authoritative.

A failed oracle invalidates that arm's saving claim. Single runs are fresh evidence, not confidence intervals — repeat with --reps before changing defaults.
