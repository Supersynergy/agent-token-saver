# Playbook — the universal token-saver path

One page, eight phases, a worked example each. The goal is not the smallest
context; it is the **fewest tokens spent per verified result**. Those are
different targets, and optimising the first one alone is how a session ends
cheap, fast and wrong.

Every command below was executed on 2026-09-03 while writing this file. Where a
number appears, it is measured, not estimated.

## The rule the rest of the page serves

```
Effectiveness = (closed loop) × (machine-checkable oracle) × (at bottleneck) ÷ waste
```

Saving tokens shrinks the denominator. Nothing on this page is worth doing if it
also shrinks the numerator — and three of the eight phases exist purely to stop
that happening.

## Phase map

| # | Phase | Question it answers | Primary tool |
|---|---|---|---|
| 1 | Recall | Did we already solve this? | `ats-recall` |
| 2 | Contract | What counts as done? | `goal-init` |
| 2b | Route | Which one skill applies? | `si route --max 1` |
| 3 | Locate | Where is the code? | `rg`, `code_nav`, Tilth |
| 4 | Fresh docs | What is the API *in the version I have*? | `freshdocs`, `--version` |
| 5 | Build | Smallest reversible slice | your editor |
| 6 | Verify | Did it actually work? | **`ats-verify`** |
| 7 | Account | What did it cost? | `agent-token-ledger`, `ats-cache` |
| 8 | Learn | So the next run is cheaper | `synx put` |

Phases 1, 4 and 6 are the ones that make the difference. Phases 3 and 7 are
where most people start, and they are the least valuable.

---

## 1. Recall — the cheapest tokens are the ones you never spend

Before any search, ask whether a past session already answered this. A recall
hit costs a few hundred tokens; re-deriving the answer costs thousands and may
land on a worse solution.

```bash
ats-recall --limit 3 "rtk pipe filter"
ats-recall --corpus "session guard incremental replay"
```

Output is a ranked block per hit, scored and labelled by kind:

```
══ verified memory (brain) ══
🔍 rtk pipe filter  →  3 hits
  0.016  fact  rtk
      [tools] rtk RTK (Rust Token Killer) — 60-90% token savings on build/test…
```

**Worked example.** The RTK version drift fixed in this repo was found because a
past session had recorded the 0.43 pin. Re-reading that note cost ~200 tokens.
Re-benchmarking the whole landscape to rediscover it would have cost tens of
thousands.

Stop condition: a hit that answers the question ends the phase. Do not "verify"
a recall hit by redoing the work it describes — verify it in phase 6, once, on
the real code.

---

## 2. Contract — an oracle before an edit

An oracle is a command whose exit code decides whether you are done. Without
one, every later phase is unfalsifiable and the token count is meaningless.

```bash
goal-init "make filter suite pass" --oracle "uv run pytest -q tests/test_ats_verify_rtk_filters.py"
```

`goal-init` enforces a **closed verb**: the title must contain a measurable
condition. It rejects "optimize", "improve", "polish" and — checked while
writing this page — "wire RTK per-tool filters", which was the first title
tried here. That rejection is a feature: an open verb has no failure state, so
it cannot end.

**Worked example.** The oracle for the filter work was *"every filter keeps the
failure signal and the exit code"*. That sentence is why the mypy filter was
caught regrouping `session.py:31` into a file header plus `L31:` — a check
written as "output is smaller" would have passed and shipped a worse tool.

A good oracle names a **behaviour**, never a size. `output is smaller` is not an
oracle. `red run still names the failing file and line` is.

---

## 2b. Route — one skill, named by the indexer, before the first edit

`si` indexes ~985 skills across every agent home on this machine and names
**one** for a task, or none. It is silent on doubt (`selected: []`), so an empty
answer is a result, not a failure.

```bash
si route "review my diff before merge" --max 1 --json
```

Measured 2026-09-04: 100 ms, 604 tokens of router output, then the one
SKILL.md it names (3,420 tokens for `code-review-excellence`). The honest
baseline is not "every skill" — nobody loads 2,137 files — but the 1,870
name+description lines a router-free system prompt would carry: **133k tokens
against 4k, 33x.**

