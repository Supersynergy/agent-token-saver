# Token Stack Matrix — 2026-07-23

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Est. visible input | Observed output | Combined payload | Payload index | Accepted |
|---|---:|---:|---:|---:|:--:|
| cli-selective | 1,854 | 0 | 1,854 | 0.46 | no |
| current-lean | 3,782 | 0 | 3,782 | 0.93 | no |
| context-on-demand | 9,387 | 0 | 9,387 | 2.32 | no |
| max-all+ponytail | 12,614 | 0 | 12,614 | 3.12 | no |
| none/raw | 404,634 | 0 | 404,634 | 100.00 | no |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 65,068 | 35 | 99.95% | 0 | 85 | no |
| rtk-ps | 32,210 | 887 | 97.25% | 421 | 37 | yes |
| tilth-read | 6,882 | 747 | 89.15% | 0 | 5 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 1 | yes |
| context-mode-log | 300,474 | 260 | 99.91% | 0 | 864 | yes |

## Fixed overhead and observed runtime

- Tilth MCP: 6 tools / 1,836 tokens.
- context-mode MCP: 11 tools / 7,458 tokens.
- Ponytail full skill: 1,299 input tokens.
- Headroom: optional provider/proxy; excluded from Lean totals and never loaded as MCP.
- Monetary cost: not measured; payload index is not billing or quota cost.

## Notes

- **none/raw**: Full skill catalog + raw shell/file/log; no schema overhead.
- **cli-selective**: Router + RTK + Tilth CLI + native projection; zero MCP schema.
- **current-lean**: Prompt hook + RTK + Tilth MCP + native projection; no Headroom.
- **context-on-demand**: Router + RTK + Tilth CLI + context-mode schema/call; no Headroom.
- **max-all+ponytail**: Current + context-mode MCP + full Ponytail skill; cold-schema cost.
