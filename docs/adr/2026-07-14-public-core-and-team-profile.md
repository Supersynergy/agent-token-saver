# Public core and bounded team profile

Status: accepted, 2026-07-14.

## Context

The token saver is a public installer. Private host tools and a web-fetch
runtime cannot be required for reproducible installs or a measured default.
Agent teams can also waste more bootstrap context than they save when the work
overlaps.

## Decision

- The public core is native projection, the optional published skill-router,
  RTK and Tilth. Heavy public tools remain explicit session choices.
- The main installer never downloads the router. It detects an already
  installed `si`; the router is an extra, separately installable skill/CLI.
- `teams` reuses the Lean runtime and documents a controller/worker contract.
  It adds no daemon, model, crawler, MCP schema or fan-out behavior.
- Teams are limited to three independent workers. Every worker has a compact
  evidence-by-reference capsule and a machine oracle. Accounting includes the
  parent, children, retries, fallbacks and compactions.
- The former `news` profile is absent from new installs. Doctor maps an old
  configured `news` value to `teams` so existing hosts remain inspectable.

## Consequences

The installer has a smaller, public and measurable dependency surface. Users
who need web retrieval choose and approve it outside this project. A team only
remains enabled after the same accepted result shows a net total-token or
latency win.
