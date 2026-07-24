# Changelog

## 4.8.0 — 2026-07-24

### agy is a real headless lane — antigravity GUI marker deleted

The earlier claim that Antigravity is "GUI-only" was wrong. `agy` is
Antigravity's headless CLI (`agy -p <prompt>`, flags BEFORE `-p` or it eats
the next flag as the prompt) and is the free Gemini path now that Google
retired the standalone gemini CLI. Models include gemini-3.6-flash,
gemini-3.1-pro, claude-sonnet-4-6, opus-4-6-thinking, gpt-oss-120b — all on
the Antigravity subscription ($0 per call here).

- **feat(swarm): real agy lanes** — `agy_gemini_flash`
  (gemini-3.6-flash-low) and `agy_claude_sonnet` (claude-sonnet-4-6) replace
  the `antigravity` `open -a` marker. Measured: both success 1.0, valid JSON,
  ~35-42s, $0. Run 2026-07-24: 9/11 lanes successful at $0.0000.
- **feat(jury): agy candidate** — replaces the antigravity marker; verified
  in both roles (ask_agent answer + blind_review returns 5.0).
- **refactor:** deleted the GUI-launch special cases
  (`_antigravity_available`, the `open -a` branch in `run_agent`/`ask_agent`,
  the reviewer/aggregate skips). `ask_agent` and `blind_review` gained
  `__PROMPT__` arg-mode so arg-based CLIs (agy) work alongside stdin CLIs.
- **note(devin):** local `Devin.app` exists (VS Code fork) and is logged in
  (macOS Keychain has a `Devin` item), but its agent CLI is `chisel` speaking
  ACP (JSON-RPC) authenticated with a windsurf-api-key — there is no
  `agy -p`-style prompt frontend (`devin-desktop` only does diff/merge/goto
  window ops). A headless Devin lane would need an ACP client + the extracted
  chisel binary; it is paid and session-async, a poor swarm fit. Not built.

## 4.7.2 — 2026-07-24

### Jury reviewer fixed — dead gemini out, live kimi in

- **fix(jury): dead reviewer zeroed every score** — `gemini --print` is on
  PATH but Google killed the free individual Gemini-CLI tier
  (`IneligibleTierError` → "migrate to Antigravity"), so the auto-picked
  reviewer returned an error and every `reviewer_score` was 0.0 (visible in
  the earlier smoke: "88% saved, ★ 0 vs 0"). gemini removed from the jury.
- **fix(jury): wrong kimi binary** — the jury used `kimi --print` (no such
  flag); corrected to the working `kimi-awake --quiet --input-format text`
  (OAuth, reads stdin). Now the default reviewer for a codex+claude jury is
  live kimi — verified: single blind-review call returns 5.0, was 0.0.
- **fix(jury): hermes lanes hermetic + alive** — `hermes_kimi` (dead
  kimi-k3 key) replaced by `hermes_free` (OpenRouter `ling-3.0-flash:free`);
  all hermes jury lanes pass `--ignore-user-config` so the user-level
  fallback chain can't turn a failure into a 120s retry.
- **note:** Devin has no local CLI and no key here (checked env/keychain);
  its official API is session-based, a poor fit for the one-shot extraction
  swarm — not added. Antigravity's `language_server` exposes a CSRF-gated
  HTTP API on a random port, but wrapping that reverse-engineered IDE
  protocol is a liability, so antigravity stays a GUI-launch marker.

## 4.7.1 — 2026-07-24

### Kimi lane revived (OAuth) + hermes default fixed + hermetic bench lanes

- **fix(kimi):** `kimi login --json` device-flow re-authorized the kimi CLI
  (OAuth, auto-approved by the active kimi.com browser session). Lane
  restored in the swarm bench: success 1.0, valid JSON, ~11s. ggcoder's
  moonshot OAuth was already healthy (5.2s). The legacy `KIMI_API_KEY` in
  `~/.hermes/.env` stays dead (401 on api.kimi.com/coding AND
  api.moonshot.ai) — only hermes reads it.