The prompt hook already does this on every non-trivial prompt. Two things it
did not do until 2026-09-04, both found by reading the route log rather than
the docs:

- **The loop was open.** `si stats` reported a 3.5% apply rate — 7,090 routes,
  245 applied — and that number measured a telemetry gap, not the agents:
  `applied` was read only from GG Coder and Hermes sidecar files, while Claude
  Code and Codex, which produce nearly every route, reported nothing. The
  observer now also watches file reads and shell `cat`/`sed` of a `SKILL.md`,
  so a routed skill that is actually opened counts, and the adaptive ranking
  finally learns from the hosts that use it.
- **Every hook paid a shim tax.** `#!/usr/bin/env python3` resolved to a pyenv
  shim that cost 160 ms before the first line ran — twice per prompt, because
  the prompt hook launches the router as a subprocess. The installers now pin
  the real interpreter and the `si` launcher is a stub that imports a cached
  module with a pre-import fast path. Prompt hook: 280 ms to 120 ms. Observer
  on a non-skill Read, the most frequent hook event: 200 ms to 10 ms.

Hosts that merge the Claude and Codex hook files fired the prompt hook twice
per prompt (one in ten in the log). A same-session, same-prompt call within two
seconds is now suppressed; without a session id nothing is suppressed, so the
hook stays a pure function of its input.

## 3. Locate — exact before semantic, narrow before broad

Ordered by cost. Stop at the first rung that answers the question.

```bash
rg -n "VERIFY_CMD_RE" scripts
rg --files-with-matches "rtk pipe" docs integration
```

Only when structure genuinely matters, and only scoped to one project, reach for
an AST tool. Never point one at `$HOME`, a project collection or a cache.

**Worked example.** Finding where verification commands are recognised took one
`rg -n "VERIFY_CMD_RE" scripts` — two matches, ~40 tokens. A semantic index over
the repo would have cost a multi-thousand-token cold build to answer the same
question worse.

---

## 4. Fresh docs — read the installed thing, never your memory of it

This is the phase that separates a correct agent from a confident one. Model
memory of a CLI's flags, a filter's name or a default is a **stale hint**, and
acting on it produces code that looks right and fails in a way nobody sees until
production.

Order of trust:

1. **The binary on this machine.** `--help` and `--version` cannot be out of date.
2. **The installed source.** Read the dependency you actually import.
3. **Version-pinned local docs.** `freshdocs`, pinned to the version in the
   project manifest — not the newest release upstream.
4. **Upstream docs, cached.** `ats-url-cache` keeps one copy per TTL window, so
   re-reading the same page in a later phase is free.
5. **Memory.** Only to form a hypothesis you are about to check against 1–4.

The tool for rung 3 on this machine is **freshdocs 0.2.0**: a local,
version-pinned documentation index (35 libraries, re-synced daily).

```bash
freshdocs status
freshdocs analyze
freshdocs context "how do I configure lint rules" --project . --limit 3
freshdocs context "how do I add a dev dependency" --lib uv --limit 3
```

Measured on 2026-09-03, six queries in both modes
(`data/benchmarks/freshdocs-lane-2026-09-03.md`):

- **80.8–96.9% fewer tokens** than loading the upstream sources the pack cites.
- **~70 ms** per pack, against ~200 ms for a *single* network fetch — and a pack
  usually cites three sources, so the serial-fetch alternative is far worse.
- **Fails closed.** When nothing is indexed it refuses and prints the exact
  `--sync-stale` command, instead of answering from something adjacent.

### The two modes fail differently — this is the part to get right

`freshdocs` retrieves either by project or by library, and the benchmark found a
distinct failure in each. Neither mode is safe used blindly.

| Mode | Version fidelity | Failure found |
|---|---|---|
| `--project` | pinned to the manifest — `ruff 0.14.14`, exactly what is installed | **5 of 6 off-topic.** Queries about libraries the project does not declare were answered from ruff, silently |
| `--lib` | registry's cached version | **2 of 6 drifted** from the installed binary: `uv 0.12.9` served vs `0.11.5` installed, `bun 1.4.0` vs `1.3.14` |

