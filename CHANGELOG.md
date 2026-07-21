# Changelog

## Unreleased

## 3.3.0 — 2026-07-21

- Benchmark the kimi-worker lane on Kimi K3
  (`data/benchmarks/kimi-k3-lane-2026-07-21`, driven by the new reproducible
  `scripts/kimi_k3_lane_benchmark.py` with `--arm`/`--repeat`/`--dry-run`,
  fixture SHA-256 pinning, run-order recording, K3 list-price estimates and a
  positional-subcount hardened oracle): the K3 three-worker team passes the
  hardened oracle at **73,710 gross input — −82.1%** vs the 2026-07-19 Claude
  team and **−65.3%** vs the CLI's built-in `Agent` swarm on the same model
  (212,310 gross, 2.3x its K2.7 cost), so the lean-lane advantage over the
  built-in swarm grew from −27.2% to −65.3%. Findings: K3's PARL-trained
  Swarm Max is app-only with no documented API/CLI access (the CLI `Agent`
  tool stays the headless comparand); K3 single lane = 24,691 gross (+4.8%
  vs K2.7, output 356 → 227); `--no-thinking` is **not** a win on shallow
  lanes (−4% output but +71% uncached input via prefix change) — hypothesis
  measured and refuted. K2.7 drift since 2026-07-19: +5.8% gross.
- Add `KIMI_WORKER_NO_THINKING=1` to `kimi-worker` (passes `--no-thinking`);
  deliberately not a generic `--config` passthrough — kimi-cli 1.49
  `--config` fully replaces the config file (no merge) and would drop the
  `[models.*]` aliases the wrapper relies on.
- Fix swarm-arm usage accounting in benchmarks: built-in `Agent` subagents
  write their own `wire.jsonl` beside the parent's (kimi-cli 1.49
  `subagents/store.py`), so usage is summed over `sessions/**/wire.jsonl`
  recursively.

- Ship `kimi-worker` (`integration/cli/kimi-worker`, installed to
  `~/.agent-token-saver/bin` + `~/.local/bin`): lean Kimi child with empty
  skills dir, `--quiet` final-message contract, exit-75-only retry, and
  seeded per-worker `KIMI_SHARE_DIR` isolation. System benchmark
  (`data/benchmarks/kimi-worker-system-2026-07-19`): three-worker team =
  67,514 gross input, **−83.6%** vs the same-day Claude team and **−27.2%** /
  3.6x faster vs Kimi 1.49's built-in `Agent` swarm on the same oracle;
  single lane = 22,268 gross (−82.8% vs a single Claude projection child).
  kimi-cli upgraded 1.48.0 → 1.49.0 (lean-lane regression +1.0%, stable;
  rollback `uv tool install kimi-cli==1.48.0`). Skill team guidance now
  routes shell-projection lanes through `kimi-worker`.
- Harden `kimi-worker` to production: contract tests against a stubbed
  `kimi-cli` (retry-75 semantics, share-dir seeding, evidence suffix, lean
  args) and a `KIMI_WORKER_USAGE_OUT` export that feeds
  `agent-token-ledger` one summed usage record per run — ledger totals now
  match the wire log exactly (verified 68,474/1,247 on a repeat team run,
  +1.4% vs the first, oracle PASS).

- Refute the staggered-spawn cache hypothesis with a measured A/B
  (`data/benchmarks/claude-stagger-ab-2026-07-19`): staggered = 411,946 gross
  vs simultaneous = 411,938 on the same three-slice oracle. Children share the
  ~90k prefix via cache read in both arms; the ~47k per-child write is
  child-unique suffix. Protocol now says: fan out simultaneously, cut suffix
  or switch runtime to save.
- Add the Kimi CLI engine lane (`data/benchmarks/kimi-lane-2026-07-19`):
  default child ≈ 63.8k gross per lane, `--skills-dir <empty>` cuts uncached
  input 91% (22.9k → 2.1k, gross 22.0k) — 83% of the Kimi system prompt is
  the user skills index. Moonshot caching is implicit and write-free
  (`input_cache_creation` = 0 everywhere), so simultaneous Kimi fan-out
  carries no cache penalty; a lean three-child Kimi team passed the same
  oracle at 16% of the measured Claude team's gross input.
- Make the log fixture reproducible: `scripts/make_log_fixture.py` (4,000
  lines, 100 `ERROR`, `CRITICAL-MARKER` at 3777, seeded).
- Distill external research into `docs/TOKEN_SAVER_RESEARCH_2026-07-19.md`:
  cache mechanics behind the retired stagger rule, child-effort and hard
  budget-cap levers, Kimi CLI operational facts (`--quiet`, exit 75 =
  retryable, `KIMI_SHARE_DIR` per swarm), and a reported upstream
  cache-counter inflation issue scoping all token claims.

