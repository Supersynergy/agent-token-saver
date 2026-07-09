# Changelog

## Unreleased

- Added `docs/TOKEN_SAVER_STACK_2026.md` with the current SuperSynergy token-saver stack: top-50 context/token-saving tools and methods, wiring defaults, benchmark evidence, universal cost formula, and rollout gates.
- Captured current research artifacts under `data/research/token-saver-2026-07-09/` using local KB, `ghmax`, `superweb mega`, and local tool doctors.
- Documented local verification: Skill Router 99.46% estimated token reduction on 416 scanned skills; `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest` passing 14 tests; Headroom installed but not routed; context-mode storage/server healthy but Codex hooks missing.
- Added `scripts/token_saver_benchmark.py` plus `data/benchmarks/token-saver-local-2026-07-09.{json,md}` for local no-provider benchmarks of RTK, Tilth, context-mode, hyperfetch threshold behavior, MCP schema slimming, and Headroom profile rendering.
- Updated `README.md` to point at the July 2026 token-saver matrix and current local benchmark results.

Verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest
python3 /Users/master/BASE/projects/agent-token-saver-skill-router/scripts/agent_token_saver.py bench "deep hermes token saver stack top50 context optimization"
headroom doctor
context-mode doctor
ghmax --doctor
superweb doctor
ruff check scripts/token_saver_benchmark.py
python3 -m pytest -q
python3 scripts/token_saver_benchmark.py
```
