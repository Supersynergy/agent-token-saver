# 20 Skills, 20 konkrete Beiträge

Stand: 12. November 2026. Auswahl aus dem lokalen SI Atlas für diesen Entwurf.
„Top“ bedeutet hier passend zum Engpass. Die Auswahl ist keine Leistungsrangliste.
Atlas-Nutzung und Score beweisen keine Qualität.

Antislop ist die aktive Text-Linse. Die anderen 19 liefern abgegrenzte Prinzipien;
ihre Workflows werden weder gemeinsam gestartet noch global installiert.
Die anwendbaren Einstiegsabschnitte wurden gelesen; tiefe Referenzbibliotheken
und optionale Skripte wurden nicht ausgeführt.

| Skill | Übernommenes Prinzip | Anwendung in ATS 5 | Grenze |
|---|---|---|---|
| `superfast` | Gesamtaufwand bis zur Abnahme messen. | Keine Zusatzrunden nach erfülltem Vertrag. | Eine Laufzeitverkürzung gilt erst bei gleicher Abnahme. |
| `aiworkflow` | Ziel und ausführbare Abnahme vor der Werkzeugwahl festlegen. | Ein CLI-Kern mit festen Befehlen statt mehrerer Controller. | verify führt den angegebenen Prüfbefehl unverändert aus. |
| `zeroloop` | Den engsten betroffenen Check wählen; nach Grün stoppen. | `just check` bündelt Typprüfung und Verhaltenstests. | Ein grüner Stand wird nicht zur Beruhigung erneut getestet. |
| `warm-handoff` | Weniger Anfragen auf kleinerem Kontext; stabile Übergaben. | Lange Logs bleiben als Dateien; Ergebnis enthält Pfade. | Keine periodischen Keepalives oder erzwungenen Neustarts. |
| `synapse-recall` | Nur frühere Entscheidungen laden, die den nächsten Schritt ändern. | Vorhandene Benchmarkartefakte auswerten statt alles neu messen. | Veränderliche Aussagen bleiben an Datum und Quelle gebunden. |
| `agent-efficiency-orchestrator` | Abgenommene Arbeit pro Gesamtaufwand optimieren. | Kein Sparversprechen, wenn die Abnahme scheitert. | Kosten separat von Laufzeit und Qualität berichten. |
| `superiss` | Claim und Quellenstand mit der Abnahme verbinden. | Projekt-DB explizit; ATS baut kein zweites Aufgabenboard. | ATS-result.json ersetzt keinen sis-Proof. |
| `best-defaults` | Kleine umkehrbare Voreinstellung mit begründetem Ausweg. | Installation zeigt zuerst einen Plan; --apply schreibt. | Keine globale Konfiguration bei einem Projekt-Update anfassen. |
| `antislop` | Jede Bewertung braucht eine prüfbare Aussage. | README mit einem gescheiterten Benchmark statt Siegesslogan. | slopcheck plus redaktionelle Streichprobe. |
| `thinkforward` | Engpass und Widerlegung als Denkfilter. | Gegenprobe: Kürzung verliert das Fehlersignal. | Tests prüfen Exitcode und Rohbeleg. Auslassungen bleiben sichtbar. |
| `speedplaybook` | Kostenklasse vor der Optimierung bestimmen. | Cachekosten separat von Prozesszeit und Ausgabemenge messen. | Kein pauschaler Geschwindigkeitsfaktor aus fremden Workloads. |
| `loop2goal` | Den nächsten Schritt am Oracle ausrichten. | verify liefert ein Ergebnisartefakt für genau eine Ausführung. | Das Ergebnis verweist auf seinen Rohbeleg. |
| `skill-portfolio-governance` | Überlappung und beobachtetes Verhalten vor Archivierung prüfen. | 20 Prinzipien kuratieren; keine 20 Skills automatisch laden. | Atlas-Score belegt weder Qualität noch allgemeine Rangfolge. |
| `verify-and-stop` | Pass, fail, unavailable und blocked unterscheiden. | Startfehler ist 127, Zeitlimit 124; keine künstliche grüne Ausgabe. | Nur die betroffenen roten Checks nach einer Korrektur wiederholen. |
| `researchflow` | Quellen sichern und prüfbare Aussagen daraus ableiten. | Quellenhash pro Skill und relative Benchmarklinks. | Messung von Schätzung trennen; Vorschläge eigens kennzeichnen. |
| `autom` | Einen begrenzten Kandidaten prüfen und behalten oder verwerfen. | Neue Defaults brauchen wiederholte Vergleiche mit festem Oracle. | Keine automatische Selbständerung und keine bezahlten Modellaufrufe. |
| `context-budget` | Geladene Regeln, Skills und Werkzeugdefinitionen sichtbar machen. | Keine dauerhafte breite Werkzeugregistrierung im Kern. | Pauschale Tokens-pro-Tool-Heuristiken gelten nicht als Abrechnung. |
| `systematic-debugging` | Ursache aus Fehlermeldung und Reproduktion bestimmen. | Vollständiges stdout und stderr vor jeder Kürzung sichern. | Leere oder ungewöhnliche Fehlerausgabe bleibt als Fehler sichtbar. |
| `ratiomaster` | Nutzeraufwand und tatsächlichen Erfolg gemeinsam messen. | Ein Aufruf bis zum Ergebnis; Dry-run und Rückbaupfad. | CLI-Laufzeit ist kein Beleg für Browser- oder Kunden-UX. |
| `ponytail` | Vorhandenes und Standardbibliothek vor neuer Abstraktion. | Bun und Node-Standardbibliothek; null Laufzeitpakete. | Keine Providervermittlung, Cronjobs oder generischen Plugins im Kern. |

Die [maschinenlesbare Auswahl](../data/skills-v5.json) enthält für jeden Eintrag
den SHA-256-Hash des gelesenen SKILL.md und den Atlas-Detailaufruf. Die Hashes
belegen den ausgewerteten Textstand; sie beweisen keine laufende Integration.
Quellenpfade bleiben lokal, damit dieser Katalog auf anderen Rechnern lesbar ist.

## Was bewusst draußen bleibt

Einige Spender beschreiben zusätzliche Reviewer, Hintergrundprozesse, Trainingsläufe
oder Python-Skripte. Daraus folgt kein Auftrag, diese zu starten. ATS übernimmt
die oben genannten Prinzipien und behält den Projektvertrag. Kundenabnahme braucht
einen echten Kundenbeleg; Simulation und lokaler Test bleiben getrennt.
