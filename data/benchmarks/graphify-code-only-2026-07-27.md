# Graphify code-only pilot — 2026-07-27

Scope: repository root, Graphify 0.9.25.
The run used local AST extraction only: `--code-only --no-cluster`, no API key,
no LLM semantic extraction and no persistent repository artifact.

| Metric | Result |
|---|---:|
| Code files inspected | 93 |
| Graph nodes / edges | 641 / 1,482 |
| Build wall time | 8.3 s |
| Peak RSS | 100 MiB |
| Raw graph bytes / estimated tokens | 676,659 / 169,165 |
| Bounded query output | 477 estimated tokens |
| Query wall time | 844 ms |
| Raw-to-query reduction | 99.72% (354.6x) |

Oracle query: `How does stack_doctor build and validate the installed profile?`
Required term: `build_report`. The query passed.

Decision: graph is accepted as an explicit Heavy-session or repeated-repo
accelerator. It is rejected as a Lean default: an 8.3-second, 100-MiB build is
not a good trade for one symbol/file question, where Tilth, Gmax or `ast-grep`
has lower startup cost.
