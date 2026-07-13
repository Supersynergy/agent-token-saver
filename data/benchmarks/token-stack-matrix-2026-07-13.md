# Token Stack Matrix — 2026-07-13

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Input tok | Provider input | Output tok | Total | Cost index | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| cli-selective | 2,303 | 2,303 | 340 | 2,643 | 0.68 | yes |
| current-lean | 4,011 | 4,011 | 340 | 4,351 | 1.13 | yes |
| context-on-demand | 9,837 | 9,837 | 340 | 10,177 | 2.64 | yes |
| max-all+ponytail | 12,844 | 12,844 | 265 | 13,109 | 3.40 | yes |
| none/raw | 385,707 | 385,707 | 340 | 386,047 | 100.00 | yes |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 37,108 | 226 | 99.39% | 0 | 453 | yes |
| rtk-ps | 44,711 | 1,158 | 97.41% | 67 | 91 | yes |
| tilth-read | 3,414 | 734 | 78.50% | 0 | 6 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 2 | yes |
| context-mode-log | 300,474 | 261 | 99.91% | 0 | 405 | yes |

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
