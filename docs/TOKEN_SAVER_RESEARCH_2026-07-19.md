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
