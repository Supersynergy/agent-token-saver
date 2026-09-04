# Changelog

## [Unreleased]

- Fresh-install journey audited on a clean HOME with no version manager and
  fixed where it broke; analysis and plan in
  `docs/adr/2026-09-04-fresh-install-journey.md`.
  - `install-universal.sh` picks the newest interpreter that meets the 3.11
    floor (`python3.14` … `python3`) instead of execing `python3` blindly. A
    stock macOS resolves `python3` to 3.9 beside a qualifying Homebrew Python,
    and the README one-liner failed on it with the floor message. With no
    qualifying interpreter it now names what it found and how to install one.
  - `hook_interpreter()` enforces the same floor. It had pinned the stock 3.9
    for the hooks on that machine — they happened to import, but the CLI they
    launch needs `tomllib`. The doctor accepts a pinned interpreter only while
    it exists *and* meets the floor.
  - The doctor prints the install line for every optional layer it cannot
    find, and what each needs to be useful. The skill router was never in the
    MISSING list, so a user following "install MISSING lines above" never
    learned it existed. Once present, the router line reports indexed skills
    and whether an observer hook is registered.
  - Hermes reports its real state: `explicit-only: no SOUL.md, the skill loads
    only when named` instead of a bare `installed`.
- GG Coder integration verified against 5.46.2 with live subagents: the
  policy block and both skills reach a full agent and load through its `skill`
  tool. GG Coder has no hook system, and subagents whose `tools:` allow-list
  omits `skill` never see skills — documented in the README with a per-host
  needs table, not papered over.
- Hook commands are registered as `<interpreter> <hook>` with a real python3
  pinned by the installer — never a version-manager shim, never a project venv
  (`pyenv which` is asked, then validated: under a foreign HOME it answered
  with the venv interpreter). The shim alone cost 160 ms before the first line
  of a hook ran, paid twice per prompt. Measured: prompt hook 280 ms to 120 ms,
  Stop hook to 30 ms. `doctor` accepts the new shape only while the pinned
  interpreter still exists, so a Python upgrade that removes it is an error,
  not a silently dead hook.
- The prompt hook suppresses a same-session repeat of the same prompt within
  two seconds. Hosts that merge the Claude and Codex hook files fired it twice
  per prompt (one in ten in the route log), re-running the router and injecting
  the skill route twice. Without a session id nothing is suppressed; the hook
  stays a pure function of its input for the cache-hygiene tests.
- Playbook gains phase 2b (skill routing) with the measured 33x figure on the
  honest baseline, and records that the installed `si` had drifted behind its
  repo.
- New opt-in OmniRoute gateway lanes for `llmadapter` (`omniroute`,
  `omniroute-coding`), with the audit and PRD in
  `docs/adr/2026-09-03-omniroute-lane.md`. OmniRoute is an OpenAI-compatible
  gateway fronting many providers, so it reaches free-tier capacity we do not
  maintain by hand.
  The audit's decisive finding is about *our* code, not theirs: this repo asks
  `isLoopbackUrl()` to decide whether a prompt leaves the machine, and that
  question returns the wrong answer for a forwarding proxy. Modelling OmniRoute
  the way Ollama is modelled would have marked a `localhost` gateway as local
  and **silently disabled PII masking on prompts forwarded to third parties**.
  Gateway lanes therefore keep `kind: "openrouter"`, whose trust branch is
  unconditionally remote. A test mutating the lane back to the local shape fails
  seven ways.
  Their guardrails are documented as fail-open; ours stays fail-closed and runs
  first. Lanes are opt-in, so no class selector pulls a third-party gateway into
  a swarm. Non-http schemes and credential-bearing URLs are rejected before any
  call, and an absent gateway is `omniroute_gateway_unreachable` rather than a
  generic error — but only for genuine transport failures, so a PII-shield
  failure can never be misread as "start your gateway".
- New `scripts/benchmark_freshdocs_lane.py` plus its 2026-09-03 artifact:
  measures the documentation lane against freshdocs 0.2.0 in both retrieval
  modes. Context packs cost **80.8-96.9% fewer tokens** than the upstream
  sources they cite, at **~70 ms** versus ~200 ms for a single network fetch.
  Correctness, not size, decides the lane, and each mode fails differently:
  `--project` is version-exact (`ruff 0.14.14`, matching the manifest) but
  answered **5 of 6** off-topic queries from ruff when the library was not
  declared; `--lib` is always on topic but served **2 of 6** at upstream
  versions that differ from the installed binary (`uv 0.12.9` vs `0.11.5`,
  `bun 1.4.0` vs `1.3.14`). A refusal is scored as a refusal, never as the
  cheapest answer — the benchmark would otherwise rank "said nothing" first,
  which is the same mistake as scoring an empty failing test run as a saving.
- Playbook phase 4 now names freshdocs, both modes and the rule for choosing
  between them, instead of a generic URL cache.
- New `docs/PLAYBOOK.md`: the universal path in eight phases (recall, contract,
  locate, fresh docs, build, verify, account, learn), one worked example each,
  every command executed while writing it. Two of those examples are corrections
  the page earned by running its own advice: `goal-init` rejected the open-verb
  title first tried, and the RTK filter is `ruff-check`, not `ruff`. The page
  also carries a live version-drift table — only RTK was pinned tightly enough
  for drift to be detectable, and it had drifted three minor versions.
- RTK pin corrected 0.43.0 to 0.46.0, and its new per-tool `pipe` filters are
  wired into the verification path. `ats-verify` now offers `rtk pipe --filter`
  as a second projection of the *already captured* output, so the command is
  still executed exactly once. Adoption is per run and by measurement: every
  candidate must still contain a signal line, and the smallest survivor wins.
  There is no fixed winner, and the first draft of this note overstated one:
  measurement shows selection depends on the *shape* of the log, not the tool.
  `cargo-test` is the only filter that wins at every size (3,060 B to 323 B on a
  long red log). `pytest` wins on short red logs and on green ones (the full
  suite goes 2,425 B to 18 B) but loses to the builtin on a long red log.
  `mypy`, `tsc` and `ruff-check` lose on the shapes measured. A red `mypy`/`tsc`
  run consequently saves almost nothing — when every line is a diagnostic,
  completeness beats compactness on purpose. A stub filter that returns a
  cheerful "ok" for a failing run is rejected; that case is a test.
- The Stop guard counts `ats-verify` as a verification command and parses its
  `ats-verify: red exit=N` verdict, so wrapped checks reach the outcome ledger.
  `ruff format --check` now counts as verification too.
- New `ats-verify`: run one check, keep the failure. A filter that shrinks a
  *failing* test run to nothing is worse than no filter — a red result with no
  evidence is indistinguishable from a broken wrapper, and observed today:
  `rtk pytest` on a failing test printed zero bytes and exit 1. `ats-verify` is
  asymmetric on purpose: compact on green (288-test run: 35 lines to 3), every
  decisive line in source order on red, with a raw-tail floor so red is never
  empty. One execution, exit code passed through, full log kept on disk,
  stdlib only. `goal-check` now projects a failed oracle through it instead of
  a blind `tail -5`, which could drop the one line that named the failure.
