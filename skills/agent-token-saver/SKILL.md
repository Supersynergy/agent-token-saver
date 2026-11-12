---
name: agent-token-saver
description: Reduce repeated work and noisy context while preserving task evidence. Use for long check output, exact log questions and RTK comparisons; skip already-small lookups.
version: 5.1.1
license: MIT
---

# Agent Token Saver

Optimize accepted work per total effort. Keep the task, permissions and oracle.

1. Reuse decisions and green checks only with matching source evidence.
2. Ask one exact question. Use scoped `rg --no-config`, `jq` or SQL before broad reads.
3. `ats verify -- COMMAND` executes once and preserves exit status plus full raw logs.
4. `ats project FILE --match TEXT` finds literal matches with line numbers and coverage counts.
5. Tail views and shortened inventories are previews. Never feed them to a parser expecting complete input.
6. `ats bench --out DIR` checks eight synthetic RTK contracts. Reject evidence loss and zero byte gain.
7. `ats cost FILE` uses disjoint usage and explicit prices. Bytes removed are not provider savings.
8. Use `ats --json ...` for scripts; `ats guide` for the next task. Load one primary skill per phase.
9. Stop after acceptance. Write reference-only handoffs at real context boundaries.

RTK is optional. Do not rewrite commands automatically, install hooks, spawn
workers, make paid calls, start maintenance or change memory because this skill
is loaded. Missing evidence stays unknown. The 20-skill catalog contains distilled
principles, not an instruction to load every source.

The CLI, installer, fixtures and tests use TypeScript/Bun. Retired Python, shell,
provider and hook surfaces are documented in docs/MIGRATION.md. A source update
does not migrate old hooks already installed in a user's home.
