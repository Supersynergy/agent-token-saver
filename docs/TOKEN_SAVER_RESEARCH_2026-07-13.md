# Token-saver landscape — 2026-07-13

Public GitHub metadata snapshot. Stars are discovery signals, not benchmark scores.

## Ranked candidates

| Tool | Stars | Freshness | Evidence verdict |
|---|---:|---|---|
| [Graphify](https://github.com/Graphify-Labs/graphify) | 83,830 | pushed 2026-07-13 | Excellent persistent graph projection; not an always-on saver |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | 81,839 | v4.8.4, 2026-07-10 | Popular; local A/B was net more tokens |
| [RTK](https://github.com/rtk-ai/rtk) | 70,717 | v0.43.0, 2026-06-28 | Strongest mature default; stable process-fixture reduction 97.25% |
| [CodeGraph](https://github.com/colbymchenry/codegraph) | 59,586 | pushed 2026-07-13 | Strong repeated repo relationship queries; workload-gated |
| [Headroom](https://github.com/headroomlabs-ai/headroom) | 58,872 | v0.31.0, 2026-07-09 | Large vendor claims; observed Codex gain was workload-dependent |
| [context-mode](https://github.com/mksglu/context-mode) | 18,878 | v1.0.169 | 99.91% large-log projection; 7,458-token cold schema |
| [LLMLingua](https://github.com/microsoft/LLMLingua) | 6,431 | pushed 2026-04-08 | Mature research compressor, not a ready coding-agent stack |
| [lean-ctx](https://github.com/yvgude/lean-ctx) | 3,230 | v3.9.8, 2026-07-12 | Interesting but 76 MCP tools and <14-day release |
| [Tilth](https://github.com/jahala/tilth) | 310 | v0.9.0 | Local code-read reduction 86.43% |
| [squeez](https://github.com/claudioemmanuel/squeez) | 167 | v1.36.0, 2026-07-10 | Unverified 95% claim; <14-day release |
| [token-saver](https://github.com/ppgranger/token-saver) | 115 | pushed 2026-06-02 | Useful format filters; no measured win over RTK/native projection |
| [mcp-compressor](https://github.com/atlassian-labs/mcp-compressor) | 97 | v0.31.5, 2026-07-09 | Good schema-router design; unnecessary for one lean MCP |
| [tokbench](https://github.com/Entelligentsia/tokbench) | 9 | pushed 2026-06-15 | Useful eval direction; low adoption |

Community sources:

- [Atlassian: MCP compression and tool bloat](https://www.atlassian.com/blog/development/mcp-compression-preventing-tool-bloat-in-ai-agents)
- [StackOne: MCP token optimization](https://www.stackone.com/blog/mcp-token-optimization/)
- [Pinggy: token-usage tools overview](https://pinggy.io/blog/tools_to_reduce_ai_coding_agent_token_usage/)

The strongest repeated community pattern is progressive tool/schema disclosure. Manufacturer savings claims were not promoted over local accepted-output measurements.

## Local versions and upgrade decision

| Tool | Local | Upstream | Decision |
|---|---|---|---|
| RTK | 0.46.0 | 0.46.0 | current (was 0.43.0 at snapshot; see the 2026-09-03 addendum) |
| context-mode | 1.0.169 runtime; older Codex cache | 1.0.169 | runtime current; keep on demand |
| Headroom | 0.31.0 | 0.31.0 | optional provider/proxy; not Lean-default and never MCP |
| Tilth | 0.9.0 | 0.9.0 release | current release |
| Graphify | 0.9.11 | 0.9.14 | defer: release inside 14-day gate |
| CodeGraph | 1.3.1 | 1.4.1 | defer: release inside 14-day gate |
| Ponytail | local unversioned skill | 4.8.4 | do not global-load; measured net negative |

No new candidate was installed merely because it was new or popular.

## Addendum 2026-09-03 — RTK 0.43.0 to 0.46.0

The table above is a snapshot and stays as recorded. This addendum carries the
drift found when the pin was re-checked against the installed binary.

RTK 0.46 adds per-tool `pipe` filters that project **already captured** output
from stdin, so a wrapper can use them without re-running the command:

`cargo-test, pytest, go-test, go-build, tsc, vitest, mypy, ruff-check,
ruff-format, prettier, grep, rg, find, fd, git-log, git-diff, git-status, log,
phpunit, pest, paratest, php-test, ecs, phpstan, pint`

Measured on this machine, not adopted on the strength of the version number.
There is no fixed winner: selection happens **per run**, and which projector is
smaller depends on the shape of the log rather than on the tool.

Red-log measurement, bytes shown by the selected projector:

| Filter | Short red log | Long red log | Selected |
|---|---|---|---|
| `cargo-test` | 76 B to 39 B | 3,060 B to 323 B | RTK both times |
| `pytest` | 76 B to 26 B | 3,132 B to 957 B (RTK offered 1,264 B) | RTK short, builtin long |
| `mypy` | 71 B to 70 B | 2,125 B to 2,124 B | builtin both times |
| `tsc` | 75 B to 74 B | 2,529 B to 2,528 B | builtin both times |
| `ruff-check` | 58 B to 57 B | 2,677 B to 110 B | builtin both times |

Green runs are where the saving is largest and least contested: the full local
suite goes from 2,425 B to 18 B (`Pytest: 328 passed`) through the RTK filter.

Reading the table honestly:

- **Only `cargo-test` wins consistently.** Its output is repetitive enough that
  grouping beats line selection at every size.
- **The builtin wins on short logs**, because a handful of diagnostic lines
  cannot be compressed below themselves once a filter adds a header.
- **`mypy` and `tsc` stay with the builtin even on long logs.** RTK's mypy
  filter was passthrough for the shape tested here (2,125 B in, 2,125 B out),
  although it does regroup other layouts. That format sensitivity is the whole
  argument for measuring per run instead of pinning a winner in a table.
- **A red `mypy`/`tsc` run therefore saves almost nothing, by design.** When
  every line is already a diagnostic, "complete on red" and "compact" are in
  direct conflict, and completeness wins. The saving for those tools comes from
  their green runs, not their red ones.

Two findings drove the wiring:

- The `rtk pytest` **wrapper** printed zero bytes on a failing test while
  returning exit 1. A red result with no evidence is the worst possible output,
  so `ats-verify` never delegates execution to a filter; it captures the run
  itself and offers the output to `rtk pipe` as one candidate projection.
- A filter is adopted per run, by measurement: every candidate must still carry
  a signal line, and the smallest surviving candidate wins. `ruff-check`,
  `mypy` and `tsc` lose that comparison on the shapes measured here and are
  simply not used, without special-casing. Nothing is marked "adopted" globally.

## Graphify query measurement

Existing code graph:

- 2,982 nodes, 6,187 links, 10 hyperedges.
- raw `graph.json`: 3,094,806 bytes, about 773,702 tokens.
- `graphify query --budget 800`: about 652 tokens, 450 ms.
- projection: 99.92% smaller, 1,186.7x reduction.

The graph was stale versus the repo and used a pre-#1504 node-ID schema. This proves compression, not current answer accuracy; rebuild after the Graphify upgrade passes the age gate.

## Decision

```text
default: router -> RTK -> native projection -> memory/Tilth CLI on demand
heavy payload: context-mode session
repeated structure: choose Graphify OR CodeGraph per repo
broad MCP catalog: benchmark mcp-compressor before enabling
```

Do not combine every layer. The measured all-on profile cost 12,567 input tokens versus 1,918 for CLI-selective.