- The Stop hook now tracks outcome, not only cost. The ledger records the exit
  status of verification commands (pytest, cargo test, go test, npm/bun test,
  just/make check, ruff, mypy, tsc) from Codex and Claude transcripts, keeping
  only call ids, never command text. `session_guard.observed.verify_status` is
  `none`, `green` or `red`; a red last run adds the `last_verification_failed`
  warning and a one-time system message: do not report done or count a saving
  until the check is green. Fail-open, warns only, never blocks STOP. Old guard
  state without the new counters falls back to one full replay.
- Codex's cache-write counter is no longer invisible. Codex reports
  `cache_write_input_tokens` as a subset of `input_tokens`; that field was
  unknown to both the pricer and the ledger, so a Codex prefix re-written every
  turn reported zero writes, no verdict and a flattering saving — the one
  stream shape the diagnosis exists to catch was the one it could not see.
  Anthropic's disjoint `cache_creation_input_tokens` still adds to the input
  total, the Codex subset field does not.
- New regression test: the prompt gate's injected context must be byte-identical
  across runs. That string sits inside the host's cached prefix on later turns,
  so a clock, counter or session id leaking into it would break cache reuse
  silently.
- `ats-cache` and the ledger now name the cache failure mode instead of only
  reporting a rate: `write-only` (prefix written every turn, never read back),
  `rewriting` (more written than read), `uncached`, or nothing at all when the
  run is healthy. A re-written prefix previously surfaced as a low hit rate and
  a small negative saving, which reads like rounding noise rather than the
  1.25x write penalty on every input token it actually is.
- The compact default and README now name two vendor-documented cache failure
  modes: a byte-identical prefix still misses once the breakpoint drifts past
  the 20-block lookback window, and a mid-wave tool/catalog load or compaction
  voids the prefix from the first changed token. Both make lazy loading and
  eager compaction cost a full re-write, which the previous "keep it
  byte-identical" wording did not cover. Cache price ratios re-verified against
  the published tables on 2026-08-31: unchanged.
- The cache pricer is now reachable as a command: the installer links
  `~/.local/bin/ats-cache` to the installed `cache_economics.py`, next to the
  existing doctor, ledger and audit launchers. Before this it existed only as
  a shell function in `integration/cli/agent-token-saver.sh`, so Codex, Claude
  and any other host that runs commands rather than sourcing a helper could
  not price a cached prefix at all. Covered by a new installer test that runs
  the launcher end to end.
- `agent-token-saver doctor` now reports Codex hook trust. Codex 0.147 refuses
  to run a hook without a persisted `[hooks.state]` entry, and that trust is
  keyed by event *position*, so another tool inserting an entry ahead of ours
  silently disables the gate or the guard while `hooks.json` still looks
  correct. The doctor prints `N trusted` or `N UNTRUSTED`, and stays `unknown`
  when the host keeps no trust table at all.
- `cache_economics` accepts camelCase usage blocks (`inputTokens`, `cacheRead`,
  `cacheWrite`) from JS hosts such as GG Coder, and now exits non-zero on a
  payload with no recognised token counters instead of printing a confident
  0-vs-0 report.
- The Stop guard now prunes its own per-session state: files older than 14 days
  are removed on write, keeping the current session and `-latest`. One file per
  session with no expiry path meant `~/.local/state/agent-token-saver/` grew
  without bound for the lifetime of the installation.
- The prompt hook rotates `hook-events.jsonl` at 1 MB into one `.1` generation
  instead of appending to it forever.
- `integration/hooks/token-session-guard.py` no longer returns from a `finally`
  block. Python 3.12+ emits a `SyntaxWarning` for that pattern, which the Stop
  hook printed to the host's stderr on every run, and the `return` silently
  discarded any in-flight exception from the state write.

- `scripts/codex_provider_ab.py` now computes weighted (cache-priced) A/B
  numbers in code instead of leaving them to the hand calculation quoted
  below. `summarize_pair()` gains a `weighted_delta` block and `aggregate()` a
  `weighted` block, both via `cache_economics.compare()`; the markdown report
  shows raw and weighted savings side by side plus cache hit rate per arm and
  the ratio profile with its verified date. Raw provider counters stay
  authoritative and visible, because raw and weighted can disagree; weighted
  stays a labelled list-ratio estimate against a no-cache counterfactual, not
  an invoice. The harness prices itself with `openai-gpt-5.6-terra`, the model
  it actually drives, rather than the Anthropic default.
  `result.json` `schema_version` 1 -> 2 for the new keys; existing artifacts
  remain valid v1 records.
- Re-checked the hand-computed ratios quoted below against vendor pricing on
  2026-08-25 and corrected two of them. Cache reads are 0.1x as stated, but
  `gpt-5.6-terra` output is 6x its input ($12.00 vs $2.00 per MTok), not the
  8x used in that prose, and OpenAI now charges an explicit 1.25x cache write
  rather than writing for free. Weighted *input* savings therefore stand;
  weighted *total* moves slightly. `tests/test_cache_economics.py` pins every
  profile to its published per-MTok prices so the next ratio change fails a
  test instead of ageing quietly in a changelog entry.
- New `scripts/cache_economics.py` prices a cached prefix instead of counting
  raw tokens, and is the single place ratios live. It folds both vendor usage
  conventions into one shape (Anthropic reports `input_tokens` excluding
  cache; OpenAI reports it including cache with `cached_input_tokens` as a
  subset), reports cache hit rate, and expresses savings against an explicit
  no-cache counterfactual. Wired into `full_context_ledger.py` (optional and
  fail-open: a missing module degrades to the previous cache-unaware output)
  and exposed as `ats-cache` for a markdown, JSON or one-line statusline view.
  The installer ships it beside the installed ledger as a managed asset, so an
  installed ledger keeps pricing the prefix.
- Compact policy gains cache hygiene, the behavioural half of the same
  problem: grow context append-only, keep clocks and session ids out of a
  cached prefix, hold tool definitions stable within a wave, and compact at a
  stable boundary. `tests/test_prompt_hook.py` now asserts the hook's own
  injected context is byte-stable across runs and carries no timestamp or
  session id, since that text sits inside the cached prefix it protects.
- Three repeated live provider A/B runs with `gpt-5.6-terra` (3 tasks per run,
  fresh HOME per arm, all oracles passed in every run) replaced the previous
  single-run reporting. Two findings survived the noise. First, raw token sums
  misprice a cached prefix: Lean shifts fresh input into cache hits, so the
  unweighted sum reported +11.4% / +0.9% / -4.4% while the same runs are
  -18.8% / -20.1% / -7.8% at public list ratios (cached 10%, output 8x).
  Second, Lean is markedly more reproducible: across runs, uncached input on
  the noisy tasks varied by 100 and 466 tokens under the compact policy versus
  7,159 and 9,989 for the baseline. Identical baseline runs differed by up to
  2.2x on one task, so every earlier single-run headline (including
  2026-07-15) sits inside that noise; the README now says so and links all
  three artifacts. RTK engaged in no arm of any run, so the measured deltas
  come from the prompt and Stop hooks alone. Also reran the local fixture
  matrix (raw 406,991 -> lean 3,803) and the hook hot path (only drift versus
  the pinned ref is the capsule version string, p50 ~22 ms).
