---
name: agent-token-saver
description: Route token-heavy context, noisy shell logs and output through the smallest measured CLI or projection before loading heavy tools; benchmark cheap subagent workflows without broad prompt bloat.
version: 3.2.0
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, context, cli, benchmark, compress, log, noisy, output, subagent, agent-teams, capsule, codex, claude-code, hermes, ggcoder]
---

# Agent Token Saver

Use this skill when a task can produce large logs, files, tool schemas,
repeated work, a broad skill catalog, or an agent team.

## Default ladder

1. Exact local search or deterministic projection.
2. RTK for supported noisy shell commands.
3. Load zero or one primary routed skill automatically, never the whole library.
4. Use a budgeted code reader only when exact search misses.
5. Enable graph, browser, or large-context tooling for one session only.

Keep approvals, safety rules, exact evidence and error lines intact. Never claim
provider billing savings from a local character estimate.

## Commands

```bash
agent-token-saver doctor --profile lean
agent-token-saver doctor --profile teams
agent-token-ledger --help
python3 scripts/token_stack_matrix_benchmark.py --help
```

## Companion skill router

For adaptive routing across a large skill collection, install
[agent-token-saver-skill-router](https://github.com/Supersynergy/agent-token-saver-skill-router).
Keep the index and ranking outside model context; load only the selected domain
skill:

```bash
si route "<task>" --max 1 --strict --json  # automatic 0/1 decision
si find "<capability>" --json               # manual discovery only
si resolve "<exact-name>" --json            # exact path only
si index --refresh --json                    # after skill changes
```

Do not auto-load the router skill itself or a second reserve skill. An explicit
`$SkillName` remains the user override.

## Agent teams

`agent-token-saver` is the installer and measured core. The router is a
separate optional skill/CLI: install it only when a large skill catalog makes
0/1 routing worthwhile.

Before a team starts, keep one controller and require every worker to have:

- one independent closed objective;
- one 300–700-token capsule with paths/hashes, exact constraints and a PASS/FAIL oracle;
- zero or one routed primary skill; never the controller's catalog or transcript;
- at most three attempts and a <=500-token result pointing to evidence.

Do not spawn for a small overlapping check. Sum parent, children, retries,
fallbacks and compactions in `agent-token-ledger`; parallelism saves wall time,
not automatically provider tokens. Default maximum: three independent workers.

## Done gate

- Same accepted result before and after optimization.
- Raw and optimized token estimate recorded.
- Latency recorded.
- Parent-plus-children total and the machine oracle recorded for a team.
- `--require-complete-team` and `--require-within-guard` pass before team completion.
- Optional tools remain optional.
- Hook presence verified in live agent config, not inferred from files on disk.
