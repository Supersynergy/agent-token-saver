# agent-token-saver

![agent-token-saver — less noise, better judgment](docs/assets/social-preview.png)

**Use your coding agent more. Spend far fewer tokens getting there.**

[![MIT](https://img.shields.io/badge/license-MIT-1c7c54.svg)](LICENSE)
[![CI](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml/badge.svg)](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml)
![verified agents](https://img.shields.io/badge/verified-Codex%20%7C%20Claude%20%7C%20Hermes%20%7C%20GG%20Coder-f2c14e.svg)
![measured](https://img.shields.io/badge/measured-up%20to%20146.1x%20payload%20capacity-e8f1f2.svg)

> **Imagine getting 100x more context-heavy work from Codex, Claude Code,
> Hermes or GG Coder before hitting the same token budget. In the included
> accepted-workload benchmark, you can: 386,047 tokens became 2,643 tokens --
> 99.32% less, or 146.1x more payload capacity.**

`agent-token-saver` stops wasted tokens before they reach your model. It sends
the smallest context that can still produce the correct result: the relevant
skills, the useful error lines, the needed code and the right tools for this
task.

Verified with Codex CLI, Claude Code, Hermes Agent and GG Coder. The repo-local
skill plus CLI/JSON interfaces also work with agents that understand
`SKILL.md` or can run shell commands. No API keys or private configuration are
shipped.

## What this means in plain English

Without routing, a coding agent may receive 459 skill descriptions, a complete
process table, a full README and a 20,000-line log before it starts solving the
task. Most of those tokens never help the answer.

With `agent-token-saver`, the same accepted workload used:

- **2,643 instead of 386,047 tokens** in the CLI-selective profile.
- **4,351 instead of 386,047 tokens** in the automatic Lean profile.
- **Up to 99.32% fewer tokens** across the measured workload.
- **Up to 146 comparable payloads** inside the token budget previously used by one raw payload.

That can mean more Codex or Claude work from the same subscription/API budget,
longer useful sessions before compaction, fewer quota interruptions and more
room for the model to reason about the code that actually matters.

It does **not** make the model cheaper by making it dumber. It removes context
the task did not need while keeping required evidence, errors, approvals and
acceptance checks intact.

## Why this exists

Most "token optimization" advice asks humans to think about tokens all day.
That is backwards.

`agent-token-saver` makes the token-efficient choice automatic, preserves the
evidence needed for a good answer and keeps heavy tools one command away. Your
agent reads less irrelevant text, consumes fewer tokens and keeps more of its
context window for judgment and implementation.

**The result:** more useful agent work per token, one understandable stack, four
workload profiles, real A/B measurements, reversible hooks and no lock-in.

## The measured result

Local benchmark, 2026-07-13. Same accepted workload in every arm; UTF-8 bytes / 4 for local payloads and provider-reported usage for the live output A/B.

This is a **profile payload benchmark**, not a claim that a brand-new host will
immediately reduce its complete provider bill by 146.1x. The full profile used
the named Router, RTK and Tilth components. Clean-host portability and complete
provider context are measured separately below.

| Stack | Tokens per workload | Tokens saved | Payload capacity in the same raw budget |
|---|---:|---:|---:|
| **CLI selective** | **2,643** | **99.32%** | **146.1x** |
| Lean automatic | 4,351 | 98.87% | 88.7x |
| Context-mode on demand | 10,177 | 97.36% | 37.9x |
| Everything + Ponytail | 13,109 | 96.60% | 29.4x |
| No saver | 386,047 | 0% | 1.0x |

### What "100x more usage" actually means

Take the token budget consumed by one raw benchmark workload: **386,047
tokens**.

- Raw approach: that budget carries **1** comparable workload.
- CLI-selective profile: that budget carries **146 full comparable payloads**.
- Automatic Lean profile: that budget carries **88 full comparable payloads**.
- Across 100 comparable workloads: **38,604,700 raw tokens vs 264,300 CLI-selective tokens**.

The multiplier is `raw tokens / optimized tokens`. It measures useful payload
capacity, not a promise of 146x more provider calls: subscription rate limits,
cache accounting, model output, tool calls and task mix still matter. If tokens
or quota are your bottleneck and your workload resembles this one, however,
the practical gain can be enormous.

### Where the tokens disappear

| Instead of sending this | The agent receives this | Measured reduction |
|---|---|---:|
| All 459 installed skills | The 3 relevant skills | 99.39% |
| Full noisy process output | RTK's useful projection | 97.41% |
| Entire README | A bounded structural read | 78.50% |
| A 20,000-line log | Exact error count + last 10 errors | 99.94% |

The model still gets the facts needed to pass the same acceptance check. It
simply stops paying attention to everything else.

The cheapest default is not “enable everything”:

```text
skill router -> RTK -> deterministic projection
             -> Tilth on demand -> workload-gated heavy tools
```

Reproduce it:

```bash
python3 scripts/token_stack_matrix_benchmark.py \
  --reuse-live data/benchmarks/token-stack-matrix-2026-07-13.json
```

Raw result: [data/benchmarks/token-stack-matrix-2026-07-13.md](data/benchmarks/token-stack-matrix-2026-07-13.md).

## Does it work on a neutral machine?

Yes for the portable core. Every push runs a fresh-HOME install on a clean
GitHub-hosted Ubuntu runner. It verifies the installer, CLI, ledger, Codex and
Claude hook files, Hermes and GG Coder skills, and the repo-local skill without
this machine's dotfiles.

There are two deliberately separate states:

- `core-ready`: portable skill, hooks, doctor and token ledger work; optional
  optimizers may be missing.
- `full`: every component selected by that profile is installed and detected.

```bash
bash scripts/neutral_install_smoke.sh
bash scripts/remote_bootstrap_smoke.sh
agent-token-saver doctor --profile lean --json
```

Live neutral runner: [GitHub Actions](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml).

## Profiles

| Profile | Use | Default components |
|---|---|---|
| `minimal` | Lowest measured token cost | skill router, RTK, native projection |
| `lean` | Daily automatic coding | minimal + Tilth |
| `heavy` | large logs, deep code graph, browser | lean + context-mode/Graphify/CodeGraph only for that session |
| `news` | scrape/research fan-out | lean + cached fetch + dedupe/rank/project + bounded subagents |

Rules:

- RTK compresses noisy shell output. It does not clean HTML or replace a fetcher.
- Exact local projection beats a sandbox MCP for one deterministic extraction.
- Context-mode wins on repeated questions over large logs, JSON, DOM or API payloads; keep its schema on demand.
- Graphify wins when a repo/corpus is queried repeatedly and structural paths matter; do not build it for one exact lookup.
- Ponytail/caveman shape output. Their instruction tokens can cost more than they save on short answers.
- MCP schemas are a recurring tax. Default to CLI/file/socket surfaces unless measured otherwise.

## Install and wire hooks

One-command install:

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver/main/install-universal.sh \
  | bash -s -- --profile lean --agent auto
```

Prefer to inspect first:

```bash
git clone https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
./install-universal.sh --profile lean --agent all --dry-run
./install-universal.sh --profile lean --agent all
agent-token-saver doctor --profile lean
```

The installer copies this repository's manifest, doctor, skill and hooks. It
backs up and merges existing Codex/Claude JSON; it does not replace settings or
silently install third-party packages. `--agent auto` touches only detected
agents. `--agent repo --project /path/to/repo` installs a portable
`.agents/skills` copy.

Integration is capability-based:

- **Codex:** `UserPromptSubmit` routing plus skill/CLI guidance. Current
  `unified_exec` paths are not all intercepted by `PreToolUse`.
- **Claude Code:** native `rtk hook claude` for `PreToolUse` plus
  `UserPromptSubmit` routing.
- **Hermes:** `~/.hermes/skills/agent-token-saver/SKILL.md`.
- **GG Coder:** `~/.gg/skills/agent-token-saver.md`; GG Coder 5.15.1 has no equivalent public hook CLI.
- **Any repo agent:** `.agents/skills/agent-token-saver/SKILL.md` plus the CLI.

Hooks fail open and never change approval policy. Prompt routing skips trivial
prompts, loads at most three skills, and emits nothing when the companion router
is absent. Codex uses agent-guided RTK CLI calls until its shell hook coverage is
complete; the installer does not pretend Claude hook parity.

Use `agent-token-saver doctor --profile <name> --json` for machine-readable
inventory. `healthy=true` means the portable core is usable;
`profile_complete=true` means every selected optional optimizer is also present.

## Verified agent smokes

Same prompt, one turn, no tool calls, 2026-07-13:

| Agent | Version | Result | Provider-reported usage |
|---|---:|:---:|---:|
| Codex CLI | 0.144.2 | PASS | 16,747 input (8,960 cached), 101 output |
| Claude Code | 2.1.207 | PASS | 2 input + 41,757 cache write + 21,242 cache read, 14 output |
| Hermes Agent | 0.18.2 | PASS | 12,208 input, 26 output |
| GG Coder core | 5.15.1 | PASS | 10,603 input, 8 output |

These are compatibility smokes on one heavily configured machine—not a savings
benchmark and not clean-host baselines. They expose the next optimization
frontier: host instructions, tool schemas and plugin catalogs can cost 10k–60k+
tokens before task payload optimization begins. The component matrix below
measures the task payload separately so those two effects are not mixed.

Exact commands and caveats: [data/benchmarks/agent-cli-smoke-2026-07-13.md](data/benchmarks/agent-cli-smoke-2026-07-13.md).

## Measure the complete token bill

The installed `agent-token-ledger` reconciles provider-reported usage with the
context layers you can see. Whatever the provider reports but your files do not
explain becomes `unattributed_input_tokens` instead of disappearing from the
benchmark.

```bash
codex exec --json --ephemeral "your real task" > run.jsonl

agent-token-ledger \
  --usage run.jsonl \
  --provider codex \
  --component project-rules=AGENTS.md \
  --component active-skill=.agents/skills/agent-token-saver/SKILL.md \
  --format markdown \
  --out token-ledger.md
```

Add exported tool schemas, hook output, task text, retrieved context and history
as more `--component NAME=PATH` arguments. Provider totals stay authoritative;
visible files use the transparent bytes/4 estimate. Cached Codex input is
treated as a subset, while Claude cache-create/cache-read fields are added as
separate input classes.

Full method, limitations and optimization ladder:
[docs/FULL_CONTEXT_MEASUREMENT.md](docs/FULL_CONTEXT_MEASUREMENT.md).

Neutral Codex control result: a trivial no-tool task cost **0.68% more** with
the saver skill because there was nothing large to reduce. The attempted
context-heavy shell arm did not expose a verifiable command event and was
rejected. See the complete negative result:
[data/benchmarks/full-context-codex-neutral-2026-07-13.md](data/benchmarks/full-context-codex-neutral-2026-07-13.md).

## Component routing

| Component | Default posture | Use when |
|---|---|---|
| [RTK](https://github.com/rtk-ai/rtk) | native Claude hook; agent-guided Codex CLI | git diff/log, builds, tests, process/docker output |
| Skill router | automatic, prompt-gated | large skill catalogs |
| Any local memory CLI | optional/on demand | recall before repeated web or file loading |
| Tilth | CLI or one lean MCP | structural code reads with a token budget |
| [context-mode](https://github.com/mksglu/context-mode) | session/on demand | large payload queried or transformed repeatedly |
| Graphify | build once, query on demand | persistent repo/corpus graph and paths |
| CodeGraph | on demand | callers, callees and impact analysis |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | off by default | long prose/code generation after an A/B proves gain |
| Headroom | optional provider/proxy, never MCP | keep when the agent connection depends on it; exclude from Lean stack claims and measure separately |
| Superweb-compatible fetch CLI | on demand | current web/search/fetch; save raw responses outside prompt context |

Exact source, version, activation and profile metadata live in [stack/catalog.json](stack/catalog.json). Latest versions and popularity drift; `doctor` reports the installed state, while release decisions belong in dated benchmark/research artifacts.

Synapse is not released and is not a dependency of this repository. The public
stack exposes replaceable CLI/file/JSON seams so a memory system can be added
without changing the core.

Agent-specific hook evidence: [docs/HOOKS_AND_AGENTS.md](docs/HOOKS_AND_AGENTS.md).
Benchmark contributions: [CONTRIBUTING.md](CONTRIBUTING.md).
Security boundary: [SECURITY.md](SECURITY.md).

## Token-efficient news and scraping

Do not give every subagent the same raw scrape.

```text
fetch once -> content-addressed cache -> normalize -> canonical URL dedupe
-> trust/relevance score -> bounded evidence packet -> parallel specialists
-> one final synthesis -> memory/artifact writeback
```

Project raw JSONL into a small evidence packet:

```bash
python3 scripts/news_projection.py raw-news.jsonl \
  --keywords "Fed,ECB,earnings,tariff,oil,gold" \
  --top 40 --format jsonl > evidence.jsonl
```

Required JSONL fields are flexible: `url`, `title`, `text`/`summary`, `source`, `published_at`; unknown fields are ignored. Output is deduplicated, ranked and bounded. Full operating pattern: [docs/NEWS_PIPELINE.md](docs/NEWS_PIPELINE.md).

Subagent rule:

- One deterministic intake pass.
- Specialists receive only source deltas relevant to their lane.
- Maximum three parallel specialists unless a machine oracle justifies more.
- Final synthesizer receives evidence packets, never raw HTML.

## Benchmark details

Measured component reductions:

| Component | Raw | Optimized | Saved |
|---|---:|---:|---:|
| Skill catalog -> router | 37,108 | 226 | 99.39% |
| process output -> RTK | 44,711 | 1,158 | 97.41% |
| README -> Tilth budget | 3,414 | 734 | 78.50% |
| 20k-line log -> native projection | 300,474 | 185 | 99.94% |
| same log -> context-mode | 300,474 | 261 | 99.91% |

Fixed cold overhead in that run:

- Tilth MCP: 6 tools / 1,836 schema tokens.
- context-mode MCP: 11 tools / 7,458 schema tokens.
- Ponytail skill: 1,299 input tokens for 20 average output tokens saved.
- Headroom: optional provider/proxy, excluded from Lean profile totals and never loaded as an MCP.

Run checks:

```bash
uv run pytest
uv run ruff check scripts/install_agent_token_saver.py scripts/stack_doctor.py \
  scripts/full_context_ledger.py scripts/news_projection.py \
  scripts/token_stack_matrix_benchmark.py tests/test_installer.py \
  tests/test_stack_doctor.py tests/test_full_context_ledger.py
bash scripts/neutral_install_smoke.sh
```

## What this repository does not claim

- Token proxies are not provider billing meters.
- A component's best-case reduction is not the whole session reduction.
- The 146.1x payload result is not a clean-host or provider-billing multiplier.
- Popularity is not proof of savings.
- “Installed” is not “active”; verify hooks, MCP startup and real usage.
- Optional local models can add latency and storage while saving almost nothing after deterministic filtering.

## Why GitHub users may care

- **Copy one profile, not one person's dotfiles.** Paths and secrets stay local.
- **See the trade-off before installing.** Every heavy layer shows its fixed schema/input cost.
- **Bring your own agent.** The core is CLI, JSON, JSONL and hooks—not a proprietary runtime.
- **Prove improvement.** Benchmarks include an acceptance oracle, latency and raw artifacts.

If a new saver beats a profile on the same accepted workload, add it to the matrix. If it only has a percentage in a README, keep it out of the default.

That makes this repository useful as a living benchmark, not another “awesome list”.

## Migration from claude-token-saver

GitHub redirects the former repository name. Existing `cts` entrypoints remain compatible; new docs and tooling use `agent-token-saver` / `ats`. Re-run the universal installer to merge current hooks without deleting existing settings.

License: MIT.
