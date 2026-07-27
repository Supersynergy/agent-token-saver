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
