# Token-Saver Research 2026-07-09

## Entscheidung

Der aktive Lean-Codex-Stack ist bereits nahe am Pareto-Punkt.

- Kein weiterer Always-on-MCP oder Kompressionsproxy.
- Neu prüfen: `mcp-token-audit` als Driftmessung und CompactBench als Qualitäts-Gate.
- Headroom/context-mode erst nach lokalem A/B-Test mit Ergebnisqualität verdrahten.
- Native Tool-Suche oder Schema-Kompression erst bei mehr als 20 Tools oder mehr als 10% Schemaanteil am Kontext.

## Lokale Realität

Headroom-Audit über 875 Codex-Sessions:

| Signal | Wert |
|---|---:|
| Exec-Aufrufe | 73.895 |
| Gesamte Tool-Ausgabe | 767.226.002 Bytes |
| Datei-Leseaufrufe | 24.539 |
| Datei-Leseausgabe | 140.719.367 Bytes |
| Search-Ausgabe | 77.465.758 Bytes |
| Read + Search am Gesamtvolumen | 28,4% |
| Wiederholte Reads | 8.639 / 35,2% |
| Reads über Kompressionsschwelle | 17.159 / 69,9% |

Das echte offene Potenzial liegt in wiederholten Reads, großen dynamischen Toolresultaten und Messbarkeit. Der Start-Schema-Bloat ist mit `tilth` als einzigem Standard-MCP bereits klein.

Aktueller Runtime-Check:

- Headroom v0.31.0; Proxy läuft, Codex wird noch nicht geroutet, keine Savings gemessen.
- context-mode v1.0.169; Storage/Server/FTS gesund, Codex-Hooks fehlen.
- Codex hat `enable_request_compression`, `remote_compaction_v2` und `shell_snapshot` aktiv.

## 300 YouTube-Videos

Recherchewege: `ghmax` für GitHub-Primärquellen, Superweb für aktuelle Web-/Herstellerquellen, lokaler YouTube-Transcript-Cache für das 300er-Sample. Die Nutzereingabe „Gerhard Marx“/„Sporbapp“ wurde als Spracherkennungsform von `ghmax`/Superweb verstanden; es wurden keine gleichnamigen Personen oder Kanäle vorausgesetzt.

### Methode

- Cache-Zeitraum: 2026-05-17 bis 2026-07-02.
- Bestand: 1.697 Video-IDs, davon 863 erfolgreiche Transkripte.
- Zehn exakte Phrasenfamilien: Kontext, Tokenkosten, Prompt-Caching, MCP/Tools, Retrieval/RAG, Kompaktion, Memory, Subagenten, Modellrouting, Outputfilterung.
- 378 relevante Kandidaten; nach Familienbreite, Phrasenbreite und Wiederholungen gerankt; Top 300 ausgewählt.
- Loader-Nachweis: 300 angefordert, 300 aus Cache, 300 erfolgreich, 0 neue Transcript-Fetches, 0 Fehler.
- Sprache: 294 Englisch, 5 Deutsch, 1 Französisch.
- Quelle: 169 `youtube-transcript-api`, 131 Innertube.
- Metadaten: 298/300 erfolgreich. Keine belastbaren Views oder Upload-Zeitpunkte; deshalb keine Creator-Influence-/Velocity-Rangliste.

### Beobachtete Cluster

Cluster überlappen; Zahlen sind Videos mit mindestens einem Signal.

| Cluster | Videos |
|---|---:|
| MCP-/Tool-Bloat | 150 |
| Context Engineering | 130 |
| Subagenten/Isolation | 114 |
| Tokenökonomie/Budgets | 90 |
| Retrieval/RAG | 76 |
| Modellrouting | 47 |
| Agent Memory | 39 |
| CLI-/Tool-Outputfilterung | 25 |
| Compression/Compaction | 16 |
| Prompt-Caching | 5 |

### Was davon für Codex trägt

1. Toolfläche klein halten und Schemas bei Bedarf entdecken. Bereits umgesetzt: `tilth`-only, übrige Werkzeuge CLI/on-demand.
2. Nur taskrelevanten Kontext laden; Masse in Dateien/Retrieval halten. Bereits umgesetzt: Synapse, `rg`, Tilth, Graphify/CodeGraph nur gezielt.
3. Recherche in isolierte Subagenten geben; nur verdichtete Ergebnisse zurückholen. Bereits umgesetzt.
4. Token-/Reasoning-Budget an die Aufgabe koppeln. Weitgehend umgesetzt.
5. Memory selektiv abrufen, nie vollständig vorladen. Bereits umgesetzt: Synapse top-k.
6. Shell-/Toolausgabe vor Modellkontakt filtern. Bereits umgesetzt: RTK; Projektion großer JSON/CSV/API-Payloads weiter ausbauen.
7. Nur an klaren Grenzen kompaktieren; bei Aufgabenwechsel frischen Task starten. Native Compaction bevorzugen.
8. Prompt-/Toolpräfix stabil halten. Noch messbar machen: Cache-Hit-Verhältnis und Drift-Gate.
9. CLI/on-demand einem gleichwertigen Always-on-MCP vorziehen. Bereits umgesetzt.
10. Schmale Skills gezielt laden statt alle Regeln ständig einzublenden. Bereits umgesetzt: Skill-Router.

YouTube-Behauptungen, die nicht als Fakt übernommen wurden:

