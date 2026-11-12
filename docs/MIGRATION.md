# Move to the Bun product

The maintained CLI, installer, fixtures and tests use TypeScript/Bun. Python
and shell surfaces were retired. Historical reports remain in `data/benchmarks/`;
they are not current installation instructions.

This is a deliberate reduction. ATS is not also a provider gateway, task board
and hook platform. Users who need a removed feature should keep their existing
system until that migration is separately verified.

| Previous surface | Current path | Limit |
|---|---|---|
| `ats-verify` | `ats verify -- COMMAND` | one execution, raw logs, original exit |
| `ats-cache`, token ledger/CFO | `ats cost FILE` | normalized usage; no provider ingestion or team billing |
| `ats-pipe`, LLM pipe | exact search, `jq`/SQL, `ats project` | no model required to shorten deterministic data |
| URL cache and news pipeline | existing fetch/cache client | no HTTP or news service in ATS |
| Recall and CLI-log ingestion | existing scoped recall tool | no cron job or second memory store |
| Goal/worker/provider adapters | existing task and agent system | no automatic worker or provider calls |
| Prompt/Stop/Capsule/Explore hooks | compact skill plus explicit commands | no automatic host wiring |
| Minimal/Lean/Teams/Heavy profiles | one Bun core | old profile arguments fail explicitly |
| Python/shell benchmark launchers | `ats bench --out DIR` | eight synthetic RTK contracts, not provider A/B |
| `install-universal.sh` | `bun install.ts` | reviewed local checkout; `--apply` writes |
| `just legacy-check` | `just check` | types and current Bun behavior tests |

Removed special cases were not silently replaced with incomplete equivalents.
Previous sources remain in Git history. Local uncommitted work was archived
outside the product tree before retirement. The
[retired-surface manifest](retired-surfaces.json) records source identities.

## Existing host installations need a separate migration

A checkout update does not remove old global commands or v4 hooks. Those may
still need Python. Inspect the real host config, back it up and remove only
known old entries. A filename inventory does not prove an active integration.
The new doctor does not audit unrelated host files.

The installer writes only its own generation, receipts and two starters. Bun
must already be installed; `~/.local/bin` must be on PATH. It installs no packages.

## Try recovery in a separate home

```bash
bun install.ts --home ./probe-home --apply
bun run ats doctor --home ./probe-home
bun run ats rollback --home ./probe-home --id INSTALLATION_ID
bun run ats rollback --home ./probe-home --id INSTALLATION_ID --apply
```

Use the ID returned by installation. Rollback restores earlier files or symlinks,
refuses a receipt for an older active generation and preserves later starter
edits. Generations are not automatically deleted.

## Release history

Version 5.1.0 is the initial Bun-only release. Version 5.1.1 updates presentation
and shipped text to English. The old tag is retained; current downloads carry
the newer text. No host permissions or automatic integrations changed.
