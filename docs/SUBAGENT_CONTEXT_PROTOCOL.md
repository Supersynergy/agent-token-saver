# Subagent context protocol

Parallelism saves wall time. It saves provider tokens only when the context kept
out of the parent is larger than the child's bootstrap, task packet and result.

## Default decision

Use deterministic projection first. Spawn a worker only for an independent lane
with a closed oracle or for raw material that would otherwise pollute several
future parent turns.

```text
spawn when:
future parent turns × (raw context - compact result)
> child base input + task packet + child output
```

With a clean Codex base near 11k input tokens, a small two-file read almost
never breaks even. A 40k-token log or independent research corpus can.

## Task packet

Send only:

```json
{
  "objective": "one closed verb",
  "scope": ["exact paths or URLs"],
  "inputs": [{"uri": "artifact path or memory id", "sha256": "..."}],
  "constraints": ["must-preserve rules"],
  "oracle": ["exact command or output schema"],
  "skills": ["zero to three exact SKILL.md paths"],
  "limits": {"tries": 3, "return_tokens": 500},
  "return": "status, evidence references, checks, blockers"
}
```

Use no parent-history fork for independent work. Use one-turn inheritance only
when the immediately preceding user turn is essential. Full-history forks are
for rare tasks whose acceptance depends on the whole conversation.

## Lossless-by-reference

Free-form summarization is not lossless. Recoverability is:

- raw data stays unchanged outside model context;
- every packet contains path/URI, hash, source and freshness;
- exact errors, approvals and safety constraints are copied verbatim;
- worker results point back to evidence rather than embedding it;
- the parent can retrieve the original on uncertainty.

## Memory tiers

| Tier | Budget | Content |
|---|---:|---|
| Hot | 100–300 tokens | stable rules and one routing pointer |
| Task | 300–700 | objective, scope, oracle, evidence references |
| Recall | 0–300 | one to three project-filtered memory hits on demand |
| Artifact | unbounded outside prompt | logs, pages, reports, raw JSONL |
| Heavy graph/browser | session only | schemas and runtime tools |

An empty router or memory result is success. Never fill a budget merely because
it exists.

## Accounting

```text
Ttotal = sum(parent requests)
       + sum(child requests)
       + retries + fallbacks + compactions
```

Report total input, uncached input, cache classes, output, reasoning, latency,
oracle pass/fail and duplicate visible context. Use one named `--usage` argument
per parent or child with `agent-token-ledger`.
