# Changelog

## Unreleased

## 4.0.0 — 2026-07-24

### Superintelligent Stack — omnigoal compounding + token-cfo + jury-bench v2 + DuckLake archive

This release combines five feature axes into one major version. The public
`ats-*` surface gains three new helpers (`ats-token-cfo`, `ats-goal-archive`,
`ats-metareview --via metareview`) and the goal system gains compounding
writeback to a human-readable canon. The benchmark harness gains ABBA-adaptive
ordering and a blind reviewer score.

- **feat(cli): `ats-token-cfo`** — shell wrapper at
  `integration/cli/ats-token-cfo` that exposes the `token-cfo` Python package
  (routing audit + cost simulation + sales-ready report) as an `ats-*` helper.
  Subcommands pass through: `audit`, `simulate`, `plan`, `report`, `pricing`.
  Fail-open: missing package → warning + return 0. Configurable via
  `ATS_TOKEN_CFO_DIR` (default: `~/BASE/projects/token-cfo`). Sourced
  automatically by `agent-token-saver.sh` alongside `goal.sh`.

- **feat(goal): compounding writeback to `universal-goal-science.md`** —
  `goal-close --decision "<text>"` now appends a dated insight block
  (decision, bottleneck, levers, oracle, summary) to
  `~/BASE/docs/universal-goal-science.md` (configurable via `GOAL_SCIENCE_DOC`).
  This is the human-readable canon companion to the existing `synx put`
  durable-fact writeback. Fail-open: missing dir → skip.

- **feat(cli): `ats-goal-archive <slug> [--all]`** — archives closed goals to
  a DuckLake catalog (default: `~/.synapse/goal-archive.duckdb`). Enables
  time-travel queries over closed goals ("what did we decide on 2026-07-23?").
  Idempotent: re-running on an already-archived slug upserts. Fail-open:
  missing `duckdb` → warning + return 0. Configurable via
  `ATS_GOAL_ARCHIVE_DB` and `ATS_GOAL_ARCHIVE_TABLE`.

- **feat(metareview): `--via metareview`** — `ats-metareview` now supports the
  `metareview` skill as a reviewer backend, in addition to `agentmaster`,
  `grepgod`, `si`, and `manual`. Uses `METAREVIEW_ROOT` (default:
  `~/.claude/skills/metareview`) and invokes `run.sh` if present, else the
  `metareview` CLI. Fail-open: missing skill → falls through to next backend.

- **feat(bench): `ats-jury-bench-v2.py`** — jury of agents with:
  1. Broader jury: `codex`, `claude`, `kimi`, `gemini`, `fable` (auto-filtered
     to those available on PATH; hermes_* variants kept for backward-compat).
  2. ABBA-adaptive ordering: each (agent, question) pair runs
     baseline/ats_recon in ABBA or BAAB order (counter-balanced) so
     warmup/fatigue bias cancels. `--no-abba` disables.
  3. Blind reviewer score: a second pass where a different agent (the
     "reviewer") rates the answer 1-5 without seeing which path produced it.
     The mean reviewer score per path is the "quality" metric.
  Flags: `--agents codex,claude`, `--reviewer gemini`, `--iter N`, `--no-abba`.
  Output: JSON + Markdown with per-question savings and per-agent/path detail.

- **feat(doctor): `ats-doctor`** now reports `ats-token-cfo`,
  `ats-goal-archive`, `token-cfo` package, and `metareview` skill availability.

- **docs:** README and AGENTS.md updated with v4.0.0 sections.

### Benchmark results (2026-07-24, v2 harness, 1 iter, ABBA)

The v2 harness uses ABBA-adaptive ordering and a blind reviewer. Results are
comparable to v1 in shape; the v2 JSON includes `reviewer_score_mean` per
path. Run locally to regenerate:

```
python3 integration/cli/ats-jury-bench-v2.py --iter 1 \
  --out /tmp/ats_jury_bench_v2.json --md /tmp/ats_jury_bench_v2.md
```

### Public usability of the ggcoder shim

The universal shell wrapper `integration/cli/agent-token-saver.sh` is the
publicly usable "ggcoder shim". It sources `goal.sh` (v3.5.0+) and
`ats-token-cfo` (v4.0.0+) and is wrapped by agent-specific profiles
(`devin-token-saver.sh`, `claude-token-saver.sh`, `codex-token-saver.sh`,
`cmux-token-saver.sh`). All fail-open: missing tools degrade gracefully.

