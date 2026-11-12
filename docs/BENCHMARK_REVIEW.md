# What the other benchmarks change

Reviewed November 12, 2026 from existing reports. No new paid model runs.
Each result remains tied to its original task, host and method.

## A smaller team can finish the same job

On July 16, one projection worker solved a log task with 129,836 gross input
tokens. Three workers needed 390,010 for the same oracle. The large raw-read
arm used more and still counted incorrectly. Parallelism can buy wall time;
a deterministic projection does not automatically need a team.
[Report](../data/benchmarks/claude-team-ab-2026-07-16.md).

That report also recommended staggered child starts. The July 19 counterexample
refuted the cache benefit on its tested host: 411,938 gross input for simultaneous
starts, 411,946 for staggered starts. The later result supersedes that earlier
recommendation. ATS adds no scheduler or general fan-out recipe.
[Counterexample](../data/benchmarks/claude-stagger-ab-2026-07-19.md).

## A short documentation answer can describe the wrong library

The September 3 comparison had five off-topic rows out of twelve, two version
drifts and one explicit refusal. The smallest output was not an answer; a
refusal cannot win a saving leaderboard.

Confirm library and version before accepting the shorter lane. The raw-source
comparison rows were not freshly fetched in that run, which further limits the
reported byte comparisons.
[Report](../data/benchmarks/freshdocs-lane-2026-09-03.md).

## A proxy-arm difference does not isolate compression

One Headroom comparison reported 45,206 versus 20,598 total tokens on a large
Git diff, with both oracles passing. The proxy itself reported zero removed
tokens. The runs differed, but the cause was not isolated. Ordering and cache
state affect that comparison. ATS derives no automatic proxy route from it.
[Report](../data/benchmarks/headroom-ab-2026-07-18/result.md).

## Small packets are not completed acceptance

The capsule fixture shrank a three-worker packet from 3,800 to 530 estimated
units. This was a local capacity comparison without provider calls. It proves
neither invoice savings nor better worker outcomes. Keep bounded task packets
and evidence references; do not infer permission to start workers.
[Report](../data/benchmarks/swarm-control-2026-07-27.md).

## The short run was not the cheaper solved task

An October 30 local harness study used small tasks and unchanged hidden tests.
A fast arm needed fewer prompt tokens but solved only one of two tasks. Its
reported cost per solved task exceeded the slower baseline. That supports an
accepted-task denominator, not a current model ranking.

The same study found increasing effort in a long continued session. Its proposed
fixed turn cap is not adopted here: it came from few tasks, and a difficult
third task was excluded from the main table. A universal cap needs other evidence.
The underlying protocol is local; its [source hashes](../data/research/speed-review-2026-11-12.json)
identify the reviewed documents. Private experiment files are not republished.

## What ATS takes from this

`ats guide speed` separates model wait from tool time. The [Speed page](SPEED.md)
explains the next-step choice. Automatic model selection, off-peak schedules
and universal turn caps stay out. Historical prices are not current tariffs.

The [eight RTK contracts](RTK.md) test a different boundary: use raw evidence when
a candidate loses required literals or saves no bytes. Passing those literal
checks is weaker than fixing a real bug. Provider prices and usage classes remain
explicit inputs to `ats cost`.
