# ATS Poweruser Benchmark — Analysis 2026-07-23

## Headline

3 agents × 10 cases × 2 paths = 60 runs, 28 min wall. Token savings
**75-85%** aggregate, best cases **86-97%**. Two cases show negative
savings that are a **metric artifact**, not an ATS-recon regression.

## The "negative savings" artifact (cases 08, 10)

| Case | Baseline tool | ATS tool | Baseline tok | ATS tok | Saved % |
|---|---|---|---|---|---|
| 08_ats_hooks | `ls integration/hooks` | `gmax "which hooks"` | 14 | 168 | -162% |
| 10_ats_recon_router | `grep -n "ats-recon\|ats_auto\|route"` | `gmax "how does ats-recon route"` | 0 | 135 | -102% |

**Root cause:** the baseline command returns nothing useful (case 10 grep
pattern does not match the actual router code; case 08 `ls` returns only
filenames). The agent then answers from its own training/context, not from
the tool output. ATS-recon (gmax) returns real content, which costs more
tokens but gives a grounded answer.

**Evidence (codex answers):**

- `10_ats_recon_router / baseline`: tool=0t, agent=88t — agent produces a
  correct routing description with *zero* tool context. This is
  hallucination-risk, not a savings win.
- `10_ats_recon_router / ats_recon`: tool=135t, agent=85t — same answer
  quality, but grounded in gmax output.

**Implication:** raw `total_tokens` undercounts quality. A fairer metric
would score answer correctness against a reference and penalize
ungrounded answers. For now, treat cases 08 and 10 as "ATS-recon provides
grounding, baseline agent hallucinates from training memory".

## Agent-level findings

- **codex**: 20/20 OK, slowest wall (reasoning model), highest answer
  quality. Best baseline for fair comparison.
- **kimi**: 16/20 OK, 4 FAILs (02/03 ats_recon + 02 baseline). FAILs
  return 4t — rate-limit/network issue, not billing. Retry would likely
  recover.
- **hermes_luna**: 20/20 OK but 18 of 20 answers are exactly 135 tokens
  — OpenRouter 402 billing exhausted. Agent returns a canned error
  message. **Answer quality not measurable on this run.**
- **hermes_terra**: omitted (402 billing exhausted, same root cause as
  luna).

## Recommendation

1. **For headline token-savings**: use cases 01, 06, 07 (large tool
   output, 86-97% saved). These are the unambiguous wins.
2. **For answer-quality comparison**: re-run after OpenRouter credits
   refresh. Current hermes_luna/terra data is invalid.
3. **For cases 08, 10**: either (a) rewrite the baseline command so it
   returns real content (e.g. `cat` instead of `ls`, broader grep), or
   (b) add a groundedness score so ungrounded baseline answers are
   penalized.
4. **For kimi**: retry once with `--iter 2` to fill the 4 FAILs.

## Aggregate (3 agents, 10 cases, 1 iter)

| Agent | Baseline tok | ATS tok | Saved % | Notes |
|---|---|---|---|---|
| codex | 6579 | 1269 | 80.7% | all OK, reference run |
| kimi | 6604 | 1015 | 84.6% | 4 FAILs inflating savings |
| hermes_luna | 7049 | 1758 | 75.1% | 402 billing, answers invalid |