So the rule is:

- **Use `--project` for the code you are editing.** Its version pin is exact,
  and that is the whole point of the phase: it hands you the API of the version
  you actually import, not the newest one on the internet.
- **Use `--lib` only for a library the project genuinely does not declare**, and
  then confirm the version against the installed binary before trusting a flag
  or a default.
- **Never ask `--project` about an undeclared library.** It answers, confidently,
  from the wrong one. That is the most expensive failure on this page, because
  it looks exactly like a correct answer.

Rung 1 stays mandatory regardless: `--version` on the binary is the only source
that cannot be stale.

```bash
rtk --version
rtk pipe --help
```

**Worked example, and the reason this phase exists.** Memory said RTK was 0.43
with a handful of filters. The binary said:

```
rtk 0.46.0
```

and `rtk pipe --help` listed 25 filters, including `ruff-check`, `mypy` and
`tsc` that did not exist in the pinned version. Cost of asking: ~150 tokens.
Cost of not asking: a wiring built against a two-version-old flag surface.

The same check found a second thing memory could never have supplied — the
filter is `ruff-check`, not `ruff`, and guessing returns:

```
rtk: Unknown filter 'ruff'. Available: cargo-test, pytest, go-test, ...
```

That error message is itself the freshest documentation on the machine.

---

## 5. Build — the smallest slice that can be verified

Nothing token-specific here, with one exception: **do not compress the code you
are writing to save context.** Cutting error handling, input validation or a
guard clause to keep a diff small trades a durable defect for a rounding error
in the token bill.

**Worked example.** `ats-verify` deliberately keeps a raw log on disk and prints
its path — bytes that never enter the model context but make every red run
recoverable. That is the shape to aim for: cheap in context, complete on disk.

---

## 6. Verify — `ats-verify` is the oracle wrapper

Run every check through it. It runs the command **once**, passes the exit code
through unchanged, keeps the full log on disk, and prints an asymmetric
projection:

- **green** → a few lines; this is where the saving is
- **red** → every decisive line, in source order, with a floor so it is never empty

```bash
ats-verify -- uv run pytest -q
ats-verify --json -- cargo test
ats-verify --no-rtk -- ruff check .
```

**Worked example, green.** The full local suite:

```
Pytest: 328 passed
ats-verify: green exit=0 50464ms via=rtk:pytest lines=1/37 raw=/tmp/.../verify-….log
```

2,425 bytes of pytest output became 18 bytes. The exit code still gates the work.

**Worked example, red — and why this wrapper exists.** RTK's `pytest`
*wrapper subcommand* was observed printing **zero bytes** for a failing test
while returning exit 1. A red result with no evidence is the worst output a
harness can produce: indistinguishable from a broken tool, and the next move is
a guess. So `ats-verify` never lets a filter own execution. It captures the run
itself, then offers that captured text to `rtk pipe` as **one candidate**, which
must still contain a signal line to be eligible. The smaller survivor wins.

There is **no globally adopted filter**, because none wins globally:

| Filter | Short red log | Long red log | Selected |
|---|---|---|---|
| `cargo-test` | 76 B → 39 B | 3,060 B → 323 B | RTK both |
| `pytest` | 76 B → 26 B | 3,132 B → 957 B (RTK offered 1,264 B) | RTK short, builtin long |
| `mypy` | 71 B → 70 B | 2,125 B → 2,124 B | builtin both |
| `tsc` | 75 B → 74 B | 2,529 B → 2,528 B | builtin both |
| `ruff-check` | 58 B → 57 B | 2,677 B → 110 B | builtin both |

Read that honestly: **a red `mypy` or `tsc` run saves almost nothing.** When
every line is already a diagnostic, "complete on red" and "compact" are in
direct conflict and completeness wins on purpose. The saving on those tools
comes from their green runs. Anyone promising compression on a red type-check
is selling you a filter that drops your errors.

