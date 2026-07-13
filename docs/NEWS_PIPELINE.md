# Token-efficient news and research pipeline

## Contract

Goal: preserve critical primary-source events while keeping repeated model context at least 95% below the raw feed.

```text
fetch -> cache -> normalize -> canonicalize -> dedupe -> score -> top-K delta
      -> two cheap batch reviewers -> deterministic join -> optional arbiter
```

Stop conditions:

- critical-event recall must not fall below the raw/reference arm;
- duplicate rate is zero;
- structured output parses at least 99% of the time;
- strong-model escalation is at most one call per run/day;
- empty delta means zero model calls;
- no model is allowed in a live order path.

## Acquisition ladder

1. Existing database/cache and official feed/API/bulk download.
2. Direct HTTP using a browser-compatible client and conditional requests.
3. Bounded fetch/batch tool for blocked pages.
4. Search only for unresolved source gaps.
5. Browser only after a fetch failure that matters to the oracle.

Store raw responses with URL, retrieval time, status, content hash and source class. Agents receive file paths or projected records, not raw HTML in prompts.

RTK belongs around noisy command/log inspection. It does not replace HTML extraction, canonicalization or domain ranking.

## Projection

`scripts/news_projection.py` accepts generic JSONL. It removes tracking parameters, deduplicates canonical URL/title identities, keeps bounded text, scores primary sources and keyword hits, then emits top-K records.

Example:

```bash
python3 scripts/news_projection.py news.jsonl \
  --keywords "Fed,ECB,earnings,oil,gold" --top 8 > evidence.jsonl
```

For a domain system, replace the generic score with deterministic reason codes such as official source, freshness, symbol/atlas match and novel content hash. Keep the output schema small and stable.

## Subagents

Use at most two independent cheap batch reviewers for the same top-K delta. Each returns one bounded JSON object per event. Join by event/content hash. Call one strong arbiter only when reviewers disagree and the deterministic score exceeds the escalation threshold.

Never fan out one agent per article by default. Never send the complete raw feed to every agent.

## Benchmark arms

| Arm | Context | Calls |
|---|---|---:|
| A | raw 24h feed -> strong model | 1 strong |
| B | existing per-event panel | up to N x engines |
| C | top-K delta -> cheap batch | 1 cheap |
| D | top-K delta -> two reviewers -> dissent arbiter | 2 cheap, <=1 strong |
| E | deterministic projection only | 0 |

Record input/output tokens, wall time, calls, parse success, duplicates, critical-event recall, precision@K, source URL coverage, staleness and monetary cost. Do not compare token count without a quality oracle.

## Measured WINvestment-shaped fixture, 2026-07-13

Using the same UTF-8 bytes / 4 proxy as the stack matrix:

| Payload | Tokens |
|---|---:|
| 334 raw 24h Primequellen items | 75,275 |
| projected top 20 | 1,237 |
| projected top 8 | 576 |
| 86 raw Source-Mesh events | 28,325 |
| projected top 5 | 522 |

Top-8 versus raw was 99.24% smaller; Source-Mesh top-5 was 98.16% smaller. These are context reductions, not claims about prediction quality.
