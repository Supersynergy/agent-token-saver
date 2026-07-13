# Meta-Prompt: Autonomous Multi-Benchmark Runner

Drop this into any AI agent (Claude Code, Cursor, Aider, OpenCode, etc.) to make it run its own parametric benchmarks against a local tool — no human handholding.

## Use Case

You have a tool with N configurable knobs (model, threshold, stage cap, cache on/off, pre-processor on/off, timeout, ...) and you want to know:

- Which knob combination is Pareto-optimal for cost vs quality?
- Which input classes benefit most / least?
- Where are the cliffs (latency spikes, quality drops, timeouts)?
- What are the headline numbers for a README/pitch deck?

You don't want to design 50 configurations by hand. You want the agent to **explore the configuration space** itself, prune dead-ends, and return a Pareto frontier.

## The Meta-Prompt

```
You are running an autonomous benchmark mission for <TOOL_NAME>.

=== GROUND RULES ===

1. You are measuring REAL outputs against REAL inputs. No mocks, no simulations.
   Every datapoint must come from an actual tool invocation with an actual response.

2. You may not exceed <BUDGET_TOKENS> API tokens or <BUDGET_MINUTES> minutes of wall clock.
   Check your spend with <BUDGET_CHECK_CMD> after every batch.

3. Every run writes JSON to <RESULTS_DIR>/<run_id>.json with the exact schema:
   {
     "run_id": str, "timestamp": iso8601, "input_id": str,
     "config": { knob_name: value, ... },
     "metrics": { tokens_in: int, tokens_out: int, latency_ms: float,
                  bytes_in: int, bytes_out: int, quality_score: 0-1, ok: bool },
     "sample_output": str (first 200 chars),
     "error": str|null
   }

4. You must design the experiment in three phases:

   Phase 1 — BASELINE (N=5 runs):
     Lock all knobs to their documented defaults. Run against all test inputs.
     This is your reference point. If baselines fail, fix the setup before proceeding.

   Phase 2 — ONE-AT-A-TIME (OAT) sweep (N = num_knobs × num_inputs):
     Hold everything at default, vary ONE knob at a time through its range.
     Rank knobs by impact on your headline metric (tokens_out usually).
     Prune knobs with <5% impact — they're not worth combining.

   Phase 3 — PARETO COMBINATION (N ≤ 20 runs):
     Take the top 3 knobs from Phase 2. Grid-search their promising ranges
     across ALL test inputs. Pick the combinations on the efficient frontier
     (minimum tokens_out at each quality level).

5. Test inputs must span at least 4 difficulty tiers:
   - trivial (baseline noise floor)
   - typical (what users actually use)
   - large (stresses summarization/chunking)
   - adversarial (edge case: malformed, huge, or intentionally noisy)

6. Quality scoring MUST be deliberate. For text-summarization tools, score on:
   - Does the output preserve factual claims from the input? (0.4 weight)
   - Is the output actually shorter than the input? (0.2 weight)
   - Is the output readable (no tag soup, no truncation mid-word)? (0.2 weight)
   - Does the output match the requested format (JSON/bullets/markdown)? (0.2 weight)
   Run quality eval with a SEPARATE model instance to avoid self-grading bias.

=== YOUR DELIVERABLES ===

After the three phases, write <RESULTS_DIR>/REPORT.md with:

1. **TL;DR** (3 bullets max): best config, headline savings factor, main tradeoff.
2. **Pareto frontier table**: one row per efficient config, columns for each metric.
3. **Per-input-tier breakdown**: which inputs benefit most, which least, why.
4. **Latency profile**: p50/p95/p99 for each config. Flag any >10x spikes.
5. **Quality cliffs**: configs that saved tokens but tanked quality, with examples.
6. **Recommended default**: the single config you'd ship as the new default.
7. **Unresolved questions**: 3-5 things a human should decide before shipping.

=== CONSTRAINTS ===

- Never modify the tool's source during benchmarking. If a bug blocks you,
  log it to <RESULTS_DIR>/BUGS.md and skip that configuration.
- Never retry a failed run more than 2 times. Record the failure and move on.
- If Phase 2 shows a knob has zero impact, do NOT include it in Phase 3.
- If Phase 3 blows your budget, truncate to the top-5 combinations.
- If you discover the tool is fundamentally broken on some input class,
  write that finding FIRST before continuing other work.

=== ANTI-PATTERNS (you will be judged on these) ===

- Designing 50 configurations upfront and running them all. Use Phase 2 to prune.
- Running 100 trials on input X and 3 on input Y. Balance the matrix.
- Self-grading quality with the same model that produced the output.
- Reporting mean latency without p95/p99.
- Claiming Nx savings without a like-for-like baseline.
- Stopping the benchmark the moment you find one impressive number.
- Ignoring configs that saved tokens but failed on adversarial inputs.

=== TOOL UNDER TEST ===

Name: <TOOL_NAME>
Invocation: <TOOL_CMD> [flags]
Docs: <TOOL_DOCS_PATH>
Knobs to vary:
  - <knob_1>: <range>
  - <knob_2>: <range>
  - ...
Test inputs at: <INPUTS_DIR>
Baseline command: <BASELINE_CMD>

Begin with Phase 1. Report progress after each phase.
```

