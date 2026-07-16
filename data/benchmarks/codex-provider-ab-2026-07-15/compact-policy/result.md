# Codex provider A/B — 2026-07-15 16:09:47 CEST

Fresh HOME per run; same model, fixture and task oracle. Baseline disables hooks; Lean installs the canonical prompt and Stop hooks. Provider-reported Codex usage is authoritative.

| Task | Baseline input | Lean input | Input saved | Baseline total | Lean total | Accepted | RTK in Lean |
|---|---:|---:|---:|---:|---:|:--:|:--:|
| process-table | 29,250 | 38,418 | -31.34% | 29,359 | 38,800 | yes | no |
| large-git-diff | 44,496 | 25,691 | 42.26% | 44,629 | 25,886 | yes | no |
| git-history | 38,136 | 25,476 | 33.20% | 38,500 | 25,678 | yes | no |

## Aggregate gate

- All task oracles accepted: **yes**.
- Baseline provider total: **112,488**.
- Lean provider total: **90,364**.
- Provider total saving: **19.67%**.
- 99%+ provider saving proven: **no**.

A failed oracle invalidates the saving claim. One run per arm is fresh evidence, not a statistical confidence interval; repeat ABBA before changing defaults.
