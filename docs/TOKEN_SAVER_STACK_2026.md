# Token Saver Stack 2026 — SuperSynergy Default

Stand: 2026-07-09
Ambition: in geeigneten Payload-Klassen 80–99% weniger Kontext-/Ausgabe-Tokens. End-to-end-Ersparnis und gleiche Trefferquote sind erst nach Task-Evals belegt.

## Antwort in 60 Sekunden

Der beste Stack ist kein einzelner Compressor. Es ist eine Kette:

1. **Nicht laden** — Skill-Router, MCP-Allowlist, Tool-Suche statt Tool-Dump.
2. **Stabil cachen** — Systemprompt, Regeln, Tool-Schemas, häufige Präfixe.
3. **Gezielt holen** — Synapse/FTS/CodeGraph/Graphify vor Datei-Dumps.
4. **Output filtern** — RTK für Terminal, Headroom für Tool/RAG/Logs, Preview statt Rohdaten.
5. **Reversibel speichern** — Context-Mode/Synapse halten Originale + Retrieval-Pfade; Graphify hält den abgeleiteten Projektgraphen.
6. **Kurz antworten** — Ponytail/Output-Shaper gegen Zeremonie und Erklär-Overhead.
7. **Messen erzwingen** — Token-Ledger, Budget-Gates, Benchmark vor Default-Rollout.

SuperSynergy Default:

```text
ask/Synapse -> Skill Router -> ghmax/superweb CLI only when needed
-> MCP Dynamic Toolset only when >20 tools or schemas >10% of context
-> tool execution via RTK/batch/hyperfetch
-> Headroom for large tool/RAG/log payloads
-> context-mode snapshots + Synapse/Graphify durable memory
-> output shaper / Ponytail for concise delivery
-> token ledger + benchmark gates
```

## Geprüfte lokale Evidenz

| Bereich | Befehl | Ergebnis |
|---|---|---:|
| Skill-Router Katalog-Benchmark | `python3 scripts/agent_token_saver.py bench "deep hermes token saver stack top50 context optimization"` in `$HOME/BASE/projects/agent-token-saver-skill-router` | 456 Skills; 36.840 → 211 geschätzte Katalog-Tokens, **99,43% Reduktion**. Nicht der gesamte Taskkontext. |
| Token-Saver Tests | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest` | **14 passed in 0.13s** |
| Hermes Desktop Patch | `cd $HOME/.hermes/hermes-agent/apps/desktop && npm run typecheck` | **OK** |
| Headroom | `headroom doctor` | v0.31.0; persistenter Proxy :8787 (launchd), Claude Code + Codex via `headroom init -g` geroutet (2026-07-12) |
| Context-Mode | `context-mode doctor` | Alle Checks PASS nach `context-mode upgrade` (2026-07-12); Codex-Seite läuft über Headroom-Proxy |
| RTK | `rtk --version` | v0.43.0 installiert |
| ghmax | `ghmax --doctor` | **17/17 OK** |
| superweb | `superweb doctor` | **HEALTHY** |
| Recherche | `superweb mega ...` | 26 URLs fetched, 25 final pages |

Wichtig: Ein erster `uv run pytest` ohne `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` wurde durch globale `langsmith`/`pydantic_core` Plugin-Kontamination blockiert. Der isolierte Testlauf ist der kanonische Nachweis.

Zusätzlicher lokaler Stack-Benchmark in diesem Repo:

```bash
python3 scripts/token_saver_benchmark.py
```

| Case | Base tok | Opt tok | Saved | Factor | Ergebnis |
|---|---:|---:|---:|---:|---|
| RTK `ps aux` filter, Beispielrun | 45,459 | 1,408 | 96.9% | 32.29x | ✅ flüchtige Prozessliste |
| Tilth README smart read | 5,172 | 683 | 86.8% | 7.57x | ✅ |
| context-mode README search | 5,172 | 474 | 90.8% | 10.91x | ✅ |
| hyperfetch markdown on tiny page | 139 | 207 | -48.9% | 0.67x | ✅ Backfire erkannt |
| MCP schema slimming proxy | 5,649 | 577 | 89.8% | 9.79x | ✅ |
| Headroom profile render | 121 | 121 | 0.0% | 1.0x | ✅ install check |

Tokenwerte sind UTF-8-Bytes/4-Schätzungen und messen Payload-Größe, nicht Taskqualität. Exakte `ps aux`-Werte ändern sich pro Lauf. Regel daraus: Web-Markdown/LLM-Extraktion nur mit Schwelle aktivieren; sehr kleine Seiten roh lassen.

## Universelle Formel

Token-Kosten sind drei Ströme:

```text
Gesamt = statischer Kontext + dynamischer Kontext + Ausgabe
```

Optimierungsformel:

```text
EffectiveTokens =
  StaticTokens
    × CacheMissRate
    × (1 - StaticDedup)
    × (1 - SchemaCompression)
