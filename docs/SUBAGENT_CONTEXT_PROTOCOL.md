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

The child bootstrap is host- and runtime-specific; measure it before assuming
break-even. Measured 2026-07-16 on one host, one command per worker lane:

| Child runtime | First-request bootstrap | Requests per one-command lane | Gross input |
|---|---:|---:|---:|
| Codex CLI, clean base (assumed) | ~11k | — | — |
| Claude Code subagent, cheapest tier | ~44k cache write | 4 | ~130k–137k |
| Kimi CLI `--print`, default | ~31.8k (22.6k uncached) | 2 | ~64k |
| Kimi CLI `--print --skills-dir <empty>` | ~10.8k (2.1k uncached) | 2 | ~22k |

Kimi loads the user skills index (83% of its system prompt) into every child;
an empty `--skills-dir` removes it and cuts uncached input by 91%
([kimi-lane-2026-07-19](../data/benchmarks/kimi-lane-2026-07-19.md)). For
Kimi worker lanes: `--quiet` returns only the final message, exit code 75
(and only 75) means retry, and a per-team `KIMI_SHARE_DIR` keeps swarm usage
accounting separable
([research 2026-07-19](TOKEN_SAVER_RESEARCH_2026-07-19.md)).

K3 facts ([kimi-k3-lane-2026-07-21](../data/benchmarks/kimi-k3-lane-2026-07-21.md)):
a lean three-worker team beats the CLI's built-in `Agent` swarm on the same
model by **−65.3%** gross (73,710 vs 212,310; the swarm arm costs 2.3x its
K2.7 value). The PARL-trained Swarm Max is app-only with no documented
API/CLI access, so the built-in `Agent` tool remains the headless comparand.
`--no-thinking` is **not** a saving on shallow lanes: output drops 4% but the
changed prompt prefix shifts +71% into uncached input — measured and refuted.

With a clean Codex base near 11k input tokens, a small two-file read almost
never breaks even; a Claude Code child pays roughly four times that bootstrap,
so its break-even point is correspondingly higher. A 40k-token log or an
independent research corpus can qualify. A two-file read almost never does.

## Team profile

The `teams` installer profile has the same lean runtime surface. It adds no
daemon, no always-hot schema and no automatic fan-out; it exists to make this
contract explicit.

1. The controller performs local projection and states one machine oracle.
2. A worker gets one independent lane, one 300–700-token capsule and zero or
   one routed skill path.
3. Start at most three independent workers. Do not split a small overlapping
   check merely to reduce wall time.
4. Workers return claim, evidence path/hash, command, oracle result and blocker
   in at most 500 tokens.
5. The controller sums parent, children, retries, fallbacks and compactions;
   it accepts the team only when the same oracle passes.

Measured Claude datapoint (2026-07-16, same fixture and oracle): one projection
worker used 129,836 gross input tokens and passed; a three-worker team used
390,010 (3.0x) and passed; a raw full-read child used 1,848,571 (14.2x) and
**failed** — it miscounted. Fan-out buys wall time, never tokens, and raw reads
also lose correctness. Artifact:
[claude-team-ab-2026-07-16](../data/benchmarks/claude-team-ab-2026-07-16.md).

### Cache-aware fan-out

Measured 2026-07-19 (A/B, same fixture and oracle): **staggering the spawn
saves nothing on Claude Code subagents** — 411,946 gross staggered vs 411,938
simultaneous. Every child already reads the shared ~90k prefix from cache in
both arms; the ~47k per-child cache write is child-unique suffix (per-agent
context, task packet, the child's own conversation) that no spawn schedule can
convert. Fan out simultaneously: same tokens, less wall time. Artifact:
[claude-stagger-ab-2026-07-19](../data/benchmarks/claude-stagger-ab-2026-07-19.md).

Moonshot/Kimi behaves the same way for scheduling but cheaper in kind: caching
is implicit with no write premium (`input_cache_creation` = 0 in every
measured request), so simultaneous Kimi fan-out is also free of cache penalty.
Cut team cost by shrinking per-child suffix and requests per lane, or by
routing shell-projection lanes to a cheaper runtime — a lean Kimi three-child
team ran the same oracle at 16% of the Claude team's gross input.

### Model tiers inside a team

Run every worker on the cheapest model that passes the lane's oracle; reserve
the expensive model for the controller and for verification. The measured
three-worker team ran entirely on the cheapest tier and passed the same oracle
as the single-worker arm. Two rules keep this honest:

1. No self-grading: a worker's claim is checked by a deterministic oracle or a
   different model, never by the worker itself.
2. Escalate a lane's model only after the oracle fails on the cheap tier, and
   record the escalation in the ledger as a retry, not a new task.

When an existing ACP workflow already uses `acpx`, use `--format quiet` for the
worker return and keep JSON/NDJSON as an artifact. The pinned mock transport
measured 6 output bytes in quiet mode versus 1,013 in JSON mode. Do not add ACP
only for this formatting win: it does not remove the child model's bootstrap.

Use `agent-token-ledger --format json-compact` when the full ledger must cross
an agent boundary; keep the pretty JSON/Markdown copy for humans.

The router remains a separate optional skill. The main installer detects an
existing `si` launcher but never downloads, clones or silently installs it.

## Task packet

Send only:

```json
{
  "objective": "one closed verb",
  "scope": ["exact paths or URLs"],
  "inputs": [{"uri": "artifact path or memory id", "sha256": "..."}],
  "constraints": ["must-preserve rules"],
  "oracle": ["exact command or output schema"],
  "skills": ["zero or one exact primary SKILL.md path"],
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
per parent or child with `agent-token-ledger --require-complete-team`; missing
worker usage is a failed done gate, not an estimate.
