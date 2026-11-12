# Von der alten Werkzeugkette zum Bun-Produkt

Stand: 12. November 2026. Der gepflegte Quellbaum enthält TypeScript/Bun für
CLI, Installer, Vergleichsfixtures und Tests. Die Python- und Shell-Oberflächen
sind entfernt. Historische Messdaten bleiben unter `data/benchmarks/` erhalten.

Die Ablösung ist eine bewusste Verkleinerung. ATS wird nicht gleichzeitig
Providervermittlung, Aufgabenboard und Hookplattform. Auf diese Funktionen
angewiesene Nutzer behalten ihr bisheriges System, bis sie dessen Migration
getrennt geprüft haben.

## Befehle und Ersatz

| Bisherige Fläche | Neuer Weg | Grenze |
|---|---|---|
| `ats-verify` | `ats verify -- COMMAND` | einmaliger Lauf, Rohlogs, erhaltener Exitcode |
| `ats-cache`, `agent-token-ledger`, `ats-token-cfo` | `ats cost FILE` für normalisierte Nutzung | native Provider-Ingestion und Teamabrechnung sind entfernt |
| `ats-pipe`, `ats-llm-pipe` | genaue Suche, `jq`/SQL, `ats project` | kein Modell zum Kürzen deterministischer Daten |
| `ats-url-cache`, News-Pipeline | eigener vorhandener Fetch-/Cache-Client | ATS übernimmt keine HTTP- oder Nachrichtendienste |
| `ats-recall`, CLI-Log-Ingestion | bestehendes Recall-Werkzeug gezielt verwenden | kein Cronjob und kein zweiter Speicher in ATS |
| `goal`, Provider-/Kimi-Worker und `llmadapter` | bestehendes Aufgaben- und Agentensystem | kein automatischer Agentenstart oder Provideraufruf |
| Prompt-, Stop-, Capsule- und Explore-Hooks | kompakter Skill plus explizite Befehle | keine automatische Hostverdrahtung |
| Profile `minimal`, `lean`, `teams`, `heavy` | ein expliziter Bun-Kern | alte Profilargumente werden als unbekannt abgewiesen |
| Python- und Shell-Benchmarkstarter | `ats bench --out DIR` | acht lokale synthetische RTK-Verträge, kein Provider-A/B-Ersatz |
| `install-universal.sh` | `bun install.ts` | lokaler geprüfter Checkout, `--apply` schreibt |
| `just legacy-check` | `just check` | Typprüfung und aktuelle Bun-Verhaltenstests |

Das ist keine Zusage, dass jeder entfernte Spezialfall identisch portiert wurde.
Die neue Hilfe beschreibt nur verfügbare Funktionen. Vorherige Quellen und
Anleitungen sind über die Git-Historie vor diesem Umbau auffindbar.
Vorhandene lokale Änderungen an entfernten Dateien wurden vor dem Umbau
außerhalb des Produktbaums gesichert und nicht als neue Implementierung übernommen.

## Persönliche Installationen bleiben ein eigener Schritt

Ein Checkout-Update entfernt weder alte globale Befehle noch aktive v4-Hooks.
Sie können weiterhin Python benötigen. Wer einen Host vollständig ablösen will,
prüft dessen tatsächliche Konfiguration, sichert sie und entfernt nur die
bekannten alten Einträge. Eine Liste alter Dateinamen beweist keine aktive
Integration. Ein neuer CLI-Doctor prüft keine fremden Hostdateien.

Die neue Installation schreibt ausschließlich ihre Generation, Installationsbelege
und zwei Starter. Sie führt keine Abhängigkeitsinstallation aus. Bun muss
vorhanden sein; `~/.local/bin/` muss für die kurzen Befehle im Suchpfad liegen.

## Installation und Rückbau testen

```bash
bun install.ts --home ./probe-home --apply
bun run ats doctor --home ./probe-home
bun run ats rollback --home ./probe-home --id INSTALLATIONS_ID
bun run ats rollback --home ./probe-home --id INSTALLATIONS_ID --apply
```

Die Kennung stammt aus der Installation. Der Rückbau stellt vorherige Dateien
oder Verknüpfungen wieder her. Er verweigert eine veraltete Kennung, wenn bereits
eine neuere Generation aktiv ist, und überschreibt keine später geänderten Starter.
Generationen werden nicht automatisch gelöscht.

## Was geändert wurde

Die bisherigen parallel gepflegten Anleitungen sind durch einen Einstieg und
aufgabenbezogene Seiten ersetzt. Herstellerzähler, lokale Bytemessungen und
Preisschätzungen bleiben getrennt. Die früheren Sparschlagzeilen sind datierten
Befunden gewichen, einschließlich fehlgeschlagener Vergleiche.