## 3.8.1 — 2026-07-23

### stdio LLM bridge + ats-recon auto-router + jury benchmarks

- **feat(cli): `ats-llm-pipe`** — Python bridge that reads OpenAI-style
  messages JSON from stdin and routes to the first available CLI LLM
  (codex, kimi, claude, llm). Enables supacrawl LLM extraction without
  Ollama or API keys. Installed at `integration/cli/ats-llm-pipe`.

- **feat(supacrawl): stdio LLM provider** — patched `supacrawl/llm/config.py`
  and `supacrawl/llm/client.py` (site-packages) to recognize `stdio` as a
  valid provider. Configured via `SUPACRAWL_LLM_PROVIDER=stdio` and
  `SUPACRAWL_LLM_STDIO_CMD=ats-llm-pipe`. No API key, no Ollama daemon.

- **feat(cli): `ats-supacrawl-extract <url> "<prompt>"`** — bash wrapper
  that runs scrape + LLM extraction in one call using the stdio bridge.

- **feat(cli): `ats-recon "<query>"`** — auto-routing pipeline that picks
  the best recon tool based on the query shape:
  - URL → `supacrawl scrape` (or `extract` if `--extract` flag)
  - `owner/repo` → `ghx explore` (or `inspect` if question contains "where"/"how")
  - else → `gmax` semantic search
  Fail-open: missing tools degrade gracefully.

- **feat(cli): `ats-recon-doctor`** — now checks `ats-llm-pipe` and stdio
  LLM CLIs (codex/kimi/claude/llm) alongside gmax/ghx/supacrawl.

- **feat(bench): `ats-recon-bench.py`** — benchmarks gmax vs grep,
  ghx explore/inspect vs `gh api`, supacrawl scrape vs curl, and
  supacrawl stdio extraction. Outputs JSON + Markdown table.

- **feat(bench): `ats-swarm-bench.py`** — tests the stdio bridge across
  multiple agent CLIs (codex, hermes+kimi, hermes+luna, hermes+terra).
  Measures wall time, chars, JSON validity.

- **feat(bench): `ats-jury-bench.py`** — jury of agents answers questions
  about agent-token-saver via baseline (grep/gh api/curl) vs ats-recon
  (gmax/ghx/supacrawl). Measures token savings per question.

### Benchmark results (2026-07-23, 1 iter, 4 agents)

| Probe | Baseline tokens | ATS-recon tokens | Saved |
|---|---|---|---|
| local_search | 930 | 167 | 82.0% |
| github_recon | 8836 | 85 | 99.0% |
| web_scrape | 157 | 64 | 59.2% |

## 3.8.0 — 2026-07-23

### Recon CLI integration — gmax + ghx + supacrawl (fail-open, no MCP, no API keys)

- **feat(cli): `ats-gmax` wraps grepmax (gmax)** — persistent semantic index of
  local codebases. Replaces Cascade `code_search` for indexed projects.
  `--agent` output is ledger-compatible (single-line hits + similarity score +
  role tag ORCH/DEFI). Subcommands `trace`, `skeleton`, `extract`, `peek`,
  `dead` exposed. Index once: `gmax add <path>`. Query: `gmax "<q>" --agent`.
  Install: `npm install -g grepmax` (requires `npm config set allow-scripts`
  for native ONNX/MLX/sharp modules).

- **feat(cli): `ats-ghx` wraps ghx (GitHub reconnaissance sidecar)** — GraphQL
  batching (10 files/call), `read --map` output ~92% token reduction vs raw
  file reads. `inspect <owner/repo> "<concern>"` ranks files by relevance.
  Uses `gh` CLI auth, no extra API key. Ideal pre-step before
  `superweb research --deep` for repo-specific questions.
  Install: `npm install -g @gkoreli/ghx`.

- **feat(cli): `ats-supacrawl` wraps supacrawl (HTTP-first web scraper)** —
  markdown output, `map`/`crawl`/`batch`/`search` subcommands. No API key
  required for scrape/map/crawl/batch. LLM-Extract with Ollama currently
  broken (schema serialization) — pipe `supacrawl scrape` to `ollama`
  directly as workaround. Complements `superweb research --deep` for quick
  single-page pulls. Install: `pip install supacrawl`.

- **feat(cli): `ats-recon-doctor`** — quick health check for the three recon
  CLIs. Shows install state + `gh`/`ollama` dependencies + `gmax status` for
  indexed projects overview.

