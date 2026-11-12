# Claude hook-matrix A/B — 2026-09-13 21:38:09 CEST

Every arm runs `--setting-sources` isolation in the real HOME plus its own `--settings` hook fragment; baseline carries none. Usage is summed from the session transcript (authoritative); `modelUsage` and `total_cost_usd` cross-check. Weighted columns price cache classes via the Anthropic ratios.

| Task | Model | Arm | Input | Total | Input saved (raw) | Input saved (weighted) | Total saved (weighted) | Cache hit | Cost | Accepted |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| git-history | haiku | baseline | 88,484 | 89,292 | — | — | — | — | $0.0161 | yes |
| git-history | haiku | all | 97,034 | 98,492 | -9.66% | -26.94% | -36.21% | 86.76% | $0.0217 | yes |
| git-history | haiku | ats | 91,276 | 92,368 | -3.16% | -4.63% | -9.92% | 89.47% | $0.0174 | yes |
| git-history | haiku | ctx | 93,918 | 94,800 | -6.14% | -20.21% | -18.29% | 87.23% | $0.0193 | yes |
| git-history | sonnet | baseline | 85,026 | 85,468 | — | — | — | — | $0.0312 | yes |
| git-history | sonnet | ats | 60,809 | 61,011 | 28.48% | 31.00% | 33.52% | 90.70% | $0.0367 | yes |
| large-git-diff | haiku | baseline | 186,666 | 188,696 | — | — | — | — | $0.0279 | no |
| large-git-diff | haiku | all | 96,430 | 97,770 | n/a | n/a | n/a | 87.29% | $0.0208 | no |
| large-git-diff | haiku | ats | 184,194 | 185,860 | n/a | n/a | n/a | 94.32% | $0.0243 | no |
| large-git-diff | haiku | ctx | 196,124 | 197,882 | n/a | n/a | n/a | 92.25% | $0.0296 | no |
| large-git-diff | sonnet | baseline | 118,246 | 118,816 | — | — | — | — | $0.0369 | yes |
| large-git-diff | sonnet | ats | 91,155 | 91,648 | 22.91% | 11.12% | 11.37% | 87.78% | $0.0375 | yes |
| large-git-diff | sonnet | ctx | 191,080 | 192,956 | -61.60% | -53.90% | -72.04% | 91.42% | $0.0607 | yes |
| multi-edit | haiku | baseline | 711,268 | 725,088 | — | — | — | — | $0.0719 | yes |
| multi-edit | haiku | ats-cap | 483,045 | 507,834 | 32.09% | -47.64% | -59.58% | 78.26% | $0.0488 | yes |
| multi-edit | haiku | cap | 457,745 | 483,488 | 35.64% | 2.21% | -31.09% | 87.42% | $0.0391 | yes |
| multi-edit | sonnet | baseline | 210,847 | 212,486 | — | — | — | — | $0.0831 | yes |
| multi-edit | sonnet | ats-cap | 149,190 | 150,057 | n/a | n/a | n/a | 84.49% | $0.0694 | no |
| multi-edit | sonnet | cap | 181,333 | 182,674 | n/a | n/a | n/a | 89.54% | $0.0524 | no |
| process-table | haiku | baseline | 90,210 | 90,660 | — | — | — | — | $0.0254 | yes |
| process-table | haiku | all | 98,252 | 98,952 | -8.91% | -14.53% | -17.24% | 76.45% | $0.0296 | yes |
| process-table | haiku | ats | 93,036 | 93,576 | -3.13% | 29.47% | 26.20% | 87.73% | $0.0178 | yes |
| process-table | haiku | ctx | 95,686 | 96,226 | -6.07% | 16.59% | 14.18% | 84.58% | $0.0211 | yes |
| process-table | sonnet | baseline | 89,665 | 89,953 | — | — | — | — | $0.0610 | no |
| process-table | sonnet | ats | 91,268 | 92,167 | n/a | n/a | n/a | 74.26% | $0.0634 | no |
| process-table | sonnet | ctx | 94,269 | 95,264 | n/a | n/a | n/a | 84.28% | $0.0484 | no |

## Aggregate vs baseline

- Baseline total (raw): **1,600,459**, cost **$0.3535**.
- **all**: raw total 295,214 (saved n/a), weighted total saved n/a, cost $0.0721 (saved n/a), oracles no.
- **ats**: raw total 616,630 (saved n/a), weighted total saved n/a, cost $0.1971 (saved n/a), oracles no.
- **ats-cap**: raw total 657,891 (saved n/a), weighted total saved n/a, cost $0.1182 (saved n/a), oracles no.
- **cap**: raw total 666,162 (saved n/a), weighted total saved n/a, cost $0.0915 (saved n/a), oracles no.
- **ctx**: raw total 677,128 (saved n/a), weighted total saved n/a, cost $0.1791 (saved n/a), oracles no.

Ratio profile `anthropic` (verified 2026-08-25): cache read 0.1x, cache write 1.25x, output 5.0x base input. Source: https://platform.claude.com/docs/en/build-with-claude/prompt-caching.

Weighted numbers are a list-ratio estimate against a no-cache counterfactual, not an invoice. Raw provider counters stay authoritative.

A failed oracle invalidates that arm's saving claim. Single runs are fresh evidence, not confidence intervals — repeat with --reps before changing defaults.
