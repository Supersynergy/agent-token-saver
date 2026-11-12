# Contributing

Start with a user question and an executable acceptance condition.

```bash
bun install --frozen-lockfile --ignore-scripts
just check
```

The product, installer, fixtures and tests use TypeScript/Bun. No Python or shell
implementation is maintained. Runtime dependencies are unnecessary for the
current scope. Propose a new package only with a concrete gap and a measured cost.

For output changes, prove that the needed evidence survives. Include empty output,
a nonzero exit and a nonstandard diagnostic. Save raw evidence before filtering.
A tiny output with a failed task oracle is a rejected candidate.

RTK is optional. Unit tests use a controlled TypeScript stand-in; a local live
comparison is separate:

```bash
bun run ats bench --out ./rtk-report
```

Use a new output directory for a new comparison. Report RTK version, fixture hashes,
required evidence, byte counts and filter-process time. Do not present a synthetic
payload comparison as provider savings or an end-to-end speed measurement.

Keep a source-matched green test result. Repeat only after affected code changes,
a failed check or an explicit request. Publishing and release changes require
their own authorization. See [the test and release boundaries](SECURITY.md).

If a new filter removes a file path that the next debugging step needs, keep the
failed candidate in the report even when its byte count looks better than every
accepted alternative. That loss is the result.