- Exakte „60–70% durch CLI“-Angabe: Richtung plausibel, Zahl nicht primär bestätigt.
- „RAG ist tot“: wegen fehlendem Vergleichsbenchmark nicht übernommen; 76/300 zeigen nur Diskussionshäufigkeit. Aktuelle Progressive-Discovery-Implementierungen sind ein separates Gegenbeispiel.
- „Permanent Memory“ via Mem0/AgentMemory: kein Vergleichsbenchmark gegen Synapse.
- „1M Kontext löst Kontextverlust“: Kapazität ist nicht gleich effektive Genauigkeit.
- 90%-Cache-Versprechen: keine Codex-spezifische lokale Messung.

Repräsentative Videos:

- https://www.youtube.com/watch?v=nsWdSaKVbIY
- https://www.youtube.com/watch?v=QoQBzR1NIqI
- https://www.youtube.com/watch?v=hpC4qjWu_aY
- https://www.youtube.com/watch?v=6cEQEba0i2A
- https://www.youtube.com/watch?v=kkBFmwkDzdo
- https://www.youtube.com/watch?v=0bpYCxv2qhw
- https://www.youtube.com/watch?v=miDg-3rSJlQ
- https://www.youtube.com/watch?v=nXROzh6vOps

## GitHub-Scan: neue Kandidaten

| Rang | Kandidat | Urteil | Warum |
|---:|---|---|---|
| 1 | https://github.com/michaeltuszynski/mcp-token-audit | Test | Kleine Diagnose; zählt Schema-Tokens und erzeugt ein Deferred-Loading-Manifest. Kein Laufzeitdienst. Jung/0 Sterne: Source-Audit und Fixture-Test zuerst. |
| 2 | https://github.com/compactbench/compactbench | Test | Misst Qualitätsverlust über wiederholte Compaction-Zyklen. Spart selbst keine Tokens, verhindert aber falsche Optimierung. |
| 3 | https://github.com/openai/openai-agents-python | Adopt für eigene Responses-Agenten | Native `defer_loading`/Tool Search. Nicht als Codex-Host-Funktion belegt. |
| 4 | https://github.com/SKZL-AI/tscg | Heavy A/B | Deterministische Schema-Kompression; nur bei großer Toolfläche und zuerst im konservativen Description-only-Modus. |
| 5 | https://github.com/KGT24k/mcp-tool-search | Watch | Vier Meta-Tools plus Lazy Spawn; zusätzliche Turns. Erst bei 20+ Tools/mehreren Servern. |
| 6 | https://github.com/assimelha/cmcp | Avoid default | Code Mode kann Schemafläche stark drücken, erweitert aber Rechte und Blast Radius. Nur isoliertes Heavy-Profil. |

Bereits abgedeckt oder negativer Grenznutzen:

- https://github.com/open-compress/claw-compactor — überschneidet Headroom + RTK + context-mode.
- https://github.com/AssafWoo/homebrew-pandafilter — überschneidet RTK + Headroom.
- https://github.com/jia-gao/leanctx und https://github.com/microsoft/LLMLingua — höchstens lange RAG-Prosa; nicht Code, Security oder exakte Logs.
- https://github.com/repoprompt/repoprompt-ce und https://github.com/yamadashy/repomix — One-off-Handoff okay; interaktiv durch Tilth/Graphify/CodeGraph abgedeckt.

## Primärquellen-Check

- OpenAI Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI Compaction: https://developers.openai.com/api/docs/guides/compaction
- OpenAI Tool Search: https://developers.openai.com/api/docs/guides/tools-tool-search
- Anthropic Code Execution mit MCP: https://www.anthropic.com/engineering/code-execution-with-mcp
- Anthropic Advanced Tool Use: https://www.anthropic.com/engineering/advanced-tool-use
- Anthropic Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- Anthropic Context Editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
- Cloudflare Code Mode: https://blog.cloudflare.com/code-mode-mcp/
- MCP Client Best Practices: https://modelcontextprotocol.io/docs/develop/clients/client-best-practices
- MCP Tools Specification: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- Context Rot replication: https://github.com/chroma-core/context-rot
- Context Rot paper: https://aclanthology.org/2025.findings-emnlp.1264/

Herstellerbenchmarks sind Richtungsbelege, keine lokalen Einsparungswerte. Lokale Adoption verlangt immer: Inputtokens, akzeptiertes Ergebnis, Cache-Hit, Latenz, Nacharbeit und Betriebsaufwand.

Reproduzierbare Auswahl-/Auditdaten:

- `../data/research/token-saver-2026-07-09/youtube-token-saver-300-analysis.json` — alle 300 IDs, Ranking-Signale, Cluster und Loader-Protokoll.
- `../data/research/token-saver-2026-07-09/headroom-codex-audit.json` — Headroom-Audit der 875 Codex-Sessions.

## Umsetzungsreihenfolge

1. Startup-/Schema-Drift-Test hinzufügen.
2. Headroom/context-mode mit CompactBench oder kleiner lokaler Qualitäts-Suite vergleichen.
3. Cache-Hygiene messen: stabile Tools/Instructions innerhalb einer Session; Taskwechsel als frischer Task.
4. Nur wenn >20 Tools oder >10% Schemaanteil: native Deferred Tool Search zuerst, TSCG A/B zweitens.
5. Kein neues MCP oder Kompressionsmodell ohne lokalen Netto-Gewinn.
