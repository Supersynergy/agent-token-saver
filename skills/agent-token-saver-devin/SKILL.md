---
name: agent-token-saver-devin
description: Devin token-saver profile — repo-instructions + shell-wrapper + KB retrieval instead of host hooks; subagents use bounded capsules.
version: 1.2.0
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, context, devin, cli, delegate, subagent, capsule, knowledge-base, zero-hot, shell-wrapper, synx, omnigoal]
  agents: [devin]
---

# Agent Token Saver — Devin Profile

Devin hat **keine host-nativen Prompt-Hooks** (wie Codex `UserPromptSubmit` oder Claude `PreToolUse`). Dieses Profil ersetzt Hooks durch 3 portable Seams:

1. **Repo-Instructions** (`AGENTS.md`) — einmal gelesen, keine per-turn Kosten.
2. **Shell-Wrapper** (`devin-token-saver.sh`) — sourced die universelle `agent-token-saver.sh` und leitet noisy Commands durch `rtk`.
3. **Knowledge Base** — `SKILL.md` + Referenzen, RAG-gated (zero-hot: lädt nur, wenn Task es braucht).

## When to use

- Devin-Sessions auf Repo mit `.agents/skills/agent-token-saver-devin/SKILL.md`.
- Delegate-Subagents (parallele Lanes).
- Workloads mit Host-Instruction-Bloat (10k–60k+ Tokens).

**Nicht verwenden** bei hook-fähigen Agents (Codex, Claude Code, Hermes, GG Coder) — da `agent-token-saver` canonical nutzen.

## Default ladder

1. `AGENTS.md` nennt Wrapper + Capsule-Protokoll — einmal gelesen.
2. `source scripts/devin-token-saver.sh` installiert Aliases (`ps`, `git diff`, `git log`, `docker logs`, `cat *.log`) → `rtk` wenn present, else passthrough. Die universellen `ats-*` / `goal-*` Funktionen kommen von `agent-token-saver.sh`; `devin-*` sind Backward-Compat-Aliase.
3. `si route "<task>" --max 1 --strict --json` — explicit CLI, nie auto-load.
4. KB für tiefe Docs — `FULL_CONTEXT_MEASUREMENT`, `SUBAGENT_CONTEXT_PROTOCOL` live in Devins KB.
5. Delegate-Subagents: 300–700 Token Capsule, closed oracle, max 3 Worker.
6. Post-Session: `agent-token-ledger` über exported JSONL → `unattributed_input_tokens`.

## Setup

```bash
./install-universal.sh --profile lean --agent repo --project /path/to/target
cp skills/agent-token-saver-devin/SKILL.md /path/to/target/.agents/skills/agent-token-saver-devin/
cp integration/cli/devin-token-saver.sh /path/to/target/scripts/ && chmod +x /path/to/target/scripts/devin-token-saver.sh
cp integration/cli/agent-token-saver.sh /path/to/target/scripts/ && chmod +x /path/to/target/scripts/agent-token-saver.sh
```

Dann Devin-Block an `AGENTS.md` anhängen (Template in `integration/cli/devin-bootstrap.md`).

## Wrapper contract (fail-open)

- `rtk` fehlt → Alias passthrough. `si` fehlt → Routing übersprungen. Kein Error.
- Aliases ändern nie Approval-Policy oder User-Input. Idempotent bei zweimaligem Sourcing.

## Delegate protocol

- **1 Controller** (teures Model) + **max 3 Worker** (billig, z.B. `kimi-worker`).
- **Pro Worker:** 300–700 Token Capsule (Pfade, Hashes, Constraints, PASS/FAIL-Oracle). **Kein Parent-Transcript.**
- **0 oder 1 gerouteter Skill** pro Worker — nie der Controller-Katalog.
- `agent-token-ledger` summiert Parent + Children + Retries. Parallelismus spart Wall-Time, nicht automatisch Provider-Tokens.

Ref: `docs/SUBAGENT_CONTEXT_PROTOCOL.md`.

## Maximization stack (optional, additiv)

### Synapse Ultra (Pre/Post-Session Brain)

- **Pre:** `ats-synapse-prime "<topic> devin <repo> decisions"` (alias: `devin-synapse-prime`) → `synx hybrid` zero-hot RAG.
- **Post:** `ats-synapse-remember "<title>" "<decision>"` (alias: `devin-synapse-remember`) → `synx put`.
- **Post:** `ats-synapse-ingest <session.jsonl>` (alias: `devin-synapse-ingest`) → `devin-usage.py` → `~/.synapse/brain.db`, tracks `unattributed_input_tokens` in `meta`. `ATS_AGENT_NAME=devin` wird vom Devin-Wrapper gesetzt.
- **Inspect:** `synapse-ultra events --agent devin`, `replay --session <id>`, `why --uri file:src/foo.rs --depth 5`.

### DuckLake (Token-Ledger Time-Travel)