- Add `scripts/headroom_provider_ab.py` and the first accepted Headroom
  provider A/B: routing Codex through the proxy saved `54.44%` provider total
  (`45,206` vs `20,598`) on the `large-git-diff` oracle, proxy arm run first
  (bias against Headroom). Per-arm `agent-token-ledger` entries and ADR
  `2026-07-18-headroom-proxy-provider-ab` record the numbers; Headroom stays
  optional pending an ABBA repeat and a low-tool-output task.
- Record the first Claude parent-plus-children A/B (projection worker vs
  three-worker team vs raw full-read child) with cache classes and oracle
  results: team = 3.0x a single worker, raw read = 14.2x and wrong.
- Document host-specific child bootstrap (~44k Claude vs ~11k Codex), staggered
  spawn for shared-prefix cache reuse, and model-tier rules (cheap workers,
  expensive controller/verifier, no self-grading) in the subagent protocol.
- Probe four engine lanes on the same fixture and oracle (free-tier capsule
  verifier, sandboxed Codex worker, council-driven executor, local free CLI)
  and record the cheapest viable team structure as an ADR.
- Link every operating guide from the README layout section.

- Add `agent-token-audit`, an isolated fail-closed comparison gate for pinned
  Splitrail, Tokscale, CodeBurn and normalized aiusage exports.
- Add lossless `agent-token-ledger --format json-compact` and publish the dated
  audit/MCP/cache/ACP combination matrix without adding a hot runtime layer.

## 3.2.0 — 2026-07-15

- Prefer cumulative Codex `total_token_usage`, reject duplicate usage sources
  and fail closed when spawned-worker ledgers are missing.
- Add configurable context-rot thresholds plus a fail-open Stop hook that
  warns without automatically continuing or blocking the user's STOP.
- Pin token-saver routing to an owner-controlled canonical skill; validate
  roots, ownership, modes, frontmatter names and symlink containment.
- Add a hashed install manifest and an end-to-end doctor that detects stale
  skills, altered managed assets and broken prompt/guard hook wiring.
- Rename local bytes/4 benchmark fields to payload estimates and separate them
  from provider usage, quota and monetary-cost claims.
- Replace the automatic full-skill read after a valid -29.24% provider
  regression; the compact policy's three-task Codex probe passes every oracle
  and saves 19.67% aggregate provider total, while explicitly rejecting a 99%
  end-to-end claim.

## 3.1.5 — 2026-07-14

- Add the `teams` profile: the Lean runtime plus an explicit bounded
  controller/worker protocol, not another daemon or always-hot tool schema.
- Position `agent-token-saver-skill-router` as a separate optional skill/CLI;
  the installer detects an existing router but never installs third-party code.
- Remove Superweb and private/unreleased host-tool references from the active
  public catalog and CLI-first guidance. Existing `news` config maps to
  `teams` in the read-only doctor for a non-breaking upgrade.
- Document capsule, oracle, accounting and three-worker limits for cheap agent
  teams.

## 3.1.4 — 2026-07-14

- Point the Router companion guidance at current releases, including v1.2.2's
  zero-skill behavior for plain test verification.

## 3.1.3 — 2026-07-14

- Add a dedicated Router companion section with install, index and strict-route
  commands, plus a stated zero-hot integration boundary.
- State the project's measurable commitment and the remaining fresh-host,
  parent-plus-children and native-Codex-hook proof obligations.
- Cross-link router v1.2.1, which keeps context-mode explicit-only for
  automatic routing so ordinary verification tasks do not load its handbook.

## 3.1.2 — 2026-07-14

- Preserve unrelated Claude Code `UserPromptSubmit` hooks when a managed
  token-saver hook shares their entry; repeated installs remain idempotent.
- Add router metadata for noisy output compression, CLI benchmarks and bounded
  subagent work so strict `si` routing selects the token-saver skill when it
  is the best match.
- Removed retired adaptive-model, MCP, Hyperstack, Rust, local-ML and legacy installer trees from the active checkout.
- Removed the unused Anthropic runtime dependency and obsolete `cts`/`ats` package entrypoints.
- Kept one canonical v3 installer/runtime surface and pruned its retired managed RTK rewrite file on upgrade.
- Made Minimal doctor inventory truly zero-hot and added direct `si` launcher discovery for 0/1 routing.
- Prefer the canonical `si` launcher over its legacy alias and preserve user-owned host-specific Heavy launchers.
- Keep the public Heavy launcher portable: no local app paths, browser hashes or private host configuration.
- Consolidated release notes, research dumps and generated visuals into current docs plus dated benchmark evidence.
- Replaced the volatile live process-table matrix arm with a deterministic 900-row fixture through the real RTK CLI.
- Pinned Ruff to 0.14.14 (released 2026-01-22) instead of the four-day-old lock version.

## 3.1.1 — 2026-07-14

- Restore the hidden token-saver fallback when an installed companion router
  returns no valid primary selection for an explicit token/context task.
- Add a regression test for the empty-router fallback; trivial and ordinary
  prompts remain silent unless the router selects one primary skill.

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
