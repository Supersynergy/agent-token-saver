export const guides: Record<string, string> = {
  start: `Start with the question, not the compressor.
  Check once:       ats verify -- bun test
  Find a log error: ats project build.log --match TS2322
  Read the end:     ats project build.log --max-bytes 4096
  Compare RTK:      ats bench --out ./rtk-report
  Machine output:  ats --json verify -- bun test
  Local setup:     bun install.ts              (plan)
                   bun install.ts --apply      (install ats + agent-token-saver)
Full guide: docs/GUIDE.md. No automatic hooks or paid calls.`,
  rtk: `RTK helps only when the needed evidence survives and output gets smaller.
Use a supported RTK command for a human/agent preview of noisy output.
Use raw rg --no-config for complete inventories; jq/SQL for structured data.
Keep patch bytes and pipeline inputs raw. Never parse a shortened preview.
Run ats bench --out ./rtk-report to inspect local, task-specific counterexamples.
rtk gain counts an output estimate, not your provider invoice.
Docs: docs/RTK.md. Optional RTK is detected, never installed.`,
  checks: `Choose the narrowest required check. Run it once per unchanged source state.
ats verify -- bun test ./test/example.test.ts
On failure, read the saved raw stdout/stderr. Do not rerun to recover output.
Exit codes survive; timeout is 124 and unavailable executable is 127.
A green exit proves only the command you chose, not customer acceptance.`,
  cache: `Keep fresh input, cache reads, cache writes and output disjoint.
ats cost --example
Supply dated prices and currency. No built-in "current" tariff.
Byte reduction, weighted token estimates and provider charges are different.
Price a cache rewrite before changing a stable prompt prefix.`,
  handoff: `Reuse known decisions. Keep the active prefix stable while it is useful.
At a real boundary, write references to scope, decisions, remaining work,
running processes and source-matched check evidence. Then start fresh if needed.
No timed keepalive, background warmup or automatic session restart.`,
  speed: `Measure the bottleneck before adding another loop.
Separate model wait, tool wall time, init and retries; never infer one from another.
Keep task quality fixed. A shorter failing run has no cost-per-solved-task gain.
Batch only when individual statuses and required evidence survive.
Use a warm service only with measured startup cost and a real repeated consumer.
Choose the narrow required check, preserve release gates, stop after acceptance.
No universal turn cap, daemon, reclaim, keepalive or automatic worker launch.
Read docs/SPEED.md and docs/BENCHMARK_REVIEW.md for sources and rejected claims.`,
  migration: `The maintained product is TypeScript/Bun, including installer and tests.
Old providers, hook stacks, Python tools and one-off benchmark launchers are retired.
Historical reports remain data, not current guarantees. See docs/MIGRATION.md.
Existing personal v4 hooks are not removed by a checkout update.
Installation/rollback require --apply; doctor checks files, not a live host session.`,
};
