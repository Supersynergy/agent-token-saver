# External research — swarm and child-cost best practices (2026-07-19)

Distilled from a ghmax repo/code sweep and a superweb documentation sweep run
alongside the [kimi-lane](../data/benchmarks/kimi-lane-2026-07-19.md) and
[claude-stagger-ab](../data/benchmarks/claude-stagger-ab-2026-07-19.md)
benchmarks. Claims below are external unless marked measured-here.

## Cache mechanics (context for the refuted stagger rule)

- Anthropic prefix cache matches over `tools → system → messages`; reads bill
  ~0.1x, writes 1.25x, idle TTL 5 min (source: moai-adk docs sweep). Our A/B
  shows the harness already shares the child prefix as cache reads in both
  spawn schedules — the naive "stagger to convert writes" advice is dead on
  this harness, measured-here.
- Two cache-bust traps worth guarding anyway: an idle gap over the 5-minute
  TTL (a blocking question mid-team) re-writes the full accumulated prefix at
  1.25x, and any tool-schema change invalidates the prefix from that point
  (arxiv 2601.06007v2 ablation: cache benefit is linear in prefix size after
  the provider minimum — 54–89% at 50k-token prompts).
- Reported upstream issue (Claude Code #46917): `cache_creation_input_tokens`
  inflated per request via a User-Agent header change in v2.1.100+. Unverified
  here; our per-child write ratio (~12k/request) did not obviously match the
  reported ~20k/request, but all bench docs already scope token classes as
  "provider usage fields, not billing claims".

## Adoptable levers, priority order

1. **Runtime routing beats scheduling and agent-type tuning** (measured-here):
   lean Kimi team = 16% of Claude team gross; agent-type restriction = 0%
   saving; stagger = 0% saving.
2. **Child reasoning effort** — external repos cut per-child tokens by running
   children at low effort and reserving high effort for the controller.
   Untested here; candidate for the next A/B on a lane whose oracle can catch
   quality loss.
3. **Hard budget cap per team** — cheapest external fan-out pattern pairs a
   cheap-model agent team with a hard token budget and minimum context per
   child. Matches our capsule/task-packet contract (300–700 tokens).
4. **Cold-start multiple** — external metering puts naive subagent fan-out at
   ~4.2x a solo run (121K → 513K), same shape as our measured 3.0x team.
5. **File-based evidence passing** — a final-summary-only contract loses the
   whole child run if the parent's tool dispatch hiccups (documented 14.8-min
   subagent loss, oh-my-hermes). Children should write findings to a file and
   return the path; this also matches the protocol's evidence-path rule.
6. **Per-chain budget + ratio alarm** — OWASP AISVS C09: enforce a cumulative
   per-chain token counter with a circuit breaker (per-call limits missed a
   documented $47K four-agent run) and watch the input:output ratio — 5:1 to
   15:1 is normal for coding agents; a client bug surfaced at 74:1 and 175:1.

## Kimi CLI operational facts (official docs sweep)

- Headless: `kimi --print -p "..."` auto-approves tools; `--quiet` = final
  message only (ideal for capsule worker returns); `--output-format
  stream-json` for programmatic parsing.
- Exit codes are retry-aware: 0 success, 1 permanent failure, **75 retryable**
  — a swarm retry loop should retry only on 75.
- No CLI spend history; token usage lives in the TUI `/usage`, or read
  `~/.kimi/sessions/<proj>/<id>/wire.jsonl` locally (what our bench does).
  `KIMI_SHARE_DIR` overrides the state root — set one per swarm for clean
  per-team usage accounting.
- Quota is subscription-shared across devices and keys; the
  `kimi-for-coding` slug reports $0 in ccusage-style tools (slug not priced).
- More headless surface: `echo "..." | kimi --print` (stdin),
  `--final-message-only`, `--input-format stream-json` (JSONL backend mode),
  resume via `-C`/`-S <id>`, `kimi export [id]` for artifacts.
- Kimi CLI 1.49.0 (2026-07-16, one minor above the 1.48.0 we benchmarked)
  adds a built-in swarm mode (`/swarm`), sub-agent tools, background tasks
  and cron, plus an adaptive completion-token budget — the built-in swarm is
  an obvious next lane to bench against our shell-orchestrated team.