+
  DynamicTokens
    × RetrievalSelectivity
    × OutputFilterRatio
    × CompressionRatio
    × RepetitionRatio
+
  OutputTokens
    × VerbosityRatio
    × ReworkRatio
```

Startheuristiken, noch nicht universell kalibriert:

```text
CacheMissRate        <= 0.10 für stabile Präfixe
RetrievalSelectivity <= 0.05 bis 0.20 statt whole-file / whole-doc
OutputFilterRatio   <= 0.05 bis 0.30 für Terminal/Logs/JSON
VerbosityRatio      <= 0.30 bis 0.60 für Routineantworten
ReworkRatio         <= 1.0; alles >1 heißt Kontext hat Fehler erzeugt
```

Entscheidungsregel:

```text
Adoptieren, wenn:
  Nettoersparnis = TokenSavedValue - (LatencyCost + ErrorRisk + MaintenanceCost) > 0

und:
  AccuracyDrop wird mit derselben Task-Suite gemessen
  keine Null-Auswirkung durch Filterung/Caching/Routing voraussetzen
```

## Optimale Verdrahtung für Hermes/SuperSynergy

### 1. Systemprompt und Skills

Default:

```text
Systemprompt stabil halten -> Provider Cache trifft.
Skills nie komplett laden -> Router zuerst -> nur 0–3 Skills laden.
Lange Regeln in Dateien/Skills -> erst bei Bedarf nachladen.
```

Default-Tools:

- Skill Router / `agent-token-saver-skill-router`
- Synapse `synxp` / `ask`
- Hermes `skill_view` just-in-time
- Ponytail für Lean-Code/Anti-Overengineering, nicht für Faktentreue-Kompression

### 2. MCP-Schema-Bloat

Problem: Große MCP-Server verbrennen Kontext nur durch Tool-Schemas.

Default für eine gemessen große Toolfläche:

```text
Bei >20 Tools oder >10% Schemaanteil native Deferred Tool Search zuerst testen.
Nur falls der Client das nicht kann, Gateway A/B testen:
  list/search tools -> select -> load exact schema -> call
```

Herstellerbenchmarks und Muster; erst an der Schwelle testen:

- Dynamic Toolsets nach Speakeasy/Gram-Muster: bis 96% Input- und 90% Gesamtreduktion laut veröffentlichter Benchmark-Seite.
- `mcp-compressor`-Muster nach Atlassian: 70–97% Tool-Schema-Reduktion je Kompressionslevel.
- Hermes/OpenClaw: Agent-/Tool-Policy + allowlist + lazy tool schema loading.

### 3. Terminal- und Build-Output

Default:

```text
rtk <cmd> für noisy commands.
rtk test / rtk pytest / rtk tsc / rtk npm statt Rohoutput.
Bei Debug: erst summary, dann gezielte Fehlzeilen.
```

Nicht komprimieren:

- Security findings ohne Originalzugriff
- Migration output mit eindeutigen IDs
- Zahlungs-/Money-/Trading-Daten ohne Auditpfad

### 4. Tool/RAG/Log-Kompression

Default:

```text
Headroom nur für große dynamische Payloads.
Original muss abrufbar bleiben.
Kein Blind-Summarize für kleine exakte Daten.
```

Lokaler Status (2026-07-12):

- Headroom v0.31.0 installiert; persistenter Proxy (launchd, Preset `persistent-service`) läuft auf `http://127.0.0.1:8787`.
- Claude Code und Codex sind via `headroom init -g claude` / `headroom init -g codex` durch den Proxy geroutet; `headroom doctor` grün.
- Savings-Ledger beginnt zu füllen; Netto-Wirkung nach einigen Sessions mit `headroom savings` bewerten.
- Gotcha: erster Start lädt ein ONNX-Embedding-Modell; meldet `install apply` "did not become ready", einfach erneut ausführen (Modell dann gecacht).

