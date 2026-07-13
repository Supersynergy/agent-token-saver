<!-- REPO-POLISH-AGENTS:START -->
# AGENTS.md

Agent Token Saver is an agent-neutral toolkit for measured context reduction, safe hook wiring, and bounded research/news projection.

## Commands

- `build`: `bun run build`
- `setup`: `bun install`
- `test`: `uv run pytest`
- `check`: `uv run pytest`

## Repo Rules

- Optimize for Time-to-First-Success: keep setup and verification commands obvious.
- Keep changes scoped to the domain being edited; avoid catch-all `utils`, `helpers`, and `misc` buckets.
- Preserve existing user changes in this repository. Do not run destructive git commands.
- Add or update tests when behavior changes.
- Put durable architecture rationale in `docs/adr/`.
<!-- REPO-POLISH-AGENTS:END -->