- **fix(hermes):** default model was the dead `kimi-k3/kimi-coding` → every
  plain `hermes -z` call died with 401. New default:
  `openrouter/inclusionai/ling-3.0-flash:free` with a fallback chain
  (gemma-4-31b:free, nemotron-3-nano:free) in `~/.hermes/config.yaml`;
  restore instructions for kimi-k3 are in a comment. Verified: plain
  `hermes -z` answers again.
- **fix(bench): hermetic hermes lanes** — the new user-level fallback chain
  made failing bench lanes retry until timeout (120s instead of fast-fail).
  All hermes bench lanes now pass `--ignore-user-config`.
- **bench run 2026-07-24 (post-fix):** 8/10 lanes successful at $0.0000
  spent — codex, kimi, ggcoder_kimi, hermes_luna, hermes_free_ling, claude,
  ollama_phi4, ollama_dolphin3. Artifact:
  `data/benchmarks/swarm-v4-kimi-fixed-2026-07-24.json`.

## 4.7.0 — 2026-07-24

### Swarm fleet v2 — OpenRouter free lanes, ggcoder-kimi, credit tracking, parallel jury

Lane audit 2026-07-24 (keys probed against live APIs): `KIMI_API_KEY` is dead
(401 at api.moonshot.ai) — that killed both `hermes -m kimi-k3` and the
`kimi` CLI, independent of OpenRouter. The OpenRouter key is VALID with
$0.39 credits left (65 − 64.61 used) → paid lanes 402, `:free` models work.

- **feat(swarm): OpenRouter `:free` lanes** — current free list fetched live
  (15 models). New lanes `hermes_free_ling`
  (`inclusionai/ling-3.0-flash:free`) and `hermes_free_gemma4`
  (`google/gemma-4-31b-it:free`) via `--provider openrouter`; correct syntax
  is the `--provider` flag, not an `openrouter/` model prefix (that 401s).
  Free lanes are rate-limited at peak (honest 429); nemotron free returned
  empty and was dropped after measurement.
- **feat(swarm): `ggcoder_kimi` lane** — `ggcoder --json --provider moonshot`
  runs Kimi over ggcoder's own OAuth (independent of the dead API key) and
  emits exact usage in JSON events (`agent_done.totalUsage`). Measured:
  5.6-6.5s, valid JSON, fastest working kimi lane. New `__PROMPT__` arg-mode
  support + `_parse_ggcoder_json` (answer from `text_delta` events).
- **feat(swarm): credit tracking** — hermes lanes get `--usage-file`
  per call; `SwarmResult.cost_usd` + `cost_usd_sum` per agent + report
  footer `Total credits spent: $X — successful $0-lane calls: N`. Run
  2026-07-24 (9 lanes): $0.0000 spent, 6 successful $0 calls
  (codex, ggcoder_kimi, ling, claude, phi4, dolphin3).
- **fix(swarm): kimi CLI lane removed** — `kimi-awake` reads the dead
  `KIMI_API_KEY` (401). Re-add when renewed; comment documents it.
- **feat(jury): parallel agents** — `ats-jury-bench-v2.py` runs one worker
  per agent (`--workers`, default min(4, agents)); the ABBA sequence stays
  strictly sequential inside each worker, so bias cancellation is intact.
  New `--only-q <substr>` filter for fast smokes. Smoke (codex+claude
  parallel, local_search, ABBA): 177s wall vs ~265s+ sequential chains;
  savings metric intact (88.0% saved).
- Artifacts: `data/benchmarks/swarm-v2-2026-07-24.json`,
  `data/benchmarks/jury-parallel-smoke-2026-07-24.json`.

## 4.6.0 — 2026-07-24

### Swarm bench: parallel by default + honest success metric

- **feat(swarm): parallel execution** — `ats-swarm-bench.py` runs all
  (agent × iteration) calls through a `ThreadPoolExecutor` (default
  `min(8, calls)`, `--workers N` override, `--sequential` opt-out).
  Wall-clock becomes the slowest agent instead of the sum: measured
  2026-07-24, 9 agents × 1 iter = ~92s of agent work in 32s wall (2.9×);
  the old sequential loop needed 31s for only 6 agents. Report order stays
  deterministic regardless of completion order.