- **feat(doctor): `ats-doctor` now reports gmax/ghx/supacrawl install state**
  alongside existing rtk/si/synx/duckdb/jq lines. New adaptive functions
  `ats-gmax`, `ats-ghx`, `ats-supacrawl`, `ats-recon-doctor` listed.

- **docs(skill): SKILL.md bumped to 3.8.0** — new "Recon CLIs" section
  documents the three helpers, fail-open contract, and MCP-free rationale.

- **docs(agents): AGENTS.md "Recon CLIs (v3.8.0+)" section** — discoverable by
  agents reading repo rules.

All three recon CLIs are optional and fail-open: missing CLI → passthrough
message, never error. MCP servers deliberately NOT used — CLIs keep
Cascade/agent context clean. No API keys required (ghx uses `gh` auth,
supacrawl scrape/map/crawl/batch are key-free, gmax is fully local).

## 3.7.0 — 2026-07-23

### Adaptive agent system — universal wrapper + auto-detection + hard gates

- **feat(cli): `ats-detect-agent` auto-detects the calling agent from env vars**
  (`DEVIN`, `CLAUDECODE`, `CODEX_AGENT`, `CMUX_SESSION`, `KIMI_WORKER`,
  `CASCADE_AGENT`, `TERM_PROGRAM`) and process-name heuristic. Sets
  `ATS_AGENT_NAME` + auto-discovers `ATS_ACTIVE_SKILL` from
  `skills/agent-token-saver-<name>/SKILL.md`. Agents can override by exporting
  `ATS_AGENT_NAME` before sourcing. Enables "source one wrapper, works for
  any agent" deployment.

- **feat(cli): `ats-safe <fn> [args...]` fail-open wrapper** — calls `<fn>` if
  defined, else warns + returns 0. Lets agents call optional ats-* helpers
  without knowing whether they're installed. `ats-have <tool>` silent CLI
  existence check.

- **feat(cli): `ats-metareview <slug>` spawns a FRESH reviewer to refute the
  DoD** — implements omnigoal Hard Gate #5 (foreign cross-check, never
  self-review). Tries in order: `agentmaster send` → `grepgod review` →
  `si route code-reviewer` → manual prompt. Records verdict in goal JSON
  `.evidence.refuter` = PASS|FAIL|PENDING|SKIPPED + `.evidence.refuter_via`.
  `--skip-if-missing` lets close proceed when no reviewer is available.

- **feat(cli): `goal-close --require-metareview`** — refuses close when no
  foreign reviewer was ever run (refuter == SKIPPED). Makes the metareview
  gate enforceable rather than advisory. Without the flag, behavior is
  unchanged (backward-compatible).

- **feat(cli): `ats-omnigoal-check <slug>` verifies the 7 omnigoal hard gates**
  before a "done" claim: (1) oracle exists, (2) eval written before build
  (EDD), (3) bottleneck named, (4) commits since spawn, (5) metareview PASS,
  (6) compounding writeback (summary), (7) no 3-try cap violation. Returns 0
  only if all gates pass. Prints a concise pass/fail report.

- **feat(cli): `ats-auto` runs the full omnigoal loop in one call** —
  recall → contract → leverage → slice → execute (you) → eval-gate → learn →
  report. Two-phase: `ats-auto "<title>" --oracle "..."` starts the loop and
  pauses at EXECUTE; `ats-auto --continue <slug>` runs goal-check +
  ats-metareview + ats-omnigoal-check + goal-close. `--skip-metareview` for
  environments without a reviewer runtime.

- **feat(cli): `ats-prime-and-init` parallel speedtuning** — runs `synx hybrid`
  recall AND `goal-init` in parallel, then joins. Cuts loop latency on the
  first omnigoal step by ~50% when synx is available. Recall results appended
  to goal JSON `.evidence.recall[]`. Falls back to sequential when synx
  missing. `ats-parallel "<cmd1>" "<cmd2>" ...` general-purpose parallel
  runner with join + indexed output.

- **feat(cli): thin agent wrappers `claude-token-saver.sh`,
  `codex-token-saver.sh`, `cmux-token-saver.sh`** — each is ~40 lines, sources
  the universal wrapper, sets `ATS_AGENT_NAME` + `ATS_ACTIVE_SKILL`, installs
  `<agent>-*` aliases mirroring the Devin pattern. Enables any hookless agent
  to use the system with one `source` line.

