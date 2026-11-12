# The next unnecessary step can cost more than the text it removes

Reviewed November 12, 2026. ATS starts with an accepted result, then removes
unnecessary operations and shortens evidence views. A small output is useful
only while the information needed for the next decision survives.

## What matters most

### Remove repeated work

Before a call, identify the open question it will answer. Reuse relevant decisions
and source-matched green checks. Batch independent reads when each result stays
observable. Stop after the agreed acceptance condition passes.

This is a process priority, not a universal percentage derived from ATS data.
Track requests, wall time, rework and interruptions alongside tokens. A faster
projection does not fix a queue or an incorrect task contract.

### Preserve the acceptance condition

The September 13 matrix estimated 407,670 visible input units for the raw path
and 1,932 for a selective CLI path. Every aggregate row was unaccepted because
the skill-routing component failed its oracle. The small output was not an
accepted saving. [Source](../data/benchmarks/token-stack-matrix-2026-09-13.md).

`verify` therefore saves raw logs and the original exit before showing a shorter
view. `project` reports omissions. A match limit is not a complete inventory.
An empty diagnostic view cannot turn a failed command into success.

An oracle must also fit the task. Correctly forwarding an exit proves only what
the selected command actually checked.

### Select before the model reads

The September 13 microbenchmark reduced a Git-log view from 10,636 to 52 estimated
units; JSON-key selection reduced 48,487 to 582. These were UTF-8-bytes/4 proxies,
not provider counters or money. [Source](../data/benchmarks/stack-tool-microbench-2026-09-13.md).

Start with an exact search or the needed data fields. Use a bounded structural
read when that is insufficient. A graph or browser needs a named open question;
a small known log does not automatically need an indexing service.

### Price cache and output separately

The July 15 Codex comparison reported 19.67% fewer aggregate provider tokens,
but its process-table task used 32.16% more. There was one run per arm. An
aggregate cannot promise a gain for every task.
[Source](../data/benchmarks/codex-provider-ab-2026-07-15/compact-policy/result.md).

Three August runs showed variable baselines and different signs for raw counts
and weighted list-price estimates. Their price ratios are historical assumptions.
[Run 1](../data/benchmarks/codex-provider-ab-2026-08-22-terra/result.md),
[run 2](../data/benchmarks/codex-provider-ab-2026-08-22-terra-v2/result.md),
[run 3](../data/benchmarks/codex-provider-ab-2026-08-22-terra-v3/result.md).

In the September 14 Claude sample, `cap-graperoot` used 0.21% more raw total tokens
while its reported cost was 9.46% lower. `cap-budget` reported 35.92% lower cost
but only 1.61% fewer weighted total tokens. Different metrics answer different
questions; this sample does not establish a general default.
[Source](../data/benchmarks/claude-ab-2026-09-14/result.md).

ATS requires an explicit price source, currency and disjoint usage classes.
It does not pick a current provider tariff. A stable prefix can help cache reuse;
its value must be measured on the actual route. Keepalive calls are not part of
the design.

### Count maintenance and startup

The September 13 hook study measured roughly four seconds for individual Synapse
hooks and roughly 32 ms for the ATS prompt hook on that host. These are dated
observations, not current guarantees.
[Source](../data/benchmarks/hook-stack-2026-09-13.md).

The July capsule study also showed fewer bytes with slightly worse median time
in one case. Bytes and milliseconds need separate columns.
[Source](../data/benchmarks/hook-and-capsule-hotpath-2026-07-27.md).

The maintained core installs no prompt hook. The TypeScript/Bun move unifies the
implementation; it does not prove that every TypeScript hook is faster than Python.

## A small explicit surface

| Command | Job | Limit |
|---|---|---|
| `verify` | one command, raw logs, original exit | the chosen oracle defines quality |
| `project` | bounded tail or literal-match view | omissions prevent a completeness claim |
| `cost` | supplied usage times explicit rates | estimate, not an invoice |
| `skills` | read the 20 reviewed contributions | no automatic skill execution |
| `install` | create a generation and starters | no host-hook migration |
| `doctor` | check installed hashes and starters | no live host or customer acceptance |
| `bench` | compare eight RTK task contracts | synthetic evidence, not a ranking |
| `guide` | explain a next useful action | no automatic routing |
| `rollback` | restore previous starters and generation | refuses later edits |

Bun and the Node standard library cover the runtime. TypeScript and Bun types
are pinned development dependencies. [Bun's TypeScript documentation](https://bun.sh/docs/runtime/typescript)
distinguishes execution from type checking; its
[process API](https://bun.sh/docs/runtime/child-process) documents argv and streams.

## Remove breadth, retain counterexamples

Automatic routers, provider gateways and overlapping hook profiles were retired.
Existing task systems keep task ownership; ATS creates no second board. Local
changes were archived before obsolete surfaces were removed. Git history and
[the migration map](MIGRATION.md) preserve the boundary.

The [November RTK review](RTK.md) accepted one of eight candidates. Three saved
no bytes; four lost required evidence. This supports task-specific selection,
not a blanket rejection of RTK.

## Before making a new saving claim

Fix task, model, source and oracle before the experiment. Compare the same
independent tasks with balanced ordering and multiple runs. Keep every started
arm in the accounting, including failures. Record accepted outcomes, fresh input,
cache classes, output, wall time and rework.

Date the price source. Keep byte proxies separate. A failed oracle invalidates
that arm's saving claim; changing the oracle or fixture begins a new comparison.
A local source gate proves behavior under its checks. Provider costs and customer
outcomes still need their own evidence.
