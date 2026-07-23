# Devin Token-Saver — Master-Plan

**v1.2.0** (2026-07-23) · SynapseUltra + DuckLake + Goal-System · live-validated

## Ziel

Maximaler ROI für Devin — clean, lean, intelligent — über 3 Schichten:

1. **Token-Saver Core** — Shell-Wrapper + Skill-Router + Ledger (Zero-Hot KB)
2. **SynapseUltra Brain** — Pre/Post-Session RAG, Event-Log, Cost-Analytics
3. **Goal-System** — Oracle-gated Stop, Cross-Agent Coordination via Goal-JSON

Alle Schichten fail-open. Kein MCP-Server. Kein Balast. `synx` statt `syn`.

## Architektur

```
Devin Session
  Start:  source devin-token-saver.sh · devin-token-doctor · devin-synapse-prime · devin-goal-init
  Work:   si route --max 1 --strict · rtk aliases · devin-goal-spawn · devin-goal-check
  End:    devin-token-ledger · devin-synapse-ingest · devin-goal-close · just dl-ingest goals
                │
                ▼
~/.synapse/  brain.db (events, graph, cost) · goals/*.json (oracle, budget, subagents)
                │
                ▼
DuckLake  token_ledger snapshots · goals snapshots · branches (conservative/aggressive routing)
```

## Rollout-Checkliste

### Phase A — Core Wrapper ✅

- [x] `integration/cli/devin-token-saver.sh` · Fail-open Aliases (`ps`, `gitdiff`, `gitlog`, `dockerlogs`, `journalctl`, `catlog`)
- [x] `devin-token-doctor` prüft 9 Tools · `DEVIN_TOKEN_SAVER_LOADED` Guard · `bash -n` grün · idempotent

### Phase B — Skill-Router ✅

- [x] `si route --max 1 --strict --json` einziger Routing-Aufruf · Max 1 Skill, nie Router selbst
- [x] `SKILL.md` + `devin-bootstrap.md` + README aktualisiert

### Phase C — SynapseUltra ✅ live validiert

- [x] `syn` → `synx` Rename · `devin-synapse-prime` / `-remember` / `-ingest`
- [x] `devin-usage.py` erstellt · `unattributed_input_tokens` in `meta`
- [x] Live: 2 Events ingestiert, `replay` grün · `prime` returned 4 Treffer · Doctor zeigt `synx`+`synapse-ultra`+`duckdb`

### Phase D — DuckLake ✅ recipes ready

- [x] `justfile.ducklake` in superweb · AGENTS.md + SKILL.md DuckLake-Blöcke
- [ ] **TODO (Devin-Web):** `just dl-ingest token_ledger ...` · `just dl-at token_ledger 5` · `just dl-branch conservative-routing`

### Phase E — Goal-System ✅ live validiert

- [x] `devin-goal-init/check/close/spawn` · Goals in `~/.synapse/goals/` · `jq` im Doctor
- [x] SKILL.md + AGENTS.md Goal-Sektionen · Smoke-Test 9/9 grün
- [ ] **TODO (Devin-Web):** `devin-goal-init` für echte cargo-test-Task · `spawn` mit echtem Capsule · `close --summary` in `synx` verifizieren

### Phase F — VelesDB ✅ evaluiert, nicht integriert

- [x] Recherche + Pros/Cons + Entscheidung: Synapse deckt Vector+Graph ab. Revisit bei >10k Nodes oder WASM-Target.

### Phase G — Benchmark & Doku ✅

- [x] `devin-profile-2026-07-23.json` v1.2.0 · KB-Savings 79,62 % · Wrapper 3.678 Tokens · AGENTS-Block 1.102 Tokens · MASTER-PLAN.md

### Phase H — Live-Test in Devin Web ⏳

- [ ] Devin-Web-Session mit `superweb`-Repo · Test-Prompt ausführen (siehe §Test-Prompt)
- [ ] `devin-token-doctor` + `si route` + `devin-goal-init/check` für echte Task
- [ ] Session-JSONL exportieren · `devin-token-ledger` · `devin-synapse-ingest`
- [ ] `devin-goal-close --summary` · `synx find "goal-close:"` verifizieren
- [ ] Benchmark-JSON mit Live-Daten aktualisieren

## ROI-Messung

```
saved_tokens = baseline_unattributed − actual_unattributed
ROI = saved_tokens / baseline
```

