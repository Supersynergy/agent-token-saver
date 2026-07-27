---
name: agent-token-saver
description: Route token-heavy context, noisy shell logs and output through the smallest measured CLI or projection before loading heavy tools; recall past agent sessions before re-deriving; fan out to free lanes; benchmark cheap subagent workflows without broad prompt bloat.
version: 4.22.0
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, context, cli, benchmark, compress, log, noisy, output, subagent, agent-teams, capsule, recall, fanout, llmadapter, codex, claude-code, hermes, ggcoder]
---

# Agent Token Saver

Use this skill when a task can produce large logs, files, tool schemas,
repeated work, a broad skill catalog, or an agent team.

## Default ladder

1. **Recall first.** `ats-recall "<q>"` — your agents may have solved this
   already. No LLM, no API, ~0s.
2. Exact local search or deterministic projection.
3. RTK for supported noisy shell commands.
4. Load zero or one primary routed skill automatically, never the whole library.
5. Use a budgeted code reader only when exact search misses.
6. Enable graph, browser, or large-context tooling for one session only.

## Recall loop (v4.18–4.20) — the compounding half

Every agent CLI session becomes searchable; every new run reads the corpus back.

```bash
ats-recall "<question>"              # corpus + brain, deduped, one block per doc
ats-recall --brain "<q>"             # verified memory only
ats-recall --corpus "<q>" --limit 10 # raw CLI-log corpus only
synapse-ingest-cli-logs.py --since 2 # fill it (Codex/Claude/aider/opencode)
bash scripts/install-ingest-cron.sh  # daily launchd job, 04:30, idempotent
```

Sessions bulk-import into the main brain under `cli-log://`, which `synx hybrid`
searches in ~0s (the corpus sidecar is opt-in and slower). Job installed as
`de.supersynergy.synapse-cli-log-ingest`. Do not re-derive what recall returns.

## Fan-out engine — `llmadapter` (23 lanes, one interface)

```bash
llmadapter ask "<prompt>" --json                 # single cheapest lane
llmadapter ask "<prompt>" --aggregate            # consensus merge
llmadapter ask "<prompt>" --tier                 # cheap proposers → aggregate → fresh verify
llmadapter ask "<prompt>" --verify               # independent fresh-context verifier gate
llmadapter lanes | doctor | stats                # inventory / health / usage
```

Lane classes: `free` (14 OpenRouter), `paid` (kimi), `local` (ollama),
`cli` (codex, agy, ggcoder, claude-haiku, devin, cursor). `--tier` is the
pilotfish/Anthropic pattern in one flag: cheap proposers → strong aggregate →
verifier from a **different model family** so the cross-check is real.
Private lanes live in `~/.agent-token-saver/local-lanes.json`, outside the
repo — never committed, never deployed.

### PII shield (mandatory on every remote lane)

`shieldPrompt()` pseudonymises via `ggadapter/adapter/dsgvo-shield.mjs` before
the prompt leaves the machine and restores real values in the response, before
cache and caller. `ollama` is untouched (never leaves the machine).
**Missing shield → the remote lane aborts instead of sending plaintext.**
Path via `ATS_SHIELD_PATH`; deliberate opt-out only via `ATS_PII_SHIELD=0`.
Known effect: a full company name incl. legal form becomes one token, so the
industry word is lost — for classification workloads prefer local lanes.

## One-shot pipeline — `ats-pipe`

GATHER (cheapest recon) → FANOUT (llmadapter) → SYNTH (consensus).

```bash
ats-pipe --recall "<q>"          # prepend past-session hits, then fan out
ats-pipe --web "<q>"             # gather via the configured web-research CLI
ats-pipe --github "<query>"      # gather via the configured code-search CLI
ats-pipe --url <url> "<q>"       # gather a page, ask about it
ats-pipe --gather-only "<q>"     # context only, no model call
ats-pipe --synth "<q>"           # fan out then merge to one answer
ats-pipe --tier "<q>"            # tiered proposers→aggregate→verify
ats-pipe --verify "<q>"          # fresh-context verifier gate
ats-pipe --lanes free|local|all --first 3 --only <lane>
```

