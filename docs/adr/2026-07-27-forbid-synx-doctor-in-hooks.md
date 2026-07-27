# ADR 2026-07-27 — Keep `synx doctor` out of automatic hooks

## Status

Accepted.

## Context

The token-saving path must not add an expensive maintenance scan to every agent
event. On the reference host, `synx doctor` reached roughly one CPU core and
1.8 GB RSS for minutes. That is incompatible with prompt, tool, or session
hooks. The command is valuable for a deliberate operator diagnosis, not for
automatic routing.

## Decision

`agent-token-saver doctor` reads the active Codex and Claude hook command
fields, never executes them, and records only the count of `synx doctor`
matches. A match for an agent configured by Agent Token Saver produces the
machine-readable error `forbidden_hot_path_synx_doctor:<agent>`.

No broad home-directory scan. No process control. No database operation. No
command text is returned, so unrelated hook credentials do not enter the
report.

## Consequences

- Profile health fails early instead of hiding recurring CPU/RAM cost.
- Manual maintenance stays possible: run `synx doctor` intentionally outside a
  hook, with a bounded resource budget.
- The guard covers installer-managed Codex and Claude hooks. Hermes and other
  hosts remain explicit skill/CLI integrations and require their own verified
  hook adapters before enforcement.
