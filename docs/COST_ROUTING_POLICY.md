# Cost routing policy

Which lane answers which task, ordered by **marginal** cost — what the next
call actually adds to the bill, not what the model list says it costs.

Two subscriptions are active. A subscription call is already paid for, so it
outranks a free call that costs nothing but answers worse. Pay-per-token is
the last resort, not the default.

Every row below is backed by a number from `~/.agent-token-saver/ledger/`.
`scripts/lane_policy_check.py` is the oracle: it re-reads the ledger and exits
non-zero if this document claims something the measurements do not support.
Run it before editing the roster.

Measured 2026-08-20, 7-day window, 2 ledger files.

## Account state

| Account | State | Evidence |
|---|---|---|
| Anthropic | **primary carrier** | `sk-ant-oat…` + refreshToken = OAuth subscription, so marginal cost is 0 until the plan's own rate limit |
| OpenAI / Codex | **at its limit** | live probe: `You've hit your usage limit… try again at 12:19 PM` |
| OpenRouter | **dead, account-wide** | live probe on 3 lanes: `Insufficient credits`; the whole `cheap`+`paid` band is unreachable |
| Local (Ollama) | **excluded** | operator preference, not a measurement — top-model latency is wanted, and `justvugg/colibri` is not installed on this host |

The consequence is blunt: with OpenRouter at zero balance and ChatGPT at its
cap, **the Anthropic subscription carries the entire workload**, and the free
OpenRouter lanes are the only no-cost breadth left.

## Lane roster

Ordered fastest-first inside each tier. `window` is the 7-day success rate,
`lifetime` is every call on record, `avg` is mean latency of successful
in-window calls.

### Tier 1 — subscription (marginal cost 0)

| Lane | window | lifetime | avg | Task class |
|---|---|---|---|---|
| `claude-haiku` | 6/6 | 7/7 | 19.7s | Default. Recon, extraction, summarising, closed-form checks |
| `claude-opus` | 2/2 | 3/3 | 57.1s | Hard reasoning, architecture, anything irreversible |
| `claude-sonnet` | 2/2 | 2/2 | 60.2s | Middle band; measured no faster than Opus here, so prefer Opus when quality matters and Haiku when it does not |

Haiku is 3x faster than both frontier lanes and has not failed a call on
record. Sonnet's measured latency (60.2s) is *above* Opus's (57.1s) on this
host — the usual "Sonnet is the fast compromise" assumption does not hold
here, so the middle lane earns its place only when a task is too hard for
Haiku and not worth Opus.

### Tier 2 — free fanout (cost 0, breadth not depth)

Rostered on **lifetime** evidence, not on a single window. These run in
parallel, so the list is a membership claim, not an execution order.

| Lane | lifetime | avg (30d) | Task class |
|---|---|---|---|
| `nemotron-3-nano-omni-30b-a3b-reasoning` | 31/35 (89%) | 4.9s | Fastest reliable free voice |
| `nemotron-nano-12b-v2-vl` | 24/30 (80%) | 5.3s | Second opinion |
| `laguna-xs-2.1` | 21/26 (81%) | 7.7s | Third opinion |
| `nemotron-3-super-120b-a12b` | 325/347 (94%) | 14.3s | Aggregator / verifier — best-evidenced lane in the ledger |

Combined availability of the four, assuming independent failures:
**99.98%** — the fanout answers even when individual lanes do not. That is the
point of the tier, and `lane_policy_check.py` enforces it as a hard bar
(≥99%) *on top of* a per-lane floor.

Use these for **breadth** (fan one question across independent opinions) and
for the second, independent verifier in a `--verify` or `--tier` run. Not for
the primary answer: at 80–94% each, roughly one call in six needs a retry,
which a subscription lane does not.

**A 7-day window ranks noise.** The first version of this roster was built from
one week and put `laguna-s-2.1` (43% lifetime, 26/61) and `gemma-4-26b-a4b-it`
(70%, 78/112) in the tier, because both looked fast in that window. Over the
full record they are beaten on *both* reliability and latency by every lane
above. Check lifetime before promoting a lane.

### Tier 3 — pay-per-token

Empty. Every OpenRouter paid lane returns `quota / Insufficient credits`.
Restore a balance before treating this tier as a fallback; until then a
"fallback to cheap" instruction silently produces zero answers.

## Denied lanes

Kept out of the default rotation, each with the measurement that earned it.
Re-probe before restoring.

