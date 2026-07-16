# External auditor and transport gates

Status: accepted, 2026-07-15.

## Context

New usage dashboards, MCP schema routers, file caches and ACP clients can make
one layer smaller while increasing fixed schemas, process memory, startup work
or child-agent bootstrap tokens. Popularity and vendor savings are insufficient
for changing the Lean default.

## Decision

- `agent-token-ledger` remains canonical for provider totals, complete
  parent/worker accounting and context-guard decisions.
- Install `agent-token-audit` as a separate CLI. It copies named Codex sessions
  into a temporary home, strips inherited credentials, executes only
  caller-supplied candidates, normalizes their exports and fails closed on
  token-field mismatch. The gate does not claim OS or network isolation.
- Support Splitrail, Tokscale and CodeBurn as optional audit views. Support
  aiusage only through normalized raw exports because its native summary is not
  additive for Codex cache and thinking fields.
- Add lossless `agent-token-ledger --format json-compact` for machine and
  agent-to-agent transfer. Keep pretty JSON as the human-readable default.
- Do not add cachebro, mcpc, mcpx, mcp-compressor, acpx, APM or Honey to an
  always-on profile. Revisit a schema compressor only after a provider A/B on a
  broad MCP catalog; revisit ACP only with a locked Codex adapter and real-agent
  total-token evidence.

## Consequences

The public install gains one dependency-free comparison gate and one compact
serialization mode, but no third-party dependency, daemon, model, MCP schema or
automatic worker. Optional dashboards can improve observability without being
allowed to redefine provider truth. The dated external stack matrix records the
rejected combinations and their break-even conditions.
