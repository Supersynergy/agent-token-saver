# Full-context token measurement

Goal: measure the whole agent request, not only the file or log that was easy to
compress.

## The accounting model

A real agent turn can contain:

1. Host system instructions.
2. Built-in tools and MCP schemas.
3. User and project rules.
4. Hook output and loaded skills.
5. Conversation history and summaries.
6. Retrieved code, logs, web pages and memory.
7. The current task.
8. Model output and reasoning tokens.
9. Retries, failed tool calls and rework.

The provider-reported input/output total is the authority. Local files are
attribution evidence, not a replacement billing meter.

```text
provider input total
  - estimated visible rules
  - estimated visible tool schemas
  - estimated hooks and skills
  - estimated history/retrieval/task
= unattributed host input
```

`unattributed host input` can include a hidden system prompt, built-in tool
schemas, plugins, cache accounting and tokenizer differences. Reducing it
requires an A/B at the agent boundary; it must never be presented as an already
achieved saving.

## Parent-and-child ledger

Capture the agent's machine-readable usage and every visible context layer you
can export:

```bash
codex exec --json --ephemeral "your real task" > run.jsonl

agent-token-ledger \
  --usage parent=run.jsonl \
  --usage child-review=child-review.jsonl \
  --usage child-research=child-research.jsonl \
  --provider codex \
  --component system-rules=/path/to/AGENTS.md \
  --component tool-schemas=/path/to/tools.json \
  --component hook-output=/path/to/hook-output.json \
  --component active-skills=/path/to/skills.txt \
  --component retrieved-context=/path/to/context.txt \
  --component task=/path/to/task.txt \
  --format markdown \
  --out ledger.md
```

The parser accepts JSON or JSONL and understands common Codex, Claude and
OpenAI-style usage fields. Codex `cached_input_tokens` is treated as a subset of
input. Claude `cache_creation_input_tokens` and `cache_read_input_tokens` are
separate input classes and are added.

Each usage file contributes its final provider usage object. Repeat `--usage`
for every parent, child, retry, fallback and compaction request. The ledger sums
them and shows the individual sources. Visible components carry SHA-256
fingerprints; repeated payloads are reported as duplicate visible input.

Do not use `fork all` as an invisible shortcut. A worker should receive a small
task capsule: objective, exact input pointers, constraints, oracle, allowed
tools, try limit and bounded return schema. Keep raw material in files or a
content-addressed store and pass path/hash identifiers.

## A defensible A/B

Use at least ten real tasks across code search, test failure diagnosis, large
logs, repo understanding and research. For each task:

1. Start from a fresh HOME or disposable container/VM.
2. Pin the agent version, model, repo commit and task prompt.
3. Run cold-cache baseline and optimized arms.
4. Run a warm-cache repetition separately.
5. Require the same executable acceptance oracle.
6. Record provider input, cache classes, output, latency, tool calls, retries,
   compactions and human rework.
7. Report median and p95; keep failures in the denominator.

Never compare one raw payload estimate with a full provider request and call the
difference end-to-end savings.

## Optimization order

1. Remove unused always-on MCP schemas and plugin catalogs.
2. Route zero or one primary skill automatically; add another only for a distinct explicit phase.
3. Project large shell/log/web payloads before model context.
4. Prefer diffs, exact symbols and source deltas over whole files.
5. Keep stable prefixes cacheable; separate cold and warm results.
6. Compact history into durable state before context rot.
7. Route trivial work to cheaper models only after a quality gate.
8. Shape output only when provider-reported total tokens improve.
9. Track retries and rework; a short wrong answer is not a saving.
10. Use subagents only after deterministic projection; sum their bootstrap and output.

The release gate is simple: no optimization becomes a default unless task
success stays equal and full provider tokens improve on the same workload.