- **fix(swarm): honest success metric** — hosted CLIs (hermes lanes) print
  HTTP 401/402 billing errors to STDOUT and exit 0; the bench counted them
  as success=1.0. New `ERROR_MARKERS` head-scan flips these to failures:
  hermes_kimi/luna/terra/codex now correctly report 0.0 while codex,
  claude and ollama_dolphin3 hold real 1.0 with valid JSON.
- **feat(swarm): local lanes** — adds `claude -p`, `ollama_phi4`,
  `ollama_dolphin3` (no API key, no billing). Data point: phi4-reasoning
  dumps its chain of thought (4.5k chars, invalid JSON) — a bad extraction
  lane, dolphin3:8b answers clean JSON in 9.6s.
- **feat(swarm): `--timeout N`** (default 120) — also fixes the timeout
  result recording the hardcoded 120.0 instead of the actual limit.
- **feat(swarm): PATH pre-filter** — missing CLIs are reported once and
  skipped instead of burning a FileNotFoundError per iteration.
- **tests:** `tests/test_swarm_bench.py` (error-marker semantics, head-only
  scan, real answers pass). Artifacts:
  `data/benchmarks/swarm-{seq,par}-2026-07-24.json`.

## 4.5.0 — 2026-07-24

### Final product pass — ats-gain ledger + URL cache + fast-tier fallback, all agents

Lean/low-wear by design: the ledger appends one ~100-byte JSONL line per
recon op to a monthly file; the URL cache is one SQLite file in WAL mode with
`synchronous=NORMAL` (few fsyncs), writes only on new-URL misses, and is
vacuumed manually/monthly — never automatically.

- **feat(cli): `ats-gain`** — recon savings report. `ats-recon` is now a thin
  instrumented wrapper around the routing core: it counts output tokens per
  call and logs shape (local/repo/url) plus the measured baseline factor
  (gmax vs grep ×11.0, ghx vs gh api ×2.9, supacrawl vs curl ×4.8 — from
  `data/benchmarks/recon-2026-07-24`). `ats-gain` aggregates: ops, tokens
  spent, estimated tokens saved, reduction %. Estimates are labeled as such.
  Fail-open: ledger trouble never blocks output. `ATS_LEDGER_DIR` overrides.
- **feat(cli): `ats-url-cache`** — URL→markdown cache (get/put/stats/vacuum)
  at `~/.agent-token-saver/url-cache.db`. `_ats_scrape_url` checks it before
  scraping and stores successful scrape/fallback bodies (TTL 24h,
  `ATS_FRESH=1` bypass, `ATS_URL_CACHE_DB`/`ATS_URL_CACHE_TTL` overrides).
  Empty bodies are never cached. Measured: bun.com/blog miss 1.26s → hit
  0.04s (31×), identical 59.6k chars, repeat scrapes cost 0 network.
- **feat(recon): superweb fast-tier fallback** — the superweb lane tries
  `--max-tier 1` first (measured 0.9s vs 23s for identical content on static
  pages) and only climbs the full escalation ladder when the fast tier
  returns nothing (SPA/blocked pages).
- **fix(shell): `ATS_CLI_DIR`** — absolute sibling-CLI dir resolved at source
  time; helpers work from any cwd.
- **tests:** `tests/test_url_cache.py` (roundtrip, TTL expiry, empty-body
  guard, vacuum). Vacuum uses `<=` so `--ttl 0` expires same-second rows.
- **install:** applied with `--profile heavy --agent all`
  (codex/claude/hermes/ggcoder + repo), onboarding 7/7 layers · 3/3 sidecars.

## 4.4.0 — 2026-07-24

### Smart URL lanes + bench-fleet expansion

- **feat(recon): `_ats_scrape_url` smart URL lane** — every URL entering
  `ats-recon` (via `--url` or as the query) now routes through one helper:
  1. `github.com/<o>/<r>/blob/<branch>/<file>` → `ghx read` (structure-aware,
     measured 1.8-3s vs 31s supacrawl on the same file);
  2. `github.com/<o>/<r>` repo-root → `ghx explore` (tree+README in 1 call
     instead of scraping the HTML UI);
  3. everything else → `supacrawl scrape`;
  4. empty/blocked scrape → `superweb fetch --mode auto` fallback (fail-open,
     only if `superweb` is on PATH).
  Fixes a lane-order bug where the `github.com` query regex hijacked full
  URLs before the URL lane could run (blob URLs landed in `ghx inspect` with
  the raw URL as concern).
