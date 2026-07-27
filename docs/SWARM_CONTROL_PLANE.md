# Bounded worker control plane

One controller owns scope, source verification, mutation and final decision.
Workers receive one 300–700-token capsule, one route hint and a PASS/FAIL
oracle. They return:

```text
STATUS: PASS|FAIL|BLOCKED; EVIDENCE: path or command+exit; HANDOFF: none|question
```

| Work | First move | Escalate only when needed |
|---|---|---|
| Exact source | `rg` | scoped structural read |
| Impact | repository ground/graph query | existing graph only |
| Noisy output | bounded command + RTK | raw artifact by path |
| Fresh fact | controller-provided primary-source artifact | controller synthesis |

No peer transcript relay. One targeted handoff at most. Do not spawn for a
small or overlapping check. Parallelism saves wall time, not automatic provider
tokens; record controller, workers and retries together.

Claude's `teams` profile installs the worker-capsule hook. Other hosts use the
same contract through their skill or explicit CLI path.

`llmadapter ask --swarm` is that explicit CLI path: it caps a requested lane
set at three, sends the same bounded capsule, requests at most 500 result
tokens and records each lane in the ledger. `ats-pipe` uses it by default.
`--fanout` is deliberately required for wide model comparison; it is not a
token-saving swarm mode.

For machine controllers, use `ask-v2`: exactly one stdin or regular-file
prompt transport, local lanes by default, one global deadline, terminal records
for every selected lane and atomic private accounting. Remote and paid lanes
need separate explicit gates. `--first`, `--aggregate`, `--verify` and `--tier`
are deliberately rejected because the worker stage does not own selection,
synthesis or verification.

The prompt limit is 1,800 UTF-8 bytes; larger input fails before capsule
construction. `--cap` is a total selection cap, not only concurrency: normal
runs select at most `min(cap, 3)`, explicit `--fanout` at most `min(cap, 64)`.
Pure model lanes receive reasoning-only wording. Tool hints appear only on a
host lane that explicitly advertises tool access.

Trust follows actual egress rather than the display class. OpenRouter is remote,
CLI is remote unless a private lane explicitly declares `local_safe`, and
Ollama is remote when its configured URL is not loopback. Remote shielding and
the `--allow-remote` gate follow that decision. Redirects are rejected rather
than silently changing egress after classification. Host-local lanes require a
bounded current-user-owned, non-symlink `0600` configuration file.

The v2 JSON schema is
[`schemas/llmadapter-result-v2.schema.json`](../schemas/llmadapter-result-v2.schema.json).
Its token-cap mode is explicit: OpenRouter `provider_server`, Ollama
`local_native`, CLI `advisory_only`. CLI output remains byte-bounded and a
nonzero CLI exit is always a failed terminal record. Each record also exposes
`call_started`, making calls, cache hits and token coverage independently
derivable from the selected terminal records; pre-transport validation,
shielding, key lookup and spawn failures remain false.

Transport keeps the prompt out of argv and result metadata, but a model may
repeat input in its answer. Cached answers can therefore contain repeated
input; use `--no-cache` when the controller must not persist answers.

There are 21 built-in lanes in this checkout. Private host configuration may
add more; runtime inventory, not a fixed marketing count, is authoritative.
