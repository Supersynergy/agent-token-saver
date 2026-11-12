# Start with Bun

Agent Token Saver runs a check once, keeps its complete local output and gives
coding agents a bounded view of the evidence. Runtime packages and API keys are
not required. The maintained release uses TypeScript/Bun throughout.

## Install release 5.1.0

Install Bun using its [official instructions](https://bun.sh/docs/installation),
then use the tagged source:

```bash
git clone --branch v5.1.0 --depth 1 https://github.com/Supersynergy/agent-token-saver.git
cd agent-token-saver
bun run ats guide
bun install.ts              # show the plan
bun install.ts --apply      # create ats and agent-token-saver
```

Add `~/.local/bin` to your PATH if needed. `ats doctor` checks installed hashes
and starters. It does not claim your coding agent has loaded an integration.
ATS does not install hooks or change host permissions.

## Use it

```bash
ats verify -- bun test
ats project build.log --match TS2322
ats --json project build.log --max-bytes 4096
ats cost --example
ats guide speed
ats bench --out ./rtk-report
```

A check keeps its exit code. Full stdout and stderr stay on disk. On failure,
the short view contains only their tails; search the saved files to recover
earlier evidence instead of rerunning the check. Logs may contain whatever
secrets the invoked command prints, so inspect them before sharing.

RTK is optional. The comparison uses synthetic task contracts and rejects
candidates that lose required evidence or do not reduce bytes. It is not a
provider-cost benchmark or a general failure rate for RTK.

## Update and roll back

Install from the next reviewed checkout using `bun install.ts --apply`. The
installer records the previous starters and generation. To restore them, use
the ID printed by that installation:

```bash
bun run ats rollback --id INSTALLATION_ID
bun run ats rollback --id INSTALLATION_ID --apply
```

Rollback refuses newer generations and later changes to starters. Existing v4
host hooks are a separate migration; replacing the checkout does not remove them.
See [migration](MIGRATION.md) and the [benchmark review](BENCHMARK_REVIEW.md).