| Schicht | Saved | ROI kumuliert |
|---|---:|---:|
| Core Wrapper (Aliases + si route) | 8.000 | 40 % |
| + SynapseUltra Prime (zero-hot RAG) | +3.000 | 55 % |
| + Goal-System (oracle-gated stop) | +4.000 | 75 % |
| + DuckLake (cross-session learning) | +1.000 | 80 % |

**Balast vermieden:** Kein MCP-Server (−2k Tokens/Session) · Kein Ponytail/Caveman · Kein L1-Trap (−743ms/Cmd) · Kein VelesDB · Kein Auto-Skill-Loading · KB statt Inline-Docs (79,62 % Always-Hot-Ersparnis).

## Test-Prompt (Devin Web, Copy-Paste)

```
You are working in the superweb repo with the agent-token-saver-devin profile.

Start:
  source scripts/devin-token-saver.sh
  devin-token-doctor
  devin-synapse-prime "devin superweb token-saver decisions"

Task: Fix any compile errors in `cargo test --workspace --no-run`.
Use the goal system:
  devin-goal-init "fix-cargo-test" \
    --oracle "cargo test --workspace --no-run 2>&1 | tail -1 | grep -q 'Finished'" \
    --budget-tokens 50000 --deadline 1h
  # If errors: devin-goal-spawn fix-cargo-test --capsule capsules/extract-errors.md
  # Work on bottleneck from devin-goal-check. Repeat until oracle passes.
  devin-goal-check fix-cargo-test
  devin-goal-close fix-cargo-test --summary "Fixed N errors, M tokens spent"

Post-task:
  # Export session JSONL, then:
  devin-token-ledger <session.jsonl>
  devin-synapse-ingest <session.jsonl --session superweb-$(date +%F)

Report:
  - unattributed_input_tokens from the ledger
  - synapse-ultra events --agent devin --limit 5
  - goal status: devin-goal-check
  - synx memory: synx find "goal-close:"

Constraints:
  - No MCP server. CLI / file / JSON seams only.
  - Fail-open: missing rtk/si/synx → proceed without them.
  - Keep AGENTS.md slim; deep docs in Knowledge Base.
  - Max 1 skill via si route. Max 3 subagents. Max 3 attempts.
```

## Wartung

**Monatlich:** `synapse-ultra doctor` · `synx doctor` · DuckLake-Snapshots aufräumen · `~/.synapse/goals/` archivieren (geschlossene nach 30d) · Benchmark aktualisieren.

**Bei neuen Skills:** in `skills/` ablegen · in Devin-KB referenzieren (nicht in `AGENTS.md` inline) · Oracle-Beispiel im SKILL.md.

**Bei neuen Agents:** gleicher Goal-JSON-Contract · eigener Ingest-Script in `synapse-memory/crates/synapse-ultra/scripts/ingest/` · `--agent <name>` übergeben.

**Revisit-Kriterien:** VelesDB bei Graph >10k Nodes oder WASM · L1-Trap bei Sessions >50 Commands · MCP nur bei Devin-Schema-Caching · Dolt bei OLTP auf Goals.

## Known Limitations

- **Keine nativen Hooks** — Shell-Wrapper + Repo-Instructions als Workaround. User muss Wrapper manuell sourcen.
- **`synapse-ultra cost` zeigt keine Rows** für Devin — Cost in `meta`, nicht in `token_cost`. Workaround: `events --agent devin` + `jq`.
- **DuckLake JSON-Inlining-Bug** — JSON mit `CAST(... AS DATE)`-Strings nicht deserialisierbar. Workaround: JSONL/CSV statt JSON.
- **Goal-System benötigt `jq`** — Fail-open: ohne `jq` werden Goal-Funktionen übersprungen.
- **Budget-Enforcement ist Advisory** — `--budget-tokens` gespeichert, nicht hard-enforced. Hard-Enforcement möglich via `agent-token-ledger --warn-total-tokens` im Oracle.

## Definition of Done

- [ ] Alle Phase A-G Boxen angehakt
- [ ] Phase H Live-Test durchgeführt
- [ ] `unattributed_input_tokens`-Reduktion ≥40 % gemessen
- [ ] Mindestens 1 `devin-goal-close` mit `synx put` persistiert
- [ ] Mindestens 1 DuckLake-Snapshot von `token_ledger` erstellt
- [ ] Benchmark-JSON mit Live-Daten aktualisiert

**Effort:** 4-6h (inkl. Devin-Web-Test) · **Maintenance:** 15 min/Monat
