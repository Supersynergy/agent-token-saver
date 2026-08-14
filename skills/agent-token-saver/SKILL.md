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

## Fan-out engine — `llmadapter` (one interface over every lane)

```bash
llmadapter ask-v2 --stdin --swarm --lanes cheap --allow-remote --allow-paid \
  --contract prose --max-tokens 500 --deadline-secs 180   # the default swarm
llmadapter ask "<prompt>" --json                 # single lane, no capsule
llmadapter ask "<prompt>" --tier                 # proposers → aggregate → fresh verify
llmadapter lanes | doctor [--probe] | stats      # inventory / health / usage
```

`ask-v2 --swarm` is the one to reach for: deadline, accounting, per-lane cache,
first-pass pruning, oracle gate, ledger. Plain `ask` has none of that.

`llmadapter lanes` is the only source of truth for what exists on this host:
the built-in table plus any host-local lanes, so the count is host-specific
and drifts with every catalog sweep. Selectors (`cheap`, `free`, `paid`,
`local`, `cli`) are stable; do not memorise lane names or counts.

**Start with `--lanes cheap`, not `free`.** Measured 2026-08-01 over closed-form
tasks with known answers, three samples each:

| selector | models | correct | cost |
|---|---|---|---|
| `cheap` | gpt-oss-120b, gpt-5.6-luna, ling-2.6-flash | 9/9, 9/9, 7/9 | $0.00046 per 9 calls |
| `free` | nemotron / gemma / laguna `:free` | 6-7/9 | $0 |

Free lanes buy a 20-30 point correctness drop to save five thousandths of a
cent. `cheap` is a selector keyword over the paid class, so it needs
`--allow-paid`; the wire `class` stays `paid`.

`--contract verdict|prose|json` picks the answer shape. `verdict` is the default
(`STATUS: PASS|FAIL|BLOCKED; EVIDENCE: …; HANDOFF: …`) and is what a controller
gates on. Use `prose` or `json` for anything that is not a verification — the
verdict shape used to make workers argue about format instead of answering.

Lane selectors: `free` · `cheap` · `paid` (kimi) · `local` (ollama) ·
`cli` (codex, agy, ggcoder, claude-haiku, devin, cursor) · `all` · or lane names.
A class selector is ordered by **measured health** from the ledger (7-day
Laplace-smoothed success rate), so a provider outage sinks that lane and a
working one takes the slot; `--lanes a,b,c` keeps your order.
`LLMADAPTER_LANE_HEALTH=0` opts out. `doctor` prints the three lanes `--lanes
free` will actually run; `doctor --probe` spends one 32-token call per free lane
to show which answer today.

A model id that leaves the catalog fails only at call time, as a generic
provider error — check before trusting any lane list:

```bash
curl -s https://openrouter.ai/api/v1/models | jq -r '.data[].id' | grep :free
```

`--tier` is the pilotfish/Anthropic pattern in one flag: proposers → strong
aggregate → verifier from a **different model family** so the cross-check is
real. Aggregator, verifier and council synthesis all pick by health now; pin one
with `LLMADAPTER_AGGREGATE_LANE` / `_VERIFY_LANE` / `_COUNCIL_LANE`.
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
