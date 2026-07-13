# Agent Token Saver — Launch Kit

## Non-negotiable launch truth

- The public standalone router is `agent-token-saver-skill-router`.
- The private Synapse memory layer is not released, not required, and must not appear as a product dependency.
- Public claims must use reproducible benchmark artifacts and state their acceptance oracle.
- Do not publish the full-stack release until the canonical GitHub name is resolved.

## Product ladder

```text
Skill Router (free wedge)
  -> proves 0-3 skill lazy-loading on a user's own library
  -> links to Agent Token Saver

Agent Token Saver (full open-source harness)
  -> RTK + deterministic projection + profiles + doctor + benchmarks
  -> links back to the Router for the 60-second start
```

## Router v1.0.6 GitHub Release copy

### Title

`v1.0.6 — Better test/debug routing without loading more skills`

### Body

The router still keeps the default at 0-3 loaded skills. This release makes those few choices more accurate.

- Uses frontmatter tags in ranking.
- Normalizes common test/debug terms such as `pytest`, `testing`, and `failed`.
- Prefers relevant software-development skills over generic name collisions.
- Keeps broad controller manifests capped at 10 paths; workers still receive only their own 1-3 active skills.

Measured on 458 installed skills: **37,080 → 227 estimated catalog tokens** before the task-specific skill bodies are loaded.

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- codex
```

Verify your own environment:

```bash
python3 scripts/agent_token_saver.py bench "debug failing pytest in a Python project"
```

This is a router, not a magic compression proxy. It chooses the smallest useful skill set; benchmark results remain estimates until you run them on your own library.

## Full-stack GitHub Release copy — only after canonical URL is fixed

### Title

`v2.1.0 — Measured context routing for coding agents`

### Body

Agent Token Saver is a reproducible token-efficiency harness for coding agents.

On one accepted local workload:

- raw stack: 380,871 tokens
- Lean automatic profile: 4,476 tokens
- reduction: 98.8%

The benchmark rejects a smaller result that loses required signals or changes the expected exit code.

The public core is agent-neutral: skill routing, RTK output filtering, deterministic projection, bounded reads, profile doctor, and benchmark artifacts. Heavy graph/browser/context tools remain on demand.

Private Synapse infrastructure is not part of this release. Memory remains an optional replaceable CLI adapter.

## README hero

```text
Stop paying context tax before your agent starts working.

Agent Token Saver gives Codex, Claude Code and other coding agents the smallest decisive context.

380,871 raw tokens -> 4,476 Lean tokens on the same accepted workload.

[Start with the 60-second Skill Router] [See the reproducible benchmark]
```

## Social card

```text
YOUR AGENT DOES NOT NEED EVERY SKILL

458 skills -> 3 loaded
37,080 -> 227 catalog tokens

Less noise. Better judgment.
Measured, not guessed.
```

## 15-second terminal demo

```text
0-03s  Show a 458-skill inventory.
03-06s Run: agent_token_saver.py route "debug failing pytest in Python"
06-09s Show exactly three selected skills.
09-12s Run: bench "same task"
12-15s Freeze on: 37,080 -> 227 tokens | 99.39% estimated reduction.
```

Do not show private paths, Synapse data, model keys, or a raw full terminal history.

## Skool post CTA

> Run the benchmark on your own skill library. Share skills scanned, raw versus routed token estimate, and whether the answer still passed your real check.

This makes the community produce comparable proof, not testimonials.

## Launch order

1. Choose canonical full-stack repository URL.
2. Fix all `agent-token-saver` links or rename the repository so redirects are real.
3. Release router `v1.0.6` from commit `63aa6f8`.
4. Publish a clean full-stack release from a clean worktree with benchmark JSON/Markdown attached.
5. Publish the Skool post plus social card and terminal GIF.
6. Open a GitHub discussion: `Post your benchmark — accepted workload required`.

## Success metrics, week one

| Metric | Target | Why |
|---|---:|---|
| Router installs | 50 | Proves wedge clarity |
| User-posted benchmark receipts | 10 | More credible than claims |
| Full-stack conversion from router README | 15% | Validates product ladder |
| Open benchmark issues/PRs | 5 | Makes the benchmark a living standard |