- Tested a reworded compact policy (name rtk first, forbid invented one-liner
  projections) across two further live A/B runs and reverted it. An early
  variant that let the model skip projection when it judged output "already
  small" made it paste a full 165 KB process table, tripling output tokens on
  the task the policy exists for; the corrected variant matched the shipped
  wording within noise. No measured gain, so the shipped policy text is
  unchanged.

- Rewrote the README as an invitation instead of a wall: hero pitch plus a
  60-second dry-run install above the fold, one credible headline number
  (the real Codex A/B, 19.67%), condensed benchmark sections that link to the
  full artifacts, and 441 -> ~210 lines. The full AgentMaster protocol
  (lane selectors, oracles, opt-in extensions) moved unchanged to
  `docs/AGENTMASTER_PROTOCOL.md`; the README keeps a short pointer section.
  All honesty constraints stay: per-task regression shown, estimate vs.
  provider-counter labeling, no universal-savings claim.
- Integrated cache-aware warm handoffs into the compact always-on policy and
  Stop guard without auto-loading another full skill. Model and effort stay
  stable per wave. A checkpoint uses one reference-only 300–700-token artifact
  with the next oracle and test checklist before a cache-expiring pause or hard
  context threshold. The hook still warns only and never writes, continues or
  blocks.
- Added OpenRouter `stealth/ox-alpha` as the explicit `ox-alpha` free lane.
  The 2026-08-22 catalog reports a 1,048,576-token window, mandatory reasoning,
  131,072 max output tokens and zero prompt/completion price. The adapter sends
  the lowest supported effort with returned reasoning excluded and keeps this
  stealth alpha out of `free` and `all` until it has repeated oracle evidence.
- Removed the retired `openai/gpt-oss-20b:free` and
  `inclusionai/ling-3.0-flash:free` catalog slugs from routing and benchmark
  defaults. Their paid replacements are not promoted without measurements and
  an explicit paid budget; the Hermes benchmark fallback uses the existing
  Nemotron free lane instead.

- Found while re-verifying after an unrelated benchmark fix: the installer's
  `self_update()` runs a real `git pull` against the actual repo checkout on
  every install, regardless of `--project`. 15+ installer tests each doing a
  live network pull made the suite non-hermetic and intermittently
  timeout-flaky (60s subprocess timeout hit under rapid repeat invocation,
  even though a single standalone `git pull` took <1s). Added
  `ATS_SKIP_SELF_UPDATE=1`, set only by the test harness; real installs are
  unaffected. Full suite: 110-126s and occasionally flaky -> 42-43s and
  clean on two consecutive runs.

