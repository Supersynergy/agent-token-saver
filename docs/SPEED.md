# Geschwindigkeit am abgenommenen Ergebnis messen

Stand: 12. November 2026. Diese Seite übernimmt begrenzte Prinzipien aus den
lokalen Speed-Skills und Superloop. Sie startet deren Workflows nicht.
`ats guide speed` ist die kurze Merkhilfe.

## Erst unterscheiden, wo die Zeit bleibt

Ein langsamer Schritt kann Modellwartezeit, Prozessstart, tatsächliche Toolarbeit
oder Nacharbeit enthalten. Diese Zeiten brauchen getrennte Messungen. Die
Toollaufzeit aus `ats verify` enthält keine außerhalb des Aufrufs liegende
Modellwartezeit. Aus einer kleinen Werkzeugmessung lässt sich deshalb kein
Anteil an der gesamten Agentensitzung ableiten.

Vor einem Versuch stehen die konkrete Aufgabe, die unveränderte Prüfaussage
und die Abbruchbedingung. Ändere den vermuteten Engpass. Vergleiche denselben
Auftrag mit gleicher Abnahme und notiere Fehler statt sie aus der Bilanz zu
entfernen. Bei Startkosten Kalt- und Warmlauf trennen; bei CPU-Arbeit zusätzlich
CPU-Zeit beobachten. Ein einzelner niedriger Wanduhrwert kann Lastdrift sein.

## Was wir aus Superloop übernehmen

Der Ablauf Auftrag → Quelle finden → ändern → prüfen → Beleg → ausliefern ist
für einen vollständigen Slice brauchbar. Es ist ein Gerüst, keine Pflicht,
für jeden Dateinamen eine neue Planungsrunde zu erzeugen. Ein lokaler Lookup
bleibt ein direkter Lookup.

Einmalige Initialisierung kann sich für wiederholte Aufrufe lohnen. Das muss die
wirkliche Aufrufhäufigkeit tragen. Ein Dienst auf Vorrat kostet Ressourcen,
auch wenn nie ein zweiter Aufruf kommt. ATS startet deshalb keinen Daemon.

Gebündelte Abfragen sind nützlich, wenn die Einzelstatus und nötigen Belege
erhalten bleiben. Abhängige Änderungen bleiben geordnet. Ein gemeinsamer
Exitcode, der einen roten Teilschritt versteckt, ist kein Gewinn.

Der engste betroffene Check verkürzt den inneren Arbeitsloop. Vorgeschriebene
Release- oder Sicherheitsgates bleiben bestehen. Nach passender grüner Abnahme
endet die Arbeit; ein Quellenwechsel macht den alten Beleg nicht automatisch
für die neue Fassung gültig.

## Was wir ausdrücklich nicht übernehmen

- „Runden sind immer wichtiger als Millisekunden“ wird keine pauschale Regel.
  Zuerst Modellwartezeit und Toolzeit unterscheiden; Häufigkeit und Engpass messen.
- Ein fehlendes erforderliches Werkzeug ist kein bestandener Check. Optionales
  RTK wird als `unavailable` ausgewiesen; ein fehlender Pflicht-Oracle blockiert.
- Kein automatisches Reclaim, Töten fremder Prozesse oder Tracker-Fallback.
- Keine feste Turn-Grenze aus zwei Aufgaben und keine heutige Preisempfehlung
  aus einem alten Off-Peak-Vergleich.
- Keine zusätzlichen Keepalives, Hintergrund-Warmups oder Modellaufrufe zur
  Optimierung einer bereits deterministisch beantwortbaren Frage.

## Wie die Quellen verwendet wurden

`superloop` liefert das Phasengerüst. `speedtuning` liefert Kostenklassen und
Qualitätsinvarianten. `speedplaybook` liefert Gegenbeispiele für unpassende
Parallelität und nicht amortisierte Startkosten. Der lokale Harness-Bericht
zeigt die Grenze reiner Tokenminimierung. Die
[Quellhashes](../data/research/speed-review-2026-11-12.json) kennzeichnen die
geprüften Fassungen. Ihre Zahlen werden weder als ATS-Messung noch als
übertragbarer Beschleunigungsfaktor ausgegeben.

Die ursprüngliche [Auswahl der 20 Skills](SKILLS.md) bleibt als Entwurfsnachweis
erhalten. Diese zusätzliche Prüfung erweitert die Begründung, nicht die Zahl
der automatisch geladenen Skills oder die Befugnisse des Werkzeugs.
