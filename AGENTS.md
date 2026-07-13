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
<!-- REPO-POLISH-AGENTS:END -->