- **refactor(tests): expand `tests/test_goal_system.sh` from 20 to 30 checks**
  covering ats-detect-agent, ats-safe, ats-have, ats-parallel, ats-metareview,
  ats-omnigoal-check, ats-auto (both phases), goal-close --require-metareview,
  and claude/codex/cmux wrapper loading. All 30 checks green.

- **docs: update ats-doctor** to report `ATS_AGENT_DETECTED`,
  `ATS_ACTIVE_SKILL`, and list all adaptive functions installed.

- **compat: no breaking changes.** Existing `source scripts/devin-token-saver.sh`
  sessions continue to work unchanged. New adaptive functions are additive.
  `goal-close` without `--require-metareview` behaves as before.

## 3.6.0 — 2026-07-23

### Devin-naming cleanup — universal `ats-*` wrapper, Devin becomes thin profile

- **refactor(cli): split `devin-token-saver.sh` into universal + Devin wrapper.**
  The universal helpers (`ats-token-ledger`, `ats-synapse-prime`,
  `ats-synapse-remember`, `ats-synapse-ingest`, `ats-capsule-template`,
  `ats-doctor`) now live in `integration/cli/agent-token-saver.sh` and work for
  any hookless agent. `devin-token-saver.sh` is now a ~50-line wrapper that:
  1. sources the universal wrapper,
  2. exports `ATS_AGENT_NAME=devin` + `ATS_ACTIVE_SKILL=…devin/SKILL.md`,
  3. re-exports `devin-*` as 1-line backward-compat aliases.
  Existing Devin sessions keep working; new agents call `ats-*` / `goal-*`
  directly.

- **refactor(cli): `devin-*` functions renamed to universal `ats-*` names** in
  the universal wrapper. `devin-token-ledger` → `ats-token-ledger`,
  `devin-synapse-prime` → `ats-synapse-prime`, `devin-synapse-remember` →
  `ats-synapse-remember`, `devin-synapse-ingest` → `ats-synapse-ingest`,
  `devin-capsule-template` → `ats-capsule-template`, `devin-token-doctor` →
  `ats-doctor`. The Devin wrapper re-exports all six as `devin-*` aliases.

- **feat(cli): `ATS_AGENT_NAME` + `ATS_ACTIVE_SKILL` env overrides** let
  agent-specific wrappers customize the ledger's `--agent` field and
  `active-skill` component without re-implementing `ats-token-ledger`. Devin
  sets both via the wrapper; other agents can set them inline or via their own
  wrapper.

- **refactor(tests): rename `tests/test_devin_goal_system.sh` →
  `tests/test_goal_system.sh`** and expand from 19 to 20 checks. New test
  verifies `ats-doctor` reports `AGENT_TOKEN_SAVER_LOADED` + `ATS_AGENT_NAME`;
  the existing `devin-goal-init` / `devin-token-doctor` alias check remains as
  backward-compat coverage. All 20 checks green.

- **docs: update README, SKILL.md, MASTER-PLAN.md, capsule-template.md,
  devin-bootstrap.md** to reference the universal `ats-*` / `goal-*` CLI as
  primary and `devin-*` as backward-compat aliases. MASTER-PLAN bumped to
  v1.3.0; Devin profile is now described as a strict subset of the universal
  wrapper plus env overrides + aliases.

- **compat: no breaking changes.** `source scripts/devin-token-saver.sh` still
  installs `devin-*` aliases; existing Devin sessions and docs continue to
  work. The universal wrapper is additive.

## 3.5.0 — 2026-07-23

### Universal goal-* CLI — full omnigoal loop for ALL agents

