# AgentMaster protocol

`llmadapter ask-v2` is the strict machine interface for an external controller.
The universal installer places a managed copy on `PATH`; this optional adapter
requires [Bun](https://bun.sh/) at runtime, and `agent-token-saver doctor --json`
reports its exact capability/launcher status without starting a provider.
Use `doctor --require-llmadapter` for fail-closed AgentMaster automation.
It reads prompts from stdin or a regular file, never a positional argument.
Input is limited to 1,800 UTF-8 bytes so the worker capsule never silently
truncates it. Prompt files must be regular, owned by the current user and have
no group/other permissions. Three selected workers, a 500-token requested
ceiling and a 120-second global deadline are the defaults.

```bash
printf '%s' "$TASK" | llmadapter ask-v2 \
  --stdin --swarm --lanes local --no-cache \
  --usage-out run-accounting.json
```

`--contract verdict|prose|json` picks the answer shape. `verdict` is the default
and is what a controller gates on:
`STATUS: PASS|FAIL|BLOCKED; EVIDENCE: …; HANDOFF: …`. Use `prose` or `json` for
work that is not a verification — a verdict shape around a prose objective makes
workers argue about format instead of answering.

`--lanes` takes a lane name or a selector: `free`, `cheap`, `paid`, `local`,
`cli`, `all`. `cheap` is the measured band of paid models that cost a rounding
error — over closed-form tasks with known answers, three samples each,
`openai/gpt-oss-120b` scored 9/9 for $0.00046 per nine calls and
`openai/gpt-5.6-luna` 9/9 for $0.00093, against 6-7/9 for the best free lanes.
It is a selector keyword and not a class, so the wire `class` stays `paid` and
`--allow-paid` still applies.

A class selector is ordered by measured lane health — a 7-day Laplace-smoothed
success rate over the call ledger — so a provider outage sinks that lane and a
working one takes the worker slot. An explicit `--lanes a,b,c` keeps the
caller's order. `LLMADAPTER_LANE_HEALTH=0` restores table order.
`llmadapter doctor` reports which lanes a selector will actually run and checks
every configured model id against the live OpenRouter catalog; `doctor --probe`
adds one 32-token call per free lane, because a model can sit in the catalog and
still return a provider error on every request.

`ox-alpha` selects OpenRouter's experimental `stealth/ox-alpha` model by name.
The 2026-08-22 catalog reports zero prompt/completion price, a 1,048,576-token
window, mandatory reasoning and a 131,072-token output ceiling. The lane uses
`low` effort with returned reasoning excluded. It is deliberately opt-in and
never joins `free` or `all`; use `llmadapter doctor` before relying on an alpha
model whose availability or identity can change.

`--cap` is the total selected-worker limit: at most three normally, or at most
64 with explicit `--fanout`. OpenRouter is always remote; CLI agents are remote
unless a private host lane explicitly declares `local_safe`; Ollama is local
only on a loopback URL. Remote lanes require `--allow-remote`; paid lanes also
require `--allow-paid`. HTTP redirects are rejected. Host lanes load only from
a current-user-owned, regular, non-symlink `0600`
`~/.agent-token-saver/local-lanes.json`.
The command emits exactly one
[`llmadapter.result` v2](../schemas/llmadapter-result-v2.schema.json) JSON object.
The private `0600` usage file contains its completed accounting object. Token
counts remain `reported`, `estimated` or `unknown`; cost is `null` unless a
future provider supplies authoritative billing. The requested output cap is
server-side for OpenRouter, native for Ollama and advisory-only for CLI agents,
whose captured output is still byte-bounded. Every lane record exposes
`call_started`, so a controller can independently derive call counts, cache
hits, and token-coverage totals instead of trusting the summary. Shield, key,
configuration and spawn failures before transport starts remain false.

Stdin/file transport prevents prompt leakage through process arguments. It does
not stop a model from repeating input in its answer. With cache enabled, that
answer is stored in the private cache and may therefore contain repeated input;
use `--no-cache` for sensitive tasks.

The repository ships a built-in lane table, and a host may add local lanes
through its private configuration; `llmadapter lanes` is the runtime inventory.
A lane marked `"opt_in": true` is skipped by `all` and by the class selectors
and is reachable only by name, so an experimental or heavy lane never joins a
swarm by accident.

## Opt-in extensions

Every flag below is off by default. The capability contract and the default
result envelope are unchanged, so a controller written against the strict v2
protocol keeps working without knowing these exist. `contract --extended`
advertises them for controllers that opt in.

```bash
printf '%s' "$TASK" | llmadapter ask-v2 \
  --stdin --swarm --lanes local --first-pass \
  --oracle 'grep -qi sqlite "$LLMADAPTER_ANSWER_PATH"' \
  --budget-tokens 2000
```

- `--first-pass` starts every selected lane at once, runs the oracle on each
  answer as it lands and prunes the peers at the first PASS. Pruned lanes keep a
  record with terminal `pruned`, which appears only in this mode. Without an
  oracle the first valid answer wins.
- `--oracle` is a shell command; exit 0 is PASS. It receives
  `LLMADAPTER_ANSWER_PATH` (a private `0600` file) and `LLMADAPTER_RUN_DIR`, and
  is killed after two seconds. The answer never reaches it through argv. The
  oracle verdict is reported in `first_pass.winner`, not in the exit code: the
  v2 contract fixes exit 0 to mean status `ok` or `partial`, and a lane that
  answered did answer.
- `--oracle-env-prefix NAME` additionally exports `NAME_ANSWER_PATH` and
  `NAME_RUN_DIR`, so a controller can hand down an oracle it already wrote
  against its own variable names. Without it that oracle reads an empty path,
  never passes, and `--first-pass` degrades into a full-price run with nothing
  pruned.
- `llmadapter evidence [--mode …] (--target X | --stdin) [--bytes N] [--out PATH]`
  runs the gather step alone: no lane, no model token, a private artifact and a
  report with `model_tokens_spent: 0`. Use it to gather once and give N workers
  a path instead of a payload.
- `--budget-tokens N` is enforced locally rather than requested from a provider:
  an input estimate above the budget refuses before the call, a CLI lane's
  stdout is bounded at four bytes per budgeted token, and a reported total above
  the budget fails the record with `budget_exceeded`.
- `--evidence` gathers one primary-source artifact before the workers start,
  projects it to `--evidence-bytes` (default 600) and injects it into every
  capsule, so tool-less lanes can cite a fresh fact instead of being told not to
  claim one. Lookup order is `ats-url-cache`, then the provider, then the cache
  write. No scraper is bundled: the provider is a host executable named by
  `LLMADAPTER_EVIDENCE_CMD`, called as `"$LLMADAPTER_EVIDENCE_CMD" <mode>` with
  the query on stdin and the artifact on stdout. Modes are `research` (default),
  `mega`, `fetch` (needs `--evidence-target <url>`) and `primary`, which asks the
  provider's primary-source registry so a version, price or policy claim can
  cite whoever owns the fact. If the artifact reports
  a bot wall (`page_status: challenge`), it is discarded and the capsule asks
  the worker for BLOCKED — the adapter never attempts a bypass. Without a
  provider the run continues with evidence marked unavailable. The provider
  receives `LLMADAPTER_EVIDENCE_DEADLINE_MS` so it can bound itself, and may
  exit 4 to report that it is busy rather than out of answers — that surfaces as
  `evidence_provider_busy`, which is worth retrying.
- `--skill-route` asks `si` for one skill and puts its path in the capsule
  instead of relying on the four built-in regex routes. Fail-open.
- `llmadapter council` runs the identical worker stage and adds one
  fresh-context lane that reports CONSENSUS, DISSENT and CONFIDENCE. Choose it
  with `--synth-lane NAME`.
- `llmadapter cache-export --out PATH.jsonl [--with-answers] [--duckdb PATH]`
  snapshots the private cache for replay or analysis. Answers are hashed unless
  `--with-answers` is passed; the live cache keeps its `0600` files.
