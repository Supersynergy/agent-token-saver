# Codex provider A/B — 2026-08-22 17:06:21 CEST

Fresh HOME per run; same model, fixture and task oracle. Baseline disables hooks; Lean installs the canonical prompt and Stop hooks. Provider-reported Codex usage is authoritative.

| Task | Baseline input | Lean input | Input saved | Baseline total | Lean total | Accepted | RTK in Lean |
|---|---:|---:|---:|---:|---:|:--:|:--:|
| process-table | 33,435 | 30,315 | 9.33% | 33,560 | 30,457 | yes | no |
| large-git-diff | 33,137 | 46,184 | -39.37% | 33,347 | 46,630 | yes | no |
| git-history | 29,600 | 30,412 | -2.74% | 29,795 | 30,599 | yes | no |

## Aggregate gate

- All task oracles accepted: **yes**.
- Baseline provider total: **96,702**.
- Lean provider total: **107,686**.
- Provider total saving: **-11.36%**.
- 99%+ provider saving proven: **no**.

A failed oracle invalidates the saving claim. One run per arm is fresh evidence, not a statistical confidence interval; repeat ABBA before changing defaults.
