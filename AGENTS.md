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
<!-- REPO-POLISH-AGENTS:END -->
