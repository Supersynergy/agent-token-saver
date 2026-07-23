---
name: agent-token-saver
description: Route token-heavy context, noisy shell logs and output through the smallest measured CLI or projection before loading heavy tools; benchmark cheap subagent workflows without broad prompt bloat.
version: 3.8.1
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

## Recon CLIs (v3.8.0+)

Three fail-open recon tools are wrapped as `ats-*` helpers and exposed in
`ats-doctor`. All run without MCP and without API keys (ghx uses `gh` auth).

- **`ats-gmax "<question>"`** — semantic search over indexed local codebases.
  Persistent index under `~/.gmax/`. `--agent` output is ledger-compatible
  (single-line hits + similarity score + role tag). Subcommands: `trace`,
  `skeleton`, `extract`, `peek`, `dead`. Replaces Cascade `code_search` for
  indexed projects — index once with `gmax add <path>`, query from project root.
- **`ats-ghx explore|read|inspect|search <owner/repo>`** — GitHub reconnaissance
  sidecar. GraphQL batching (10 files/call), `--map` output ~92% token reduction
  vs raw file reads. `inspect` ranks files by concern. Uses `gh` CLI auth, no
  extra API key. Ideal pre-step before deep web research for repo-specific
  questions.
- **`ats-supacrawl scrape|map|crawl|batch <url>`** — HTTP-first web scraper,
  markdown output. Complements heavier research tooling for quick single-page
  pulls. No API key for scrape/map/crawl/batch. LLM-Extract with Ollama
  currently broken (schema serialization) — pipe `supacrawl scrape` to
  `ollama` directly as workaround. For cited multi-hop research use your
  existing deep-research CLI.

All three are optional and fail-open: missing CLI → passthrough message, never
error. `ats-recon-doctor` shows install state + gmax indexed projects.

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

Spawn workers simultaneously — a measured A/B (2026-07-19) shows staggering
saves zero input tokens on Claude children and Moonshot caching is implicit.
Route shell-projection lanes to the cheapest passing runtime: `kimi-worker`
(lean Kimi child, empty skills dir, exit-75 retry, per-team `KIMI_SHARE_DIR`,
optional evidence file) ran the same oracle at 16% of a Claude team's gross
input. Keep the expensive model for the controller and verification.

## Done gate

- Same accepted result before and after optimization.
- Raw and optimized token estimate recorded.
- Latency recorded.
- Parent-plus-children total and the machine oracle recorded for a team.
- `--require-complete-team` and `--require-within-guard` pass before team completion.
- Optional tools remain optional.
- Hook presence verified in live agent config, not inferred from files on disk.
