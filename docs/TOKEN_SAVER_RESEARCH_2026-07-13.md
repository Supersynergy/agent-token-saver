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

Measured on this machine, not adopted on the strength of the version number:

| Filter | Green | Red | Verdict |
|---|---|---|---|
| `pytest` | 2,425 B to 18 B | keeps assertion, file and line | adopt |
| `mypy` | summary only | regroups to file header plus `L31:`; keeps code and reason | adopt |
| `cargo-test` | summary only | keeps failing test, panic site | adopt |
| `tsc` | summary only | keeps `TS####`, file and position | adopt |
| `ruff-check` | passthrough | passthrough | no win; builtin projection used |

Two findings drove the wiring:

- The `rtk pytest` **wrapper** printed zero bytes on a failing test while
  returning exit 1. A red result with no evidence is the worst possible output,
  so `ats-verify` never delegates execution to a filter; it captures the run
  itself and offers the output to `rtk pipe` as one candidate projection.
- A filter is adopted per run, by measurement: every candidate must still carry
  a signal line, and the smallest surviving candidate wins. `ruff-check` loses
  that comparison here and is simply not used, without special-casing.

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
