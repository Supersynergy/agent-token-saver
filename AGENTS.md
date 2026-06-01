<!-- REPO-POLISH-AGENTS:START -->
# AGENTS.md

Claude Token Saver is a TypeScript app/toolkit for practical developer workflows.

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

