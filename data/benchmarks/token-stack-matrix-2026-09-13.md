# Token Stack Matrix — 2026-09-13

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Est. visible input | Observed output | Combined payload | Payload index | Accepted |
|---|---:|---:|---:|---:|:--:|
| cli-selective | 1,932 | 0 | 1,932 | 0.47 | no |
| current-lean | 4,117 | 0 | 4,117 | 1.01 | no |
| context-on-demand | 9,465 | 0 | 9,465 | 2.32 | no |
| max-all+ponytail | 11,650 | 0 | 11,650 | 2.86 | no |
| none/raw | 407,670 | 0 | 407,670 | 100.00 | no |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 67,886 | 106 | 99.84% | 0 | 116 | no |
| rtk-ps | 32,210 | 897 | 97.22% | 296 | 50 | yes |
| tilth-read | 7,100 | 744 | 89.52% | 0 | 5 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 1 | yes |
| context-mode-log | 300,474 | 260 | 99.91% | 0 | 508 | yes |

## Fixed overhead and observed runtime

- Tilth MCP: 7 tools / 2,164 tokens.
- context-mode MCP: 11 tools / 7,458 tokens.
- Ponytail full skill: 0 input tokens.
- Headroom: optional provider/proxy; excluded from Lean totals and never loaded as MCP.
- Monetary cost: not measured; payload index is not billing or quota cost.

## Notes

- **none/raw**: Full skill catalog + raw shell/file/log; no schema overhead.
- **cli-selective**: Router + RTK + Tilth CLI + native projection; zero MCP schema.
- **current-lean**: Prompt hook + RTK + Tilth MCP + native projection; no Headroom.
- **context-on-demand**: Router + RTK + Tilth CLI + context-mode schema/call; no Headroom.
- **max-all+ponytail**: Ponytail not installed on this host; row excluded from ranking.
