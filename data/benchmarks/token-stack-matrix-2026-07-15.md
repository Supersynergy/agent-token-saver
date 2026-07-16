# Token Stack Matrix — 2026-07-15

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Est. visible input | Observed output | Combined payload | Payload index | Accepted |
|---|---:|---:|---:|---:|:--:|
| cli-selective | 1,887 | 0 | 1,887 | 0.50 | yes |
| current-lean | 3,782 | 0 | 3,782 | 1.01 | yes |
| context-on-demand | 9,420 | 0 | 9,420 | 2.51 | yes |
| max-all+ponytail | 12,614 | 0 | 12,614 | 3.36 | yes |
| none/raw | 375,673 | 0 | 375,673 | 100.00 | yes |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 36,107 | 68 | 99.81% | 0 | 92 | yes |
| rtk-ps | 32,210 | 887 | 97.25% | 28 | 45 | yes |
| tilth-read | 6,882 | 747 | 89.15% | 0 | 4 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 2 | yes |
| context-mode-log | 300,474 | 260 | 99.91% | 0 | 328 | yes |

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
