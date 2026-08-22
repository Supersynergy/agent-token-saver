# Codex provider A/B — 2026-08-22 19:16:42 CEST

Fresh HOME per run; same model, fixture and task oracle. Baseline disables hooks; Lean installs the canonical prompt and Stop hooks. Provider-reported Codex usage is authoritative.

| Task | Baseline input | Lean input | Input saved | Baseline total | Lean total | Accepted | RTK in Lean |
|---|---:|---:|---:|---:|---:|:--:|:--:|
| process-table | 33,444 | 30,415 | 9.06% | 33,565 | 30,601 | yes | no |
| large-git-diff | 33,108 | 30,614 | 7.53% | 33,268 | 30,932 | yes | no |
| git-history | 29,607 | 30,615 | -3.40% | 29,799 | 30,836 | yes | no |

## Aggregate gate

- All task oracles accepted: **yes**.
- Baseline provider total: **96,632**.
- Lean provider total: **92,369**.
- Provider total saving: **4.41%**.
- 99%+ provider saving proven: **no**.

A failed oracle invalidates the saving claim. One run per arm is fresh evidence, not a statistical confidence interval; repeat ABBA before changing defaults.
