# Codex provider A/B index — 2026-07-15

All runs pin Codex CLI 0.144.3 and `gpt-5.6-sol`, use a fresh HOME per arm and
keep the same prompt and machine-checkable oracle inside each task pair.

| Phase | Accepted | Baseline total | Lean total | Result |
|---|:--:|---:|---:|---:|
| Automatic full skill read (`result.md`) | yes | 94,082 | 121,590 | 29.24% more; rejected design |
| Compact automatic policy (`compact-policy/result.md`) | yes | 112,488 | 90,364 | 19.67% less; current accepted evidence |
| First-command wording follow-up (`compact-policy-v2-process/result.md`) | no | 0 | 25,446 | baseline hit account usage limit; no claim |

The component fixture separately shows 99.50% visible-input reduction. That
is not provider usage. The accepted provider result here is 19.67% aggregate,
with one task regressing and only one run per arm. ABBA repetition is still
required before treating the percentage as stable.

Raw Codex JSONL is kept under each phase's `runs/` directory. Authentication,
temporary Homes and internal persisted sessions were deleted after each run.
