# agent-token-saver

![agent-token-saver — less noise, better judgment](docs/assets/social-preview.svg)

**Your coding agent burns most of its tokens on junk it never asked for.
This strips the junk before the model sees it.**

[![MIT](https://img.shields.io/badge/license-MIT-1c7c54.svg)](LICENSE)
[![CI](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml/badge.svg)](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml)
![Agents](https://img.shields.io/badge/agents-Codex%20%7C%20Claude%20%7C%20Hermes%20%7C%20GG%20Coder-5b5bd6)
![Measured](https://img.shields.io/badge/evidence-fixture%20%2B%20provider%20A%2FB-1c7c54)

Works with Codex CLI, Claude Code, Hermes and GG Coder. Requires Python 3.11+
and `git`; the core is standard library only. No daemon, no build step.
Uninstall is deleting the installed files.

**Measured:** a real Codex A/B on identical tasks used **19.67% fewer**
provider-reported tokens. [Benchmarks →](#benchmarks)

## Try it in 60 seconds

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver/main/install-universal.sh \
  | bash -s -- --profile lean --agent auto --dry-run
```

`--dry-run` only prints what it would change; nothing is installed yet.
Liked what you saw? Run the same line again without `--dry-run`, then check
the wiring:

```bash
agent-token-saver doctor --profile lean --json
```

Prefer reviewing the code first?

```bash
git clone https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
./install-universal.sh --profile lean --agent auto --dry-run
./install-universal.sh --profile lean --agent auto
```

`--agent auto` configures the supported hosts it finds. Use `--agent all` only
when you intentionally want every host integration. The installer copies and
hashes its own files, merges existing Codex and Claude hook JSON, and creates
backups. It leaves host configs and optional packages alone.

## What it removes

Without routing, one task can accidentally load hundreds of skill
descriptions, a full source file for one symbol, a 20,000-line log for one
error count, and the same tool catalog again for every worker.

With `agent-token-saver`, the normal path is:

```text
exact local evidence
  → deterministic compact projection
  → zero or one routed skill
  → bounded structural read
  → broader tools only when the task earns them
```

The model still gets the decisive lines. It carries less baggage. Your agent,
its approval rules and its quality gates stay exactly as they are.

## Why people use it

| USP | What it means in practice |
|---|---|
| **Automatic, but reversible** | Lean prompt and Stop hooks reduce routine waste; hooks are fail-open and preserve host control. |
| **Measured honestly** | Fixture estimates, provider counters and team projections are labeled separately. Failed task oracles invalidate a saving. |
| **Works across agents** | One portable core supports Codex CLI, Claude Code, Hermes, GG Coder and generic CLI/JSON hosts. |
| **Low fixed overhead** | CLI-first routing avoids loading a broad MCP schema to discover one useful tool. |
| **Team-aware** | Workers receive small task capsules instead of the full parent transcript; one controller keeps the final decision. |
| **Safe to adopt** | Dry-run, file hashes, merged hook JSON and backups. Optional third-party tools are detected, never silently installed. |

## What happens after installation

1. **Route:** the prompt gate selects compact policy only when the task matches.
2. **Project:** noisy deterministic output becomes a small evidence view.
3. **Load:** the agent gets zero or one relevant skill, then only the code or
   logs needed for the decision.
4. **Guard:** the Stop hook checks measured session budgets and requests a
   checkpoint when needed. It never auto-continues or blocks the session.

## Benchmarks

Provider counters are authoritative; local payload numbers are transparent
`bytes / 4` estimates and say so.

### Real Codex provider A/B

Fresh home directory per run, same model, task and fixture; baseline disabled
the hooks:

| Task | Baseline total | Lean total | Change |
|---|---:|---:|---:|
| Process table | 29,359 | 38,800 | **32.16% more** |
| Large Git diff | 44,629 | 25,886 | **42.00% less** |
| Git history | 38,500 | 25,678 | **33.30% less** |
| **Aggregate** | **112,488** | **90,364** | **19.67% less** |

All three task oracles passed. One task got worse, which is why this README
avoids universal-savings claims. One run per arm; repeat ABBA runs before
changing organization-wide defaults.
Artifact: [Codex provider A/B](data/benchmarks/codex-provider-ab-2026-07-15/compact-policy/result.md).

### Three repeated runs: what survives the noise

Three `gpt-5.6-terra` runs on 2026-08-22 (same harness, all oracles passed in
every run) showed that a single A/B cannot settle this question. Identical
baseline runs varied by up to 2.2x on the same task — uncached input on the
git-diff task came out 8,049, then 18,009, then 8,020. Any single-run headline
number, including the 2026-07-15 one above, sits inside that noise.

Two things survived all three runs.

**Raw token counts misprice a cached prefix.** Lean moves work out of fresh
input and into cache hits, which a provider bills at a fraction of the rate.
Summing tokens unweighted therefore reports a regression where the invoice
shows a saving:

| Run | Raw token change | At list ratios (cached 10%, output 8x) |
|---|---:|---:|
| 1 | +11.4% | −18.8% |
| 2 | +0.9% | −20.1% |
| 3 | −4.4% | −7.8% |

The weighted column is negative in all three runs (mean −15.6%); the raw
column straddles zero (mean +2.6%). These are public list ratios, not an
invoice.

**Lean is far more predictable than the baseline.** Across runs, uncached
input on the two noisy tasks barely moved under the compact policy while the
baseline swung wildly:

| Task | Lean spread | Baseline spread |
|---|---:|---:|
| process-table | 100 | 7,159 |
| large-git-diff | 466 | 9,989 |
| git-history | 203 | 40 |

The lean figures even span two different policy wordings, which is part of the
point: bounding noisy output early makes the run reproducible, and a
reproducible context is what keeps a long session inside its budget.

Artifacts: [run 1](data/benchmarks/codex-provider-ab-2026-08-22-terra/result.md),
[run 2](data/benchmarks/codex-provider-ab-2026-08-22-terra-v2/result.md),
[run 3](data/benchmarks/codex-provider-ab-2026-08-22-terra-v3/result.md).

### Fixed payload fixture

The accepted local fixture drops from 375,673 to
1,887 estimated visible-input units (99.50% less) on the CLI-selective path;
the automatic Lean path lands at 3,782 (98.99% less). Skill routing, log
projection and bounded reads carry most of it.
Artifact and method: [token-stack-matrix-2026-07-15.md](data/benchmarks/token-stack-matrix-2026-07-15.md).

### Bounded worker packets

One controller, compact capsules, independent lanes, one machine-checkable
oracle:

![Raw context compressed into bounded agent capsules and one verified result](docs/assets/agentmaster-swarm-flow.png)

The three-worker fixture avoids 86.1% of the naive packet (3,800 → 530
estimated visible-input units); capsule deduplication removes another 43.1%.
Artifacts: [swarm control](data/benchmarks/swarm-control-2026-07-27.md),
[hook hot path](data/benchmarks/hook-and-capsule-hotpath-2026-07-27.md).

### Heavier retrieval stays on demand

Tilth answers bounded symbol lookups
in 27 ms at 4 MB RSS, while graph tools like Gmax and Graphify earn their
90-110 MB and multi-second builds only for semantic recall or repeated deep
analysis. Artifacts: [Tilth vs. Gmax](data/benchmarks/tilth-vs-gmax-2026-07-27.md),
[Graphify code-only](data/benchmarks/graphify-code-only-2026-07-27.md).

## Choose a profile

Start with `lean`. Change profiles only for a concrete need.

| Profile | Best for | Visible surface |
|---|---|---|
| `minimal` | portable CLI and ledger | no visible skill or prompt hook |
| `lean` | normal daily coding | compact host default, prompt gate, Stop guard, optional projection CLIs |
| `teams` | independent parallel lanes | Lean plus bounded worker-capsule contract |
| `heavy` | one explicit deep session | Lean plus graph and large-context tools |

## Supported hosts

| Host | Integration |
|---|---|
| Codex CLI | compact global default, prompt gate and Stop guard |
| Claude Code | compact global default, prompt gate, Stop guard, RTK when present, worker capsule |
| Hermes | compact default in an existing `SOUL.md` plus installed Agent Skill |
| GG Coder | compact home `AGENTS.md` default plus installed Markdown skill |
| Other agents | repo-local `SKILL.md` plus CLI/JSON |

The installer merges into existing host files and never creates a new Hermes
`SOUL.md`. Files on disk are not proof of active wiring; the doctor checks
installed paths, hooks and the exact managed default blocks. Details:
[Hooks and agents](docs/HOOKS_AND_AGENTS.md).

### Companion: the skill router

[agent-token-saver-skill-router](https://github.com/Supersynergy/agent-token-saver-skill-router)
is a separate stdlib-only CLI that picks zero or one skill out of a large
local skill catalog. Install it when a host loads many `SKILL.md` files; skip
it otherwise. Neither installer ever installs the other package.

## AgentMaster protocol (optional)

`llmadapter ask-v2` is the strict machine interface for an external
controller: stdin-only prompts, bounded capsules, lane selectors
(`free`/`cheap`/`paid`/`local`/`cli`), health-ordered routing, oracles,
budgets and one schema-fixed JSON result. It requires [Bun](https://bun.sh/)
at runtime and stays optional.

```bash
printf '%s' "$TASK" | llmadapter ask-v2 \
  --stdin --swarm --lanes local --no-cache \
  --usage-out run-accounting.json
```

Full contract, lane table, extensions:
[AgentMaster protocol](docs/AGENTMASTER_PROTOCOL.md).

## Measure your own result

```bash
agent-token-ledger \
  --usage parent=run.jsonl \
  --usage child-review=child.jsonl \
  --provider codex \
  --require-complete-team \
  --require-within-guard \
  --format markdown \
  --out token-ledger.md
```

Keep the model, task, fixture and acceptance oracle fixed for a credible
before/after. Never translate a local payload estimate directly into money
saved.

### Price the cache, don't just count tokens

Raw token sums misprice a cached prefix. Moving fresh input into cache reads
raises the raw input count while lowering the bill, so an unweighted
before/after can call a cheaper run a regression.

```bash
ats-cache usage.json                      # hit rate, split, weighted vs no-cache
ats-cache - --format line < usage.json    # one-line statusline summary
ats-cache lean.json --against base.json   # weighted A/B
```

`ats-cache` is installed on `PATH`, so an agent can call it as a command; the
sourced CLI helper defines the same name as a shell function.

```
cache 90.00% hit | 9,000 read / 0 write / 1,000 fresh | weighted in 1,900 vs 10,000 uncached (81.00% saved)
cache 0.00% hit | 0 read / 19,967 write / 2 fresh | weighted in 24,961 vs 19,969 uncached (-25.00% saved) | write-only
```

The trailing verdict names the failure mode instead of leaving it to the
reader: `write-only` (a prefix written every turn and never read back),
`rewriting` (more written than read), or `uncached`. A healthy run prints no
verdict. The ledger carries the same row.

The ledger reports the same block. Weighted tokens are a list-ratio estimate
against an explicit no-cache counterfactual, never an invoice; provider
counters stay authoritative. Ratios live in `scripts/cache_economics.py`, each
pinned to its published per-MTok price by a test.

The cache only pays while the prefix stays byte-identical: grow context
append-only, keep clocks and session ids out of it, hold tool definitions
stable within a wave, and don't switch model or effort mid-wave.

Two failure modes cost more than they look, both vendor-documented:

- A byte-identical prefix still misses once the breakpoint drifts past the
  [lookback window](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
  (20 blocks on Anthropic), so a burst of large turns silently pays a full
  re-write. Add a breakpoint at the end of the static prefix, or keep per-turn
  growth small.
- Loading a tool or skill catalog mid-session, and compaction itself, invalidate
  the prefix [from the first changed token onward](https://developers.openai.com/api/docs/guides/prompt-caching).
  Lazy-loading definitions to save their tokens can therefore cost a whole
  cached prefix; price the re-write before calling it a saving.

## Verify the checkout

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check scripts integration tests
bash scripts/neutral_install_smoke.sh
agent-token-saver doctor --profile teams --json
```

`core-ready` means the portable core works while an optional tool is missing.
`full` means every tool required by the selected profile is detected.

## Safety and honest limits

- Hooks are fail-open and preserve host approval, sandbox and Stop ownership.
- The installer merges recognized config sections and creates backups.
- Optional tools remain optional; no always-on broad tool catalog.
- Savings depend on workload. Quality gates come before token counts.
- One controller owns scope and the final answer. Default team cap: three
  independent workers with 300–700-token task capsules.

## Documentation

- [Tooling and wiring](docs/TOOLING_AND_WIRING.md)
- [Hooks and agents](docs/HOOKS_AND_AGENTS.md)
- [AgentMaster protocol](docs/AGENTMASTER_PROTOCOL.md)
- [Full measurement method](docs/FULL_CONTEXT_MEASUREMENT.md)
- [Subagent context protocol](docs/SUBAGENT_CONTEXT_PROTOCOL.md)
- [Worker control plane](docs/SWARM_CONTROL_PLANE.md)
- [All benchmark artifacts](data/benchmarks/)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)

License: MIT.
