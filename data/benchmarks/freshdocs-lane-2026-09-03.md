# Documentation-lane benchmark — freshdocs vs raw source vs memory

- date: 2026-09-03 22:56:22 CEST
- freshdocs: freshdocs 0.2.0
- token proxy: UTF-8 bytes / 4, applied identically to every lane
- raw-source rows fetched live this run: 0

## Cost

| Library | Mode | freshdocs tok | raw-source tok | Saved | ms |
|---|---|---:|---:|---:|---:|
| ruff | `--project` | 1,233 | 12,069 | 89.8% | 66 |
| ruff | `--lib` | 1,233 | 12,069 | 89.8% | 66 |
| uv | `--project` | 624 | 13,847 | 95.5% | 68 |
| uv | `--lib` | 923 | 9,950 | 90.7% | 68 |
| typescript | `--project` | 849 | 8,125 | 89.5% | 68 |
| typescript | `--lib` | 123 (refusal, not an answer) | n/a | n/a | 66 |
| bun | `--project` | 899 | 9,523 | 90.6% | 68 |
| bun | `--lib` | 1,220 | 11,425 | 89.3% | 67 |
| vitest | `--project` | 490 | 9,304 | 94.7% | 68 |
| vitest | `--lib` | 990 | 6,234 | 84.1% | 68 |
| zod | `--project` | 879 | 16,079 | 94.5% | 67 |
| zod | `--lib` | 961 | 30,879 | 96.9% | 67 |

## Correctness — the metric that decides the lane

Two independent ways a documentation lane can be wrong while looking cheap:
answering from the wrong library, or from the wrong version.

| Library | Mode | Answered from | On topic | Installed | Served | Version verdict |
|---|---|---|:--:|---|---|---|
| ruff | `--project` | ruff | yes | 0.14.14 | 0.14.14 | match |
| ruff | `--lib` | ruff | yes | 0.14.14 | 0.14.14 | match |
| uv | `--project` | ruff | NO | 0.11.5 | n/a | no-version |
| uv | `--lib` | uv | yes | 0.11.5 | 0.12.9 | drift(0.12.9 vs 0.11.5) |
| typescript | `--project` | ruff | NO | 7.0.2 | n/a | no-version |
| typescript | `--lib` | refused (fail-closed) | n/a | 7.0.2 | n/a | no-version |
| bun | `--project` | ruff | NO | 1.3.14 | n/a | no-version |
| bun | `--lib` | bun | yes | 1.3.14 | 1.4.0 | drift(1.4.0 vs 1.3.14) |
| vitest | `--project` | ruff | NO | n/a | n/a | unknown |
| vitest | `--lib` | vitest | yes | n/a | 5.0.0 | unknown |
| zod | `--project` | ruff | NO | n/a | n/a | unknown |
| zod | `--lib` | zod | yes | n/a | 4.5.4 | unknown |

Off-topic answers: **5 / 12**. Version drift: **2 / 12**. Honest refusals: **1 / 12**.

A refusal is a *good* outcome and is excluded from the saving columns on
purpose. It is the smallest output in the run, and scoring it as the
cheapest answer would rank 'said nothing' above 'was correct'.

Memory is absent from the cost table on purpose: it costs zero tokens and
carries zero fidelity, so ranking it by size would reward being wrong.
