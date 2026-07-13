# agent-token-saver

![agent-token-saver — less noise, better judgment](docs/assets/social-preview.png)

**Less noise. Better judgment. Measured, not guessed.**

[![MIT](https://img.shields.io/badge/license-MIT-1c7c54.svg)](LICENSE)
![verified agents](https://img.shields.io/badge/verified-Codex%20%7C%20Claude%20%7C%20Hermes%20%7C%20GG%20Coder-f2c14e.svg)
![measured](https://img.shields.io/badge/benchmark-0.73%25%20of%20raw-e8f1f2.svg)

Universal token routing for coding agents. Give the model the smallest decisive context, not another mountain of logs, schemas and duplicate research.

Verified with Codex CLI, Claude Code, Hermes Agent and GG Coder. The repo-local
skill plus CLI/JSON interfaces also work with agents that understand
`SKILL.md` or can run shell commands. No API keys or private configuration are
shipped.

## Why this exists

Most “token optimization” advice asks humans to think about tokens all day. That is backwards.

`agent-token-saver` makes the cheap choice automatic, preserves the evidence needed for a good answer, and keeps heavy tools one command away. You spend less quota. Your agent spends less attention. Neither of you has to work in caveman darkness to get there.

**The result:** one understandable stack, four workload profiles, real A/B measurements, reversible hooks and no lock-in.

## Measured answer

Local benchmark, 2026-07-13. Same accepted workload in every arm; UTF-8 bytes / 4 for local payloads and provider-reported usage for the live output A/B.

| Stack | Total tokens | Index vs no saver |
|---|---:|---:|
| **CLI selective** | **2,768** | **0.73** |
| Lean automatic | 4,476 | 1.18 |
| Context-mode on demand | 10,302 | 2.70 |
| Everything + Ponytail | 13,234 | 3.47 |
| No saver | 380,871 | 100.00 |

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

- **Codex + Claude Code:** native `PreToolUse` and `UserPromptSubmit` hooks.
- **Hermes:** `~/.hermes/skills/agent-token-saver/SKILL.md`.
- **GG Coder:** `~/.gg/skills/agent-token-saver.md`; GG Coder 5.15.1 has no equivalent public hook CLI.
- **Any repo agent:** `.agents/skills/agent-token-saver/SKILL.md` plus the CLI.

Hooks fail open. Shell rewriting asks RTK for a safe rewrite and never changes
approval policy. Prompt routing skips trivial prompts, loads at most three
skills, and emits nothing when the companion router is absent.

Use `agent-token-saver doctor --profile <name> --json` for machine-readable inventory. Missing optional tools remain optional.

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

## Component routing

| Component | Default posture | Use when |
|---|---|---|
| [RTK](https://github.com/rtk-ai/rtk) | automatic for supported noisy commands | git diff/log, builds, tests, process/docker output |
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
| Skill catalog -> router | 37,080 | 226 | 99.39% |
| process output -> RTK | 40,844 | 1,447 | 96.46% |
| README -> Tilth budget | 2,133 | 570 | 73.28% |
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
  scripts/news_projection.py scripts/token_stack_matrix_benchmark.py \
  tests/test_installer.py tests/test_stack_doctor.py tests/test_news_projection.py
bash -n install-universal.sh integration/hooks/rtk-rewrite.sh
```

## What this repository does not claim

- Token proxies are not provider billing meters.
- A component's best-case reduction is not the whole session reduction.
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
