# 5.1.1: English throughout, a compact first view

The README now keeps installation and three useful commands in its opening view,
while readers who need the evidence, recovery rules or the 20-skill catalog can
follow a link without scrolling through the full explanation first.
Current guides and shipped summaries are in English.

```bash
git clone --branch v5.1.1 --depth 1 https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
bun install.ts --apply
ats guide
```

## Changed

- Compact English README with the 5.1 release graphic.
- English guide, RTK interpretation, benchmark review, migration and design notes.
- English summaries returned by `ats skills`.
- English GitHub release text and a patch archive carrying the translated files.

## Unchanged

Command execution, exit handling, raw evidence retention and rollback behavior
are unchanged. Bun is still the only runtime requirement; RTK remains optional.
No new hooks, providers, background services or permissions are introduced.
The existing v5.1.0 tag is retained.

[Guide](GUIDE.md) · [RTK limits](RTK.md) · [Migration](MIGRATION.md) ·
[Speed review](SPEED.md). License: MIT.
