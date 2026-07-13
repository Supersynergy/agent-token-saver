# Stop Loading Your Coding Agent With Its Entire Brain

Most coding agents waste context before they start working.

They load every skill, every MCP schema, huge terminal logs, and duplicate project instructions into the prompt. The result is slower work, weaker focus, and a quota that disappears for no useful reason.

I built **Agent Token Saver** around one rule:

> Give the agent the smallest decisive context — not the biggest possible context.

## The measured result

On the same accepted workload:

- Raw stack: **380,871 tokens**
- Lean automatic stack: **4,476 tokens**
- Reduction: **98.8%**

The test does not reward a shorter answer that loses facts. Each run must preserve the required signals and exit code.

## The stack

```text
tiny skill router
  -> RTK for noisy shell output
  -> deterministic projection for logs and large files
  -> small, optional code reader
  -> heavy graph/browser tools only when the task proves it needs them
```

What stays off by default matters as much as what stays on.

- Full skill catalogs: off
- Extra MCP schemas: off
- Massive raw logs: off
- Heavy graph tools: on demand
- Output-shaping prompts: only after an A/B test proves they help

## Why it is different

This is not another "save 90%" README claim.

It is a reproducible, agent-neutral harness for Codex, Claude Code, Gemini CLI, OpenCode, Kimi, and shell-first workflows.

The router is the small entry point: it scans cheap skill metadata and loads only the 0–3 skills that change the next action. The full stack adds measured shell filtering, bounded reads, profile checks, and reproducible benchmarks.

## Try the small part first

The public skill router is here:

https://github.com/Supersynergy/agent-token-saver-skill-router

It is intentionally tiny. Install it, benchmark your own skill library, and post the before/after numbers. If another tool beats it on the same accepted workload, that is a useful result too.

## What is not being claimed

My private Synapse memory layer is **not released** and is not required for the public router. The public stack works with normal CLI/file/socket interfaces; any memory integration is optional and replaceable.

No secrets, personal paths, or private infrastructure are part of the public product.

## The challenge

Run this on your own agent setup:

```bash
python3 scripts/agent_token_saver.py bench "your real task"
```

Post three things:

1. skills scanned
2. raw versus routed token estimate
3. whether the routed answer still passed your real task check

Less noise. Better judgment. Measured, not guessed.
