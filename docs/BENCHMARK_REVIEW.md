# Was die anderen Benchmarks am Entwurf ändern

Prüfstand: 12. November 2026. Ausgewertet wurden vorhandene Berichte; es wurden
keine bezahlten Modellläufe neu gestartet. Aussagen bleiben an den damaligen
Host, die Aufgabe und die Messmethode gebunden.

## Weniger Agenten kann mehr erledigen

Am 16. Juli löste ein einzelner Projektions-Worker die Logaufgabe mit 129.836
Brutto-Eingabetokens. Das Team aus drei Workern brauchte 390.010 für denselben
Oracle. Der große Rohlese-Arm verbrauchte mehr und zählte trotzdem falsch.
Ein Team kauft gegebenenfalls Parallelität; eine einzelne feste Projektion
braucht deshalb noch keinen Agentenschwarm.
[Quelle](../data/benchmarks/claude-team-ab-2026-07-16.md).

Der damalige Bericht empfahl auch, Kinder zeitversetzt zu starten. Die
Gegenprobe vom 19. Juli widerlegte diesen Cachevorteil auf dem geprüften Host:
411.938 Brutto-Eingabetokens bei gleichzeitigem Start, 411.946 bei versetztem
Start. Die spätere Messung ersetzt diese frühere Empfehlung. ATS installiert
weder einen Scheduler noch ein allgemeines Fan-out-Rezept.
[Quelle](../data/benchmarks/claude-stagger-ab-2026-07-19.md).

## Ein günstiger Dokumentenausschnitt kann die falsche Bibliothek beschreiben

Die Dokumentationsmessung vom 3. September enthielt 5 thematisch falsche Antworten
unter 12 Zeilen, zwei Versionsabweichungen und eine ausdrückliche Ablehnung.
Die kleinste Ausgabe war gerade keine Antwort. Eine Ablehnung darf nicht als
bestes Sparresultat gewertet werden.

Vor einer Dokumentationsabkürzung müssen Bibliothek und Version passen. Bei einem
solchen Fehler hilft die passende Primärquelle mehr als zusätzliche Kompression.
Die Vergleichswerte der Rohquellen waren in diesem Lauf nicht frisch abgerufen;
auch die ausgewiesenen Bytegewinne haben deshalb eine begrenzte Aussagekraft.
[Quelle](../data/benchmarks/freshdocs-lane-2026-09-03.md).

## Eine Proxy-Differenz beweist keinen Kompressionseffekt

Der Headroom-Einzelvergleich meldete beim großen Git-Diff 45.206 gegenüber 20.598
Gesamttokens, beide Oracles grün. Der Proxy selbst meldete dabei null entfernte
Tokens. Daraus folgt eine beobachtete Differenz zwischen diesen Läufen; die
Ursache ist damit nicht isoliert. Reihenfolge und Cachezustand beeinflussen den
Vergleich. ATS baut daraus keine automatische Proxyroute.
[Quelle](../data/benchmarks/headroom-ab-2026-07-18/result.md).

## Kleine Pakete sind noch keine vollständige Abnahme

Der Capsule-Vergleich verkleinerte ein Drei-Worker-Paket von 3.800 auf 530
geschätzte Einheiten. Das war eine lokale Kapazitätsrechnung ohne Anbieteraufruf.
Sie belegt weder eine Rechnungsersparnis noch bessere Ergebnisse der Worker.
Die sinnvolle Übernahme bleibt ein begrenzter Arbeitsauftrag mit Belegpfaden;
das ist keine Begründung, neue Worker automatisch zu starten.
[Quelle](../data/benchmarks/swarm-control-2026-07-27.md).

## Die kurze Sitzung war nicht automatisch die günstigere Lösung

Ein weiterer lokaler Harness-Bericht vom 30. Oktober verglich kleine Aufgaben
mit unveränderten versteckten Tests. Ein „fast“-Arm benötigte weniger Prompt-Tokens,
löste aber nur eine von zwei Aufgaben. Die ausgewiesenen Kosten pro gelöster
Aufgabe lagen deshalb über der langsameren Baseline. Das Beispiel begründet
Kosten pro abgenommener Aufgabe als Zielgröße, keine heutige Modellrangliste.

Derselbe Bericht zeigte steigenden Aufwand bei einer langen fortgesetzten
Sitzung. Die dort vorgeschlagene feste Turn-Grenze wird hier nicht übernommen:
Sie hängt an wenigen Aufgaben, und eine schwierige dritte Aufgabe wurde aus der
Haupttabelle ausgeschlossen. Ein allgemeiner Grenzwert braucht andere Evidenz.
Das Quellprotokoll ist lokal; seine Hashes stehen im
[Quellnachweis](../data/research/speed-review-2026-11-12.json). Vollständige private
Versuchsdateien werden nicht mitveröffentlicht.

## Folgerungen für ATS 5.1

Die neue Hilfe `ats guide speed` trennt Modellwartezeit von Toolzeit. Die
[Speed-Seite](SPEED.md) beschreibt die Auswahl des nächsten Schritts.
Automatische Modelle, Off-Peak-Zeitpläne und feste Turn-Caps bleiben draußen.
Historische Preisannahmen werden nicht als aktuelle Tarife übernommen.

Die [acht RTK-Verträge](RTK.md) ergänzen diese Befunde mit einem anderen Maßstab.
Ein Rohbeleg bleibt ausgewählt, wenn ein Filter Pflichtinformationen verliert
oder keine Bytes spart. Auch ein angenommener Literalvergleich ist schwächer
als eine echte Fehlerbehebung. Anbieterpreise und Tokenklassen bleiben eigene
Eingaben in `ats cost`.
