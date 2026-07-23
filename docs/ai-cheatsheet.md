# agent-token-saver — AI Cheatsheet

**Stack:** Python 3.13 + skill-router + CLI/JSON-Interfaces. 199.1x payload capacity gemessen.
**VCS:** Git + jj (Tier A, AI-Dev 6,5).
**Funcmap:** 273 defs, 377 edges. Hotspots: `write_text` (external_usage_gate.py:418), `run_hook` (test_prompt_hook.py:12), `run_installer` (test_installer.py:13), `build_report` (stack_doctor.py:377), `run` (codex_provider_ab.py:74).

## Commands
- `pytest tests/` — alle Tests
- `pytest -k abba` — nur ABBA-A/B-Tests
- `python -m agent_token_saver.cli audit` — Usage-Audit
- `python -m agent_token_saver.cli route` — Skill-Routing
- `just test` / `just lint` (falls justfile)
- `ruff check .` — Lint
- `mypy .` — Types

## Routing
| Intent | Skill |
|---|---|
| Skill-Routing optimieren | `agent-token-saver-skill-router` + `speedtuning` |
| A/B-Fixture bauen | `superfast` + `verification-loop` |
| Statistik/Signifikanz | `ab-testing` + `superml` |
| Provider-Integration | `ponytail` + `clear-thought` |
| Funcmap-Rebuild | `grepgod funcmap .` |
| Foreign-Review | `metareview` + `three-brain` (Codex) |

## superfast-Oracle-Beispiele
- `pytest tests/test_abba.py -k claude` exits 0 mit p<0.05
- `python -m agent_token_saver.cli audit --usage data/benchmarks/` → JSON mit p50/p95
- `ruff check .` exits 0
- `pytest tests/` → alle grün

## Top-Bottleneck (TOC)
`scripts/external_usage_gate.py:418` — 56× `write_text` = I/O-Hotspot, Hauptlatenz-Quelle.

## Open
- Claude ABBA-A/B-Fixture (gegen Codex-Baseline)
- Fresh-Host-A/B für Hermes + GG Coder