Nachmessen statt glauben:

```bash
headroom doctor
headroom savings
```

Nur bei messbarem Netto-Gewinn aus Tokens, akzeptierter Ergebnisqualität, Latenz und Nacharbeit als Default aktivieren.

### 5. Retrieval statt Dump

Default-Reihenfolge:

```text
search_files / rg files-only -> read_file line window -> codegraph/Graphify -> full file nur wenn nötig
```

Für Web:

```text
known URL -> hyperfetch <url> --markdown  # diese lokale hyperfetch-Version unterstützt kein --stage
2–1000 URLs -> batchscraper
unknown/current -> ask/Synapse -> ghmax -> superweb CLI on-demand
```

Superweb Policy:

```text
Superweb is available on demand, not disabled.
Use CLI, not MCP-default context.
Do not run a persistent `superweb mcp serve` unless a specific experiment requires it.
Default commands: `superweb search`, `superweb research`, `superweb mega`, `superweb fetch`.
Write large outputs to `data/research/...` or `/tmp/...`, then summarize before model context.
```

### 6. Memory und Langzeitkontext

Default:

```text
Session state ≠ Memory.
Dauerhafte Fakten -> Synapse/Memory/Graphify.
Zwischenstand -> session_search / context-mode snapshot.
```

Context-Mode Status:

- Storage PASS.
- Server test PASS.
- Codex hooks fehlen aktuell in `$HOME/.codex/hooks.json`.

Nächster Test, nicht ungeprüft als Default verdrahten:

```bash
context-mode doctor
# Hooks zuerst gegen Headroom/native Compaction mit gleicher Aufgabe benchmarken.
```

## Top-50 Context-/Token-Saving Tools und Methoden

Score: 0–10 für SuperSynergy-Nutzen.
Status: `adopt` = jetzt nutzen, `test` = Bench nötig, `watch` = beobachten, `avoid` = nur Referenz.

