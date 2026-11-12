# Ask one question

ATS helps a coding agent run a check once and read its evidence later. If a
small native command already answers the question, use that command directly.

```bash
ats verify -- bun test ./test/example.test.ts
ats project /path/to/stderr.log --match TS2322
ats --json project /path/to/stdout.log --max-bytes 4096
```

## Fix a failure without rerunning the check

`verify` runs an argv list once and retains the command's exit code. Complete
stdout and stderr stay under `~/.local/state/agent-token-saver/runs/` by default.
A successful result is short. A failure also shows at most 16 KiB from the end
of each stream, with omitted-byte counts. Logs are not automatically deleted.

A tail can miss the first error. Search the saved file with `project --match`
instead of starting the check again. The view reports matching lines, shown
lines and omitted matches. `complete_selection: true` means every literal match
in that file was shown; it says nothing about other files.

Match views support files up to 8 MiB. Use scoped `rg --no-config` for larger
files. Tail views read only their byte budget. A check runs once per unchanged
source state; changed code or a failed step may justify another run. The chosen
oracle determines what a passing exit proves.

## Keep inventories and parser inputs complete

```bash
rg --no-config --files src
rg --no-config -n 'createSession' src test
```

A head limit, shortened tree or capped filter turns an inventory into a preview.
Keep the required bytes intact for parsers and patches. Select JSON fields with
`jq` or database columns with SQL before asking a model to summarize them.

## Test whether RTK helps your question

```bash
ats bench --out ./rtk-report
```

The comparison supplies eight synthetic fixtures to RTK's stdin filters. It does
not rebuild your project. Raw, candidate and selected output are saved separately.
Rejected candidates count as zero byte reduction. RTK settings stay in an isolated
home inside the output directory. Missing RTK or failed preparation is reported
as `unavailable`, never as a passed RTK test. [Results and limits](RTK.md).

## Use JSON deliberately

```bash
ats --json doctor
ats --json verify -- bun test
```

`--json` before `--` controls ATS. Arguments after `--` belong to the child.
The child's exit code survives JSON output. Commands are noninteractive: stdin
is not forwarded. A timeout kills the direct child, not necessarily processes
that child deliberately detached.

## Price the usage you have

`ats cost --example` works after installation. From the checkout, edit
`examples/usage.json`, then run `ats cost examples/usage.json`; `cost -` reads
that format from stdin.

Keep fresh input, cache reads, cache writes and output disjoint. Supply currency,
a dated price source and all rates. ATS does not normalize provider-specific
counters or keep a current tariff table. Byte reduction is a different measurement.

## Install, recover and hand off

```bash
bun install.ts --home ./probe-home --apply
bun run ats doctor --home ./probe-home
bun run ats rollback --home ./probe-home --id INSTALLATION_ID --apply
```

Both starters point to a Bun entry point. A private receipt saves prior files
or symlinks and the old generation. Rollback refuses later starter changes or a
newer active generation. Generations are retained.

Individual pointer swaps are atomic; the whole installation is not a filesystem
transaction. An interruption between swaps can leave a partial update. Preserve
the receipt for a targeted recovery. `doctor` checks files and starters, not a
live coding-agent integration.

At a real context boundary, hand off scope, decisions, source-matched green
checks, running processes and the next open step. ATS adds no keepalive or forced
restart. `ats guide handoff` gives the short checklist.

## Choose the bottleneck

`ats guide speed` separates model wait, startup and tool work. Read
[Speed/Superloop](SPEED.md) and the [benchmark review](BENCHMARK_REVIEW.md) before
adopting another prompt rule or background service. Hold acceptance fixed in
any comparison. A short failed run is not a cheaper solved task.