- `scripts/token_stack_matrix_benchmark.py` crashed outright when the optional
  Ponytail comparator skill was not installed (`FileNotFoundError`), which took
  down the four unrelated stack rows (native/RTK/Tilth/context-mode) that do
  not depend on it. Now degrades: the Ponytail-only row is marked
  not-accepted with an explicit reason, `ponytail.available: false` is in the
  JSON output, and the rest of the matrix still runs. Found while checking
  the tool stack is current and used correctly on this host; also surfaced
  that the locally installed `agent-token-saver` was stale (2026-08-15,
  before this session's fixes) with a failing `doctor` integrity check --
  reinstalled from the current repo, integrity now clean.
- CI pins the Python version instead of letting uv pick the newest available.
  `requires-python = ">=3.11"` was an unverified claim: every job silently ran
  3.14, so nothing proved the documented floor worked. Tests now run on every
  supported version, **3.11 through 3.14**, on Linux, plus the floor and
  latest on macOS.
- Three test files spawned a bare `"python3"` subprocess instead of
  `sys.executable`. That interpreter can differ from the one running the
  suite (the tests prepend a fixture `bin/` to `PATH`), which both caused an
  intermittent installer test failure and let a version silently escape the
  CI matrix. Now consistent with the rest of the suite.
- `scripts/install_agent_token_saver.py` exits with a clear message on
  Python <3.11 instead of failing deep inside the stdlib with an
  unrelated-looking error. Verified on 3.10.

## 4.24.0 — 2026-08-18

- 2026-08-18: **Fixed the red CI and the broken fresh-install gate.**
  `neutral_install_smoke.sh` ran `doctor --require-llmadapter`, so a host
  without Bun failed the install gate even though the README documents the
  adapter as optional. Because the JSON report was redirected to a file, the
  failure printed nothing at all — CI and users got a bare exit 1. The smoke
  now gates on the portable core, asserts the documented `bun_missing`
  degradation when the runtime is absent, exercises the adapter lane only
  where Bun exists, and prints the doctor report on failure.
- 2026-08-18: CI now runs tests and the neutral install on macOS as well as
  Linux, plus a dedicated Bun lane so the optional adapter stays covered.
- 2026-08-18: Removed absolute `/Users/<name>/...` paths from 11 published
  benchmark artifacts, which leaked the maintainer's username and unrelated
  private project names. The guard test now scans the whole benchmark
  directory instead of a hand-listed allowlist that missed them.
- 2026-08-18: README states supported OS and runtime requirements.
- 2026-08-15: Let the compact host policy consume the router's bounded
  multi-phase result: one primary plus at most four independently relevant
  support skills; preserve zero/one routing for ordinary single-phase work.

## 4.23.0 — 2026-08-14

### Fixed, Re-Install und Doku-Drift, 2026-08-14

- `install_agent_token_saver.py`: ein zweiter Install-Lauf brach mit
  `PermissionError` ab, sobald ein Host eine installierte Skill-Kopie
  read-only markiert (Hermes setzt `0444`). `install_copy` stellt jetzt kurz
  owner-write her, um die eigene vorherige Ausgabe zu ersetzen, und verweigert
  symlinkte Ziele. Re-Install ist damit idempotent (+Regressionstest).
- Manifest-Refresh: `config.json` trug den `llmadapter`-Hash vom 2026-08-01,
  waehrend das installierte Binary bereits dem Repo-Stand (`f37da47`,
  2026-08-03) entsprach. Der Doctor meldete deshalb
  `BLOCKED managed_asset_hash_mismatch`; nach dem Refresh wieder
  `status=full`, Integritaet ohne Fehler.
- SKILL.md nennt keine volatile Lane-Zahl mehr (dokumentiert waren nacheinander
  23 und 28, real: 27 builtin, 43 inklusive host-lokaler Lanes). Ein portables
  Skill mit host-spezifischer Zahl ist auf fremden Hosts konstruktionsbedingt
  falsch — `llmadapter lanes` ist die einzige Wahrheit, Selektoren sind der
  stabile Vertrag. Neuer `tests/test_skill_doc_drift.py` haelt das fest und
  prueft zusaetzlich, dass die `.agents/`-Kopie nicht hinter der kanonischen
  Quelle zurueckfaellt.

### Added, vier neue cheap-Lanes, 2026-08-03

- OR_CHEAP: deepseek-v4-flash-0731 (0.09/0.18), qwen3.7-flash (0.03/0.13),
  gpt-5.6-luna-pro (0.10/0.60), kat-coder-air-v2.5 (0.15/0.60). Alle vier
  live geprobt (1,3-5,3 s). Katalog-Sweep nach created-Datum, datierte
  deepseek-ID statt ~latest-Alias.

- **feat: `goal` is a real command, not a shell function.** The 13 `goal-*`
  functions only existed inside a shell that had sourced the wrapper, so hooks,
  cron jobs and agent sessions could not reach them: `which goal-init` returned
  nothing. `integration/cli/goal` is a dispatching shim (`goal <verb> [args]` →
  `goal-<verb>`) that resolves its own symlink chain, sources `goal.sh` from the
  repo, and passes exit codes through unchanged. Install with
  `ln -sf <repo>/integration/cli/goal ~/.local/bin/goal`. Unknown verbs exit 2
  and print the dispatchable set; `goal verbs` lists them. Test check 37 covers
  syntax, `goal doctor`, verb dispatch and the unknown-verb guard.

- **fix: swarm calls now reach the health ledger.** `ledgerWrite` ran only on the
  v1 `ask` path, so lane health — the thing that decides which lanes a class
  selector runs — learned from `ask` and nothing at all from `ask-v2`, which is
  where the real traffic is. `runLaneV2` writes on success, failure and cache
  hit; a `pruned` lane is not evidence about a provider and stays out. The
  ledger is a local JSONL file, never part of the wire envelope.
- **docs: the surface an agent actually reads now names the measured band.**
  `SKILL.md` still described 23 lanes and only plain `ask`; the prompt hook's
  `agent_cost_route` told agents to use "free/local llmadapter proposals", which
  is now the measurably worse default. Both name `--lanes cheap --allow-paid`
  with its numbers, and the hook keeps it behind the user's consent to spend.
  End-to-end over five closed-form tasks, three reps, majority vote of a 3-lane
  swarm: `free` 8/15, `cheap` 15/15 — free scored 0/3 on two of the five tasks.
  One measured cheap swarm costs $0.000127.
- **feat: `--contract verdict|prose|json` — the swarm answers in the shape you
  asked for.** The capsule was built for verification, so every worker had to
  reply `STATUS: PASS|FAIL|BLOCKED`, which made the v2 swarm unusable for prose
  and structured output; the workaround was to fall back to plain `ask` and lose
  deadlines, accounting, first-pass and the ledger. What makes a worker cheap is
  the capsule — one objective, no peer chatter, no transcript, evidence
  discipline — not the shape of its answer. `verdict` stays the default and stays
  byte-identical, so AgentMaster, which passes no `--contract`, sees nothing new.
  Under `prose`/`json` with no evidence block the oracle line changes too:
  demanding a verdict from evidence that was never supplied made `gpt-oss-120b`
  answer "I do not have the evidence" instead of the objective.
- **feat: a `cheap` lane band, because frontier output stopped being expensive.**
  `openai/gpt-5.6-luna` is $0.10/$0.60 per million tokens with a 1.05M window;
  `moonshotai/kimi-k3`, the lane table's only other non-free option, is
  $3.00/$15.00. Measured over three closed-form reasoning tasks with a known
  answer, three samples each: `gpt-oss-120b` 9/9 correct at $0.00046 per nine
  calls, `gpt-5.6-luna` 9/9 at $0.00093, `kimi-k2.5` 8/9 at $0.00303,
  `ling-2.6-flash` 7/9 at $0.00002, the best free lanes 6-7/9 at $0. Free lanes
  buy a 20-30 point correctness drop to save five thousandths of a cent.
  `--lanes cheap` selects the measured band. It is a selector keyword, not a
  fifth class: the wire `class` stays `paid` because AgentMaster validates that
  set, and the band still needs `--allow-paid`. `lanes` now prints the per-lane
  output price. `poolside/laguna-s-2.1` paid looked like a member on one sample
  and scored 5/9 over nine — worse than its own free variant, for money.
- **feat: lane selection follows measured health, not table order.** A class
  selector returns more lanes than the worker cap takes, so the cap decided who
  ran, and that was always the first three in the table. `pickLanes` now orders
  class selectors by a Laplace-smoothed success rate over the last 7 days of the
  ledger — which already ranked both broken lanes last without being asked.
  Explicit `--lanes a,b,c` keeps the caller's order. `LLMADAPTER_LANE_HEALTH=0`
  opts out.
- **fix: aggregation, verification and council synthesis no longer pin a lane.**
  All three named a fixed lane, so one outage lost the whole step —
  `gpt-oss-20b` was the pinned verifier while the ledger recorded it at 5/10.
  They pick by health now, with the verifier held to a different vendor family
  than the aggregator so the cross-check stays independent.
  `LLMADAPTER_AGGREGATE_LANE` / `_VERIFY_LANE` / `_COUNCIL_LANE` still pin by name.
- **fix: duplicate built-in lane names now fail at startup.** A free model and
  its paid twin resolve to the same short name, which would give them one shared
  health record and make `--lanes <name>` ambiguous.

- **fix: free reasoning lanes return an answer instead of a truncated
  deliberation.** OpenRouter's free reasoning models emit their chain of thought
  as visible content, so at a 400-token ceiling they spent the whole budget
  arguing about the worker contract and returned nothing usable — while the
  envelope still said `succeeded`. Remote lanes now send OpenRouter's
  `reasoning` field, off by default. Measured over 12 free lanes x 2 objectives:
  median completion tokens 400 to 39, truncation 4/24 to 0/24, worker-contract
  compliance 25% to 88%. Two lanes are measured exceptions and are configured as
  such: `gpt-oss-20b` returns an empty completion when it receives
  `enabled:false`, `nemotron-nano-9b-v2` needs `exclude`. `LLMADAPTER_REASONING=on`
  restores the old request.
- **fix: a dropped socket costs a retry, not the lane.** A connection closed
  mid-burst throws out of `fetch` instead of returning a response, so it bypassed
  the per-lane retry entirely — one transient close killed the lane in both `ask`
  and `ask-v2`. Transport failures are now retried (`ask`: three attempts,
  `ask-v2`: one extra attempt, and only while the controller deadline still
  leaves room for a whole call). An abort or a real deadline stays terminal.
- **fix: a provider that stops at the token ceiling reports `output_limit`.**
  `ask-v2` reported `finish_reason: "length"` as `succeeded`, which made a
  truncated deliberation look like a result. CLI lanes already reported the same
  case as `output_limit`; the HTTP path now matches. `output_limit` is an
  existing terminal value, so the AgentMaster envelope is unchanged.
- **fix: removed the dead lane `poolside/laguna-m.1:free`.** OpenRouter answers
  "No endpoints found" — it left the catalog, so the lane could only fail.
- **feat: `doctor` verifies model ids, `doctor --probe` verifies availability.**
  Plain `doctor` now checks every configured OpenRouter model against the live
  catalog, which is what would have caught `laguna-m.1`. Catalog presence is not
  availability, so `--probe` spends one 32-token call per free lane and reports
  which lanes actually answer today.
- **docs: worker-capsule wording kept, on measurement.** Two rewrites derived
  from the local prompt-library corpus were A/B-tested against the incumbent
  capsule on free lanes: an explicit "first token is STATUS:, no preamble, no
  meta-commentary" contract (29% vs 45% compliance) and an anti-fabrication
  oracle line (8/20 vs 11/20 compliance at 2.2x the tokens). Both lost. The
  chain-of-thought problem was a request-parameter problem, not a wording
  problem.
- **fix: a busy provider is no longer reported as missing evidence.** Exit code
  4 from the evidence provider now yields the note `evidence_provider_busy`.
  The difference is operational: busy is worth retrying, unavailable is not, and
  collapsing the two teaches an operator that a query has no sources when it has
  plenty.
- **fix: the provider is told how long it has.** The adapter passes
  `LLMADAPTER_EVIDENCE_DEADLINE_MS` so the provider can bound itself instead of
  guessing — a guess either wastes the budget or gets killed mid-write, which
  reaches the controller as "no evidence".
- **feat: `primary` evidence mode.** Ask the provider's primary-source registry
  before the general web, so a version, price or policy claim can cite whoever
  owns the fact instead of the best-ranked article about it. Available to
  `evidence --mode primary` and `ask-v2 --evidence-mode primary`.
- **feat: `llmadapter evidence` gathers without spending a model token.** No
  lane runs: it resolves the cache, calls the configured provider, projects the
  result, writes a private `0600` artifact and prints a report with
  `model_tokens_spent: 0`. This is the primitive a controller needs to gather
  once and hand N workers a path instead of a payload.
- **feat: `--oracle-env-prefix NAME`.** A controller usually already has an
  oracle written against its own variable names. Without an alias that oracle
  reads an empty path here, never passes, and `--first-pass` silently becomes a
  full-price run with nothing pruned — measured, then fixed: with the alias the
  same run took one oracle call instead of three and pruned a lane mid-flight.
- **fix: `--first-pass` no longer breaks the status/exit invariant.** The v2
  contract fixes exit 0 to mean status `ok` or `partial`; folding a rejected
  oracle into the exit code produced `partial` with exit 1, which a strict
  controller rejects. status/exit describe lane outcomes; the oracle verdict
  lives in `first_pass.winner`, and pruned peers make the lane status `partial`.

- **feat: `llmadapter --first-pass` with an executable oracle.** All selected
  lanes start together, the oracle decides one answer at a time, and the first
  PASS prunes the peers. Losers keep a record with terminal `pruned`. The oracle
  is a shell command whose exit code is the verdict; it reads the answer from a
  private `0600` file through `LLMADAPTER_ANSWER_PATH` and never from argv.
- **feat: `--budget-tokens` is enforced, not requested.** An input estimate over
  the budget refuses before the call, a CLI lane's stdout is bounded at four
  bytes per budgeted token, and a reported total over budget fails the record.
  Unlike `--max-tokens` this does not depend on provider cooperation.
- **feat: `--evidence` supplies the fresh fact tool-less lanes may not claim.**
  One primary-source artifact is gathered before the swarm starts, projected to
  `--evidence-bytes` and injected into every capsule. Order is url-cache →
  provider → projection → url-cache. No scraper is bundled: the provider is a
  host executable named by `LLMADAPTER_EVIDENCE_CMD`, called with the mode as
  its argument and the query on stdin. An artifact reporting a bot wall
  (`page_status: challenge`) is discarded, and the capsule then says evidence is
  unavailable and asks for BLOCKED; no bypass is attempted.
- **feat: `"opt_in": true` host lanes.** A heavy host lane (scraper, browser
  driver) is skipped by `all` and the class selectors and is reachable only by
  name, so asking for `cli` never starts a scrape.
- **feat: `--skill-route` uses `si` instead of the four built-in regexes.** One
  skill, by path, into the capsule. Fail-open: no `si`, no hit or bad JSON means
  no skill line.
- **feat: `llmadapter council`.** The same worker stage plus one fresh-context
  lane that reports CONSENSUS, DISSENT and CONFIDENCE. `--tier` aggregates and
  `--verify` checks a single answer; a council names the disagreement.
- **feat: `llmadapter cache-export`.** Snapshot the private v2 cache as JSONL,
  optionally loaded into DuckDB. Answers are hashed unless `--with-answers` is
  passed; the live cache stays where it is, at `0600` under
  `~/.agent-token-saver`.
- **perf: worker capsules are memoised per objective.** A wide fanout stops
  rebuilding the same packet once per lane. This removes repeated string work,
  not tokens.
- **compat: every addition above is off unless its flag is passed.** AgentMaster
  parses the capability contract and the result envelope with
  `deny_unknown_fields` and a closed terminal enum, so the default `contract`
  output and the default `ask-v2` envelope are unchanged, and `pruned` can only
  appear under `--first-pass`. `contract --extended` advertises the extensions
  for controllers that opt in.

- **feat: compact defaults are now real host defaults.** Lean, teams and heavy
  installs merge one marker-owned, hash-verified policy into Codex
  `AGENTS.md`, Claude `CLAUDE.md`, an existing Hermes `SOUL.md`, and GG
  Coder's home `AGENTS.md`. User text is backed up and preserved; `minimal`
  removes only the managed block. Doctor now fails on missing, altered,
  misplaced or unsafe defaults instead of treating an installed skill as
  automatic behavior.
- **feat: strict `llmadapter ask-v2` controller protocol.** Prompts use stdin or
  a regular file rather than argv; local lanes and a three-worker bound are the
  defaults. Remote and paid egress require explicit gates. One schema-versioned
  JSON result includes prompt hash metadata, per-lane terminal state and honest
  reported/estimated/unknown token coverage.
- **fix: bounded and complete worker accounting.** OpenRouter receives
  `max_tokens`, Ollama receives `options.num_predict`, CLI output and time are
  bounded, and any nonzero CLI exit fails. Accounting is written atomically
  with mode `0600` only after every selected lane reaches a terminal record;
  unknown cost is `null`, never synthetic zero.
- **security: v2 trust and lifecycle hardening.** Selection cap is total rather
  than concurrency-only. Egress gates follow lane kind and endpoint, CLI
  descendants run in a detached process group, HTTP and CLI bodies are bounded,
  prompt files are private/current-user only, and cache hits require the full
  protocol/capsule/command fingerprint plus a bounded string answer.
- **fix: independently verifiable accounting.** Every v2 lane record now exposes
  `call_started`; controllers can derive calls, cache hits and token coverage
  from terminal records and reject fabricated summaries. Pre-transport shield,
  key and spawn failures no longer count as calls.
- **fix: reproducible CLI wiring.** The installer now copies and links
  `llmadapter`; doctor probes only the hash-managed copy's providerless v2
  contract and reports Bun, launcher and capability readiness.
  `--require-llmadapter` makes that readiness fail closed.
- **security: redirect and host-lane trust.** HTTP redirects are rejected, and
  local lanes load only from a bounded, current-user-owned, non-symlink `0600`
  file opened with `O_NOFOLLOW` plus inode verification.

## 4.22.0 — 2026-07-27

- **fix: doctor blocks `synx doctor` in an active managed Codex/Claude hook.**
  `agent-token-saver doctor` now parses active hook command fields read-only and
  counts this known high-cost maintenance command without executing it or
  exposing unrelated commands. A configured agent with a match returns
  `forbidden_hot_path_synx_doctor:<agent>` and is not healthy. Use `synx doctor`
  only as an explicit, operator-run maintenance action — never per prompt/tool
  event.
- **feat: bounded worker guidance.** The Claude teams hook adds one scoped
  local/impact/freshness hint and a compact result contract; freshness asks the
  controller for a primary-source artifact rather than invoking a web tool.
- **fix: public benchmark hygiene.** Published artifacts retain aggregate
  measurements but exclude private paths, process IDs and raw controller output.
- **docs: lean public surface.** README, agent instructions and operating docs
  now keep the install, verification, boundary and measurement contract only.

## 4.21.0 — 2026-07-25

### PII-Shield auf jeder Remote-Lane · Worker-Contract als Hook · Skill auf Repo-Stand

- **feat: `integration/hooks/agent-worker-capsule.py` — der Worker-Contract als Hook statt als Hoffnung (2026-07-25).** Die Team-Regeln aus SKILL.md ("one closed objective, 300–700-Token-Capsule, PASS/FAIL-Oracle, max 3 Versuche, ≤500-Token-Ergebnis") standen bisher nur im Skill-Text — ein Controller, der das Skill nicht geladen hat, spawnt ohne sie. Der PreToolUse-Hook (matcher `Agent`) injiziert den Contract in **jeden** Spawn und zählt Spawns pro Session in `~/.agent-token-saver/cache/spawns-<session>.json`; ab Spawn #4 (`ATS_TEAM_MAX_WORKERS`, default 3) hängt eine Warnung samt Ledger-Hinweis dran. Fail-open in jedem Pfad: kaputtes JSON, fremdes Tool, nicht schreibbarer State → exit 0 ohne Ausgabe. Aus über `ATS_CAPSULE_OFF=1`. Verifiziert: 3× still, 4. Spawn warnt, `tool_name != Agent` bleibt stumm.
- **feat: Controller/Worker-Split dokumentiert und erzwungen.** Neuer SKILL.md-Abschnitt "Model split": teurer Controller (Opus/Fable) plant und verifiziert, Sonnet arbeitet. Die Durchsetzung ist `CLAUDE_CODE_SUBAGENT_MODEL` — laut Claude-Code-Doku überschreibt die Env-Var sowohl das Subagent-Frontmatter als auch den per-invocation `model`-Parameter, ist also der einzige Punkt, an dem der Split nicht umgangen werden kann.
- **docs: SKILL.md 3.8.1 → 4.20.0.** Der kanonische Skill hing 12 Minor-Versionen hinter dem Repo: `ats-recall`, der Synapse-CLI-Log-Ingest samt launchd-Job, `llmadapter` mit `--tier`/`--verify`/`--aggregate` über 23 Lanes, der PII-Shield, `ats-pipe --recall/--synth/--tier/--verify`, `ats-url-cache` und `ats-token-cfo` fehlten komplett. Neue Ladder-Stufe 1 ist jetzt Recall ("deine Agents haben das vielleicht schon gelöst"), weil die 2960 ingestierten Sessions genau dafür da sind. Propagiert nach `~/.agent-token-saver`, `~/.hermes`, `~/.gg`, `.agents/`; `config.json` trägt Version + sha256 + den neuen Hook als managed asset.
- **fix: `ats-token-cfo`, `ats-url-cache`, `synapse-ingest-cli-logs` waren nie auf PATH** — im Repo vorhanden, aber nicht verlinkt, also für jeden Agenten unsichtbar. Jetzt als Symlink in `~/.local/bin` (Repo bleibt Quelle der Wahrheit, kein Kopier-Drift).

- **feat: PII-Shield vor jeder Lane, die die Maschine verlässt (2026-07-25).** `llmadapter` hatte keinerlei Maskierung — `rg -il "redact|mask|pii|anonym|sanitiz" scripts/` fand null Treffer, während im Juli-Ledger 1 043 Lane-Calls stehen. Belegter Fall: `leads-fanout-classifier.py` schickt laut eigenem Docstring über Free-Lanes; laut Synapse-Eintrag vom 24.07. wurden so 301 deutsche Firmennamen klassifiziert — bei Einzelunternehmern ist der Firmenname der Personenname. Laut OpenRouter-Doku dürfen Anbieter auf Prompts trainieren, solange die Konto-Einstellung das nicht ausschließt, und diese Einstellung ist für Free-Modelle getrennt.
  Neu in `scripts/llmadapter.ts`: `shieldPrompt()` pseudonymisiert über `ggadapter/adapter/dsgvo-shield.mjs`, bevor der Prompt rausgeht, und stellt die echten Werte in der Antwort wieder her — vor Cache und Aufrufer, damit der auf den unmaskierten Prompt geschlüsselte Cache konsistent bleibt. `ollama` bleibt unangetastet (verlässt die Maschine nicht). Der Shield wird faul geladen; **fehlt er, bricht die Remote-Lane ab statt Klartext zu senden**. Pfad über `ATS_SHIELD_PATH`, bewusster Verzicht über `ATS_PII_SHIELD=0`.
  Verifiziert durch `tests/test_llmadapter_pii_shield.sh` — eine Sonden-Lane schreibt weg, was sie tatsächlich bekommen hat, das ist die Leitung. 7/7 Prüfungen grün: Name, IBAN und Mail nicht auf der Leitung, stattdessen `[[GGD_*]]`-Token, Antwort korrekt zurückübersetzt, Opt-out wirkt wirklich, fehlender Shield blockt. Läuft gegen ein Wegwerf-`HOME`, fasst also weder Cache noch Ledger noch `local-lanes.json` an.
  Bekannte Wechselwirkung: Der Shield ersetzt vollständige Firmennamen samt Rechtsform als eine Einheit, „Bäckerei Hufnagel GmbH" wird also zu einem Token und verliert den Branchenbegriff; bei Personennamen bleibt er erhalten („Zahnarztpraxis [[GGD_NAME_1]]"). Für `leads-fanout-classifier.py` ist das im Docstring dokumentiert samt der Alternative `LANES = ["ollama-gemma4"]`.

