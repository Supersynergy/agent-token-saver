---
name: agent-token-saver
description: Route context through the smallest measured CLI or projection before loading heavy tools.
version: 3.1.0
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, context, cli, codex, claude-code, hermes, ggcoder]
---

# Agent Token Saver

Use this skill when a task can produce large logs, files, scraped pages, tool
schemas, repeated research, or a broad skill catalog.

## Default ladder

1. Exact local search or deterministic projection.
2. RTK for supported noisy shell commands.
3. Load 1-3 routed skills, not the whole skill library.
4. Use a budgeted code reader only when exact search misses.
5. Enable graph, browser, or large-context tooling for one session only.

Keep approvals, safety rules, exact evidence and error lines intact. Never claim
provider billing savings from a local character estimate.

## Commands

```bash
agent-token-saver doctor --profile lean
python3 scripts/news_projection.py raw.jsonl --top 40 --format jsonl
python3 scripts/token_stack_matrix_benchmark.py --help
```

For adaptive routing across a large skill collection, install the companion
`agent-token-saver-skill-router` and load only the paths it selects:

https://github.com/Supersynergy/agent-token-saver-skill-router

## Done gate

- Same accepted result before and after optimization.
- Raw and optimized token estimate recorded.
- Latency recorded.
- Optional tools remain optional.
- Hook presence verified in live agent config, not inferred from files on disk.
