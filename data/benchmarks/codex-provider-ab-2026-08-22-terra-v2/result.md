# Codex provider A/B — 2026-08-22 19:12:49 CEST

Fresh HOME per run; same model, fixture and task oracle. Baseline disables hooks; Lean installs the canonical prompt and Stop hooks. Provider-reported Codex usage is authoritative.

| Task | Baseline input | Lean input | Input saved | Baseline total | Lean total | Accepted | RTK in Lean |
|---|---:|---:|---:|---:|---:|:--:|:--:|
| process-table | 33,472 | 32,688 | 2.34% | 33,620 | 33,070 | yes | no |
| large-git-diff | 30,041 | 30,648 | -2.02% | 30,232 | 30,890 | yes | no |
| git-history | 29,640 | 30,394 | -2.54% | 29,864 | 30,592 | yes | no |

## Aggregate gate

- All task oracles accepted: **yes**.
- Baseline provider total: **93,716**.
- Lean provider total: **94,552**.
- Provider total saving: **-0.89%**.
- 99%+ provider saving proven: **no**.

A failed oracle invalidates the saving claim. One run per arm is fresh evidence, not a statistical confidence interval; repeat ABBA before changing defaults.
