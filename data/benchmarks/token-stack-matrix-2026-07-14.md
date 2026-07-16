# Token Stack Matrix — 2026-07-14

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Input tok | Provider input | Output tok | Total | Cost index | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| cli-selective | 1,917 | 1,917 | 340 | 2,257 | 0.60 | yes |
| current-lean | 3,733 | 3,733 | 340 | 4,073 | 1.08 | yes |
| context-on-demand | 9,450 | 9,450 | 340 | 9,790 | 2.60 | yes |
| max-all+ponytail | 12,565 | 12,565 | 265 | 12,830 | 3.40 | yes |
| none/raw | 376,626 | 376,626 | 340 | 376,966 | 100.00 | yes |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 37,157 | 98 | 99.74% | 0 | 47 | yes |
| rtk-ps | 32,210 | 887 | 97.25% | 18 | 29 | yes |
| tilth-read | 6,785 | 747 | 88.99% | 0 | 3 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 1 | yes |
| context-mode-log | 300,474 | 260 | 99.91% | 0 | 272 | yes |

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