- `just dl-ingest token_ledger data/benchmarks/devin-session-*.json` — Snapshots.
- `just dl-at token_ledger 30` — Time-Travel. `just dl-branch conservative-routing` — A/B.
- `just dl-sql "SELECT skill, COUNT(*) FROM c.token_ledger GROUP BY skill"` — OLAP.

DuckLake = OLAP (Parquet + Snapshots), Synapse = OLTP (live Brain). Sie komponieren.

### VelesDB & L1 PROMPT_COMMAND

Evaluiert, **nicht integriert**. Details in `MASTER-PLAN.md` §6 (Revisit-Kriterien) und §3 (L1-Trap-Conditions).

## Goal-achievement system (omnigoal pattern)

Die universelle `goal-*` CLI implementiert **oracle-gated stop**: Session stoppt wenn Oracle PASS oder Budget erschöpft. Goals als JSON in `~/.synapse/goals/` — cross-agent koordinierbar **ohne Transcript-Sharing**. `devin-goal-*` sind Backward-Compat-Aliase.

```bash
# 1. Goal mit checkable Definition-of-Done
goal-init "fix-cargo-test" \
  --oracle "cargo test --workspace 2>&1 | tail -1 | grep -q 'test result: ok'" \
  --budget-tokens 50000 --deadline 2h

# 2. Prime + Route + Spawn (Capsule, NICHT Transcript)
ats-synapse-prime "devin superweb cargo-test decisions"
si route "fix cargo test" --max 1 --strict --json
goal-spawn fix-cargo-test --capsule capsules/extract-errors.md --skill none

# 3. Check + Close (persistiert Summary zu synx)
goal-check fix-cargo-test
goal-close fix-cargo-test --summary "Fixed 3 errors, oracle green, 12k tokens"
```

**Warum superintelligent:**

1. **Oracle-gated stop** — keine "I think I'm done" Self-Delusion.
2. **Bottleneck-Identification** — `goal-check` extrahiert `error|fail|missing|panic`, Agent arbeitet an Root-Cause.
3. **Bounded budget** — `--budget-tokens` cappt Runaway-Sessions.
4. **Cross-agent coordination via Goal-JSON** — Subagents sehen Capsule + Goal, nicht 200k-Token-Transcript. Das ist der Token-Saver-Integration-Punkt.
5. **Persistent outcome** — `goal-close` → `synx put` → nächste Session kann `ats-synapse-prime` es abrufen.
6. **DuckLake-archiveable** — `just dl-ingest goals ~/.synapse/goals/*.json` für Time-Travel-Analytics.

**Oracle-Design-Regeln:**

- Single shell command, return 0 on success. Teste Outcome, nicht Process. Deterministisch.
- Beispiele: `cargo test ... | grep -q 'test result: ok'` · `grep -c 'TODO' src/lib.rs | grep -q '^0$'` · `jq -e '.passes > 100' reports/bench.json` · `superweb qa <url> --fail-on any`

**When NOT to use:** Triviale Tasks (<5 min, <5k Tokens) · One-shot Research · exploratives Pair-Programming (Oracle forciert zu frühe Konvergenz).

**ROI:** Bei Tasks >30 min oder >20k Tokens: 40–60% Token-Savings (gemessen auf cargo-test-fix Workflows).

## What this profile does NOT do

- **Kein MCP-Server** im Default — CLI/File/JSON-Seams sind billiger. Nur `context-mode`/`Graphify` on-demand.
- **Kein Skill-Auto-Loading** — Router ist explicit CLI. Max 1 Skill, nie 2+.
- **Kein Ponytail/Caveman** im Default — Instruction-Tokens kosten mehr als sie bei kurzen Answers sparen.
- **Kein Host-Instruction-Bloat** in `AGENTS.md` — tiefere Docs in KB.

## Done gate

- Selbes Resultat vor/nach Optimierung. · Wrapper sourced, Aliases verifiziert (`type ps`). · `si route` returned 0 oder 1 Skill. · Worker haben unabhängige Capsules. · `agent-token-ledger` ran, `unattributed_input_tokens` recorded. · Optionale Tools blieben optional.

## Companion CLI

```bash
agent-token-saver doctor --profile teams --json
si route "<task>" --max 1 --strict --json
agent-token-ledger --usage parent=run.jsonl --usage child-1=delegate1.jsonl --provider codex --expected-workers 1 --require-complete-team --require-within-guard --out token-ledger.md
```

## See also

- `skills/agent-token-saver/SKILL.md` — canonical hook-based skill.
- `integration/cli/agent-token-saver.sh` — universeller Shell-Wrapper (`ats-*` + `goal-*`).
- `integration/cli/devin-token-saver.sh` — Devin-spezifischer Wrapper (`devin-*` Aliase).
- `skills/agent-token-saver-devin/MASTER-PLAN.md` — 8-Phase Rollout + ROI-Messung + Test-Prompt.
- `skills/agent-token-saver-devin/capsule-template.md` — Capsule-Vorlage.
- `docs/SUBAGENT_CONTEXT_PROTOCOL.md` · `docs/CLI_FIRST_POLICY.md` · `docs/FULL_CONTEXT_MEASUREMENT.md`.