## 4.20.0 — 2026-07-25

### Daily auto-ingest — the recall loop stays fresh on its own

- **feat: `scripts/install-ingest-cron.sh`** — installs a launchd job that runs
  `synapse-ingest-cli-logs.py --since 2` daily (default 04:30). Resolves the
  REAL python binary (a `command -v python3` shell alias poisons the plist and
  fails with exit 78 — hit and fixed), sets a proper PATH so `synx` is found,
  loads it idempotently. Every new agent CLI session is recall-able the next
  day without any manual step. Job verified live: LastExitStatus 0, imports
  new sessions. The plist lives in `~/Library/LaunchAgents` (machine-local,
  outside the repo); this helper regenerates it on any machine with no
  hardcoded paths.

## 4.19.0 — 2026-07-24

### Compounding loop closed: `ats-pipe --recall` + 2960 sessions indexed

- **feat: `ats-pipe --recall`** — before fan-out, pull past-session hits from
  Synapse (via `ats-recall`) and prepend them to the context. Every run feeds
  the corpus (`synapse-ingest-cli-logs`), every run reads it back: the pipeline
  builds on what you already solved instead of re-deriving it. The deja-vu
  thesis, wired into the pipe.
- **fix: `ats-recall` brain-first** — CLI sessions bulk-import into the main
  brain (`cli-log://`), which `synx hybrid` searches in ~0s; the corpus
  sidecar search was 30s+ on the grown DB. Default flipped to brain; `--corpus`
  and `--both` opt-in. Recall now returns in 0s.
