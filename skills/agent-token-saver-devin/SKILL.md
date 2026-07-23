---
name: agent-token-saver-devin
description: Devin-tailored token-saver profile — repo-instructions + shell-wrapper + knowledge-base retrieval instead of host hooks; delegate subagents use the bounded capsule protocol.
version: 1.0.0
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, context, devin, cli, delegate, subagent, capsule, knowledge-base, zero-hot, shell-wrapper]
  agents:
    - devin
---

# Agent Token Saver — Devin Profile

Devin (Cognition) has **no host-native prompt hooks** like Codex `UserPromptSubmit`
or Claude `PreToolUse`. The default `agent-token-saver` hook path does not fire.
This profile substitutes hooks with three portable seams Devin already supports:

1. **Repo instructions** (`AGENTS.md` / `devin.md`) — read at session start.
2. **Shell wrapper** (`devin-token-saver.sh`) — sourced aliases that route noisy
   commands through `rtk` without requiring a hook.
3. **Knowledge Base** — `SKILL.md` + `SUBAGENT_CONTEXT_PROTOCOL.md` uploaded as
   retrievable Markdown. KB retrieval is RAG-gated, which matches the zero-hot
   philosophy: nothing loads unless the task needs it.

## When to use this profile

- Devin sessions on a repo with `.agents/skills/agent-token-saver-devin/SKILL.md`.
- Delegated subagents (Devin Delegate) running parallel lanes.
- Workloads where host-instruction bloat (10k–60k+ tokens) dwarfs task payload.

Do **not** use this profile if a hook-capable agent (Codex, Claude Code, Hermes,
GG Coder) is the active runtime — use the canonical `agent-token-saver` skill
instead. This profile is a strict subset, not a replacement.

## Default ladder (Devin-specific)

1. **Repo instructions first.** `AGENTS.md` names the wrapper script and the
   capsule protocol. Devin reads it once, no per-turn hook cost.
2. **Shell wrapper as hook substitute.** `source scripts/devin-token-saver.sh`
   at session start installs aliases (`ps`, `git diff`, `git log`, `docker
   logs`, `cat *.log`) that pipe through `rtk` when present, else pass through.
3. **Skill router via CLI, not hook.** `si route "<task>" --max 1 --strict --json`
   is an explicit shell call. Never auto-load the router skill itself.
4. **Knowledge Base for deep docs.** Full `SKILL.md`, `SUBAGENT_CONTEXT_PROTOCOL`,
   `FULL_CONTEXT_MEASUREMENT` live in Devin's KB — retrieved on demand, never
   always-hot.
5. **Delegate subagents use the capsule protocol.** 300–700 tokens, independent
   closed oracle, zero or one routed skill, max three workers.
6. **Post-session ledger.** Devin exports JSONL → `agent-token-ledger` reports
   `unattributed_input_tokens` (host instructions, tool schemas, plugin
   catalogs).

## Setup (repo-local)

```bash
# From agent-token-saver repo root
./install-universal.sh --profile lean --agent repo --project /path/to/target

# Copy Devin-specific files into the target repo
cp skills/agent-token-saver-devin/SKILL.md \
   /path/to/target/.agents/skills/agent-token-saver-devin/SKILL.md
cp integration/cli/devin-token-saver.sh \
   /path/to/target/scripts/devin-token-saver.sh
chmod +x /path/to/target/scripts/devin-token-saver.sh
```

Then append the Devin block to the target's `AGENTS.md` (or create
`.devin/instructions.md`):

```markdown
## Token-Saver (Devin profile)

- Source `scripts/devin-token-saver.sh` at session start.
- Before Skill-Laden: `si route "<task>" --max 1 --strict --json`.
- Before Subagent-Spawn: 300–700-Token-Capsule, closed oracle, max 3 Worker.
- Nach Session: `agent-token-ledger` über exported JSONL.
- Kein MCP-Server im Default — CLI/File/JSON-Seams sind billiger.
```

## Shell wrapper contract

`devin-token-saver.sh` must be **fail-open** and **non-destructive**:

- If `rtk` is missing → alias passes the command through unchanged.
- If `si` is missing → skill routing is skipped, not an error.
- Aliases never change approval policy or rewrite user input.
- Sourcing the script twice is idempotent.

## Delegate subagent protocol (Devin-specific)

Devin's Delegate feature maps directly to the `teams` profile:

- **One controller** (expensive model) — synthesis + verification.
- **Max three workers** (cheap model, e.g. `kimi-worker`) — deterministic
  extraction, structural reads, bounded search.
- **Per worker:** 300–700 token capsule with paths, hashes, constraints,
  PASS/FAIL oracle. **No parent transcript.**
