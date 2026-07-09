# Local Token-Saver Benchmark — 2026-07-09

No provider API calls. Token estimate = UTF-8 bytes / 4.

| Case | Base tok | Opt tok | Saved | Factor | Base ms | Opt ms | OK |
|---|---:|---:|---:|---:|---:|---:|:--:|
| RTK shell-output filter: ps aux | 45459 | 1408 | 96.9% | 32.29x | 45 | 58 | ✅ |
| Tilth smart file read: README outline | 5172 | 683 | 86.8% | 7.57x | 0 | 4 | ✅ |
| context-mode FTS retrieval: search not full-file | 5172 | 474 | 90.8% | 10.91x | 0 | 56 | ✅ |
| Web prefilter: curl HTML vs hyperfetch markdown | 139 | 207 | -48.9% | 0.67x | 126 | 2191 | ✅ |
| MCP schema slimming: verbose tools vs on-demand refs | 5649 | 577 | 89.8% | 9.79x | 0 | 0 | ✅ |
| Headroom availability: agent-90 profile render | 121 | 121 | 0.0% | 1.0x | 0 | 141 | ✅ |

## Notes

- **RTK shell-output filter: ps aux**: Compares raw process table against rtk-filtered output.
- **Tilth smart file read: README outline**: Compares full README.md with Tilth budgeted structural view.
- **context-mode FTS retrieval: search not full-file**: Indexes README once, then retrieves only the three relevant chunks.
- **Web prefilter: curl HTML vs hyperfetch markdown**: Compares raw HTML fetch with markdown/extracted fetch path.
- **MCP schema slimming: verbose tools vs on-demand refs**: Static deterministic proxy for StackOne/Atlassian-style tool schema compaction.
- **Headroom availability: agent-90 profile render**: Local config check only; real token savings require proxy-routed Claude/Codex traffic.