The Stop guard reads `ats-verify`'s verdict line, so a red check surfaces as
`last_verification_failed`: **not done, and no saving may be claimed.**

---

## 7. Account — price it, do not guess it

```bash
agent-token-ledger --usage parent=<session.jsonl> --provider codex --format markdown
ats-cache --profile anthropic --format line <usage.json>
```

Two traps worth naming:

- **Raw token sums misprice a cached prefix.** Moving fresh input into cache
  reads *raises* raw input while *lowering* the bill. Weight by published ratios
  or do not claim a saving.
- **A mid-wave tool load or a compaction voids the prefix** from the first
  changed token. Count that re-write against the saving it claims.

**Worked example.** On a 125 MB Codex transcript the ledger replayed in 1.3 s and
reported 43 verification runs, all green — an outcome number, not just a cost
number.

---

## 8. Learn — write it back so phase 1 works next time

```bash
synx put "rtk pipe filter is ruff-check not ruff; wrapper subcommand can print zero bytes on red"
```

A finding that stays in one session is a finding you will pay for again.

---

## Version drift — installed vs. what the docs pin

Checked 2026-09-03 on this machine. The research snapshot is dated and stays as
recorded; this table is the live delta.

| Tool | Docs pin | Installed now | Delta |
|---|---|---|---|
| RTK | 0.43.0 | **0.46.0** | **corrected** in the research addendum; 25 `pipe` filters now |
| Tilth | 0.9.0 | 0.9.0 | matches |
| freshdocs | not pinned | 0.2.0 | unpinned; 35 libs indexed, all synced 2026-09-03 |
| `si` (skill router) | not pinned | repo HEAD | **was stale**: installed copy lacked the repo's negation handling; reinstalled 2026-09-04 |
| Synapse (`synx`) | not pinned | 1.0.1-rc.1 | unpinned; a release candidate is running in the hot path |
| gmax | not pinned | 0.26.8 | unpinned |
| superweb | not pinned | 0.1.0 | unpinned |
| ripgrep | not pinned | 15.2.0 | unpinned |
| jq | not pinned | 1.8.2 | unpinned; `goal-check` hard-requires it |
| Graphify | 0.9.11 → 0.9.14 upstream | not on PATH | deferred, still deferred |
| CodeGraph | 1.3.1 → 1.4.1 upstream | not on PATH | deferred, still deferred |
| Headroom | 0.31.0 | not on PATH | optional; never MCP |
| context-mode | 1.0.169 | not on PATH | on-demand only |
| Ponytail | unversioned skill | not on PATH | measured net negative; do not global-load |

Three honest observations:

- **Only RTK was pinned tightly enough to detect drift**, and it had drifted by
  three minor versions. Everything unpinned above could have drifted without
  anyone noticing, because nothing compares them to a recorded expectation.
- **`ghmax` auto-installs dependencies on first run.** A tool that mutates its
  own environment when invoked does not belong in a hot path without a budget.
- **freshdocs makes drift visible for libraries, and inherits it for tools.**
  Its registry tracks upstream latest, so `--lib` served `uv 0.12.9` and
  `bun 1.4.0` while `0.11.5` and `1.3.14` were installed here. That is not a
  freshdocs defect — a registry *should* know the latest release — but it means
  a `--lib` answer is upstream truth, not local truth. Only `--project` gives
  local truth, and only for declared dependencies.

Re-check with one command each: `rtk --version`, `tilth --version`,
`synx --version`. If a number here is stale, that is the drift this table exists
to make visible — fix the table, do not fix the memory.

---

## What good looks like

A finished unit of work should be able to answer all four:

1. What was the oracle, and did it exit zero? (phase 2, 6)
2. Was the last verification green? (phase 6 — if red, you are not done)
3. What did it cost, priced against cache, not raw sums? (phase 7)
4. Is the finding retrievable next session? (phase 8)

A session that saved 90% of its tokens and cannot answer #2 saved nothing. It
just failed more cheaply.
