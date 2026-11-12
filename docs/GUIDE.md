# Mit einer Frage anfangen

ATS ist für Checks und Belege gedacht, die ein Coding-Agent sonst mehrfach
startet oder zu breit liest. Wenn `git status --short` bereits alles beantwortet,
brauchst du keinen Zusatzbefehl.

## Du willst einen Fehler beheben

Wähle den engsten Check, der den Fehler tatsächlich abdeckt:

```bash
ats verify -- bun test ./test/example.test.ts
```

Ein grüner Lauf erzeugt ein kleines Ergebnis. Ein roter Lauf behält seinen
Exitcode und nennt zwei vollständige Rohdateien. Das Diagnosefenster zeigt nur
deren Ende. Die Dateien liegen standardmäßig unter
`~/.local/state/agent-token-saver/runs/` und werden nicht automatisch gelöscht.

Suche dort nach dem konkreten Fehler, statt den Test erneut zu starten:

```bash
ats project /pfad/zum/stdout.log --match TS2322
ats project /pfad/zum/stderr.log --match AssertionError
```

Die Ansicht nennt Trefferzahl, angezeigte Zeilen und ausgelassene Treffer.
`complete_selection: true` bedeutet bei JSON-Ausgabe, dass alle wörtlichen Treffer
in genau dieser Datei gezeigt werden. Es sagt nichts über weitere Dateien.
Die Suchansicht unterstützt Dateien bis 8 MiB. Größere Dateien gezielt mit
`rg --no-config` durchsuchen. Endansichten lesen höchstens das angegebene Bytebudget.

Ein Check läuft pro unverändertem Quellenstand einmal. Änderungen oder ein roter
Schritt können einen weiteren Lauf nötig machen. ATS führt kein zweites
Aufgabenboard und überspringt keine Gates aufgrund eines fremden grünen Logs.
Der verwendete Prüfbefehl bestimmt, wie viel das grüne Ergebnis beweist.

## Du willst eine vollständige Liste

Nimm eine vollständige Abfrage, deren Ergebnis du verarbeiten kannst:

```bash
rg --no-config --files src
rg --no-config -n 'createSession' src test
```

Ein nachgeschaltetes `head`, eine kompakte Baumansicht oder ein Filter mit
Trefferlimit macht daraus eine Vorschau. Für Parser, Patches und Inventuren
müssen die nötigen Bytes vollständig bleiben. Liegt die Ausgabe als JSON vor,
wähle die benötigten Felder mit `jq`; bei einer Datenbank mit SQL.

## Du hast viel wiederholten Werkzeuglärm

Dann kann ein passender RTK-Filter helfen. Prüfe zuerst, welche Information für
diese Aufgabe erhalten bleiben muss. Ein Fehlercode ohne Dateipfad kann zu wenig
sein; eine Testzusammenfassung ohne Soll-/Ist-Werte ebenso.

```bash
ats bench --out ./rtk-report
```

Der Vergleich benutzt acht synthetische Aufgaben. Er startet keinen echten
Projektbuild. Jeder RTK-Filter bekommt die bereits festgelegte Fixture per stdin.
Rohtext, Kandidat und ausgewählte Ansicht werden getrennt gespeichert.
Verworfene Kandidaten zählen als null Byteersparnis. Der eigene RTK-HOME liegt
im Ausgabeordner; persönliche Einstellungen werden nicht verändert.

Fehlt RTK oder scheitert seine Vorbereitung, meldet der Bericht `unavailable`.
Das ist weder ein bestandener RTK-Test noch ein Produktfehler. Details stehen
in [RTK](RTK.md). Eine Prozesslaufzeit aus diesem Vergleich ist keine gemessene
Beschleunigung deines gesamten Arbeitsablaufs.

## Du willst ein Skript anbinden

Menschen bekommen kurze Texte. Skripte wählen ausdrücklich JSON:

```bash
ats --json project build.log --match TS2322
ats --json doctor
ats --json verify -- bun test
```

`--json` vor dem Trenner `--` steuert ATS. Alles danach gehört zum Kindprozess.
Der Exitcode des Checks bleibt auch bei JSON erhalten. ATS ist nicht interaktiv;
Eingaben an den Kindprozess werden nicht durchgereicht.

## Du willst wissen, ob es sich lohnt

Erfasse die Zahl der abgenommenen Aufgaben und der nötigen Anfragen. Ergänze
Wandzeit und Nacharbeit. Anbieterzähler gehören in getrennte Nutzungsklassen;
Preise brauchen Währung, Quelle und Datum.

```bash
ats cost examples/usage.json
```

Das Beispiel bleibt im Checkout. `cost -` liest dasselbe Format von stdin.
Es gibt keinen eingebauten aktuellen Tarif. Eine Cache-Schreibmenge darf nicht
zusätzlich als frische Eingabe gezählt werden, wenn dein Anbieter sie bereits
einschließt. Die Normalisierung liegt beim Aufrufer.

## Du willst Kontext übergeben

Notiere Ziel, relevante Entscheidungen und den nächsten offenen Schritt.
Verweise auf den Quellenstand und passende grüne Tests. Laufende Prozesse und
fremde Arbeit müssen erkennbar bleiben. Ein echter Wechsel braucht keine erneute
Grundsatzplanung. ATS erzeugt weder Warmhalteaufrufe noch automatische Neustarts.
`ats guide handoff` erinnert an die Punkte, ohne einen weiteren Ablauf zu starten.

## Installation in einem Probeordner

```bash
bun install.ts --home ./probe-home --apply
bun run ats doctor --home ./probe-home
```

Die Installation enthält auch diese Anleitung. `ats` und `agent-token-saver`
verweisen auf denselben Bun-Einstieg. Vorhandene Dateien und Verknüpfungen werden
im Installationsbeleg gesichert. Rückbau erfolgt mit dessen Kennung aus dem
Checkout. Er stoppt, sobald ein späterer Eingriff erkannt wird.

Eine Installation besteht aus mehreren atomaren Zeigerwechseln, aber nicht aus
einer gemeinsamen Dateisystemtransaktion. Ein Abbruch dazwischen kann eine
teilweise umgestellte Installation hinterlassen. Der private Beleg enthält den
vorherigen Zustand; bewahre ihn für eine gezielte Wiederherstellung auf.

## Was geändert wurde

Die Anleitung folgt jetzt den Fragen beim Arbeiten. Automatische Profile und
Providerwege sind entfernt. Jeder Ausschnitt benennt seine Grenze; jede
Kostenangabe nennt ihre Eingaben. Die RTK-Empfehlung folgt dem jeweiligen
Aufgabenvertrag.

## Den Engpass prüfen

`ats guide speed` trennt Modellwartezeit, Startkosten und Toolarbeit. Die
[Speed-Seite](SPEED.md) und die [zusätzliche Benchmark-Prüfung](BENCHMARK_REVIEW.md)
zeigen, welche Regeln übernommen und welche verworfen wurden. Eine neue
Promptregel braucht einen Vergleich mit unveränderter Abnahme.