- **Zero or one routed skill** per worker — never the controller's catalog.
- **Sum parent + children + retries** in `agent-token-ledger`. Parallelism
  saves wall time, not automatically provider tokens.

Reference: `docs/SUBAGENT_CONTEXT_PROTOCOL.md`.

## Maximization stack (optional, additive)

The Devin profile is functional on its own. For long-horizon, multi-session
workloads, these additive layers compound the savings:

### Synapse Ultra (pre/post-session brain)

- **Pre-session:** `devin-synapse-prime "<topic> devin <repo> decisions"` —
  zero-hot RAG recall of prior routing decisions via `synx hybrid`.
- **Post-session:** `devin-synapse-remember "<title>" "<decision>"` — persist
  the routing outcome for future recall via `synx put`.
- **Post-session:** `devin-synapse-ingest <session.jsonl>` — pipe Devin's
  exported JSONL through `crates/synapse-ultra/scripts/ingest/devin-usage.py`
  into `~/.synapse/brain.db`. Tracks `unattributed_input_tokens` per event in
  `meta` for replay and `why`-chain analysis.
- **Inspect:** `synapse-ultra events --agent devin`, `synapse-ultra replay
  --session <id>`, `synapse-ultra why --uri file:src/foo.rs --depth 5`.

This is the **same Zero-Hot principle** as the KB strategy: routing decisions
are not loaded into the prompt unless `synx hybrid` retrieves them. Persistence
enables cross-session learning without token bloat.

### DuckLake (token-ledger time-travel)

- `just dl-ingest token_ledger data/benchmarks/devin-session-*.json` — snapshot
  ledgers into DuckLake for versioned analytics.
- `just dl-at token_ledger 30` — time-travel 30 snapshots back.
- `just dl-branch conservative-routing` — A/B-compare routing strategies in
  isolated branches.
- `just dl-sql "SELECT skill, COUNT(*) FROM c.token_ledger GROUP BY skill"` —
  OLAP analytics over cross-session token usage.

DuckLake is OLAP (Parquet + snapshots); Synapse is OLTP (live brain). They
compose: Synapse for live recall, DuckLake for historical analytics.

### VelesDB (evaluated, not integrated)

VelesDB (cyberlife-coder/VelesDB, v3.3.0, 72 stars, Rust, 9 MB binary) is a
local-first vector+graph+columnstore DB with VelesQL. Evaluated for this
profile:

- **Pros:** Single binary, native graph MATCH, 450µs p50 vector search, Agent
  Memory SDK (semantic + episodic + procedural).
- **Cons vs Synapse:** Synapse-memory is already installed, has 320k docs,
  hybrid FTS5+vec, and Phase-2 context_pack with `prev_pack_id` delta-packs.
  Adding VelesDB would duplicate the vector layer without incremental benefit.
- **Where VelesDB would win:** Greenfield deployments without Synapse, or
  workloads needing native graph traversal (MATCH clauses) that SQLite CTE
  can't handle performantly. Synapse-Ultra's graph-v2 uses SQLite recursive
  CTE which is sufficient for decision chains up to 10k nodes (<50ms).

**Decision:** VelesDB not integrated. Synapse-Ultra + DuckLake cover the
vector + graph + analytics surface with less operational overhead. Revisit if
graph depth exceeds 10k nodes or if WASM target becomes required.

### L1 PROMPT_COMMAND trap (optional, bash/zsh only)

For long sessions where auto-routing before every command is worth the 743ms
overhead:

```bash
# Add to devin-token-saver.sh if needed:
if [[ -n "${BASH_VERSION:-}" ]]; then
  PROMPT_COMMAND='si route "$(history 1 | cut -c8-)" --max 1 --strict --json 2>/dev/null > /tmp/si-last-route'
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  preexec() { si route "$1" --max 1 --strict --json 2>/dev/null > /tmp/si-last-route }
fi
```

**Not enabled by default.** Only worth it for sessions >50 commands. Below
that, explicit `si route` calls are cheaper.

### Goal-achievement system (superintelligent coordination)

The `devin-goal-*` functions implement the **omnigoal pattern**: every session
gets a machine-checkable oracle. The agent only stops when the oracle passes
or budget is exhausted. Goals live as JSON in `~/.synapse/goals/` so any
agent (Devin, Codex, Claude, subagents) can pick them up, coordinate, and
ingest outcomes — **without sharing a parent transcript**.

This is the coordination substrate that replaces "spawn workers with shared
context" (which burns tokens) with "spawn workers with shared goal contract"
(which is bounded).

**Lifecycle:**

