# v3.1.0 — zero-hot routing and multi-agent accounting

This release removes the measurable idle tax that v3.0.1 exposed.

## What changed

- Codex and Claude keep the saver skill outside their visible skill catalogs.
- Automatic fuzzy routing is strict, emits nothing when uncertain and activates at most one primary skill.
- A conservative built-in gate still handles explicit token/context tasks when the companion router is absent.
- `minimal` is truly zero-hot: CLI and ledger only, with no visible skill or prompt hook.
- `agent-token-ledger` now sums named parent/child usage files and fingerprints duplicate visible context.

## Neutral evidence

Clean `CODEX_HOME` ABBA microbenchmark:

- Baseline median: `11,204` input.
- Lean median: `11,209` input.
- Delta: `+5` input tokens / `+0.045%`.
- Cache and output identical; every answer passed.

This is a no-tool idle-cost result, not an end-to-end savings multiplier. The
146.1x number remains a separate accepted payload-capacity benchmark.

Accepted explicit-RTK Codex probe:

- raw `ps aux`: `25,210` input
- explicit `rtk ps aux`: `23,996` input
- `1,214` fewer full input tokens (`4.82%`), identical `19,968` cached subset

One failed no-command warmup remains recorded and excluded from the accepted
A/B. Transparent Codex RTK rewriting is still not claimed.
