# CLI-first policy

CLI-first means: keep data and tools outside the prompt until a task needs
them.  It does **not** mean disable useful integrations or route every request
through a compressor.

## Runtime tiers

| Tier | Starts by default | Use for | Do not use for |
|---|---|---|---|
| Lean | prompt router, RTK hook, memory/search CLIs; at most one small code MCP | normal coding and research | browser, huge repeated payloads |
| Task CLI | one command with bounded output and an artifact path | web, GitHub, code graph, batch intake | permanent tool schemas |
| Heavy session | explicitly launched extra MCPs | browser control, repeated graph queries, large payload transformation | routine tasks |
| Provider proxy | Headroom when connection/routing requires it | provider-side cache/compression/memory | MCP discovery or terminal filtering |

## Tool routing

| Need | First choice | Escalate only when |
|---|---|---|
| Existing decision or cross-session fact | `synxp` / `synx` | cached recall misses |
| Exact local text | `rg`, then a line window | structural context is needed |
| Code structure/callers | `tilth --budget …`, `codegraph` CLI | repeated interactive navigation justifies a session MCP |
| Current GitHub pattern | `ghmax` / `ghgrep` | local and cached evidence miss |
| Current web source | `superweb fetch|batch|search` into a file, then project | an interactive browser is required |
| Noisy terminal output | RTK hook or `rtk <cmd>` | raw evidence is required for audit/debug |
| Large JSON/log/article set | deterministic projection/dedupe | repeated exploration justifies context-mode |
| Browser/JS | normal browser task or explicit heavy session | never as global default |

Every CLI call should request a limit, write raw bulk data to an artifact, and
return only counts, errors, selected fields, and the artifact path to the
model.  Keep original data retrievable for audits and exact edits.

## Codex

Lean Codex is the normal `codex` invocation.  Its standard MCP surface is
Tilth only; memory, web, GitHub, Graphify, and CodeGraph tools remain CLI/on
demand.  Headroom may remain the model provider proxy.  It contributes no MCP
schema and must not be added as a second default tool server.

For a deliberate browser/deep-graph session, use `codex-heavy-context`.  That
launcher adds CodeGraph, context-mode, and node_repl for that process only.  It
is not the normal `codex` command.  Do not assume a named Codex profile imports
a separate TOML file; verify the actual launch command with `codex mcp list`.

Verification:

```bash
agent-token-saver doctor --profile lean
codex mcp list
codex-heavy-context mcp list
```

## Claude Code and hosted connectors

Claude Code can have a different MCP inventory from Codex.  Treat configured
Claude MCPs and Claude.ai connectors as user-owned integrations: audit them,
then remove or scope them one by one only after their workflow is known.  Do
not delete a provider connection merely to make a schema count look better.

For a controlled minimal Claude run, current CLI supports `--bare`: it skips
hooks, plugin sync, auto-memory, automatic MCP loading, and CLAUDE.md discovery.
It also requires explicit credentials and explicit context/MCP configuration,
so it is an automation/debug mode rather than a replacement for normal OAuth
sessions.  `--safe-mode` is the configuration-failure recovery mode, not a
performance switch.  Use `claude mcp list` before deciding what to scope or
remove.

## Headroom versus the other token savers

Headroom sits between the agent and model provider.  It can cache, compress or
route provider traffic and preserve local memories; therefore it can change
connection behavior, latency, and provider features.  Keep it when that route
is required and evaluate it with `headroom doctor` plus `headroom savings`.

The other layers solve different, lower-risk problems before provider traffic
exists:

| Layer | What it prevents |
|---|---|
| Skill router | entire irrelevant skill catalog entering the prompt |
| RTK | verbose shell/build/test output entering the prompt |
| Synapse/`rg`/Tilth | whole files and repeated research entering the prompt |
| Superweb/GHMax CLI | web/GitHub response and tool schema always loading |
| Headroom | remaining large provider messages and repeated traffic |

The practical order is prevention first, reversible projection second,
provider compression last.  A high percentage from one layer is not an
end-to-end guarantee; retain a layer only when the same accepted task keeps
quality and lowers total tokens or quota use.

## Change rule

1. Measure the current command/session.
2. Make one reversible routing change.
3. Re-run the same task and check result quality, latency, and token/usage data.
4. Keep the change only on a net win; otherwise restore the prior route.

Never add another always-on MCP, proxy, local model, or broad crawler only
because its marketing reports a large token percentage.