- **feat(bench): fleet expansion** — `ats-poweruser-bench.py` grows to 10
  agents (adds `claude -p`, `hermes_terra`, 5 local Ollama models);
  `ats-jury-bench-v2.py` + `ats-swarm-bench.py` add `antigravity` (GUI IDE,
  launch-only; recorded honestly as success=False, excluded as blind
  reviewer).
- **bench(superweb vs supacrawl, 2026-07-24, this machine):** example.com
  240 ch/2.8s warm (superweb) vs 168 ch/0.9s (supacrawl); bun.com/blog 52.0k
  ch/24s vs 59.7k ch/2.8s; GitHub README page 9.4k ch/4.3s vs 13.0k ch/31s —
  while `ghx read` returns the same file as 11.1k ch in 3.0s without a
  browser. Conclusion encoded in the router: GitHub → ghx, static/bulk →
  supacrawl, JS-heavy/blocked → superweb.
- **docs(agents):** ghx 2.9 budget-compaction default documented (old
  `--map` flag removed).

## 4.3.0 — 2026-07-24

### Recon router hardening + locale fix + fresh benchmarks

- **feat(recon): bare `owner/repo` routing** — `ats-recon` now detects a bare
  `owner/repo` token in the query (e.g. `ats-recon "anthropics/claude-code
  where are hooks documented"`) and routes to `ghx inspect`; previously only
  `github.com/...` URLs matched and such queries silently fell through to
  gmax local search. The repo token is stripped from the concern before it is
  passed to ghx, which measurably improves ranking (top hit
  `hooks/llm.py` score=103 vs an unrelated `feed.xml` with the raw query).
  Guards against false positives: skips `http*`, `./`, `/`, `~`, paths that
  exist locally, owners containing dots, and double-slash tokens.
- **fix(shell): wrapper now loads in subshells** — `claude-token-saver.sh`
  exported its load guard, so any child shell (bash under zsh, scripts,
  subagents) inherited `CLAUDE_TOKEN_SAVER_LOADED=1` and skipped defining
  all ats-*/goal-* functions. Guard is no longer exported and additionally
  verifies the functions actually exist (`typeset -f ats-recon`).
- **fix(recon): bash-compatible regex capture** — `${match[1]}` (zsh-only)
  → `${BASH_REMATCH[1]:-${match[1]:-}}` in the github.com route.
- **fix(goal): decimal-comma locale broke goal-trust** — on `LC_NUMERIC=de_DE`
  awk printed `0,550`, jq `--argjson` rejected it, and trust updates were
  silently dropped (`trust should change` failed at HEAD). Float awk sites in
  `goal.sh` now run under `LC_ALL=C`. All 36 goal-system checks pass again.
- **docs(ghx 2.9 drift):** removed `--map` from wrapper help/comments — since
  ghx 2.9 budget compaction (~92% reduction) is the default, tunable via
  `--budget`, disabled via `--full`.
- **bench:** fresh `ats-recon-bench` run (2026-07-24, 2 iter) recorded in
  `data/benchmarks/recon-2026-07-24.{json,md}`: gmax 133 vs grep 1461 tok
  (−91%), ghx explore 1453 vs `gh api` 4142 tok (−65%), supacrawl 42 vs curl
  139 tok on the fixture page; live large-page check bun.com/blog: 14 912 vs
  70 814 tok (−79%).

## 4.2.0 — 2026-07-24

### Onboarding check + installer self-update

Closes the "doctor says 100% while gmax/ghx are missing" gap: recon sidecars
are now first-class in the doctor, and the installer ends every run with a
full onboarding check.

- **feat(doctor): recon sidecar section** — `agent-token-saver doctor` now
  probes `gmax`, `ghx`, `supacrawl` and prints one line per sidecar with the
  exact install command on MISSING (e.g. `bun add -g grepmax`). JSON report
  gains a `recon` key. New summary line:
  `onboarding: N/M layers · K/3 recon sidecars` with a fix-and-rerun hint
  when anything is missing.
