# Tilth vs Gmax local retrieval — 2026-07-27

Measured with real installed CLIs on the already-indexed repository.
Gmax receives no `--sync`; index/update cost is intentionally excluded and must be run explicitly.
`/usr/bin/time -lp` block I/O is OS-reported; visible tokens are UTF-8 bytes/4 proxy, not provider billing.
First = first request in this run; warm median = repetitions 2..n. It is a daemon-cold measurement only when no Gmax daemon was running beforehand.
Gmax background: 0 process(es) before, 5 after; post-run RSS sum 2,773,328 KiB.

| Probe | Accepted | First wall | Warm median | Visible tokens~ | Peak RSS (median) | Block R/W (median) | Gmax-state mutations |
|---|:--:|---:|---:|---:|---:|---:|---:|
| symbol_neighborhood_tilth | yes | 65 ms | 27 ms | 475 | 4,047,304 B | 0/0 | 0/3 |
| symbol_neighborhood_gmax | yes | 546 ms | 372 ms | 395 | 110,211,672 B | 0/0 | 0/3 |
| natural_language_tilth | no | 15 ms | 13 ms | 191 | 2,818,384 B | 0/0 | 0/3 |
| natural_language_gmax | yes | 4559 ms | 3807 ms | 113 | 90,385,208 B | 0/0 | 3/3 |

## Interpretation rule

- Gmax wins only for natural-language semantic recall or its prebuilt call graph; it is not a cheaper Tilth replacement.
- Tilth wins for bounded symbol/file structure when a persistent daemon/index is not justified.
- A non-empty Gmax-state mutation list is a real tool-side write signal even when macOS reports zero block output operations (writes may be buffered or page-cached).
- Do not replace Lean Codex's safe, scope-gated Tilth MCP with Gmax MCP based on this CLI-only benchmark. Gmax stays explicit CLI/on-demand.
