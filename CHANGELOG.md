# Changelog

## 3.0.1 — 2026-07-13

- Add a fresh-HOME neutral Ubuntu install gate to CI.
- Separate portable `core-ready` health from optional `full` profile coverage.
- Add `agent-token-ledger` for provider totals, cache classes, visible context
  attribution and explicit unattributed host overhead.
- Clarify that 146.1x is a dated accepted-payload result, not an automatic
  clean-host billing multiplier.
- Publish the clean-Codex full-context backfire: +0.68% on trivial work, with
  the unverified shell-rewrite arm rejected.
- Use RTK's native Claude hook and remove the unsupported transparent Codex
  rewrite claim; Codex remains skill/CLI-guided.

## 3.0.0 — 2026-07-13

- Rename the universal stack from `claude-token-saver` to `agent-token-saver`.
- Replace synthetic top-line claims with the reproducible stack matrix.
- Add minimal, lean, heavy and news profiles plus a read-only doctor.
- Add one idempotent installer for Codex, Claude Code, Hermes, GG Coder and repo-local agents.
- Add safe Codex/Claude hook merging, portable agent skills, a compact prompt router and RTK rewrite hook.
- Add deterministic news projection and the bounded subagent operating pattern.
- Add live four-agent compatibility smokes and separate host overhead from workload savings.
- Keep unreleased Synapse outside the public dependency graph; expose an optional memory CLI seam.
- Add CI, security/contribution policy, issue templates and a 1280×640 release visual.
- Keep Headroom as an optional provider/proxy, outside Lean profiles and never as MCP.
- Keep `cts` as a compatibility entrypoint; add `ats`.

## 2.x historical notes

- Integrated the full local stack (2026-07-12): wired `hooks/pretooluse_backfire.py` into `~/.claude/settings.json` (advisory, ~41ms, never blocks); updated `~/.claude/cts-env.sh` to installed non-blacklisted models (gate `smollm2:1.7b-8k`, deep `granite4.1:3b`, mid `granite4:1b`) and sourced it from `~/.zshrc`; ran `context-mode upgrade` (all hook checks PASS).
- `cts doctor` accuracy fixes: plugin-shipped hooks (`hooks/hooks.json`) now count as wired (PreCompact via context-mode), caveman detected as marketplace plugin, new Headroom proxy liveness check, dropped `PostCompact` (not a Claude Code event — recovery fires as SessionStart `compact`) in favor of `SessionEnd`. Result: ok 7→10, warn 5→2, crit 0.
- Wired Headroom end-to-end (2026-07-12): persistent proxy on 127.0.0.1:8787 via `headroom install apply --preset persistent-service`, Claude Code + Codex routed via `headroom init -g`; `headroom doctor` green. README got a Quick Start step 5 with the exact commands, the first-start ONNX gotcha, and the undo path.
- Honest-framing pass on `docs/TOKEN_SAVER_STACK_2026.md`: benchmark numbers labeled as chars/4 payload estimates, target values downgraded to start heuristics, accuracy-drop assumptions replaced with measure-first rules.
- Committed research artifacts: `docs/TOKEN_SAVER_RESEARCH_2026-07-09.md`, headroom Codex audit + YouTube token-saver analysis JSONs.
- Added `docs/TOKEN_SAVER_STACK_2026.md` with the current SuperSynergy token-saver stack: top-50 context/token-saving tools and methods, wiring defaults, benchmark evidence, universal cost formula, and rollout gates.
- Captured current research artifacts under `data/research/token-saver-2026-07-09/` using local KB, `ghmax`, `superweb mega`, and local tool doctors.
- Documented local verification: Skill Router 99.46% estimated token reduction on 416 scanned skills; `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest` passing 14 tests; Headroom installed but not routed; context-mode storage/server healthy but Codex hooks missing.
- Added `scripts/token_saver_benchmark.py` plus `data/benchmarks/token-saver-local-2026-07-09.{json,md}` for local no-provider benchmarks of RTK, Tilth, context-mode, hyperfetch threshold behavior, MCP schema slimming, and Headroom profile rendering.
- Updated `README.md` to point at the July 2026 token-saver matrix and current local benchmark results.
- Clarified Superweb default: available on demand via CLI (`search`, `research`, `mega`, `fetch`), not disabled and not loaded as default MCP context.

Verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest
python3 $HOME/BASE/projects/agent-token-saver-skill-router/scripts/agent_token_saver.py bench "deep hermes token saver stack top50 context optimization"
headroom doctor
context-mode doctor
ghmax --doctor
superweb doctor
ruff check scripts/token_saver_benchmark.py
python3 -m pytest -q
python3 scripts/token_saver_benchmark.py
```
