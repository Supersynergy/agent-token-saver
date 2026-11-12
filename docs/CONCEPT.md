# Der teuerste Token ist der nächste unnötige Schritt

Stand: 12. November 2026. Konzept und lokale Umsetzung von ATS 5.1.

Ein Agent kann eine Ausgabe um 99 Prozent kürzen und trotzdem länger brauchen.
Er übersieht einen Fehler, sucht erneut, liest die Rohdatei nach und beginnt den
Test von vorn. Die gesparten Zeichen sind weg. Die Zusatzrunde bleibt auf der Uhr.

Unser neuer Entwurf beginnt deshalb beim abgenommenen Ergebnis. Ein kleines
Ergebnis ohne erhaltene Prüfaussage ist kein Fortschritt. Die Denkfilter dafür:
Engpass suchen und die eigene Sparbehauptung widerlegen.

## Worauf es am meisten ankommt

### 1. Unnötige Runden entfernen

Vor einem Aufruf muss feststehen, welche offene Entscheidung er klärt.
Vorhandene Antworten und zum Quellenstand passende grüne Tests wiederverwenden.
Bekannte unabhängige Reads bündeln. Nach erfüllter Abnahme aufhören.

Das ist eine Priorität für den Ablauf, keine aus unseren ATS-Daten abgeleitete
allgemeine Prozentzahl. Wer sparen will, erfasst Anfragen, Wandzeit, Nacharbeit
und Nutzerunterbrechungen neben Tokens. Eine schnellere Textprojektion löst
keine Warteschlange und keinen falschen Auftrag.

### 2. Die Prüfaussage erhalten

Die Matrix vom 13. September schätzte 407.670 sichtbare Eingabeeinheiten im
Rohpfad und 1.932 im selektiven CLI-Pfad. Alle Gesamtreihen trugen `Accepted: no`.
Der Skill-Routing-Oracle scheiterte. Das Ergebnis darf keine Sparwerbung tragen.
[Quelle und Komponenten](../data/benchmarks/token-stack-matrix-2026-09-13.md).

Deshalb bewahrt `verify` Rohlogs und Exitcode, bevor eine Diagnose gekürzt wird.
`project` nennt ausgelassene Bytes. Ein Trefferlimit ist niemals eine komplette
Inventur. Ein leeres Diagnosefenster macht einen roten Befehl nicht grün.

Das Oracle selbst muss zur Aufgabe passen. Auch ein korrekt weitergereichter
Exitcode beweist nur, was der aufgerufene Check tatsächlich prüft.

### 3. Vor dem Modell auswählen

Die lokale Werkzeugmessung vom 13. September schrumpfte einen Git-Log-Ausschnitt
von 10.636 auf 52 geschätzte Einheiten. Bei `jq keys` waren es 48.487 auf 582.
Das zeigt, wo feste Projektionen helfen. Die Zahlen sind UTF-8-Bytes geteilt
durch vier; sie sind weder Anbieterzähler noch Eurobeträge.
[Quelle](../data/benchmarks/stack-tool-microbench-2026-09-13.md).

Zuerst genaue Suche oder benötigte Datenfelder. Danach ein begrenzter struktureller
Read. Größere Graphen oder Browser nur für eine benannte offene Frage. Ein
kleiner bekannter Log braucht keinen Indexdienst.

### 4. Cache und Ausgabe getrennt bepreisen

Der Codex-Vergleich vom 15. Juli meldete insgesamt 19,67 Prozent weniger
Anbietertokens. Die Prozesstabelle wurde dabei um 32,16 Prozent teurer.
Es war je ein Lauf pro Arm. Ein Durchschnitt ist kein Versprechen für jede Aufgabe.
[Quelle](../data/benchmarks/codex-provider-ab-2026-07-15/compact-policy/result.md).

Die drei Augustläufe zeigten stark schwankende Baselines und unterschiedliche
Vorzeichen bei rohen Tokens und gewichteten Listenpreis-Schätzungen. Die
ursprünglichen Preisverhältnisse sind historische Annahmen.
[Erster Lauf](../data/benchmarks/codex-provider-ab-2026-08-22-terra/result.md),
[zweiter](../data/benchmarks/codex-provider-ab-2026-08-22-terra-v2/result.md),
[dritter](../data/benchmarks/codex-provider-ab-2026-08-22-terra-v3/result.md).

Im Claude-Einzelvergleich vom 14. September war `cap-graperoot` nach rohen
Gesamttokens um 0,21 Prozent schlechter; die ausgewiesene Kostensumme lag
9,46 Prozent niedriger. `cap-budget` meldete 35,92 Prozent geringere Kosten,
aber nur 1,61 Prozent weniger gewichtete Gesamttokens. Das sind verschiedene
Messgrößen. Auch diese Stichprobe begründet keine allgemeine Voreinstellung.
[Quelle](../data/benchmarks/claude-ab-2026-09-14/result.md).

