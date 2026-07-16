# External token-stack candidate matrix — 2026-07-15

All executable candidates were pinned to releases older than 14 days, run in
an isolated temporary `HOME`, and checked against accepted output. GitHub stars
are a discovery snapshot, not a quality score. Schema and transport comparisons
use bytes as the lossless denominator; the provider ledger remains the token oracle.

Machine-readable results:

- [external-stack-matrix-2026-07-15.json](external-stack-matrix-2026-07-15.json)
- [external-candidate-gate-2026-07-15.json](external-candidate-gate-2026-07-15.json)
- [external-candidate-gate-2026-07-15.md](external-candidate-gate-2026-07-15.md)

## Candidate snapshot

| Candidate | Snapshot stars | Pin | Role tested |
|---|---:|---|---|
| [CodeBurn](https://github.com/getagentseal/codeburn) | 8,667 | `mac-v0.9.14` | usage audit, optimizer, MCP |
| [Tokscale](https://github.com/junhoyeo/tokscale) | 4,468 | `v4.0.6` | usage audit |
| [Microsoft APM](https://github.com/microsoft/apm) | 3,245 | `v0.23.1` | agent-package portability |
| [acpx](https://github.com/openclaw/acpx) | 2,975 | `v0.11.0` | ACP agent transport |
| [cachebro](https://github.com/glommer/cachebro) | 213 | `v0.2.2` | repeated file cache/diff |
| [Splitrail](https://github.com/Piebald-AI/splitrail) | 210 | `v3.5.8` | usage audit, MCP |
| [Honey](https://github.com/Green-PT/honey-for-devs) | 165 | `v1.1.0` | prompt/handoff compression |
| [aiusage](https://github.com/juliantanx/aiusage) | 106 | `v1.5.7` | usage audit |
| [mcp-compressor](https://github.com/atlassian-labs/mcp-compressor) | 97 | `v0.31.2` | progressive MCP schemas |
| [mcpx](https://github.com/evantahler/mcpx) | 32 | `v0.22.2` | MCP CLI/discovery |
| [mcpc](https://github.com/apify/mcpc) | — | `v0.4.0` | persistent MCP CLI |

`ghmax --repos` was the discovery path. Exact repository metadata and release
dates were then confirmed against GitHub's repository/release API.

## Usage-auditor gate

Fixture: three completed Codex sessions, 1,812,281 bytes. Canonical ATS totals:
7,768,418 input, 7,169,024 cached subset, 599,394 uncached, 76,884 output and
30,986 reasoning tokens.

| Tool | Exact canonical fields | Cold | Warm median | Peak RSS point sample | Decision |
|---|:---:|---:|---:|---:|---|
| ATS ledger | yes | — | 113.4 ms | 27.7 MiB | canonical team/guard truth |
| Splitrail | yes | 12.3 ms | 10.7 ms | 15.4 MiB | optional fastest global audit |
| Tokscale | yes | 2,378 ms | 49.9 ms | 31.2 MiB | optional session/model cross-check |
| CodeBurn | yes, except reasoning unsupported | 424.1 ms | 265.3 ms | 111.1 MiB | optional read-only optimizer |
| aiusage raw export through ATS normalizer | yes | — | — | 86.0 MiB | normalized export only |

The native `aiusage summary` reported 15,045,312 tokens. It added cached and
thinking fields to an input field that already contained them; the comparable
provider total was 7,845,302. The ATS adapter repairs the raw export but never
trusts that native total.

CodeBurn's optimizer reported 43.2% possible savings, almost entirely from one
high-cost-session outlier. That remains a hypothesis; it is not added to ATS's
savings claims.

## MCP, cache and schema combinations

| Combination | Measured result | Decision |
|---|---|---|
| `mcpc + cachebro`, unchanged 19.6-kB file | 20,831 → 361 bytes, **98.27% less** | mechanism works; reject default because bridge+server held 212.5 MiB and close left the server orphaned |
| `mcpc + cachebro`, one-line change | 20,831 → 633 bytes, **96.96% less** | useful diff behavior; same runtime rejection |
| `mcpx + cachebro` | 20,896 → 20,896 bytes; ~2.2 s per call | reject: per-call server restart loses cache state |
| `mcp-compressor high + cachebro` | 3,234-byte surface → 1,294; selected schema adds 1,696; net **7.54%** | reject for a four-tool server |
| `mcp-compressor high + Tilth` | 9,540-byte surface → 1,549; search+read total 6,246, **34.53% less** | workload-gated; all six schemas total 11,468, **20.21% more** |
| `mcpx` keyword index + Tilth | 8.1-s/170-MiB build; 70-ms/58.8-MiB query | optional only for broad MCP catalogs |
| `mcpx` semantic search + Tilth | 620 ms and 785.2 MiB; same top three as keyword | reject default |
| CodeBurn MCP | 1,202-byte, two-tool surface | CLI is cheaper; do not keep hot |
| Splitrail MCP | 1,564-byte, six-tool surface | CLI is cheaper; do not keep hot |

The compressor source build itself took 140.2 seconds and peaked at 1,327 MiB.
Tag `v0.31.2` produced a binary reporting `0.1.0`; this packaging mismatch is
another reason not to promote it into the default profile.

## Agent transport and team combinations

The acpx benchmark used its deterministic ACP mock because the built-in Codex
adapter resolves through an unlocked `npx ...@^0.0.44` chain. No provider-agent
claim is made from the mock.

| acpx mode | Output | Runtime/resource result | Decision |
|---|---:|---|---|
| one-shot JSON | 1,013 bytes | 139.3-ms median; 94.8-MiB peak RSS | structured diagnostics only |
| one-shot text | 85 bytes | 134.7-ms median | human terminal |
| one-shot quiet | 6 bytes | 150.6-ms median | **use for agent-to-agent return**; 99.41% smaller than JSON |
| persistent mock session | 8-byte returns | 1.26/1.09 s; 173.5 MiB resident | reject default |

The existing real Codex team benchmark still controls spawning: one minimal
agent used 64,245 input tokens; two workers used 87,475 (**36.2% more**) for
only 2.2 seconds saved. ACP changes transport structure, not model bootstrap cost.

## Packaging and prompt layers

- Microsoft APM initialized in 0.67 seconds/59.2 MiB and dry-run compiled in
  0.35 seconds/54.9 MiB. It adds manifest/lock portability, not runtime token
  reduction. ATS keeps its existing canonical Superskills routing.
- Honey `v1.1.0` was 12 days old on the benchmark date, so its code was not
  executed under the 14-day gate. Its useful idea—lossless compact handoffs—was
  tested independently: ATS ledger JSON shrank 4,097 → 3,185 bytes (**22.26%**)
  with identical decoded data. This became `--format json-compact` without a dependency.
- Avelino MCP was rejected during bootstrap because a version command attempted
  an unpinned ChronDB download. No further combinations were allowed.

## Integrated result

1. `agent-token-audit` runs explicit auditors in an isolated temporary home,
   strips inherited credentials, records their reported version, normalizes
   their exports and fails when canonical token fields differ.
2. Splitrail, Tokscale and CodeBurn are optional adapters. The ATS ledger stays
   authoritative for parent/worker completeness and context guards.
3. `agent-token-ledger --format json-compact` is the lossless machine/handoff path.
4. No new MCP, daemon, semantic model, ACP session or automatic worker enters
   Minimal, Lean, Teams or Heavy by default.

Reproduce with installed, exact-version candidate commands:

```bash
agent-token-audit \
  --usage parent=/path/to/parent.jsonl \
  --usage child=/path/to/child.jsonl \
  --candidate splitrail=/path/to/splitrail-v3.5.8 \
  --candidate 'tokscale=bunx --bun tokscale@4.0.6' \
  --candidate codeburn=/path/to/codeburn-mac-v0.9.14 \
  --runs 5 \
  --json-out candidate-gate.json \
  --markdown-out candidate-gate.md
```

The gate never installs or upgrades those tools itself. Package runners such as
`bunx`/`npx` are accepted only with an exact version and `@latest` is rejected;
direct binary paths remain caller-pinned. The temporary home and scrubbed
environment are not an OS or network sandbox.
