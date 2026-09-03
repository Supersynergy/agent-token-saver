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
| 3 | Locate | Where is the code? | `rg`, `code_nav`, Tilth |
| 4 | Fresh docs | What is the API *today*? | source on disk, `ats-url-cache` |
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
3. **Official docs, cached.** `ats-url-cache` keeps one copy per TTL window, so
   re-reading the same page in a later phase is free.
4. **Memory.** Only to form a hypothesis you are about to check against 1–3.

```bash
rtk --version
rtk pipe --help
ats-url-cache get https://example.com/docs --ttl 86400
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

Two honest observations:

- **Only RTK was pinned tightly enough to detect drift**, and it had drifted by
  three minor versions. Everything unpinned above could have drifted without
  anyone noticing, because nothing compares them to a recorded expectation.
- **`ghmax` auto-installs dependencies on first run.** A tool that mutates its
  own environment when invoked does not belong in a hot path without a budget.

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