- **feat(install): self-update** — when running from a git checkout, the
  installer fast-forwards (`git pull --ff-only`) before installing so every
  install ships the latest version. Skipped on dirty checkout or offline
  (fail-open, prints why). Opt out with `--no-update`.
- **feat(install): onboarding check on apply** — every non-dry-run install
  ends by executing the freshly installed doctor (`== onboarding check ==`),
  so missing sidecars are visible at install time instead of being
  discovered mid-session.
- **fix(readme):** rename poweruser-bench case label `02_superweb_readme` →
  `02_public_repo_readme`; the private tool name leaked into the public
  surface and failed `test_active_public_surface_excludes_private_host_tools`
  at HEAD.
- **fix(lint):** ruff pass on `scripts/abba.py` + `tests/test_abba.py`
  (UP006/UP035/F401 autofix; B011 `assert False` → `pytest.raises`).
  `uv run ruff check scripts integration tests` is clean again;
  106/106 tests pass.

## 4.1.1 — 2026-07-24

### Trust and reproducibility pass

- **fix(cli):** remove hardcoded `/Users/master/BASE` paths from all
  benchmark drivers and shell wrappers. Defaults now use `$HOME/projects/...`
  (overridable via `ATS_BENCH_BASE`, `SYNAPSE_ULTRA_BIN`,
  `SYNAPSE_ULTRA_INGEST`, `ATS_TOKEN_CFO_DIR`, `GOAL_SCIENCE_DOC`,
  `ATS_ROOT`). `ats-poweruser-bench.py`, `ats-jury-bench.py`,
  `ats-jury-bench-v2.py`, `ats-recon-bench.py` auto-detect their repo
  root from `__file__` so they run on any checkout without edits.
- **fix(tests):** `tests/test_goal_system.sh` now derives `REPO_ROOT`
  from `BASH_SOURCE` instead of a hardcoded absolute path. All 36
  checks still pass.
- **docs(readme):** soften the 199.1x headline badge from
  "up to 199.1x payload capacity" to "payload capacity fixture" and
  move the caveat into the headline quote itself. Add a new
  "Who this is for (and who it is not)" section that explicitly lists
  readers who already run context-mode / Graphify / subagent routing /
  firecrawl / strict CLAUDE.md discipline, and tells them which pieces
  (if any) are worth a second look.
- **docs(readme):** add "On reproducibility and private paths"
  subsection under "What this repository does not claim" — explains that
  historical benchmark JSON artifacts contain the author's absolute
  paths (real run output, kept as-is) while the drivers are now
  portable, and gives the shortest verify-it-yourself commands.
- **docs(readme):** replace `~/BASE/...` defaults in the Superintelligent
  Stack section with `$HOME/projects/...` and `$HOME/docs/...`.

## 4.1.0 — 2026-07-24

### Poweruser recon benchmark — 10 real cases across 3 agents

- **feat(cli): `ats-poweruser-bench.py`** — 10 real power-user cases
  (usage parsing, superweb README, chartlab QuantAgent, synapse FTS5,
  codex-pro providers, token-cfo pricing, PSI Sanctuary, ats hooks,
  example.com scrape, ats-recon router) benchmarked across 3 agents
  (codex, kimi, hermes_luna). Compares baseline (grep/gh api/curl/ls/cat)
  vs ats-recon (gmax/ghx/supacrawl) tool output + agent answer. JSON +
  Markdown report. Results 2026-07-23 (1 iter, 3 agents): codex 80.7%
  saved, kimi 84.6% saved, hermes_luna 75.1% saved. Best cases 86-97%
  saved (large tool outputs); negative cases where ats-recon router
  output exceeds baseline grep are a metric artifact (baseline returns
  no content, agent hallucinates from training). hermes_terra omitted
  (OpenRouter 402 billing exhausted).
- **docs(readme):** new "Poweruser recon benchmark (2026-07-23)"
  section with per-agent and per-case tables, plus a "What the negative
  cases mean" subsection that flags the ungrounded-baseline artifact.
- **docs(agents):** `ats-poweruser-bench.py` added to the Benchmarks
  section.

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
