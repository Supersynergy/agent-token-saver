# Changelog

## Unreleased

- Removed retired adaptive-model, MCP, Hyperstack, Rust, local-ML and legacy installer trees from the active checkout.
- Removed the unused Anthropic runtime dependency and obsolete `cts`/`ats` package entrypoints.
- Kept one canonical v3 installer/runtime surface and pruned its retired managed RTK rewrite file on upgrade.
- Made Minimal doctor inventory truly zero-hot and added direct `si` launcher discovery for 0/1 routing.
- Prefer the canonical `si` launcher over its legacy alias and preserve user-owned host-specific Heavy launchers.
- Keep the public Heavy launcher portable: no local app paths, browser hashes or private host configuration.
- Consolidated release notes, research dumps and generated visuals into current docs plus dated benchmark evidence.
- Replaced the volatile live process-table matrix arm with a deterministic 900-row fixture through the real RTK CLI.
- Pinned Ruff to 0.14.14 (released 2026-01-22) instead of the four-day-old lock version.

## 3.1.0 — 2026-07-13

- Removed visible Codex/Claude saver skills from Lean installs; the on-demand skill now lives outside native catalogs.
- Strict automatic routing now emits zero on trivial/ambiguous prompts and loads at most one primary skill.
- Added a conservative token-task fallback when the companion router is absent.
- Added real clean-CODEX_HOME ABBA evidence: `11,204` baseline vs `11,209` Lean input (`+0.045%`).
- Added accepted Codex explicit-RTK E2E evidence: `25,210` raw vs `23,996` input (`-4.82%`).
- Extended `agent-token-ledger` across parent/child usage files and duplicate-context fingerprints.
- Added Minimal zero-hot installation semantics and prompt-hook regression tests.

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

The retired adaptive-model, MCP, Hyperstack, Rust and local-ML generations are preserved in Git history. They are not part of the v3 runtime or dependency graph.
