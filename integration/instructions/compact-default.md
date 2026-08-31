## Agent Token Saver default

- First command filters/aggregates; raw/noisy data stays out of context. Exact local search or deterministic projection; RTK only when supported.
- Route zero/one skill for one phase; allow one primary plus up to four supports
  only when each support covers a distinct, confident phase. No catalog loads.
  Natural exact-name requests count as explicit. Heavy tools and remote fan-out stay opt-in.
- Preserve oracle and quality: smallest reversible verified slice; three failures means root-cause.
- Delegate only independent >5-minute or context-flood work: objective, scope, oracle, zero/one skill; max three; compact evidence.
- Cache-aware handoff: keep model and effort fixed inside a work wave; switching either voids the whole prefix. Before a pause beyond the host cache TTL or a context checkpoint, write one reference-only 300–700-token handoff. Include decisions, running state, next action, the oracle and a test checklist. Then start fresh. No background keepalive or unverified savings claim.
- Cache hygiene: a prefix is reusable only while byte-identical, and the vendor looks back a bounded number of blocks (20 on Anthropic) for a prior write, so a burst of large turns misses a prefix that never changed. Grow context append-only in small steps; never edit or reorder an earlier turn. Keep clocks, session ids and counters out of it, hold tool definitions stable within a wave, and compact at a stable boundary.
- Price the cache before claiming a saving: raw sums misprice a cached prefix, since moving fresh input into cache reads raises raw input while lowering the bill. A mid-wave tool or catalog load and a compaction both void the prefix from the first changed token, so count that re-write against the saving it claims. Weight by published ratios and state the counterfactual.
- Track context, provider tokens, latency, money, and quality separately; proxy is not billing. Full `$agent-token-saver` is explicit-only.