| Lane | Reason |
|---|---|
| `ling-3.0-flash` | 0/5 in window; provider retired the free slug ("This model is unavailable for free") |
| `gemma-4-31b-it` | 9 consecutive `exec` failures; free endpoint listed in catalog but non-functional |
| `laguna-m.1` | removed from provider catalog ("No endpoints found") |
| `gpt-oss-120b`, `gpt-5.6-luna`, `ling-2.6-flash`, `deepseek-v4-flash-0731`, `qwen3.7-flash`, `gpt-5.6-luna-pro`, `kat-coder-air-v2.5` | OpenRouter `cheap` band — zero balance |
| `kimi-k2.5`, `kimi-k2.7-code`, `kimi-k3` | OpenRouter `paid` band — zero balance; `kimi-k3` also 0/5 lifetime |
| `gpt-luna` | 1/2 lifetime and a live `exec` failure; the ChatGPT plan behind it is at its cap |
| `agy` | 0/1 lifetime, no successful call on record |
| `ollama-gemma4`, `gemma4-31b-fast` | local — excluded by operator preference |
| `nemotron-nano-9b-v2` | 56% lifetime (9/16); recovered to 4/4 only after the reasoning-off fix — sample too thin to roster |
| `gpt-oss-20b` | 51% lifetime (67/131) despite 9/11 in-window; acceptable as an extra fanout voice, not as a rostered default |
| `nemotron-3-nano-30b-a3b` | 1.2s and 12/12 in a 7-day window, but 77% lifetime (78/101) — strongest promotion candidate; re-probe |
| `laguna-s-2.1` | 43% lifetime (26/61) at 17.4s — slower *and* less reliable than every rostered fanout lane |
| `gemma-4-26b-a4b-it` | 70% lifetime (78/112) at 13.5s — beaten on both axes |
| `north-mini-code` | 49% lifetime (20/41) |
| `nemotron-3-ultra-550b-a55b` | 90% lifetime (43/48) but 23.5s — reliable and slow; above the 20s fanout ceiling |

The last two are *recovering*, not dead. `lane_policy_check.py` surfaces them
as notes rather than failures, so a later re-probe can promote them on
evidence.

## Where the money actually goes

Model choice is the smaller lever. Context size is the larger one.

A five-agent verification fanout measured on 2026-08-20 ran at **130.1k input
against 4.5k output — a 29:1 ratio** — with only **18% of that input served
from cache** (22.9k of 130.1k).

Priced as pay-per-token, that one batch of five would be:

| Model | 1 agent | 5 agents |
|---|---|---|
| Opus 5 | $0.79 | **$3.97** |
| Sonnet 5 | $0.32 | $1.59 |
| Haiku 4.5 | $0.16 | $0.79 |

On the subscription it cost **$0 in cash** and a corresponding slice of plan
capacity instead. That is the whole argument for subscription-first: the same
work is free at the margin until the plan's limit, and only then does the
model's price tag start to matter.

Two levers beat switching models:

1. **Raise the cache hit rate.** 18% is low. Every point of cached input costs
   10% of fresh input. Stable prefixes across sibling agents move this more
   than a tier downgrade does.
2. **Cut the input.** At 29:1, these agents are context-flooded, not
   output-heavy. Gathering with a deterministic CLI (`ghmax`, `rg`) and
   handing the agent only the extract is cheaper than any model swap, because
   it removes the tokens instead of repricing them.

## Routing by task class

| Task | Lane | Why |
|---|---|---|
| Search, read, count, structural recon | **no model** — `ghmax`, `rg`, `find` | 0 tokens, 0 latency; measured `ghmax --peek` at 460ms for 415k hits |
| Extraction, summarising, closed-form check | `claude-haiku` | 7/7 lifetime, 19.7s, free at the margin |
| Breadth — many opinions on one question | free fanout tier | 0 cost, 4.9–14.3s per voice, 99.98% combined |
| Independent verification of an answer | `nemotron-3-super-120b-a12b` | 325/347 lifetime; a different family than the answerer |
| Hard reasoning, irreversible decisions | `claude-opus` | 3/3, and the plan already paid for it |
| Anything after the Anthropic plan hits its limit | free fanout, degraded | no paid fallback exists while OpenRouter is at zero |

## Checking this document

```sh
uv run scripts/lane_policy_check.py                 # human-readable, exit 1 on violation
uv run scripts/lane_policy_check.py --json          # machine-readable
uv run scripts/lane_policy_check.py --window-days 14
```

Use `uv run`: the repo targets Python 3.11 and the script uses 3.10+ syntax,
so a system interpreter may be too old.

The script fails when:

- a denied lane is rostered;
- a subscription lane drops below **80%** in-window, or a fanout lane below
  **65%** — a solo lane must carry a call alone, a fanout voice does not;
- a redundant tier's **combined availability** falls under 99%;
- a **sequential** tier is ordered slower-first by more than 1.5x;
- a **parallel** fanout lane exceeds the **20s ceiling** — a fanout ends when
  its laggard does, and past ~20s it is slower than just asking `claude-haiku`
  (19.7s measured).

Order is only checked on sequential tiers. Fanout lanes start at the same
instant, so ranking them by latency would be measuring jitter — the ceiling is
the test that matches how they actually run.

It does not fail on thin samples — those surface as notes, because two calls
is not a measurement. Verified against 7-, 14- and 30-day windows; a roster
that only holds in one window is not a roster.
