<!-- REPO-POLISH-AGENTS:START -->
# AGENTS.md

Agent Token Saver is an agent-neutral toolkit for measured context reduction, safe hook wiring, and bounded research/news projection.

## Commands

- `setup`: `uv sync --extra dev`
- `test`: `uv run pytest`
- `lint`: `uv run ruff check scripts integration tests`
- `smoke`: `bash scripts/neutral_install_smoke.sh`

## Repo Rules

- Optimize for Time-to-First-Success: keep setup and verification commands obvious.
- Keep changes scoped to the domain being edited; avoid catch-all `utils`, `helpers`, and `misc` buckets.
- Preserve existing user changes in this repository. Do not run destructive git commands.
- Add or update tests when behavior changes.
- Put durable architecture rationale in `docs/adr/`.

## Recon CLIs (v3.8.0+)

Three fail-open recon tools are wrapped as `ats-*` helpers in
`integration/cli/agent-token-saver.sh` and exposed via `ats-doctor`:

- `ats-gmax "<question>"` — semantic search over indexed local codebases
  (replaces Cascade `code_search` for indexed projects). Index once:
  `gmax add /path/to/project`. Query: `gmax "<q>" --agent`.
- `ats-ghx explore|read|inspect|search <owner/repo>` — GitHub reconnaissance
  sidecar. `--map` output ~92% token reduction. Uses `gh` CLI auth, no extra
  API key.
- `ats-supacrawl scrape|map|crawl|batch <url>` — HTTP-first web scraper,
  markdown output. No API key. Complements heavier research tooling for
  quick single-page pulls.

All fail-open: missing CLI → passthrough, never error. MCP deliberately not
used — CLIs keep agent context clean. `ats-recon-doctor` shows install state.

## stdio LLM bridge + auto-router (v3.8.1+)

- `ats-llm-pipe` — Python bridge at `integration/cli/ats-llm-pipe`. Reads
  OpenAI-style messages JSON from stdin, routes to the first available CLI
  LLM (codex, kimi, claude, llm). Enables supacrawl LLM extraction without
  Ollama or API keys. Symlink into `~/.local/bin/` to use.
- `ats-supacrawl-extract <url> "<prompt>"` — scrape + LLM extraction in one
  call via the stdio bridge. Config: `SUPACRAWL_LLM_PROVIDER=stdio`,
  `SUPACRAWL_LLM_STDIO_CMD=ats-llm-pipe`.
- `ats-recon "<query>"` — auto-routing pipeline. URL → supacrawl scrape
  (or `--extract`); `owner/repo` → ghx explore (or inspect if question
  contains "where"/"how"); else → gmax semantic search. Fail-open.
- `ats-recon-doctor` — now checks `ats-llm-pipe` and stdio LLM CLIs.

## Benchmarks (v3.8.1+)

- `integration/cli/ats-recon-bench.py` — gmax vs grep, ghx vs `gh api`,
  supacrawl vs curl, stdio extraction. JSON + Markdown output.
- `integration/cli/ats-swarm-bench.py` — stdio bridge across agent CLIs
  (codex, hermes+kimi/luna/terra).
- `integration/cli/ats-jury-bench.py` — jury of agents answers questions
  via baseline vs ats-recon. Token savings per probe.

Benchmark results (2026-07-23, 1 iter, 4 agents): local_search 82% saved,
github_recon 99% saved, web_scrape 59% saved.
<!-- REPO-POLISH-AGENTS:END -->
