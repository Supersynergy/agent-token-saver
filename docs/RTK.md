# Wann RTK hilft und wann die Kürzung Arbeit macht

Stand: 12. November 2026. Lokal geprüft mit RTK 1.2.0 und Bun 1.4.4.
Die Fixtures sind synthetisch. Pro Aufgabe lief ein Filterprozess; echte
Projektprüfungen und Anbieteraufrufe waren nicht beteiligt.

Eine frühe Version unseres Ansatzes stellte die gesparten Ausgabebytes in den
Vordergrund. Damit ließ sich ein großer Effekt zeigen, ohne zu beantworten,
ob der Agent anschließend noch richtig handeln konnte. Der neue Vergleich
stellt zuerst die Frage und legt danach die benötigten Belege fest.

## Das Ergebnis dieser acht Fragen

| Aufgabe | Rohtext | RTK-Kandidat | Ausgewählt | Befund |
|---|---:|---:|---:|---|
| kurze Erfolgsmeldung lesen | 19 B | 19 B | 19 B | kein Bytegewinn |
| TypeScript-Fehler lokalisieren | 7.630 B | 230 B | 230 B | benötigte Dateinamen und Fehlercodes erhalten |
| alle 180 Routentreffer liefern | 10.510 B | 10.510 B | 10.510 B | kein Bytegewinn |
| einen Routentreffer liefern | 10.510 B | 10.510 B | 10.510 B | kein Bytegewinn; gezielte Auswahl braucht 59 B |
| alle 240 Dateipfade liefern | 6.720 B | 220 B | 6.720 B | alle vollständigen Pfadbelege fehlen im Kandidaten |
| letzte fünf Commitbetreffe lesen | 6.880 B | 169 B | 6.880 B | drei verlangte Betreffe fehlen |
| Testfehler mit Ort und Soll-/Ist-Werten lesen | 592 B | 51 B | 592 B | verlangte Detailbelege fehlen |
| ungewöhnlichen Fehler lesen | 7.506 B | 32 B | 7.506 B | Fehlerkennung und Wiederholungswert fehlen |

Ein Kandidat wurde angenommen, drei brachten keine Byteersparnis und vier
verloren festgelegte Belege. Bei den sieben verworfenen Kandidaten blieb der
Rohtext ausgewählt. Eine riskante Kürzung zählt nicht als Gewinn.
[Maschinenlesbarer Bericht](../data/benchmarks/rtk-2026-11-12.json) und
[Messprotokoll](../data/benchmarks/rtk-2026-11-12.md).

Die TypeScript-Aufgabe hatte daneben eine gezielte Referenzansicht von 153 Bytes.
Sie wurde eigens für diese Frage geschrieben. Das ist kein allgemeiner
Kompressor und kein fairer Geschwindigkeitsgegner für einen neuen RTK-Prozess.
Es zeigt, warum die genaue Frage vor dem Werkzeug stehen sollte.

## Was daraus folgt

Eine bereits kurze Meldung braucht selten einen weiteren Filter. Wenn der Filter
nichts entfernt, bleiben zumindest sein Aufruf und seine Wartung übrig. Diese
Kosten sind real, auch wenn die Bytezahl gleich bleibt.

Eine vollständige Liste muss vollständig bleiben. Bei einer Baumübersicht dürfen
Dateinamen gruppiert werden; ein nachgeschalteter Parser braucht dagegen die
verlangten Pfade. Dasselbe gilt für einen Patch. Entscheidend ist der Vertrag
mit dem nächsten Verbraucher.

Für TypeScript-Diagnosen kann eine passende Gruppierung nützlich sein. In dieser
Fixture blieben die geforderten Literale erhalten. Ob jede inhaltliche Beziehung
zwischen Dateiname, Zeile und Fehlercode erhalten ist, prüft der Literal-Oracle
nicht. Dafür braucht es einen stärkeren Parser oder eine echte Fehlerbehebung.

Ungewöhnliche Fehler brauchen besondere Aufmerksamkeit. Ein Filter, der bekannte
Fehlermuster extrahiert, kann fremde Muster übersehen. Deshalb bewahrt `verify`
seine Rohdateien vor jeder gekürzten Darstellung und übernimmt keine
Filterentscheidung als Exitcode des ursprünglichen Checks.

## Was diese Messung nicht zeigt

Die acht Aufgaben sind absichtlich auf unterschiedliche Verträge zugeschnitten.
Sie sind keine repräsentative Verteilung aller RTK-Aufrufe. „Sieben von acht
hier verworfen“ bedeutet deshalb nicht „RTK ist zu 87,5 Prozent nutzlos“.
Auch die Reduktion eines `pipe`-Filters beweist nicht, wie sich jeder spezialisierte
RTK-Befehl auf einem echten Projekt verhält.

Die erfassten Filterzeiten liegen in diesem Lauf ungefähr zwischen 4 und 7 ms.
Jede Zeit enthält Prozessstart und Filterarbeit. Es gab keine Wiederholungen für
Latenzintervalle. Die Auswahl des nächsten Werkzeugs darf daraus keinen
allgemeinen Geschwindigkeitsfaktor ableiten.

Ein Literal-Oracle kann Informationsverlust nachweisen, wenn ein verlangter
Beleg fehlt. Bestehen alle Literalprüfungen, folgt daraus nur diese begrenzte
Aussage. Semantische Gleichwertigkeit, korrekte Fehlerbehebung und geringere
Anbieterkosten brauchen eigene Prüfungen.

## Aktuelle RTK-Dokumentation richtig lesen

RTK selbst beschreibt `gain` als Schätzung entfernter Shell-Ausgabe und trennt
diese von der Anbieterrechnung. Das stützt die Trennung unserer Messgrößen.
[Offizielle Erklärung](https://github.com/rtk-ai/rtk/blob/develop/docs/usage/FEATURES.md#about-bash-output-reduction).

Die aktuelle technische Beschreibung hält Eingaben und Zwischenstufen einer
Pipeline roh und begrenzt automatische Umschreibungen. Das ist derselbe
Verbrauchervertrag: Ein Parser darf keine umformatierte Vorschau erhalten.
Diese Dokumentation beschreibt den jeweiligen Upstream-Stand; sie beweist
keine Funktion einer anderen installierten RTK-Version.
[Technische Quelle](https://github.com/rtk-ai/rtk/blob/develop/docs/contributing/TECHNICAL.md#32-command-rewriting).

## Selbst prüfen

```bash
bun run ats bench --out ./mein-rtk-bericht
```

Optional wählt `--rtk /pfad/zur/rtk` eine bestimmte installierte Binärdatei.
ATS installiert keine Software und vertraut keinen Projektfiltern. Die
Vorbereitung schaltet RTK-Telemetrie im isolierten Home ab. Scheitert sie,
werden die RTK-Arme als nicht verfügbar ausgewiesen.

Der Ordner enthält pro Fall Rohtext, Kandidat und ausgewählte Ausgabe. Der
Bericht nennt fehlende Belege, Filterstatus und Bytezahlen. Die Fixture-Hashes
machen unterschiedliche Eingaben sichtbar. Ein neuer Vergleich darf frühere
Gegenbefunde nicht aus seiner Bilanz entfernen.
