# Codex provider A/B — 2026-07-15 16:06:42 CEST

Fresh HOME per run; same model, fixture and task oracle. Baseline disables hooks; Lean installs the canonical prompt and Stop hooks. Provider-reported Codex usage is authoritative.

| Task | Baseline input | Lean input | Input saved | Baseline total | Lean total | Accepted | RTK in Lean |
|---|---:|---:|---:|---:|---:|:--:|:--:|
| process-table | 29,256 | 39,878 | -36.31% | 29,371 | 40,403 | yes | no |
| large-git-diff | 25,425 | 40,294 | -58.48% | 25,735 | 40,869 | yes | no |
| git-history | 38,507 | 39,868 | -3.53% | 38,976 | 40,318 | yes | no |

## Aggregate gate

- All task oracles accepted: **yes**.
- Baseline provider total: **94,082**.
- Lean provider total: **121,590**.
- Provider total saving: **-29.24%**.
- 99%+ provider saving proven: **no**.

A failed oracle invalidates the saving claim. One run per arm is fresh evidence, not a statistical confidence interval; repeat ABBA before changing defaults.