- **feat(goal): universal `goal-*` CLI with 13 functions covering the full
  omnigoal loop** (`integration/cli/goal.sh`, 670 lines). Replaces the
  Devin-specific 4-function MVP from v3.4.0 with a universal CLI that works
  for any agent (Devin, Codex, Claude, cmux, kimi-worker). Built on the
  omnigoal law + 2026 research (AgentLTL, AgentVerify, delegato, Orloj,
  Network-AI, CAPO). See `~/BASE/docs/goal-system-rework.md` for full spec
  + 10 ADRs. The 13 functions:
  - `goal-init` — contract with **closed-verb enforcement** (rejects
    "optimize/improve/polish" — open verbs diverge forever), bottleneck-naming
    requirement, eval-written flag, 3-try cap, budget + deadline, agent field.
    `--force` escape hatch for exploratory goals.
  - `goal-recall` — `synx hybrid` pre-session RAG (state, not narrative).
  - `goal-leverage` — name the ONE bottleneck / null-term (TOC) + min 2 levers
    (hebelwort). Refuses spawn if missing — no bottleneck = 80% waste.
  - `goal-slice` — smallest reversible vertical slice at the bottleneck.
  - `goal-spawn` — bounded subagent + capsule + skill + **trust score** (starts
    0.5, delegato pattern) + privilege attenuation. Optional `--via agentmaster`
    for cmux fleet fan-out. Subagent state machine: spawned→running→done/failed/refuted.
  - `goal-check` — runs oracle, increments `attempts[]`, enforces **3-try cap**
    → root-cause note (not try 4), checks **budget + deadline** (hard stops at
    100%, state→failed), identifies bottleneck from error log.
  - `goal-verify` — **verify-back via git commits since spawn_ts** (real work =
    commits, not mtime, not self-claim — agent-loop principle).
  - `goal-refute` — spawn FRESH subagent (no parent context) to refute DoD.
    Default verdict = "NICHT-ERFÜLLT". Catches honesty-bugs at the last inch
    (self-review finds 0/34, fresh instance 7/34, deterministic checker 34/34).
  - `goal-close` — refuses if oracle failing OR refute found a hole. **Compounding
    writeback**: `synx put` of summary + decision rationale + bottleneck + levers
    + verify-command (not just result). Next session's `goal-recall` finds the
    decision, compounds across sessions.
  - `goal-trace` — optional **LTL-style trace verification** (AgentLTL-inspired):
    `always(P)`, `eventually(P)`, `P before Q`, `P until Q`. Checks procedural
    compliance over execution trace, not just outcome.
  - `goal-trust` — per-subagent **trust scoring with asymmetric decay** (+0.05
    done, −0.15 failed, −0.30 refuted). **Circuit breaker** at Δtrust > 0.3
    pauses subagent.
  - `goal-list` — all goals with state, attempts, budget used, deadline,
    bottleneck, average trust.
  - `goal-doctor` — health check for jq, git, synx, agentmaster, rtk, si,
    synapse-ultra, duckdb.

- **feat(goal): `devin-goal-*` kept as 1-line backward-compat aliases** —
  existing Devin sessions that use `devin-goal-init/check/close/spawn` don't
  break. New agents should call `goal-*` directly.

- **feat(goal): 19-check smoke test** (`tests/test_devin_goal_system.sh`)
  covers all 13 functions + backward-compat + budget enforcement + 3-try cap
  + root-cause note. All 19 checks green.

- **docs(goal): `~/BASE/docs/goal-system-rework.md`** — 162-line design spec
  with JSON schema, 10 ADRs, testing strategy, known limitations, and 2026
  sources (AgentLTL, AgentVerify, GCRL-LTL, cDFAs, ACQL, Orloj, Network-AI,
  CAPO, delegato, A3S, Anthropic EDD, Microsoft harness-first, Karpathy
  autoresearch).

## 3.4.0 — 2026-07-23

### Devin profile — goal-achievement system + ponytail compression

- **feat(devin): add goal-achievement system + synx rename + master-plan**
  (`c42ad9f`). Adds the omnigoal-pattern goal system to the Devin profile
  (Devin has no host-native prompt hooks, so everything is wired via repo
  instructions + shell wrapper + Knowledge Base). Four new shell functions in
  `integration/cli/devin-token-saver.sh`:
  - `devin-goal-init "<slug>" --oracle "<shell cmd>" --budget-tokens 50000 --deadline 2h`
    creates `~/.synapse/goals/<slug>.json` with a machine-checkable oracle.
    Uses `jq --arg` for safe JSON quoting of oracle/title (handles quotes and
    special chars).
  - `devin-goal-check <slug>` runs the oracle, prints PASS/FAIL + bottleneck
    (first `error|fail|not found|missing|panic` line). No args = list all
    goals with id/state/title.
  - `devin-goal-close <slug> --summary "<text>"` refuses close while oracle
    fails, persists summary to `synx put` (post-session RAG), marks goal
    `closed`. `jq --arg` for safe summary quoting.
  - `devin-goal-spawn <slug> --capsule <capsule.md> [--skill <name>]` registers
    a bounded subagent in the goal JSON — subagent sees only capsule + goal
    oracle, never the parent transcript.
  Goals live in `~/.synapse/goals/*.json` so any agent (Devin, Codex, Claude)
  can pick them up, coordinate, and ingest outcomes WITHOUT sharing transcripts.
  Replaces "spawn workers with shared context" (burns tokens) with "spawn
  workers with shared goal contract" (bounded). Estimated ROI: 40–60% token
  savings on tasks >30 min or >20k tokens.
