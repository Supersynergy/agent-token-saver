# What Agent Token Saver saves

ATS has several components. They save different things, and some add a small
cost to protect the result. A hook being installed is not evidence of savings.

| Use case | What changes | What can be saved | Evidence and limits |
|---|---|---|---|
| Long passing test/build logs | `ats-verify -- <check>` retains a compact verdict and saves the full log on disk. | Input context; repeated reading of the same output in later model calls. | In the September 5 audit: 2,937 to 539 characters for an ATS check, and 15,389 to 784 for a router check, including the CLI's JSON wrapper. These are character measurements, not provider billing. |
| Noisy failed checks | The wrapper preserves the failing exit status, diagnostic lines and raw-log path. | Repeated noise in model context; potentially fewer blind retries. | Diagnostic-preservation tests pass. Retry and monetary savings require task-level comparisons; a smaller but unhelpful error report is a regression. |
| Large skill libraries | `si route` chooses metadata and paths before full skill bodies are read. | Unneeded descriptions and skill bodies, when the host can keep them out of its prompt. | `si bench` compares the whole indexed metadata catalog with its routing block. It excludes loaded bodies and host overhead. It does not prove the whole catalog would otherwise have been loaded. |
| Repeated investigation of the same issue | `ats-recall` retrieves relevant prior evidence. | Duplicate searches, rereads and reconstruction work. | Conditional on a useful, still-valid hit. No net percentage was measured in this audit. |
| Targeted code/data investigation | Scoped `rg`, projections, or supported RTK filters emit the relevant subset. | Irrelevant file content and repeated boilerplate. | Requires the same task oracle before and after. A small exact search often needs no additional wrapper. |
| Long conversations with stable prefixes | Cache-aware instructions avoid unnecessary changes to shared context. | Potentially less expensive input processing under the provider's cache pricing. | Token counts may stay equal or increase. Provider counters and cache classes must be measured; ATS cannot guarantee a cache hit. |
| Repeated tasks in a bounded team | Workers receive task capsules instead of the controller's entire transcript. | Duplicated context, when capsule preparation costs less than the avoided input. | Sum controller, workers, retries and verification. Parallel execution can save time while consuming more tokens. |
| Runaway or unverified work | The session guard reports excessive usage or a failed verification. | Potentially avoided continuation or rework. | It is a warning system. The counterfactual work avoided was not measured. |
| Skill/tool usage feedback | Observer hooks record which tool/skill was used and its outcome. | No immediate model-token saving. Feedback can improve later routing. | GG's observer injects no model context, but uses a bounded local subprocess for relevant events. Its execution adds latency. |
| Cache and usage accounting | `ats-cache` and `agent-token-ledger` calculate usage views. | Nothing by themselves. | They measure; their own command output also costs context if read by a model. |

## GG Coder example

The actual GG Coder 5.46.2 `AgentSession`, extension loader, native skill tool
and Bash tool were tested with a local deterministic provider. The same
400-line passing-test fixture produced **3,233 characters without ATS and 199
with ATS**, including GG's exit-status prefix and ATS's footer: 93.8% less
tool-result text. The acceptance check required the `400 passed` verdict to
survive. No external model call was used, so this test measures no provider
token or monetary saving.

The companion router's native extension recorded one successful skill load
and excluded a missing skill. It observes results; it does not compress them.
`ats-verify` performs the output reduction. Existing skill descriptions in GG's
tool schema are not removed by installing the observer.

Reproduce with an installed GG package and both repository checkouts:

```bash
node scripts/ggcoder_runtime_smoke.mjs /path/to/installed/ggcoder /path/to/router /path/to/agent-token-saver
```

Run that command from the router repository. It uses a temporary HOME and
workspace, starts a loopback-only test provider, and removes its test files.

## When wrapping is a loss

For two already-short smoke results in the audit, ATS's JSON wrapper changed
147 characters into 408, and 94 into 338. There was no output saving.
Use direct output for tiny checks. Repeated routing, broad policy/skill reads,
unnecessary diagnostics and redundant subagents can also exceed the context
they were supposed to save.

The audit demonstrates savings on selected tool outputs. It does not establish
net provider-token or monetary savings for the entire agent session. That needs
matched tasks, identical acceptance criteria, fresh and warm runs, and complete
usage accounting across every involved agent.
