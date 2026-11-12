# When RTK helps, and when it removes the answer

Reviewed November 12, 2026 with RTK 1.2.0 and Bun 1.4.4. Eight synthetic tasks,
one filter process per task. No provider calls or real project builds.

| Question | Raw | RTK candidate | Selected | Result |
|---|---:|---:|---:|---|
| Read a short success message | 19 B | 19 B | 19 B | no byte gain |
| Locate TypeScript errors | 7,630 B | 230 B | 230 B | required filenames and codes retained |
| Return all 180 route matches | 10,510 B | 10,510 B | 10,510 B | no byte gain |
| Return one route match | 10,510 B | 10,510 B | 10,510 B | no gain; exact selection needs 59 B |
| Return all 240 paths | 6,720 B | 220 B | 6,720 B | all exact path literals absent |
| Read the latest five commit subjects | 6,880 B | 169 B | 6,880 B | three required subjects absent |
| Read failure location and expected/actual values | 592 B | 51 B | 592 B | five required detail literals absent |
| Read an unusual failure | 7,506 B | 32 B | 7,506 B | error ID and retry value absent |

One candidate was accepted, three saved no bytes and four lost required evidence.
The seven rejected candidates kept raw output. Risky removal earns no saving.
[JSON](../data/benchmarks/rtk-2026-11-12.json) ·
[measurement record](../data/benchmarks/rtk-2026-11-12.md).

## Ask the question before choosing the filter

The TypeScript fixture also had a 153-byte exact reference tailored to that
question. It is not a general compressor or a fair latency rival for a new RTK
process. It shows why selecting the needed information can beat another layer.

A complete path list must remain complete. A grouped tree can answer an overview
question and still fail a parser that requires every path. Patch bytes and
pipeline inputs have the same consumer contract.

The accepted TypeScript candidate retained its declared literals. That does not
prove every relationship between a file, line and error code remained correct.
A stronger parser or a completed fix needs a stronger oracle.

Unknown error formats need attention. A filter trained on familiar patterns can
miss another format. `verify` therefore saves raw files before showing a short
view and never substitutes a filter's exit for the original check's exit.

## What these results do not establish

The tasks deliberately exercise different contracts. They are not a representative
sample of all RTK calls. Seven rejected cases here do not imply an 87.5% failure
rate for RTK. A `pipe` filter result does not establish how every specialized
RTK command behaves on a real project.

Filter times were roughly 4–7 ms in this run, including process startup. There
were no latency repetitions or confidence intervals. No general speed factor
or provider-bill reduction follows from those times.

A missing required literal proves failure of that declared contract. Keeping all
literals proves only that weaker condition, not semantic equivalence or a solved
task. Provider usage and prices require their own measurements.

## Compare with current upstream guidance

RTK describes `gain` as estimated shell-output reduction and distinguishes it
from provider billing. [Official explanation](https://github.com/rtk-ai/rtk/blob/develop/docs/usage/FEATURES.md#about-bash-output-reduction).

Its technical documentation keeps pipeline producers and intermediate stages
raw and limits automatic rewriting. A parser must not receive an altered
preview in place of its required input. Upstream documentation describes its
own revision; it does not prove another installed version's behavior.
[Technical source](https://github.com/rtk-ai/rtk/blob/develop/docs/contributing/TECHNICAL.md#32-command-rewriting).

## Run your comparison

```bash
bun run ats bench --out ./my-rtk-report
```

Use `--rtk /path/to/rtk` to select an installed binary. ATS installs no RTK
software or plugins. Preparation disables telemetry in an isolated home; failed
preparation marks the arms unavailable.

Each case saves raw, candidate and selected output. The report includes missing
literals, status, byte counts and fixture hashes. Keep counterexamples in the
record when comparing a new version.