- **feat(devin): rename `syn` → `synx`** across the Devin profile. `synx` is
  the full CLI (init/put/verify/keygen/snap-signed/find/vec/hybrid/context/
  remember/doctor/fallback/prime/stats/fresh-context); `syn` was the older
  subset. New helpers: `devin-synapse-prime` (pre-session `synx hybrid`),
  `devin-synapse-remember` (post-session `synx put`), `devin-synapse-ingest`
  (pipes Devin JSONL through `devin-usage.py` into `synapse-ultra ingest`).
- **feat(devin): add MASTER-PLAN.md + capsule-template.md** for the Devin
  profile. Master plan covers 8-phase rollout (A: core wrapper, B: skill
  router, C: SynapseUltra, D: DuckLake, E: goal system, F: VelesDB evaluated
  but not integrated, G: benchmark, H: live test pending), ROI measurement
  (saved = baseline − actual, target 80% cumulative), a Devin-Web test
  prompt, maintenance, and known limitations (no native hooks; cost in `meta`
  not `token_cost`; DuckLake JSON inlining bug; `jq` required for goals;
  budget advisory). Capsule template defines the 300–700-token bounded
  context for `devin-goal-spawn` (Goal/Inputs/Constraints/Output/Close +
  filled example).
- **feat(devin): add `devin-usage.py` ingest script** (in synapse-memory)
  that extracts `unattributed_input_tokens` from Devin session JSONL into
  Synapse Ultra's `meta` field. Live-validated: 2 events ingested, `replay`
  green, `prime` returned 4 relevant chunks, doctor shows `synx` +
  `synapse-ultra` + `duckdb` all present.
- **test(devin): add `tests/test_devin_goal_system.sh`** — 9-check smoke
  test (wrapper syntax, goal-init, goal-check pass/fail, goal-spawn,
  goal-close, goal-list, doctor goals, doctor uses `synx` not `syn`). All
  9 checks green after every compression pass.

### Ponytail compression — docs and wrapper

- **refactor(skill): ponytail-compress `SKILL.md`** (`3391c03`). 297 → 147
  lines, ~3352 → ~1882 tokens (**−43.9%**). Methods: bullet density,
  code-block elimination, section merging, reference linking, redundancy
  removal, example minimization, table compaction, ASCII-diagram simplify.
  Preserves all CLI commands, safety contracts, numbers/benchmarks.
- **refactor(plan): ponytail-compress `MASTER-PLAN.md`** (`f782294`).
  328 → 157 lines, ~3701 → ~1758 tokens (**−52.5%**). Same methods. All
  rollout phases, ROI numbers, test prompt, known limitations, and
  definition-of-done preserved.
- **refactor(wrapper): ponytail-compress `devin-token-saver.sh`**
  (`214e215`). 410 → 341 lines, ~3678 → ~3148 tokens (**−14.4%**). Methods:
  header-comment trim, else-branch alias merge, help-text compression,
  inline-comment removal, single-line body collapse. Preserves: all
  function signatures, `jq --arg` quoting fixes for goal-init/goal-close,
  fail-open contract, idempotency guard, doctor output. Bash syntax OK,
  9/9 smoke checks green.
- **refactor(superweb): compress Devin block in `AGENTS.md`** — 114 → 35
  lines, ~1102 → ~497 tokens (**−54.9%**). Removed inline
  Synapse/DuckLake/Goal examples (kept in `SKILL.md`), kept only routing
  rules + 1-line lifecycle reference. Deep docs live in KB, `AGENTS.md`
  stays slim.

### Benchmark — `data/benchmarks/devin-profile-2026-07-23.json`

- Updates `devin-profile-2026-07-23.json` to v1.3.0 with pre/post compression
  numbers. Always-hot tokens per session: 1102 → 497 (**−54.9%**). Zero-hot
  KB savings vs always-hot: 79.62% → **88.68%** (3968 tokens saved per
  session). ROI projection unchanged: 80% cumulative (core wrapper + synapse
  prime + goal system + ducklake). Maximization stack: synx integrated,
  synapse-ultra integrated, ducklake recipes-ready, goal-system
  live-validated, VelesDB evaluated-not-integrated.

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
