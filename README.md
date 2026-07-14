# agent-token-saver

![agent-token-saver — less noise, better judgment](docs/assets/social-preview.svg)

**Use your coding agent more. Spend far fewer tokens getting there.**

[![MIT](https://img.shields.io/badge/license-MIT-1c7c54.svg)](LICENSE)
[![CI](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml/badge.svg)](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml)
![verified agents](https://img.shields.io/badge/verified-Codex%20%7C%20Claude%20%7C%20Hermes%20%7C%20GG%20Coder-f2c14e.svg)
![measured](https://img.shields.io/badge/measured-up%20to%20196.4x%20payload%20capacity-e8f1f2.svg)

> **Imagine getting 100x more context-heavy work from Codex, Claude Code,
> Hermes or GG Coder before hitting the same token budget. In the included
> accepted-workload benchmark, you can: 376,626 tokens became 1,918 tokens --
> 99.49% less, or 196.4x more payload capacity.**

`agent-token-saver` stops wasted tokens before they reach your model. It sends
the smallest context that can still produce the correct result: the relevant
skills, the useful error lines, the needed code and the right tools for this
task.

Verified with Codex CLI, Claude Code, Hermes Agent and GG Coder. The repo-local
skill plus CLI/JSON interfaces also work with agents that understand
`SKILL.md` or can run shell commands. No API keys or private configuration are
shipped.

## What this means in plain English

Without routing, a coding agent may receive 460 skill descriptions, a complete
process table, a full README and a 20,000-line log before it starts solving the
task. Most of those tokens never help the answer.

With `agent-token-saver`, the same accepted workload used:

- **1,918 instead of 376,626 tokens** in the CLI-selective profile.
- **3,734 instead of 376,626 tokens** in the automatic Lean profile.
- **Up to 99.49% fewer tokens** across the measured workload.
- **Up to 196 comparable payloads** inside the token budget previously used by one raw payload.

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

Local benchmark, 2026-07-13. Same accepted workload and deterministic fixtures in every arm; UTF-8 bytes / 4 for local payloads and provider-reported usage for the reused live output A/B.

This is a **profile payload benchmark**, not a claim that a brand-new host will
immediately reduce its complete provider bill by 196.4x. The full profile used
the named Router, RTK and Tilth components. Clean-host portability and complete
provider context are measured separately below.

| Stack | Tokens per workload | Tokens saved | Payload capacity in the same raw budget |
|---|---:|---:|---:|
| **CLI selective** | **1,918** | **99.49%** | **196.4x** |
| Lean automatic | 3,734 | 99.01% | 100.9x |
| Context-mode on demand | 9,452 | 97.49% | 39.8x |
| Everything + Ponytail | 12,567 | 96.66% | 30.0x |
| No saver | 376,626 | 0% | 1.0x |

### What "100x more usage" actually means

Take the token budget consumed by one raw benchmark workload: **376,626
tokens**.

- Raw approach: that budget carries **1** comparable workload.
- CLI-selective profile: that budget carries **196 full comparable payloads**.
- Automatic Lean profile: that budget carries **100 full comparable payloads**.
- Across 100 comparable workloads: **37,662,600 raw tokens vs 191,800 CLI-selective tokens**.

The multiplier is `raw tokens / optimized tokens`. It measures useful payload
capacity, not a promise of 196x more provider calls: subscription rate limits,
cache accounting, model output, tool calls and task mix still matter. If tokens
or quota are your bottleneck and your workload resembles this one, however,
the practical gain can be enormous.

### Where the tokens disappear

| Instead of sending this | The agent receives this | Measured reduction |
|---|---|---:|
| All 460 installed skills | One primary skill pointer | 99.74% |
| Full noisy process fixture | RTK's useful projection | 97.25% |
| Full source file | A bounded structural read | 88.98% |
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
| `minimal` | Zero-hot portable CLI/ledger | no visible skill and no prompt hook |
| `lean` | Daily prompt-gated coding | hidden skill + zero-output gate; host-native RTK where supported |
| `heavy` | large logs and deep code graph | lean + context-mode/Graphify/CodeGraph only for that session |
| `news` | scrape/research fan-out | lean + cached fetch + dedupe/rank/project + bounded subagents |

Rules:

- RTK compresses noisy shell output. It does not clean HTML or replace a fetcher.
- Exact local projection beats a sandbox MCP for one deterministic extraction.
- Context-mode wins on repeated questions over large logs, JSON, DOM or API payloads; keep its schema on demand.
- Graphify wins when a repo/corpus is queried repeatedly and structural paths matter; do not build it for one exact lookup.
- Ponytail/caveman shape output. Their instruction tokens can cost more than they save on short answers.
- MCP schemas are a recurring tax. Default to CLI/file/socket surfaces unless measured otherwise.

## Repository layout

```text
scripts/       installer, doctor, ledger, projections and benchmarks
integration/   one prompt hook and one opt-in heavy Codex launcher
skills/        portable agent-token-saver skill
stack/         profile catalog consumed by the doctor
tests/         current release contracts only
data/          dated, reproducible benchmark evidence
docs/          operating and measurement guides
```

Older adapters, MCP servers, ML routers, Hyperstack prototypes and release
campaign files remain available in Git history, not in the active tree.

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

The installer copies this repository's manifest, doctor, hidden skill and hooks. It
backs up and merges existing Codex/Claude JSON; it does not replace settings or
silently install third-party packages. `--agent auto` touches only detected
agents. `--agent repo --project /path/to/repo` installs a portable
`.agents/skills` copy.

### Portable public core, local host overlay

The public `integration/cli/codex-heavy-context` launcher contains only portable
CodeGraph and context-mode settings. It ships no user paths, app-bundle paths,
browser hashes or private configuration.

The installer always refreshes that portable copy under
`~/.agent-token-saver/bin/`. An existing
`~/.local/bin/codex-heavy-context` is user-owned and remains untouched, so one
machine may add its own `node_repl` or browser settings without leaking them into
the public repository. Without a local override, the installer links the public
portable launcher there.

Integration is capability-based:

- **Codex:** zero-hot hidden skill activated only by `UserPromptSubmit`; current
  `unified_exec` paths are not all intercepted by `PreToolUse`.
- **Claude Code:** native `rtk hook claude` for `PreToolUse` plus
  a zero-output-unless-needed prompt gate.
- **Hermes:** `~/.hermes/skills/agent-token-saver/SKILL.md`.
- **GG Coder:** `~/.gg/skills/agent-token-saver.md`; GG Coder 5.15.1 has no equivalent public hook CLI.
- **Any repo agent:** `.agents/skills/agent-token-saver/SKILL.md` plus the CLI.

Hooks fail open and never change approval policy. Strict automatic routing loads
at most one primary skill and returns nothing for trivial, low-confidence or
ambiguous prompts. Without the companion router, or when it returns no valid
selection, a conservative built-in gate activates only the hidden token-saver
skill for explicit token/context tasks.
Codex uses agent-guided RTK CLI calls until shell-hook coverage is complete.

The companion index stays out of prompt context:

```bash
si route "<task>" --max 1 --strict --json
si find "<capability>" --json
si resolve "<exact-name>" --json
si index --refresh --json   # after skill edits
```

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
  --usage parent=run.jsonl \
  --usage child-review=child.jsonl \
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

Repeated `--usage [NAME=]PATH` inputs are summed, so parent, child, retry and
compaction runs remain in the total. Repeated visible components are fingerprinted
and reported as duplicate-context tax.

Full method, limitations and optimization ladder:
[docs/FULL_CONTEXT_MEASUREMENT.md](docs/FULL_CONTEXT_MEASUREMENT.md).

The original visible saver skill cost **0.68% more** on a trivial warm Codex
turn. The zero-hot layout removes that regression: an ABBA clean-HOME probe now
reports `11,204` baseline versus `11,209` Lean input tokens in both orders
(`+5`, `+0.045%`, identical 8,960 cached and 5 output). `minimal` has no prompt
hook at all. This is a microbenchmark, not a full workload claim. Historical
negative result and current zero-hot evidence:
[data/benchmarks/full-context-codex-neutral-2026-07-13.md](data/benchmarks/full-context-codex-neutral-2026-07-13.md).
[data/benchmarks/zero-hot-codex-neutral-2026-07-13.md](data/benchmarks/zero-hot-codex-neutral-2026-07-13.md).

Accepted Codex tool-output probe, same oracle and verified command events:

- raw `ps aux`: `25,210` input (`5,242` uncached)
- explicit `rtk ps aux`: `23,996` input (`4,028` uncached)
- saving: **1,214 full input tokens / 4.82%**, or **23.16% of uncached input**

Artifact: [data/benchmarks/codex-explicit-rtk-e2e-2026-07-13.md](data/benchmarks/codex-explicit-rtk-e2e-2026-07-13.md).

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
| Superweb-compatible fetch CLI | on demand | current web/search/fetch; save raw responses outside prompt context |

Exact active-profile source and activation metadata live in [stack/catalog.json](stack/catalog.json). Headroom and Ponytail remain dated benchmark comparators, not profile dependencies. Latest versions and popularity drift; `doctor` reports installed state.

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
- Independent workers use no parent transcript; send a 300–700-token task capsule.
- Sum every child in the ledger. Parallel execution saves wall time, not automatically tokens.
- Spawn only when displaced raw context exceeds child bootstrap + capsule + summary.

Exact task packet, break-even rule, memory tiers and parent/child accounting:
[docs/SUBAGENT_CONTEXT_PROTOCOL.md](docs/SUBAGENT_CONTEXT_PROTOCOL.md).

## Benchmark details

Measured component reductions:

| Component | Raw | Optimized | Saved |
|---|---:|---:|---:|
| Skill catalog -> router | 37,157 | 98 | 99.74% |
| process fixture -> RTK | 32,210 | 887 | 97.25% |
| source file -> Tilth budget | 6,785 | 748 | 88.98% |
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
uv run ruff check scripts integration tests
bash -n install-universal.sh integration/cli/codex-heavy-context \
  scripts/neutral_install_smoke.sh scripts/remote_bootstrap_smoke.sh
bash scripts/neutral_install_smoke.sh
```

## What this repository does not claim

- Token proxies are not provider billing meters.
- A component's best-case reduction is not the whole session reduction.
- The 196.4x payload result is not a clean-host or provider-billing multiplier.
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

GitHub redirects the former repository name. Re-run the universal installer to replace retired managed files and merge current hooks without deleting user settings.

License: MIT.