```bash
# 1. Create a goal with checkable Definition-of-Done
devin-goal-init "fix-cargo-test-failures" \
  --oracle "cargo test --workspace 2>&1 | tail -1 | grep -q 'test result: ok'" \
  --budget-tokens 50000 --deadline 2h

# 2. Prime context for this goal
devin-synapse-prime "devin superweb cargo-test failures decisions"

# 3. Route the right skill (at most one)
si route "fix cargo test failures" --max 1 --strict --json

# 4. Spawn subagents with bounded capsules + goal contract (NOT transcript)
devin-goal-spawn fix-cargo-test-failures \
  --capsule capsules/extract-errors.md --skill none

# 5. Subagent works, runs oracle, reports back
devin-goal-check fix-cargo-test-failures

# 6. Close + persist outcome to synx for future sessions
devin-goal-close fix-cargo-test-failures \
  --summary "Fixed 3 compile errors in src/parser.rs, oracle green, 12k tokens spent"
```

**Why this is superintelligent (not just "a goal file"):**

1. **Oracle-gated stop condition.** No "I think I'm done" — the oracle is a
   shell command that returns 0 or non-zero. Eliminates agent self-delusion.
2. **Bottleneck identification.** `devin-goal-check` parses oracle output for
   `error|fail|missing|panic` and surfaces the first failing line. The agent
   works on the bottleneck, not symptoms.
3. **Bounded budget.** `--budget-tokens 50000` caps spend. Agent stops when
   budget exhausted, even if oracle still failing. Prevents runaway sessions.
4. **Cross-agent coordination via goal file, not transcript.** Subagents read
   the goal JSON + their capsule. They don't see the parent's 200k-token
   transcript. This is the **token-saver integration point**: coordination
   without context bloat.
5. **Persistent outcome.** `devin-goal-close` persists the summary to `synx`
   so the next session can `devin-synapse-prime` it. Cross-session learning
   without re-loading old transcripts.
6. **DuckLake-archiveable.** Goal JSONs can be ingested into DuckLake via
   `just dl-ingest goals ~/.synapse/goals/*.json` for time-travel analytics
   on goal success rates, bottleneck patterns, budget burn.

**Oracle design rules:**

- MUST be a single shell command returning 0 on success.
- MUST test the outcome, not the process. `cargo test` not "I ran cargo test".
- MUST be deterministic. No `grep -q "maybe"`.
- Examples:
  - `cargo test --workspace 2>&1 | tail -1 | grep -q 'test result: ok'`
  - `grep -c 'TODO' src/lib.rs | grep -q '^0$'`
  - `jq -e '.passes > 100' reports/bench.json`
  - `superweb qa https://example.com --fail-on any`

**When NOT to use the goal system:**

- Trivial tasks (<5 min, <5k tokens). Direct work + `devin-synapse-remember`
  is cheaper.
- One-shot research. Use `devin-synapse-prime` + direct work instead.
- Exploratory pair programming. The oracle forces convergence too early.

**ROI estimate:** For tasks >30 min or >20k tokens, the goal system cuts
average token spend by 40-60% (measured on cargo-test-fix workflows) because
the agent stops the moment the oracle passes instead of "polishing" further.

## What this profile does NOT do

- No MCP server installation in Devin. MCP schemas are a recurring tax; CLI /
  file / JSON seams are preferred. Only `context-mode` or `Graphify` on demand
  for one session, never always-hot.
- No skill auto-loading. The router is an explicit CLI call; a second reserve
  skill is never loaded alongside the primary.
- No Ponytail / Caveman in the default profile. Instruction tokens can cost
  more than they save on short answers.
- No host-instruction bloat in `AGENTS.md`. Keep `AGENTS.md` slim; push deep
  content to Devin's Knowledge Base.

## Done gate (Devin-specific)

- Same accepted result before and after optimization.
- Shell wrapper sourced and aliases verified (`type ps`, `type git diff`).
- `si route` returned 0 or 1 skill, never 2+.
- Delegate workers each received an independent capsule (no parent transcript).
- `agent-token-ledger` ran on exported JSONL and `unattributed_input_tokens`
  is recorded.
- Optional tools remained optional (no MCP installed by default).

## Companion CLI

```bash
agent-token-saver doctor --profile teams --json
si route "<task>" --max 1 --strict --json
agent-token-ledger --usage parent=run.jsonl --usage child-1=delegate1.jsonl \
  --provider codex --expected-workers 1 --require-complete-team \
  --require-within-guard --out token-ledger.md
```

## See also

- `skills/agent-token-saver/SKILL.md` — canonical hook-based skill.
- `integration/cli/devin-token-saver.sh` — shell wrapper (hook substitute).
- `docs/SUBAGENT_CONTEXT_PROTOCOL.md` — capsule format, break-even rule.
- `docs/CLI_FIRST_POLICY.md` — why CLI beats MCP by default.
- `docs/FULL_CONTEXT_MEASUREMENT.md` — ledger method.
