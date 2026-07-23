# Devin Token-Saver — Master-Plan

**v1.3.0** (2026-07-23) · Universal `ats-*` + `goal-*` CLI + Devin-specific wrapper · SynapseUltra + DuckLake + Goal-System · live-validated

## Ziel

Maximaler ROI für Devin — clean, lean, intelligent — über 3 Schichten:

1. **Token-Saver Core** — Universal Shell-Wrapper (`agent-token-saver.sh` mit `ats-*`) + Devin-Wrapper (`devin-token-saver.sh` mit `devin-*` Aliassen) + Skill-Router + Ledger (Zero-Hot KB)
2. **SynapseUltra Brain** — Pre/Post-Session RAG, Event-Log, Cost-Analytics
3. **Goal-System** — Oracle-gated Stop, Cross-Agent Coordination via Goal-JSON

Alle Schichten fail-open. Kein MCP-Server. Kein Balast. `synx` statt `syn`.
Universal `ats-*` / `goal-*` für jeden Agent; `devin-*` als Backward-Compat-Aliase.

## Architektur

```
Devin Session
  Start:  source devin-token-saver.sh · ats-doctor (alias: devin-token-doctor) · ats-synapse-prime · goal-init
  Work:   si route --max 1 --strict · rtk aliases · goal-spawn · goal-check
  End:    ats-token-ledger · ats-synapse-ingest · goal-close · just dl-ingest goals
                │
                ▼
~/.synapse/  brain.db (events, graph, cost) · goals/*.json (oracle, budget, subagents)
                │
                ▼
DuckLake  token_ledger snapshots · goals snapshots · branches (conservative/aggressive routing)
```

Universal `agent-token-saver.sh` stellt `ats-*` + `goal-*` bereit. `devin-token-saver.sh`
setzt `ATS_AGENT_NAME=devin` + `ATS_ACTIVE_SKILL=…devin/SKILL.md` und liefert `devin-*`
Aliase für bestehende Sessions.

## Rollout-Checkliste

### Phase A — Core Wrapper ✅

- [x] `integration/cli/agent-token-saver.sh` · universelle `ats-*` Funktionen + Fail-open Aliases (`ps`, `gitdiff`, `gitlog`, `dockerlogs`, `journalctl`, `catlog`)
- [x] `integration/cli/devin-token-saver.sh` · Devin-spezifischer Wrapper (sources universal + `devin-*` Aliase)
- [x] `ats-doctor` (alias: `devin-token-doctor`) prüft 9 Tools · `AGENT_TOKEN_SAVER_LOADED` + `DEVIN_TOKEN_SAVER_LOADED` Guards · `bash -n` grün · idempotent

### Phase B — Skill-Router ✅

- [x] `si route --max 1 --strict --json` einziger Routing-Aufruf · Max 1 Skill, nie Router selbst
- [x] `SKILL.md` + `devin-bootstrap.md` + README aktualisiert

### Phase C — SynapseUltra ✅ live validiert

- [x] `syn` → `synx` Rename · `ats-synapse-prime` / `-remember` / `-ingest` (Aliase: `devin-synapse-*`)
- [x] `devin-usage.py` erstellt · `unattributed_input_tokens` in `meta` · `ATS_AGENT_NAME=devin` wird vom Devin-Wrapper gesetzt
- [x] Live: 2 Events ingestiert, `replay` grün · `prime` returned 4 Treffer · Doctor zeigt `synx`+`synapse-ultra`+`duckdb`

### Phase D — DuckLake ✅ recipes ready

- [x] `justfile.ducklake` in superweb · AGENTS.md + SKILL.md DuckLake-Blöcke
- [ ] **TODO (Devin-Web):** `just dl-ingest token_ledger ...` · `just dl-at token_ledger 5` · `just dl-branch conservative-routing`

### Phase E — Goal-System ✅ live validiert

- [x] Universelle `goal-init/check/close/spawn` CLI (in `goal.sh`) · `devin-goal-*` als 1-Zeilen-Aliase · Goals in `~/.synapse/goals/` · `jq` im Doctor
- [x] SKILL.md + AGENTS.md Goal-Sektionen · Smoke-Test 20/20 grün (`tests/test_goal_system.sh`)
- [ ] **TODO (Devin-Web):** `goal-init` für echte cargo-test-Task · `spawn` mit echtem Capsule · `close --summary` in `synx` verifizieren

### Phase F — VelesDB ✅ evaluiert, nicht integriert

- [x] Recherche + Pros/Cons + Entscheidung: Synapse deckt Vector+Graph ab. Revisit bei >10k Nodes oder WASM-Target.

### Phase G — Benchmark & Doku ✅

- [x] `devin-profile-2026-07-23.json` v1.3.0 · KB-Savings 79,62 % · Universal-Wrapper 3.678 Tokens · Devin-Wrapper ~1.100 Tokens · AGENTS-Block 1.102 Tokens · MASTER-PLAN.md

### Phase H — Live-Test in Devin Web ⏳

- [ ] Devin-Web-Session mit `superweb`-Repo · Test-Prompt ausführen (siehe §Test-Prompt)
- [ ] `devin-token-doctor` (oder `ats-doctor`) + `si route` + `goal-init/check` für echte Task
- [ ] Session-JSONL exportieren · `ats-token-ledger` (alias: `devin-token-ledger`) · `ats-synapse-ingest`
- [ ] `goal-close --summary` (alias: `devin-goal-close`) · `synx find "goal-close:"` verifizieren
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
  source scripts/devin-token-saver.sh   # sources universal agent-token-saver.sh + devin-* aliases
  devin-token-doctor                     # alias for ats-doctor
  devin-synapse-prime "devin superweb token-saver decisions"   # alias for ats-synapse-prime

Task: Fix any compile errors in `cargo test --workspace --no-run`.
Use the goal system (universal goal-* CLI; devin-goal-* are aliases):
  goal-init "fix-cargo-test" \
    --oracle "cargo test --workspace --no-run 2>&1 | tail -1 | grep -q 'Finished'" \
    --budget-tokens 50000 --deadline 1h
  # If errors: goal-spawn fix-cargo-test --capsule capsules/extract-errors.md
  # Work on bottleneck from goal-check. Repeat until oracle passes.
  goal-check fix-cargo-test
  goal-close fix-cargo-test --summary "Fixed N errors, M tokens spent"

Post-task:
  # Export session JSONL, then:
  ats-token-ledger <session.jsonl>                  # alias: devin-token-ledger
  ats-synapse-ingest <session.jsonl> --session superweb-$(date +%F)   # alias: devin-synapse-ingest

Report:
  - unattributed_input_tokens from the ledger
  - synapse-ultra events --agent devin --limit 5
  - goal status: goal-check fix-cargo-test
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

**Bei neuen Agents:** gleicher Goal-JSON-Contract · universelle `ats-*` Funktionen aus `agent-token-saver.sh` verwenden · eigener Ingest-Script in `synapse-memory/crates/synapse-ultra/scripts/ingest/` · `ATS_AGENT_NAME=<name>` setzen (oder eigenen Wrapper wie `devin-token-saver.sh` schreiben).

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
- [ ] Mindestens 1 `goal-close` (alias: `devin-goal-close`) mit `synx put` persistiert
- [ ] Mindestens 1 DuckLake-Snapshot von `token_ledger` erstellt
- [ ] Benchmark-JSON mit Live-Daten aktualisiert

**Effort:** 4-6h (inkl. Devin-Web-Test) · **Maintenance:** 15 min/Monat
