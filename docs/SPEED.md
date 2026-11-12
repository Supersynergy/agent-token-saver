# Measure speed at the accepted result

Reviewed November 12, 2026. These are bounded principles from local Speed skills
and Superloop, not instructions to start those workflows. `ats guide speed`
is the short version.

## Separate the time before optimizing it

Model wait, process startup, tool work and rework are different costs. Measure
them separately. `ats verify` cannot measure model wait outside its child-command
run. A small tool benchmark therefore cannot establish its share of an entire
agent session.

Before comparing candidates, fix the task, quality condition and stop rule.
Change the measured bottleneck. Compare the same accepted outcome and retain
failures in the accounting. Separate cold and warm calls when startup matters;
measure CPU time as well for CPU-bound work. A low wall-time sample can be load
drift rather than an improvement.

## What survives the Superloop review

Contract → find → edit → check → evidence → ship is a useful slice outline.
It is a scaffold, not a reason to plan every filename lookup. A local lookup
can remain a direct tool call.

Paying initialization once can help repeated operations, when actual frequency
repays the setup and ongoing resource cost. A service started before a real
consumer exists still costs memory and maintenance. ATS starts no daemon.

Batch operations when individual statuses and required evidence survive.
Keep dependent writes ordered. A shared exit that hides a failed step is not
a useful optimization.

The narrow affected check can shorten an inner loop. Required release and
security gates stay required. Stop after matching acceptance passes; a source
change does not automatically inherit the old proof.

## What stays out

- No universal rule that rounds always dominate milliseconds. Measure both
  model wait and tool time, then account for frequency and the actual bottleneck.
- A missing required tool is not a passed check. Optional RTK is `unavailable`;
  a missing required oracle blocks acceptance.
- No automatic reclaim, killing other owners' processes or tracker fallback.
- No fixed turn cap from two tasks or current price recommendation from an old
  off-peak experiment.
- No keepalive, background warmup or extra model call to shorten deterministic data.

## Sources and limits

`superloop` contributed the phase outline; `speedtuning` contributed cost classes
and quality invariants. `speedplaybook` supplied counterexamples to unnecessary
parallelism and unamortized startup. A local harness study showed why token
minimization alone can misprice an accepted task.

[Source hashes](../data/research/speed-review-2026-11-12.json) identify the reviewed
versions. Their figures are neither ATS measurements nor transferable speed
factors. Private source documents are not bundled.

The [20-skill design review](SKILLS.md) remains separate provenance. This review
extends the reasoning, not the number of automatically loaded skills or the
authority granted to the tool.
