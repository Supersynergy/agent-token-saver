# 5.1.0: TypeScript/Bun, mit erhaltenen Belegen

ATS 5.1 führt Checks einmal aus und macht gespeicherte Ergebnisse gezielt lesbar.
Die gepflegte Implementierung, Installation und Tests verwenden TypeScript/Bun.

## Einstieg

```bash
git clone --branch v5.1.0 --depth 1 https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
bun run ats guide
bun install.ts --apply
ats doctor
```

Bun ist Voraussetzung. Zum Benutzen braucht es weder Entwicklungsabhängigkeiten
noch API-Schlüssel. Der Release-Download enthält außerdem das Quellarchiv und
`SHA256SUMS`. GitHub stellt die üblichen Source-Archive zusätzlich bereit.

## Neu für Nutzer

- Kurze lesbare Ausgabe als Standard; `--json` für Skripte.
- `verify` mit erhaltenem Exitcode und vollständigen lokalen Logdateien.
- `project --match` mit Zeilennummern und ausgewiesenen ausgelassenen Treffern.
- `guide speed` mit getrennten Modell- und Toolzeiten statt pauschalen Speed-Regeln.
- Optionaler RTK-Vergleich, der Kandidaten mit fehlenden Belegen verwirft.
- Installation und Rückbau mit gesicherten Startern; keine automatischen Hooks.

## Brüche gegenüber 4.x

Python- und Shell-Helfer, Providervermittlung, automatische Hookprofile und alte
Profilargumente sind entfernt. `install-universal.sh` wird durch `bun install.ts`
ersetzt. Nicht jede frühere Spezialfunktion ist identisch portiert. Die
[Migrationsübersicht](MIGRATION.md) nennt die entfernten Bereiche und den Ersatz.
Bereits installierte persönliche v4-Hooks bleiben ein eigener Migrationsschritt.

## Evidenz und Grenzen

Der RTK-Vergleich benutzt acht synthetische Aufgaben. Ein Kandidat wurde kleiner
und behielt seine Pflichtliterale; drei brachten keinen Bytegewinn, vier verloren
Belege. Das ist keine allgemeine RTK-Fehlerquote oder neue ATS-Spargarantie.

Weitere Benchmarks korrigieren die frühere Empfehlung zum zeitversetzten
Agentenstart und zeigen falsche Dokumentationsantworten trotz kleiner Ausgaben.
Die Release-Unterlagen trennen diese historischen Messungen von heutigen Preisen
und vom Verhalten des Bun-Kerns. Vollständige Sitzungstraces sind nicht Teil
des gepflegten Quellarchivs; Messberichte bleiben erhalten.

Lizenz: MIT, Copyright 2026 Supersynergy.