- **milestone:** the full backfill ran — **2960 agent CLI sessions**
  (Codex/Claude/aider/opencode, 3623 scanned) imported into Synapse, searchable
  via `synx hybrid` / `ats-recall`. Past solutions across every agent CLI are
  now one query away.

## 4.18.0 — 2026-07-24

### `ats-recall` — the recall front-end for the ingested CLI histories

- **feat(cli): `ats-recall "<q>"`** — "your agents already solved this."
  Searches the Synapse corpus (now holding the ingested Codex/Claude/aider/
  opencode sessions) plus the verified brain, deduped one block per source
  document (title + best snippet). `--corpus`/`--brain` to scope, `--limit N`.
  No LLM, no API — the deja-vu recall pattern over your own agent history.
  Pairs with `synapse-ingest-cli-logs.py` (that fills the corpus, this reads
  it). Verified: surfaces past llmadapter/build sessions from the CLI logs.

## 4.17.0 — 2026-07-24

### Tiered fan-out engine + Synapse CLI-log ingest + measured savings

- **feat(llmadapter): `--tier`** — the full pilotfish/Anthropic pattern in one
  flag: 5 cheap proposers → strong aggregate (nemotron-super) → fresh
  INDEPENDENT verify (gpt-oss, different family so it is a real cross-check and
  never rate-limits the aggregator twice). `--verify` adds the fresh-context
  check to any answer (`LLMADAPTER_VERIFY_LANE` override). Verified: 17×23 →
  391 VERIFIED; "capital is Sydney" → CORRECTION: Canberra.
