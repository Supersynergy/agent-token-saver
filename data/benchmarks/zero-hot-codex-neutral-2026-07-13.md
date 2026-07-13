# Zero-hot Codex neutral microbenchmark — 2026-07-13

Goal: isolate fixed context tax after moving the saver skill outside Codex's
visible skill catalog.

## Setup

- Codex CLI `0.144.2`.
- Empty working directory.
- Fresh `CODEX_HOME` per arm; only `auth.json` copied.
- Baseline: no rules, plugins, hooks or skills.
- Lean: hidden saver skill plus fail-open `UserPromptSubmit` gate.
- Prompt: `Reply exactly with OK.`
- ABBA order; every response passed the exact-answer oracle.

## Result

| Run | Arm | Input | Cached subset | Output |
|---:|---|---:|---:|---:|
| 1 | Baseline | 11,204 | 8,960 | 5 |
| 2 | Lean | 11,209 | 8,960 | 5 |
| 3 | Lean | 11,209 | 8,960 | 5 |
| 4 | Baseline | 11,204 | 8,960 | 5 |

Median delta: **+5 input tokens / +0.045%**. Static `codex debug
prompt-input` differed by five serialized bytes. The previous visible-skill
layout measured roughly `+74` warm input tokens; that fixed catalog cost is no
longer present.

This proves only near-zero idle overhead on one trivial workload. It does not
prove savings on tool-heavy tasks. Those require accepted A/B workloads with
actual command events, parent/child aggregation, retries and cache classes.
