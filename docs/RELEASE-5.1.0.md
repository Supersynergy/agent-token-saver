# 5.1.0: TypeScript/Bun with retained evidence

ATS 5.1 runs a check once and makes its saved evidence searchable. The maintained
CLI, installer and tests use TypeScript/Bun.

## Start

```bash
git clone --branch v5.1.0 --depth 1 https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
bun run ats guide
bun install.ts --apply
ats doctor
```

Bun is required. Runtime packages and API keys are not. The release includes a
source archive and SHA256SUMS, alongside GitHub's standard source downloads.

## User-visible changes

- Short readable output by default; `--json` for scripts.
- `verify` retains the original exit and complete local output.
- `project --match` reports line numbers and omitted matches.
- `guide speed` separates model wait from tool time.
- The optional RTK comparison rejects lost evidence and zero byte gain.
- Installation keeps recoverable starters and installs no host hooks.

## Breaking changes from 4.x

Python/shell helpers, provider routing, automatic hook profiles and old profile
arguments are retired. Use `bun install.ts` in place of `install-universal.sh`.
Not every earlier special case was ported. The [migration map](MIGRATION.md)
identifies replacements and limits. Existing personal v4 hooks are a separate
migration.

## Evidence and limits

Eight synthetic RTK tasks accepted one smaller candidate with retained required
literals, rejected three with no byte gain and rejected four with lost evidence.
This is neither a general RTK failure rate nor a new ATS saving guarantee.

The additional benchmark review corrects the earlier staggered-start advice and
records wrong-library documentation answers despite small outputs. Historical
measurements are separate from current prices and Bun-core behavior. Full
session traces are excluded from the maintained source archive.

License: MIT, copyright 2026 Supersynergy. The original tag and archive are
retained; 5.1.1 carries the English presentation update.
