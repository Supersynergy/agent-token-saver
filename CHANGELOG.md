# Changelog

## 5.1.0 (2026-11-12)

Release preparation adds a tagged Bun quick start, source archive/checksums,
English onboarding, a reviewed Speed/Superloop guide and benchmark corrections.
The upstream mobile README structure and cover are retained. Full session JSONL
traces are excluded from the maintained tree; historical measurements remain.
See [release notes](docs/RELEASE-5.1.0.md) for breaking changes.

The maintained repository now uses TypeScript/Bun for the CLI, installer and tests.
Python tools, shell launchers, the provider adapter and the overlapping host/profile
stack are retired. Their functions are mapped in [migration](docs/MIGRATION.md).
Historical measurement data remains available.

The default CLI prints short readable results; `--json` provides machine output.
`project --match` finds evidence outside a log tail and reports omitted matches.
`bench` compares RTK against explicit task contracts and retains raw fallbacks.
The Bun installer creates `ats` and `agent-token-saver`; receipt-based rollback
restores previous files or symlinks and refuses to overwrite later edits.

The guide explains when direct search is enough, which RTK comparisons failed,
and why output-byte reductions do not establish bill reductions.

## 5.0.0 (local transition)

A smaller TypeScript core replaced the default Python entry point while the old
surface remained in the checkout. Version 5.1 completes that repository cleanup.
Earlier release notes remain in Git history; the live instructions describe only
the maintained commands.