ATS 5 verlangt deshalb Preisquelle, Währung und getrennte Nutzungsklassen als
Eingabe. Modell, Anbieter und Tarif bleiben außerhalb des Kerns. Ein stabiler
Präfix kann Cachetreffer begünstigen; sein Wert muss im jeweiligen Lauf gemessen
werden. Erzwungene Warmhalteaufrufe gehören nicht zum Konzept.

### 5. Werkzeugpflege mitrechnen

Der Hook-Test vom 13. September maß bei einzelnen Synapse-Hooks rund vier
Sekunden. Der eigene ATS-Prompt-Hook lag bei rund 32 Millisekunden. Solche
Messungen beschreiben den damaligen Host und dessen Last, keine heutige Garantie.
[Quelle](../data/benchmarks/hook-stack-2026-09-13.md).

Der Juli-Test zeigte außerdem: Ein kompakteres Workerpaket konnte weniger Bytes
liefern und trotzdem eine etwas schlechtere Medianlaufzeit haben. Bytes und
Millisekunden brauchen getrennte Spalten.
[Quelle](../data/benchmarks/hook-and-capsule-hotpath-2026-07-27.md).

Der neue Standard braucht keine Prompt-Hooks. Das entfernt eine permanente
Eingriffsstelle. Ob TypeScript in einem bestimmten Hook schneller als Python
ist, wurde hier nicht gemessen. Der Wechsel dient einem einheitlichen,
überschaubaren Kern und ist kein Geschwindigkeitsbeleg.

## Ein kleiner Kern mit expliziten Aufgaben

| Befehl | Aufgabe | Aussagegrenze |
|---|---|---|
| `verify` | Einmal ausführen, vollständige Logs sichern, Exitcode erhalten | Der gewählte Prüfbefehl bestimmt die Abnahmequalität |
| `project` | Endansicht mit Bytebudget liefern | Auslassungen verhindern einen Vollständigkeitsbeleg |
| `cost` | Vorgegebene Nutzung mit angegebenen Preisen verrechnen | Schätzung, keine Anbieterrechnung |
| `skills` | Die 20 ausgewerteten Prinzipien nachschlagen | Keine automatische Skill-Ausführung |
| `install` | Eigene Generation und gesicherten Starter schreiben | Keine aktive Hostkonfiguration migrieren |
| `doctor` | Installierte Dateien prüfen | Keine echte Host- oder Kundenabnahme |
| `bench` | RTK gegen acht Aufgabenverträge prüfen | Synthetische Belege, keine allgemeine Rangliste |
| `guide` | Die nächste passende Aktion erklären | Keine automatische Werkzeugwahl |
| `rollback` | Vorherige Starter und Generation herstellen | Verweigert spätere fremde Änderungen |

Die Laufzeit hat null zusätzliche Pakete. Bun und die Node-Standardbibliothek
reichen. TypeScript und Bun-Typen sind auf feste Versionen gesetzte
Entwicklungsabhängigkeiten. [Buns TypeScript-Dokumentation](https://bun.sh/docs/runtime/typescript)
beschreibt die Trennung zwischen Ausführung und Typprüfung;
[Prozessaufrufe](https://bun.sh/docs/runtime/child-process) dokumentieren Argumentlisten
und getrennte Ausgabeströme.

## Was wir streichen und was wir bewahren

Aus dem Standard verschwinden automatische Kontextrouter, Providervermittlung,
mehrere überlappende Profile und still installierte Hosthooks. Ein eigener
Aufgabenmanager wäre Doppelpflege; bestehendes `sis` bleibt zuständig.

Benchmarkartefakte bleiben. Auch Gegenbefunde. Die Python- und Shell-Implementierungen
sind aus dem Produktbaum entfernt; vorliegende lokale Änderungen wurden zuvor
außerhalb gesichert. Die [Migration](MIGRATION.md) benennt jeden Funktionsbereich
und seinen Ersatz. Vorherige Fassungen bleiben in der Git-Historie lesbar.

Der [RTK-Vergleich vom 12. November](RTK.md) ergänzt die historischen Daten.
Er nimmt nur einen von acht Kandidaten an. Drei bringen keinen Bytegewinn,
vier verlieren verlangte Belege. Das begründet eine aufgabengebundene Auswahl,
keine pauschale Ablehnung von RTK.

## Wie eine neue Sparbehauptung zugelassen wird

Für einen künftigen Vergleich werden vorab Aufgabe, Modell, Quellhash und Oracle
festgelegt. Baseline und Kandidat laufen auf denselben unabhängigen Aufgaben,
mit wechselnder Reihenfolge und mehreren Wiederholungen. Zu erfassen sind
akzeptierte Ergebnisse, frische Eingabe, Cacheklassen, Ausgabe, Laufzeit,
Fehler und Nacharbeit. Alle gestarteten Läufe bleiben in der Bilanz.

Die Preisquelle trägt ein Datum. Lokale Bytesschätzungen stehen separat.
Ein gescheitertes Oracle sperrt die Sparbehauptung dieses Arms. Eine Änderung
an Oracle oder Fixture beginnt einen neuen Vergleich. Der lokale TypeScript-Gate
belegt Verhalten; Providerkosten und Kundennutzen sind damit noch nicht gemessen.
