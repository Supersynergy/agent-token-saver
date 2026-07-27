# ADR 2026-07-27 — Public benchmarks keep aggregates, not host traces

## Status

Accepted.

## Decision

Public benchmark artifacts may contain reproducible aggregate measurements:
counts, timing, memory, visible-input estimates, accepted or failed oracles and
relative state changes. They must not contain private paths, credentials,
process IDs, raw controller plans, chat/history excerpts or tool stderr tails.

Benchmark scripts normalize repository/state paths, store process role plus RSS
instead of PID/command, and validate a dry plan without publishing it. A test
scans published fixtures for the forbidden markers.

## Consequence

The public result remains useful for a routing decision. Reproduction details
belong in code and a local run, not in a host trace committed to Git.
