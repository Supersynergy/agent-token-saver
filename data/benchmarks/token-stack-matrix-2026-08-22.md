# Token Stack Matrix — 2026-08-22

Measured local CLIs/MCP schemas. Token proxy for local payloads: UTF-8 bytes / 4.

## Stack ranking

| Stack | Est. visible input | Observed output | Combined payload | Payload index | Accepted |
|---|---:|---:|---:|---:|:--:|
| cli-selective | 1,946 | 0 | 1,946 | 0.48 | no |
| current-lean | 3,803 | 0 | 3,803 | 0.93 | no |
| context-on-demand | 9,479 | 0 | 9,479 | 2.33 | no |
| max-all+ponytail | 11,336 | 0 | 11,336 | 2.79 | no |
| none/raw | 406,991 | 0 | 406,991 | 100.00 | no |

## Components

| Component | Base tok | Optimized tok | Saved | Base ms | Opt ms | Accepted |
|---|---:|---:|---:|---:|---:|:--:|
| skill-routing | 67,260 | 106 | 99.84% | 0 | 118 | no |
| rtk-ps | 32,210 | 908 | 97.18% | 22 | 37 | yes |
| tilth-read | 7,047 | 747 | 89.40% | 0 | 4 | yes |
| native-log-projection | 300,474 | 185 | 99.94% | 0 | 1 | yes |
| context-mode-log | 300,474 | 260 | 99.91% | 0 | 510 | yes |

## Fixed overhead and observed runtime

- Tilth MCP: 6 tools / 1,836 tokens.
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
