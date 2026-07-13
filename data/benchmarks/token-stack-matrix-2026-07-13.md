# Token Stack Matrix — 2026-07-13

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Input tok | Provider input | Output tok | Total | Cost index | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| cli-selective | 2,428 | 2,428 | 340 | 2,768 | 0.73 | yes |
| current-lean | 4,136 | 4,136 | 340 | 4,476 | 1.18 | yes |
| context-on-demand | 9,962 | 9,962 | 340 | 10,302 | 2.70 | yes |
| max-all+ponytail | 12,969 | 12,969 | 265 | 13,234 | 3.47 | yes |
| none/raw | 380,531 | 380,531 | 340 | 380,871 | 100.00 | yes |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 37,080 | 226 | 99.39% | 0 | 588 | yes |
| rtk-ps | 40,844 | 1,447 | 96.46% | 111 | 256 | yes |
| tilth-read | 2,133 | 570 | 73.28% | 0 | 8 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 3 | yes |
| context-mode-log | 300,474 | 261 | 99.91% | 0 | 801 | yes |

## Fixed overhead and observed runtime

- Tilth MCP: 6 tools / 1,836 tokens.
- context-mode MCP: 11 tools / 7,458 tokens.
- Ponytail full skill: 1,299 input tokens.
- Headroom: optional provider/proxy; excluded from Lean totals and never loaded as MCP.
- Monetary marginal cost: EUR 0 inside the current subscription; cost index measures quota/token load.

## Notes

- **none/raw**: Full skill catalog + raw shell/file/log; no schema overhead.
- **cli-selective**: Router + RTK + Tilth CLI + native projection; zero MCP schema.
- **current-lean**: Prompt hook + RTK + Tilth MCP + native projection; no Headroom.
- **context-on-demand**: Router + RTK + Tilth CLI + context-mode schema/call; no Headroom.
- **max-all+ponytail**: Current + context-mode MCP + full Ponytail skill; cold-schema cost.