| # | Tool/Methode | Link | Haupthebel | Score | Status | SuperSynergy Default |
|---:|---|---|---|---:|---|---|
| 1 | RTK | local: `rtk 0.43.0` | Terminal-output filtering | 10 | adopt | Noisy shell immer via `rtk` |
| 2 | Headroom | https://github.com/headroomlabs-ai/headroom | Reversible context compression | 9 | test | Proxy/MCP für große Tool/RAG/Log-Payloads |
| 3 | context-mode MCP | local: `context-mode doctor` | Session snapshots / context recovery | 9 | test | Gegen native Compaction/Headroom benchmarken |
| 4 | Skill Router | local: `$HOME/BASE/projects/agent-token-saver-skill-router` | Lazy skill loading | 10 | adopt | Router vor Skill-Load |
| 5 | Ponytail | https://github.com/DietrichGebert/ponytail | Lean output / anti-overengineering | 8 | test | Für Code-Review/Lean-Modus, nicht als Faktenfilter |
| 6 | Synapse / ask | local: `ask`, `synxp` | Local KB before web/API | 10 | adopt | Immer erste Recherche-Stufe |
| 7 | Graphify | local install | Graph memory | 8 | adopt | Projektwissen graphen statt wiederholen |
| 8 | CodeGraph | local: `$HOME/.local/bin/codegraph` | Code retrieval | 9 | adopt | Symbol-/Graphsuche vor Datei-Dump |
| 9 | ghmax | local: `ghmax --doctor` | Current code pattern mining | 8 | adopt | GitHub-Muster ohne Browser-Rauschen |
| 10 | superweb CLI | local: `superweb doctor` | Multi-engine web + extract | 8 | adopt | On-demand via CLI nach Synapse/ghmax; nicht MCP-default |
| 11 | hyperfetch | local stack | Known URL markdown extraction | 9 | adopt | URL → markdown, nicht HTML-Dump |
| 12 | batchscraper | local stack | Parallel URL fetch | 8 | adopt | 2–1000 URLs, kein Loop-Fetch |
| 13 | Dynamic Toolsets / Gram | https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2 | MCP schema discovery | 9 | test | Tool-search gateway statt 100 Tools laden |
| 14 | Atlassian mcp-compressor | https://www.atlassian.com/blog/development/mcp-compression-preventing-tool-bloat-in-ai-agents | MCP schema compression | 8 | test | Für große MCP-Server benchmarken |
| 15 | MCP allowlist/policy | method | Tool surface minimization | 10 | adopt | Nur aktive Tools pro Task expose |
| 16 | MCP pagination | method | Response bloat control | 9 | adopt | `limit`, `fields`, `cursor`, `summary` Pflicht |
| 17 | JSON projection | method | Drop unused fields | 9 | adopt | `jq`/schema-select before model |
| 18 | TOON-like tabular encoding | method | Compact structured data | 7 | test | Nur tabellarische payloads |
| 19 | LLMLingua | https://github.com/microsoft/LLMLingua | Prompt compression | 7 | test | Offline RAG/prose compression, nicht code-critical |
| 20 | LongLLMLingua | https://github.com/microsoft/LLMLingua | Long-context prompt compression | 7 | test | Long docs mit retrieval guard |
| 21 | Selective Context | method/paper family | Entropy-based pruning | 6 | watch | Nur mit accuracy eval |
| 22 | Prompt caching | provider feature | Static prefix cost reduction | 10 | adopt | System/tool prefixes stabil halten |
| 23 | Cache-aware prompt layout | method | KV/cache hits | 9 | adopt | Variable tail ans Ende |
| 24 | Response cache | method | Repeat-call elimination | 8 | adopt | Deterministische lookups cachen |
| 25 | Semantic cache | method | Similar-call elimination | 6 | test | Nur low-risk Q&A, nie CRM writes |
| 26 | Model routing | method | Cheap model for cheap tasks | 9 | adopt | Small/fast for classify, strong for architecture |
| 27 | Batch APIs | provider feature | Discount/non-urgent work | 7 | test | Research jobs, not interactive ops |
| 28 | Output shaper | Headroom/Ponytail/method | Output-token reduction | 9 | adopt | Code-only/summary-only defaults |
| 29 | Caveman-style rules | method | Short direct answers | 7 | test | Use where clarity remains intact |
| 30 | Transcript compaction | method | History pruning | 8 | adopt | Compact at ~70%, not 95% |
| 31 | Handoff summaries | method | Session continuity | 8 | adopt | Decisions + paths + commands only |
| 32 | Error-only test output | RTK/method | Test noise removal | 9 | adopt | PASS summary + failures only |
| 33 | Log deduplication | RTK/Headroom/method | Repeated lines removal | 9 | adopt | Keep first/last/error windows |
| 34 | AST-aware code compression | Headroom/method | Code context slimming | 7 | test | Never replace exact code needed for edits |
| 35 | tree-sitter chunking | method | Symbol windows | 8 | adopt | Function/class chunks instead whole file |
| 36 | File windowing | Hermes `read_file` | Line-limited reads | 10 | adopt | 200–500 lines, paginate |
| 37 | Search before read | Hermes `search_files` | Avoid full files | 10 | adopt | files-only/count/content modes |
| 38 | Diff-only context | method | Review context slimming | 9 | adopt | Diffs over full files |
| 39 | Difftastic/semantic diff | Headroom `diff`/method | Review clarity | 7 | test | Large refactors only |
| 40 | Dependency inventory | bumblebee/local | Avoid lockfile dumps | 8 | adopt | Scan summaries, not full lockfiles |
| 41 | Local package facts cache | Synapse method | Avoid repeated web fetch | 8 | adopt | Store durable version/API findings |
| 42 | Vector + FTS hybrid retrieval | SQLite FTS5/sqlite-vec/Qdrant | Relevant snippets | 8 | adopt | Local-first retrieval layer |
| 43 | Reranking | method | Smaller top-k | 7 | adopt | Top 5–10, not top 50 |
| 44 | Query decomposition | method | Targeted retrieval | 7 | adopt | Ask smaller precise searches |
| 45 | Context budget gate | method/skill | Prevent overflow | 9 | adopt | Hard budgets per turn/tool |
| 46 | Tool-output contracts | method | Prevent retries | 8 | adopt | JSON schemas / concise result shape |
| 47 | Structured final reports | method | Fewer clarification turns | 8 | adopt | Summary/Why/Changes/Validation |
| 48 | Local preview artifacts | method | Files instead of chat dumps | 8 | adopt | `MEDIA:/path` or doc links for large output |
| 49 | Human approval gates | method | Avoid costly wrong side effects | 9 | adopt | CRM/outreach never auto-send |
| 50 | Token ledger + regression tests | method | Compounding measurement | 10 | adopt | CI fails on token blowups |

