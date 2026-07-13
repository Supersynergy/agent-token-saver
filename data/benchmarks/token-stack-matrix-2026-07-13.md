# Token Stack Matrix — 2026-07-13

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Input tok | Provider input | Output tok | Total | Cost index | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| cli-selective | 1,918 | 1,918 | 340 | 2,258 | 0.60 | yes |
| current-lean | 3,734 | 3,734 | 340 | 4,074 | 1.08 | yes |
| context-on-demand | 9,452 | 9,452 | 340 | 9,792 | 2.60 | yes |
| max-all+ponytail | 12,567 | 12,567 | 265 | 12,832 | 3.40 | yes |
| none/raw | 376,626 | 376,626 | 340 | 376,966 | 100.00 | yes |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 37,157 | 98 | 99.74% | 0 | 50 | yes |
| rtk-ps | 32,210 | 887 | 97.25% | 21 | 32 | yes |
| tilth-read | 6,785 | 748 | 88.98% | 0 | 4 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 1 | yes |
| context-mode-log | 300,474 | 261 | 99.91% | 0 | 740 | yes |

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
