# External usage-auditor gate

Provider totals come from `agent-token-ledger`. External cost estimates are not an oracle.

Canonical input: **7,768,418** total, **599,394** uncached, **7,169,024** cached.

| Candidate | Exact token fields | Wall time | Policy |
|---|:---:|---:|---|
| splitrail | yes | 10.79 ms | optional: fast global audit; ledger remains team truth |
| tokscale | yes | 50.27 ms | optional: session/model cross-check |
| codeburn | yes | 267.49 ms | optional: read-only optimizer; savings claims need separate proof |
| aiusage | yes | n/a | normalized-only: native summary double-counts cache and thinking |

Gate passed: **yes**.