Every stage is fail-open: a dead gather tool degrades to no-context, a dead
lane is reported honestly. No paid call unless you add one.

## Recon CLIs

Fail-open `ats-*` helpers, no MCP, no API keys (ghx uses `gh` auth).

- **`ats-recon "<q>"`** — auto-router: URL → supacrawl, `owner/repo` → ghx,
  else gmax semantic search. `ats-recon-doctor` shows install state.
- **`ats-gmax "<q>"`** — semantic search over indexed local codebases
  (`~/.gmax/`). `--agent` output is ledger-compatible. Sub: `trace`,
  `skeleton`, `extract`, `peek`, `dead`. Index once: `gmax add <path>`.
- **`ats-ghx explore|read|inspect|search <owner/repo>`** — GitHub recon,
  GraphQL batching (10 files/call). Budget compaction (~92% fewer tokens) is
  the default since ghx 2.9 (`--budget <chars>`, `--full` disables).
- **`ats-supacrawl scrape|map|crawl|batch <url>`** — HTTP-first scraper,
  markdown out. `ats-supacrawl-extract <url> "<prompt>"` for scrape+extract
  via the `ats-llm-pipe` stdio bridge (no Ollama, no API key).
- **`ats-url-cache get|put|stats|vacuum <url>`** — SQLite URL→markdown cache
  (WAL, TTL 86400s) so a repeated fetch never costs context twice.

## Cost accounting

```bash
agent-token-saver doctor --profile lean|teams
agent-token-ledger --usage parent=<p.json> --usage child=<c.json> \
  --require-complete-team --require-within-guard --format markdown
ats-token-cfo audit|simulate|plan|report --usage <path> --provider <name>
python3 scripts/token_stack_matrix_benchmark.py --help
```

Never claim provider billing savings from a local character estimate.

## Model split — controller vs worker

Keep the expensive model on the controller and on verification; route the work
to the cheapest runtime that still passes the oracle.

- **Controller / orchestrator**: Opus / Fable. Plans, routes, verifies, gates.
- **Workers**: Sonnet for in-harness subagents. `CLAUDE_CODE_SUBAGENT_MODEL`
  overrides both the subagent frontmatter and the per-invocation `model` param,
  so it is the single enforcement point.
- **Shell-projection lanes**: `kimi-worker` (lean Kimi child, empty skills dir,
  exit-75 retry, per-team `KIMI_SHARE_DIR`) ran the same oracle at **16%** of a
  Claude team's gross input (measured 2026-07-19).

## Agent teams

`agent-token-saver` is the installer and measured core. The router
(`agent-token-saver-skill-router`, CLI `si`) is a separate optional skill —
install it only when a large skill catalog makes 0/1 routing worthwhile:

```bash
si route "<task>" --max 1 --strict --json   # automatic 0/1 decision
si find "<capability>" --json               # manual discovery only
si index --refresh --json                   # after skill changes
```

Do not auto-load the router skill itself or a second reserve skill. An explicit
`$SkillName` remains the user override.

Before a team starts, keep one controller and require every worker to have:

- one independent closed objective;
- one 300–700-token capsule with paths/hashes, exact constraints and a PASS/FAIL oracle;
- zero or one routed primary skill; never the controller's catalog or transcript;
- at most three attempts and a <=500-token result pointing to evidence.

Do not spawn for a small overlapping check. Sum parent, children, retries,
fallbacks and compactions in `agent-token-ledger`; parallelism saves wall time,
not automatically provider tokens. Default maximum: three independent workers.
Spawn simultaneously — a measured A/B (2026-07-19) shows staggering saves zero
input tokens on Claude children and Moonshot caching is implicit.

Keep approvals, safety rules, exact evidence and error lines intact.

## Done gate

- Same accepted result before and after optimization.
- Raw and optimized token estimate recorded.
- Latency recorded.
- Parent-plus-children total and the machine oracle recorded for a team.
- `--require-complete-team` and `--require-within-guard` pass before team completion.
- Optional tools remain optional.
- Hook presence verified in live agent config, not inferred from files on disk.