- **feat: `ats-pipe --tier`/`--verify`** delegate to the engine (removed the
  bash verify — one implementation, cached + ledgered).
- **feat: `synapse-ingest-cli-logs.py`** — closes the deja-vu recall gap:
  Codex (1346), Claude Code (5314), aider, opencode session JSONLs were never
  in Synapse. Extracts user+assistant turns → `synx corpus add-text --embed`,
  fail-open, state-file dedup, `--since/--limit/--sources`. Verified: ingested
  sessions are searchable via `synx corpus search`.
- **measured savings (this session, real ledger + clean run):**
  cache hit 20807ms → 22ms (**946×**); cache-hit rate 12.6% of 554 calls =
  ~166k tokens not spent; `--tier` uses 5 proposers vs 14 (64% fewer proposer
  calls); parallel wall = slowest lane, not the ~92s sum the session-start
  Python swarm paid.

## 4.16.0 — 2026-07-24

### `ats-pipe --verify` — fresh-context verifier gate (stolen from the 500-repo sweep)

Evaluated 10 candidate repos from a 500-repo sweep against ATS. Adopted the
one idea with Anthropic-benchmarked backing and no dependency weight: a
fresh-context verifier beats self-critique (per the Fable 5 multi-agent docs;
pilotfish/tura use the same pattern).

- **feat(cli): `ats-pipe --verify`** — after the fan-out/aggregate produces an
  answer, one strong fresh-context lane checks it and replies `VERIFIED` or
  `CORRECTION: <fix>`. Costs one extra call; catches confident-wrong
  consensus. `--verify-lane` / `ATS_PIPE_VERIFY_LANE` pick the verifier
  (default `nemotron-3-super-120b-a12b`, free). Verified 2026-07-24: correct
  answer → VERIFIED; planted "17×23=371" → "CORRECTION: 391".
- **evaluation notes** (idea-adoption, not deps — bench-before-adopt):
  pilotfish tiered plan/execute/verify = adopted (verify gate). deja-vu/paxm
  memory = redundant with the local Synapse KB (311k docs incl. chat logs).
  waggle 30-byte context refs = the url-cache already does content-addressed
  storage; low marginal gain for stateless LLM fan-out. tura turn-reduction =
  applies to agent loops, ats-pipe already gathers once. fastctx/agent-chief/
  brain0/klaatcode/contextvc = adjacent surfaces, not core-thesis fits.

## 4.15.0 — 2026-07-24

### Local-only lane overlay — private CLIs stay off the deployed surface

- **feat: local lane overlay** — `llmadapter.ts`, `ats-swarm-bench.py` and
  `ats-jury-bench-v2.py` now load extra lanes from
  `~/.agent-token-saver/local-lanes.json` (a file OUTSIDE this repo, so it is
  never committed or deployed). Each lane carries a `cmd` array with a
  `__PROMPT__` placeholder. Fail-open when the file is absent — the tracked,
  deployable code ships only the portable lanes (OpenRouter free/paid,
  Ollama, and the always-installable CLI agents).
- **refactor:** removed the hardcoded personal-account CLI lanes from tracked
  source (they were subscription/quota-bound and not portable). They remain
  fully usable locally via the overlay file. `PAID_LANES` prefix generalized
  to `paid_`.
- **repo hygiene:** `integration/cli/devincontrol` and the personal-lane
  benchmark artifacts are untracked (`git rm --cached`) and gitignored;
  `local-lanes.json` is gitignored. Nothing was pushed — these commits are
  local-only (last push predates this work).

## 4.14.0 — 2026-07-24

### One fan-out engine: ats-pipe routes through llmadapter (all features together)

Consolidates the two fan-out paths. `llmadapter` (fast, cached, direct
OpenRouter HTTP, `--aggregate` consensus, `--first N` hedged race) becomes the
default FANOUT engine for `ats-pipe`; the Python `ats-swarm-bench` stays as the
metrics/jury tool and the fail-open fallback.

- **feat(cli): `ats-pipe` engine = llmadapter** — GATHER (recon) → FANOUT
  (`llmadapter ask`) → SYNTH (`--aggregate`). New flags: `--lanes
  free|paid|local|cli|all|name,…`, `--first N` (race), `--engine
  auto|llmadapter|swarm`. `--only <lane>` maps to `--lanes`; `--synth` maps to
  `--aggregate`. Verified 2026-07-24: local gather + `--first 3` → 3 answers in
  4.2s (was 22-100s on the Python path); `--synth` → 4 answers 1.2s + consensus
  "Paris"; `--engine swarm` fallback still fans out.
- **behavior:** `--engine auto` picks llmadapter when on PATH, else swarm.
  Swarm-only flags remain `--system/--workers/--timeout`; the swarm fallback
  now maps a specific `--lanes <name>` to its `--only`.
- This supersedes the v4.13.0 Python `--synth` path (kept as fallback). The
  parallel `llmadapter` (v4.12.0) is now the shared engine — no second
  fan-out system to maintain.

## 4.13.0 — 2026-07-24

### Pipeline complete: `--synth` merges the fan-out into one consensus answer

`ats-pipe` is now the full loop: GATHER → FANOUT → SYNTH.

