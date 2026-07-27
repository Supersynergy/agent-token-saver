# agent-token-saver

Measured context reduction for coding agents. Keep decisive evidence; remove
repeated catalogs, noisy output and unneeded tool surface before model context.

[![MIT](https://img.shields.io/badge/license-MIT-1c7c54.svg)](LICENSE)
[![CI](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml/badge.svg)](https://github.com/Supersynergy/agent-token-saver/actions/workflows/ci.yml)

The included fixture reduced estimated visible input from 375,673 to 1,887
units. That is fixture payload capacity, not a provider-billing promise. Use a
provider ledger and an accepted A/B for any cost claim.

## Quick start

Inspect before installing:

```bash
git clone https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
./install-universal.sh --profile lean --agent all --dry-run
./install-universal.sh --profile lean --agent all
agent-token-saver doctor --profile lean --json
```

Or use the reviewed installer:

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver/main/install-universal.sh \
  | bash -s -- --profile lean --agent auto
```

The installer copies and hashes its own files, merges existing Codex/Claude
hook JSON and backs it up. It detects optional tools but never silently installs
third-party packages.

## What is automatic

- Prompt gate: compact policy only when the task matches; full skill is
  explicit via `$agent-token-saver`.
- Stop guard: validates the transcript path and asks for a checkpoint when a
  measured budget is exceeded. It never continues or blocks a session.
- Claude `teams`: adds a worker-capsule contract. It does not auto-spawn a
  team.
- Routing: zero or one skill. Exact local search and deterministic projection
  stay ahead of broad tools.

## Profiles

| Profile | Use | Surface |
|---|---|---|
| `minimal` | portable CLI/ledger | no visible skill or prompt hook |
| `lean` | daily coding | prompt gate and Stop guard; optional projection CLIs |
| `teams` | independent lanes | Lean plus bounded worker contract |
| `heavy` | one deep session | Lean plus explicit graph/large-context tools |

## Host support

| Host | Integration |
|---|---|
| Codex CLI | prompt gate and Stop guard |
| Claude Code | RTK when present, prompt gate, Stop guard, teams worker capsule |
| Hermes | installed Agent Skill |
| GG Coder | installed Markdown skill |
| Other agents | repo-local `SKILL.md` and CLI/JSON |

See [hooks and agents](docs/HOOKS_AND_AGENTS.md). Files existing on disk are
not proof of active wiring; run the doctor.

## Verify

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check scripts integration tests
bash scripts/neutral_install_smoke.sh
agent-token-saver doctor --profile teams --json
```

`core-ready` means the portable core works and an optional tool is missing.
`full` means every tool in the selected profile is detected. Neither status
claims a provider credential, private lane or browser session works.

## Measure the real bill

Provider counters are authoritative. The ledger combines parent, workers,
retries and fallbacks; visible files use a transparent bytes/4 estimate.

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

Run an accepted before/after workload. Record provider input/output, cache
classes, latency and failures. Do not turn a local payload estimate into money
or quota saved.

## Bounded teams

One controller owns scope and the final decision. Each worker gets one
300–700-token capsule, one machine oracle, zero or one skill and a compact
evidence result. Default: at most three independent workers; no parent
transcript relay. Details: [worker control plane](docs/SWARM_CONTROL_PLANE.md).

## Optional tools

- RTK: project supported noisy shell output.
- Skill router: return zero or one relevant skill path.
- Structural reader: bounded source retrieval.
- Graph, browser and fan-out: explicit session tools, never Lean defaults.
- `ats-recall`, `ats-url-cache`, `llmadapter` and `ats-pipe`: explicit CLI
  features. Remote lanes require the PII shield.

The default rule is simple: exact local evidence → deterministic projection →
one routed skill → bounded structural read. Everything else must earn its cost.

## Safety boundary

- Hooks are fail-open and preserve host approval, sandbox and Stop ownership.
- No maintenance scan belongs in a hook; `synx doctor` is an explicit manual
  operation only.
- Public artifacts contain no private paths, credentials, process IDs or raw
  controller/transcript output.
- Optional tools stay optional. No always-on broad MCP catalog.

## Reference

- [Tooling and wiring](docs/TOOLING_AND_WIRING.md)
- [Full measurement method](docs/FULL_CONTEXT_MEASUREMENT.md)
- [Subagent context protocol](docs/SUBAGENT_CONTEXT_PROTOCOL.md)
- [Benchmark artifacts](data/benchmarks/)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)

License: MIT.
