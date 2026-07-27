<!-- REPO-POLISH-AGENTS:START -->
# Agent Token Saver

Portable context reduction. Hooks stay fail-open; optional tools stay optional.

## Commands

- setup: `uv sync --extra dev`
- test: `uv run pytest -q`
- lint: `uv run ruff check scripts integration tests`
- smoke: `bash scripts/neutral_install_smoke.sh`
- live install check: `agent-token-saver doctor --profile teams --json`

## Rules

- Preserve user changes. No destructive Git.
- Smallest change. Tests for behavior. ADR for durable design decisions.
- Public files: no private paths, credentials, PIDs, transcripts or host-only claims.
- Portable core first. Third-party CLIs are detected, never silently installed.
- Hook code receives JSON, returns JSON or nothing, and never changes approval,
  sandbox or stop ownership.
- No maintenance scan in a hook. `synx doctor` is manual-only.
- One controller; workers get one capsule, one oracle, zero or one skill and a
  compact evidence result. Three independent workers maximum by default.

## Product boundary

- `minimal`: CLI/ledger only.
- `lean`: prompt gate, session guard and optional routing/projection CLIs.
- `teams`: Lean plus Claude's worker-capsule hook; no automatic fan-out.
- `heavy`: opt-in graph/large-context tools for one session.

Codex and Claude use merged JSON hooks. Hermes and GG Coder use installed
skills. Verify active configuration with the doctor; files on disk are not proof.

## References

- [README](README.md): install and user-facing contract.
- [hooks](docs/HOOKS_AND_AGENTS.md): host matrix.
- [tooling](docs/TOOLING_AND_WIRING.md): default versus optional layers.
- [measurement](docs/FULL_CONTEXT_MEASUREMENT.md): method and limits.
<!-- REPO-POLISH-AGENTS:END -->
