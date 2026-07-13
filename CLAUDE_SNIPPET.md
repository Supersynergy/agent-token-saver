# Token Optimization Stack — CLAUDE.md Addon

> Add this to ~/.claude/CLAUDE.md — auto-loaded every session.
> Source: https://github.com/Supersynergy/agent-token-saver
> Install: curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver/main/install-universal.sh | bash -s -- --profile lean --agent claude

## Tool Routing (fastest → lowest tokens)

### Web Fetch
| Target | Tool | Tokens | Time |
|--------|------|--------|------|
| Small API (`/json` `/health` `/api/*`) | `rtk curl -s <url>` | 39t | 890ms |
| HTML article/doc | `smart-fetch <url>` | ~35t | 200ms |
| Anti-bot / Cloudflare | `hyperfetch --stage camoufox <url>` | ~153t | 3.3s |
| Specific fact | `hyperfetch --extract "term" <url>` | 5-12t | 3.2s |
| Multiple URLs | `ctx_fetch_and_index` | 50t/url | varies |

### Code Search (sg auto-routes: seek → ayg → rg)
```bash
sg <pattern>                  # BM25 ranked, 638x faster than rg on large repos
sg sym:ClassName              # symbol search via seek
ast-grep -p 'async $F($_)'    # structural AST search (syntax-aware)
rga "term"                    # search PDFs/Office/zip archives
```

### Context Protection (ALWAYS)
- 2+ commands → `ctx_batch_execute` (ONE call, 98% reduction vs multiple Bash)
- WebFetch → `ctx_fetch_and_index` (not raw WebFetch)
- Follow-up search → `ctx_search`

### Research (NEVER spawn subagents for this)
`ctx_batch_execute` = 500t. Research Agent spawn = 30,000t. **60x cheaper.**

## Anti-patterns (hooks block these automatically)
| Command | Problem | Use instead |
|---------|---------|-------------|
| `rtk ls` | +35% MORE tokens | Glob tool |
| `rtk grep` | +10,000% overhead | Grep tool / `sg` |
| `rtk env` | +105% MORE bytes | `env \| grep PATTERN` |
| `rtk read` | +412% MORE tokens | Read tool |
| `cat file.py` via Bash | floods context | Read tool |
| spawn Agent for research | 30,000t overhead | `ctx_batch_execute` |

## Output Mode
- `caveman:full` → 65% output savings (automatic via SessionStart hook)
- `caveman:ultra` → 75% (non-critical tasks)
- `stop caveman` → normal prose

## Cost Reference (Sonnet $3/M · Opus $15/M)
```
ctx_batch_execute  :    500t = $0.0015/call Sonnet
spawn Agent        : 30,000t = $0.09 Sonnet / $0.45 Opus
caveman:full       : 12,250t output (vs 35,000t baseline) = -65%
full stack session :  4,000t (vs 143,000t baseline)       = -97%
```

## Gemma Gate (HTML→compact text before Claude sees it)
Pipeline: trafilatura(0ms) → MLX Qwen3/Phi4(~15-35ms) → Ollama qwen3:0.6b(~50ms)
Config: `source ~/.claude/cts-env.sh`