## Filling in the blanks for Hyperstack

When you run this against the Hyperstack, the slots become:

- `<TOOL_NAME>`: hyperfetch
- `<BUDGET_TOKENS>`: 200000 (enough for ~40 gemma calls)
- `<BUDGET_MINUTES>`: 30
- `<RESULTS_DIR>`: `~/agent-token-saver/bench/runs/<timestamp>/`
- `<BUDGET_CHECK_CMD>`: `bash ~/agent-token-saver/plugins/team-sandbox.sh stats`
- `<TOOL_CMD>`: `hyperfetch <url>`
- `<TOOL_DOCS_PATH>`: `~/agent-token-saver/HYPERSTACK.md`
- `<BASELINE_CMD>`: `~/.cts/venv/bin/python ~/.cts/bin/hyperfetch-stage.py --stage curl_cffi --url <URL>` (raw, no optimizations)
- `<INPUTS_DIR>`: A list of URLs in tiers:
  - **trivial**: example.com, example.org, httpbin.org/html
  - **typical**: api.github.com, raw.githubusercontent.com/torvalds/linux/master/README
  - **large**: en.wikipedia.org/wiki/Token, en.wikipedia.org/wiki/Artificial_intelligence, news.ycombinator.com
  - **adversarial**: a site with heavy JS (try monday.com), a 404, a timeout, a cloudflare-gated page
- Knobs:
  - `--stage`: {curl_cffi, camoufox, domshell, browser}
  - `--no-cache` / cache-hit
  - `--no-summary` / `--summarize` / `--markdown` / `--extract "<prompt>"`
  - `CTS_GEMMA_MODEL`: {phi4-mini:latest, gemma4:e2b, gemma4:e4b, phi4:14b, mistral-small3.2:latest}
  - `CTS_GEMMA_THRESHOLD`: {50, 100, 200, 500, 1000}
  - `CTS_GEMMA_MAX_INPUT`: {1024, 2048, 4096, 8192, 16384}
  - `CTS_TEAM_NS`: new vs warm vs shared

## Quality scoring prompt (subagent for eval)

Paste this into a SECOND agent (different model) to grade outputs from the benchmark runner:

```
You are a strict quality grader. Rate the following tool output on 0.0-1.0.

INPUT (truncated to 4000 chars):
<<<
{input_text}
>>>

OUTPUT (produced by tool with config {config_json}):
<<<
{output_text}
>>>

TARGET USE CASE: An AI coding agent needs to understand {input_text}'s meaning
to make a decision. They will never see the full input — only this output.

Rate on these 4 dimensions (each 0.0-1.0):

1. factuality: Does the output faithfully represent the key facts from the input?
   (1.0 = all core facts preserved, 0.5 = half preserved, 0.0 = hallucinated or empty)

2. compression: Is the output meaningfully shorter than the input?
   (1.0 = <10% size, 0.5 = 50% size, 0.0 = same or longer)

3. cleanliness: Is the output readable — no HTML tags, no truncation mid-word,
   no repeated lines, no garbage encoding?
   (1.0 = pristine, 0.5 = minor issues, 0.0 = unreadable)

4. format_match: Does the output match the requested format? (bullets if summary,
   markdown if markdown mode, JSON if extract, etc.)
   (1.0 = perfect match, 0.0 = wrong format entirely)

Output exactly this JSON (nothing else):
{
  "factuality": 0.0,
  "compression": 0.0,
  "cleanliness": 0.0,
  "format_match": 0.0,
  "composite": 0.0,
  "justification": "one sentence"
}
```

## Why this beats human-designed benchmarks

1. **No sampling bias** — The OAT sweep in Phase 2 forces the agent to test every knob, not just the ones they expect to matter.

2. **Budget discipline** — The explicit token/minute budget and the prune rule in Phase 2 prevent combinatorial explosion.

3. **Separate grader** — Quality eval from a different model avoids the "my own output looks great" bias.

4. **Pareto, not winner** — Returns a frontier of good configs for different tradeoffs, not one "best" config.

5. **Fail-forward** — Adversarial inputs are first-class, not an afterthought.

6. **Reproducible** — Every run writes JSON with its full config, so re-runs can verify regressions.

## Variations

- **Multi-tool bakeoff**: Swap in 3-5 competing tools and compare their Pareto frontiers. Same meta-prompt works with `<TOOL_NAME>` set per sub-run.

- **Prompt-level benchmark**: Instead of tool configs, vary prompt phrasings and measure which one gives the cheapest+most-correct output from the same tool.

- **Model-swap benchmark**: Hold config fixed, swap the underlying LLM. Useful for Ollama model comparisons (gemma3 vs phi4 vs mistral vs llama3.2 etc).

- **Team-simulated benchmark**: Run the same URL through the tool from 10 different `--team-ns` values to verify cache dedupe actually saves what it claims.
