# Claude parent-plus-children A/B — 2026-07-16

First Claude-side datapoint for the parent-plus-children proof obligation.
Fixture: a generated 4,000-line log; oracle = exactly 100 `ERROR` lines plus the
single `CRITICAL-MARKER` line (3777) reported verbatim. Children are Claude Code
subagents (read-only profile, cheapest model tier). Usage comes from the
provider usage fields in each child's transcript
(`~/.claude/projects/<project>/<session>/subagents/agent-*.jsonl`), not from a
bytes proxy.

| Arm | Requests | Uncached input | Cache write | Cache read | Gross input | Output | Oracle |
|---|---:|---:|---:|---:|---:|---:|---|
| Projection child (one `rg` command) | 4 | 36 | 43,886 | 85,914 | 129,836 | 825 | PASS |
| Three-worker team (`awk` slices) | 12 | 108 | 131,912 | 257,990 | 390,010 | 1,470 | PASS (33+33+34) |
| Raw full-read child (Read tool only) | 30 | 290 | 435,611 | 1,412,670 | 1,848,571 | 6,668 | **FAIL — counted 99** |

## Findings

1. **Child bootstrap on this host is ~44k tokens** (first-request cache write per
   child). The protocol's Codex assumption is ~11k; Claude children break even
   roughly four times later.
2. **Simultaneous fan-out forfeits prefix cache reuse.** All four lean children
   paid their own ~44k cache write for an identical prompt prefix. Staggering
   the spawn converts the later children's writes into reads.
3. **A team is a wall-time purchase, not a token saving:** 3.0x the gross input
   of the single projection child for the same accepted oracle.
4. **Raw reads lose correctness, not just tokens:** 14.2x the gross input and a
   wrong count (99 of 100) with a broken return format.
5. Marginal uncached input per worker was 36 tokens; with warm caches the real
   marginal cost of a worker is the cache-write premium plus output.

One run per arm; no confidence interval. Token classes are provider usage
fields, not billing claims. Raw JSON: `claude-team-ab-2026-07-16.json`.
