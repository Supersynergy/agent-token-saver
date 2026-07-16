# Engine lane probe — 2026-07-16

Same fixture and oracle as
[claude-team-ab-2026-07-16](claude-team-ab-2026-07-16.md): a 4,000-line log,
oracle = exactly 100 `ERROR` lines plus the `CRITICAL-MARKER` line verbatim.
Each lane got one bounded task packet. Wall times from `time(1)`, one run per
lane; token fields only where the runtime reports them.

| Lane | Form | Oracle | Wall | Cost class | Notes |
|---|---|---|---:|---|---|
| OpenRouter free-tier model (local curl shim) | capsule verifier, no shell | PASS, strict JSON | 1.4 s | $0 | given pre-projected lane evidence; returned exact `{"total_errors":100,"marker_line":3777,"verdict":"pass"}` |
| Free local agent CLI (`agy -p`) | shell worker | PASS, exact format | ~9 s | $0 | ran the awk projection verbatim |
| Codex via worker pool, read-only sandbox | shell worker | PASS, exact format | 17.6 s | subscription | only OS-sandboxed lane |
| Council scheduler `tick --execute` (GG Coder) | shell worker via role executor | PASS (count lane) | 26.3 s | subscription | deterministic $0 plan phase; real LLM call: 16,098 cache-read bootstrap, 62 output tokens, 1 turn |
| Claude Code child (prior A/B) | shell worker | PASS | — | subscription | 43,886 cache-write bootstrap, 129,836 gross input |
| Claude Code raw-read child (prior A/B) | full-file read | **FAIL** | — | subscription | 14.2x input and a wrong count |

## Reading

- Verification fan-out is nearly free: a free-tier capsule verifier answered a
  strict-JSON oracle in 1.4 s. N independent cheap votes cost almost nothing
  when the controller sends evidence, not raw data.
- Cheapest shell lane was the free local agent CLI; the sandboxed Codex worker
  is the natural critic lane; the council executor carries a 16k bootstrap —
  lighter than the ~44k Claude child but heavier than the $0 lanes.
- The council scheduler's plan phase is deterministic (zero LLM calls); its
  role catalog is business-persona shaped, so it fits strategy councils, not
  generic coding lanes.
- One run per lane; latency and quota vary by host and account. This ranks
  lane shapes, not providers.