## Best-practice defaults

### Default command policy

```text
Noisy command? rtk wrapper.
File content? read_file window.
Search? search_files / ghmax / Synapse first.
Web URL? hyperfetch markdown.
Bulk URLs? batchscraper.
Fresh web/current facts? superweb CLI on-demand.
MCP? lazy tool discovery; no full tool dump.
```

### Default MCP policy — Startheuristik

```text
Expose <= 12 tools per task by default.
If server has >20 tools: require dynamic discovery/compression.
Every tool response supports: fields, limit, cursor, summary.
Large responses return artifact handle + short digest.
```

### Default context budget — Startheuristik

```text
System + rules:        <= 15% of window, cached/stable
Tools schemas:         <= 10%, ideally <= 3%
Retrieved context:     <= 25%, ranked
Conversation history:  <= 25%, compacted
Scratch/output budget: >= 25% reserved
```

### Default benchmark gate

Before adopting any new saver globally:

```text
1. Measure baseline tokens + latency + task success.
2. Enable saver.
3. Run same workload.
4. Compare: tokens, latency, success, rework, exactness.
5. Adopt only if net score improves.
```

Unkalibrierter Startscore; Gewichte nach realen Task-Evals anpassen:

```text
Score = 0.45*TokenReduction + 0.25*AccuracyRetention + 0.15*LatencyScore + 0.10*Reversibility + 0.05*MaintenanceFit
```

Minimum:

```text
Score >= 0.75 for default-on
Score >= 0.60 for opt-in
Below 0.60: keep as research only
```

## Immediate SuperSynergy TODO

1. Add a drift test for startup instructions and serialized tool-schema tokens.
2. Codex/Claude route now through Headroom (2026-07-12): watch accepted-task quality + `headroom savings` over the next sessions; unroute (`headroom unwrap codex`) if quality drops.
3. Keep the lean default at `tilth` only; test native deferred loading first if the profile exceeds 20 tools or schemas exceed 10% of context.
4. Measure cache-hit ratio when Codex exposes it; keep tools/instructions stable inside a running task.
5. Keep RTK default for noisy commands and the Skill Router before skill loading.
6. Do not add Claw Compactor, PandaFilter, LLMLingua, RepoPrompt, Repomix or another MCP proxy without a local A/B win.

Current cross-source research: [`TOKEN_SAVER_RESEARCH_2026-07-09.md`](./TOKEN_SAVER_RESEARCH_2026-07-09.md).

## Research sources captured locally

Research artifacts:

- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/00-ask.txt`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/10-ghmax.txt`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/20-superweb-mega.md`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/20-superweb-mega.jsonl`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/21-superweb-search.md`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/30-local-tool-doctor.txt`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/30-superweb-research.md`
- `$HOME/BASE/projects/agent-token-saver/data/research/token-saver-2026-07-09/40-ghmax-summary.txt`
- `$HOME/BASE/projects/agent-token-saver/data/benchmarks/token-saver-local-2026-07-09.md`
- `$HOME/BASE/projects/agent-token-saver/data/benchmarks/token-saver-local-2026-07-09.json`

Primary/current links:

- https://github.com/headroomlabs-ai/headroom
- https://github.com/DietrichGebert/ponytail
- https://github.com/microsoft/LLMLingua
- https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2
- https://www.atlassian.com/blog/development/mcp-compression-preventing-tool-bloat-in-ai-agents
- https://www.stackone.com/blog/mcp-token-optimization/
- https://www.mindstudio.ai/blog/reduce-token-usage-ai-agents-mcp-optimization
- https://github.com/olivomarco/github-copilot-token-optimization
- https://github.com/pleasedodisturb/awesome-llm-token-optimization