- **feat(cli): `ats-pipe --synth`** — after fanning the question across the
  $0 lanes, collect every successful answer and have ONE free model merge
  them into a single consensus (keep agreements, resolve conflicts by
  correctness, drop hallucinations). Judge defaults to free `glm-5-2` via
  devin (`--synth-model` / `ATS_PIPE_SYNTH_MODEL` override). Verified
  2026-07-24: gather→fanout(claude)→synth(glm-5-2) → "Paris" in 22s, $0.
- **feat(swarm): `--sample-chars N`** (default 200) — controls how much of
  each answer the result keeps; `--synth` raises it to 4000 so full answers
  reach the judge instead of a 200-char preview.

## 4.12.0 — 2026-07-24

- New `scripts/llmadapter.ts` (Bun single-file, symlinked as `llmadapter`):
  one interface over all 23 verified lanes — 16 OpenRouter (14 :free +
  kimi-k3/k2.7-code), Ollama local, codex, agy, devin (single-flight),
  cursor, ggcoder, claude-haiku. Direct OpenRouter HTTP (kills ~3s
  hermes-python startup per call), jitter, concurrency pool, retry-once
  on transient provider errors, quota/auth/timeout/empty taxonomy,
  24h exact-hash response cache, `--aggregate` dedup via nemotron-super.
  Verified: 19/23 one-shot burst 160s wall; cache hit 0ms; kimi-k3 fixed
  via max_tokens cap. Known-down: gemma-4-31b + laguna-s-2.1 (provider),
  agy (quota, resets ~6d).
- llmadapter best-practices round: `--first N` hedged-request race mode
  (3 answers in 2.2s vs 49s full burst), per-call usage capture
  (provider-reported for OpenRouter/Ollama, bytes/4 estimate for CLI
  lanes), monthly JSONL ledger in `~/.agent-token-saver/ledger/`,
  `stats` subcommand, `--usage-out` emitting hermes-style usage JSON
  verified through `agent-token-ledger --usage llmadapter=FILE` (48/53
  tokens reported end-to-end), normalized cache keys (case/whitespace
  insensitive), 429-vs-hard-quota retry split, per-kind default
  timeouts (openrouter 90s, ollama 120s, cli 170s), `--max-tokens`.

## 4.11.0 — 2026-07-24

### General fan-out + `ats-pipe` research pipeline shim

Turns the swarm from a fixed benchmark into a reusable pipeline stage.

- **feat(swarm): `--prompt <text>`** (`-` reads stdin) — override the built-in
  extraction probe with any prompt. The bench becomes a general $0 fan-out
  engine: one prompt across every free/subscription/local lane in parallel.
- **feat(cli): `ats-pipe`** — one-shot GATHER→FANOUT pipeline bundling the
  tools already installed:
  - GATHER: `ats-recon` (gmax/ghx/supacrawl, default) · `--web` superweb
    research/qa · `--github` ghmax code recon · `--url <u>` scrape one page.
  - FANOUT: pipes `question + gathered context` into `ats-swarm-bench
    --prompt -` across the $0 lanes.
  - Flags anywhere (before/after the question); `--only/--skip/--system/
    --workers/--timeout` pass through; `--gather-only` stops after context.
  - Every stage fail-open: dead gather → no-context fan-out; dead lane →
    honest failure; ANSI-stripped and capped at 6k chars so noisy tool output
    never floods model context. Symlinked to `~/.local/bin/ats-pipe`.
- Verified 2026-07-24: `--github` gather returns ghmax recon; end-to-end
  gather→fanout→claude answered in 9s at $0.

## 4.10.0 — 2026-07-24

### System-prompt support + Cursor lane

- **feat(swarm): `--system <text>`** — writes the instruction as an `AGENTS.md`
  in a per-run dir AND prepends it to the prompt. Devin and Cursor honor the
  native `AGENTS.md` rules mechanism; every other lane gets the prepended
  instruction. Verified 2026-07-24: distinctive-token tests reflected the
  system prompt (Devin `SYSCHECK-7788 PARIS`, Cursor `CURSORCHECK-4455 PARIS`,
  swarm `--system` run `ZZTOP-9911` prefix on cursor output).
- **feat(swarm+jury): `cursor_composer` lane** — `cursor-agent -p --force
  --output-format text --model composer-2.5`. `--force` supplies
  non-interactive workspace trust. Cursor's Composer 2.5 runs on the Cursor
  subscription ($0 here). Measured: success 1.0, valid JSON.
- **auth(cursor):** `cursor-agent login` is a browser-callback flow (no code
  paste — the CLI polls the callback). Installed via `cursor agent` →
  `~/.local/bin/cursor-agent`. The GUI app's `cursorAuth/accessToken` is a
  session JWT, not accepted as `CURSOR_API_KEY`, so the login flow is
  required.
- **note(devin agent-config):** Devin also accepts `--agent-config <FILE>`
  (JSON/YAML: system instructions, tool visibility, permissions) and
  `.windsurf/rules/*.md`; the AGENTS.md path is the portable one shared with
  Cursor.
- **refactor:** `run_agent` takes explicit `prompt` + `run_cwd` (was hardcoded
  `EXTRACT_PROMPT` / `/tmp`), enabling the system-prompt run dir.
- Artifacts: `data/benchmarks/swarm-cursor-system-2026-07-24.json`.

## 4.9.0 — 2026-07-24

### Devin CLI wired headless + `devincontrol` + free GLM-5.2/SWE-1.7 lanes

Devin's agent CLI (`chisel`) ships inside `Devin.app` at
`.../extensions/windsurf/devin/bin/devin`, not on PATH. It has a real headless
`--print` mode — the earlier "no prompt frontend" claim was wrong. Wired it up
end to end.

- **auth:** `devin auth login` is a PKCE browser flow whose code prompt needs
  a real TTY (rejects piped stdin, and blocks on OSC 10/11 color queries).
  Automated it with a PTY driver (`TERM=dumb` + auto-answered terminal
  queries + prompt-aware code feeding). Login succeeded, credentials stored at
  `~/.local/share/devin/credentials.toml`. `devin` symlinked into
  `~/.local/bin`.
- **feat(cli): `devincontrol`** — thin wrapper: `ask "<p>"` (one-shot,
  default free GLM-5.2 High), `ask --swe`/`--model <id>`, `chat`, `list` and
  `show <id>` (reads the local `sessions.db`: id · title · date, replays
  `message_nodes`), `models`, `auth`, `which`. Default model
  `glm-5-2` (`DEVINCONTROL_MODEL` overrides). Symlinked to `~/.local/bin`.
- **feat(swarm): free Devin lanes** — `devin_glm52` (GLM-5.2 High) and
  `devin_swe17` (SWE-1.7 Max, beta), both **$0**. Measured 2026-07-24:
  GLM 20.6s, SWE 40.0s, both valid JSON. GLM-5.2 is the default (faster +
  preferred). Paid Devin models (sonnet-5/opus-4.8/fable-5) share a weekly
  quota that is currently exhausted — the bench catches
  "usage quota"/"weekly usage" as honest failures. New `--skip <substr>`
  flag + `PAID_LANES` so paid lanes are excluded from the $0-lane count.
- **feat(jury): devin_glm52 candidate** (free GLM-5.2).
- Artifact: `data/benchmarks/swarm-devin-glm-vs-swe-2026-07-24.json`.

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
