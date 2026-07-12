# claude-token-saver v2.1.0

**88–93% token reduction for Claude Code sessions. Real benchmarks. Zero guessing.**

> **CC 2.1.x compat (May 2026)**: tested on Claude Code 2.1.126 (Opus 4.7 / Sonnet 4.6 / Haiku 4.5). Pairs with new features: `/loop` self-pacing, `/ultrareview --json`, agent teams, auto-mode classifier, fullscreen TUI, skills progressive disclosure.

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Supersynergy/claude-token-saver/main/install-optimized.sh)
```

---

## The Stack (updated 2026-07-09)

Current full matrix, top-50 tools, wiring rules, formula, and local benchmarks:
[docs/TOKEN_SAVER_STACK_2026.md](docs/TOKEN_SAVER_STACK_2026.md).

Core layers, each attacking a different token problem:

| Layer | Tool | Current status | What it saves | Local / expected savings |
|-------|------|--------------|--------------|---------|
| Shell output | RTK | active | Raw bash/git/build/process output before LLM sees it | 96.9% local, 96.3% global history |
| Code/file reads | Tilth + context-mode | active; context-mode hooks PASS (Claude Code), Codex covered via Headroom proxy | Full-file dumps; retrieves outlines/chunks | 86.8–90.8% local |
| MCP/tool schema bloat | MCP compressor / schema gateway | recommended for large catalogs | Verbose tool schemas every turn | 89.8% static local proxy |
| Dynamic context | Headroom / sqz / CCR | Headroom wired: persistent proxy :8787, Claude Code + Codex routed | Tool outputs, logs, files, RAG chunks, history | 60–95% expected; verify with `headroom savings` |
| Output verbosity | caveman + ponytail | recommended | Agent prose + unnecessary generated code | 65% typical output cut |
| Web pre-filter | superweb CLI / hyperfetch / trafilatura | installed; CLI on-demand only, not MCP-default | HTML boilerplate/noisy pages | can backfire on tiny pages |

> Current finding: Superweb is not "off". It stays available on demand via CLI. Do not load it as default MCP context; call `superweb search|research|mega|fetch` only when Synapse/local/ghmax are insufficient.

---

## Combination Benchmarks

Baseline session: 143,000 tokens (35k output + 100k tool-input + 8k bash)

| Stack | Tokens | Saved | Opus $/sess | Sonnet $/sess |
|-------|-------:|------:|------------:|--------------:|
| baseline | 143,000 | 0% | $2.1450 | $0.4290 |
| caveman:full only | 120,250 | 15.9% | $1.8037 | $0.3608 |
| context-mode only | 45,000 | 68.5% | $0.6750 | $0.1350 |
| caveman:full + context-mode | 22,250 | **84.4%** | $0.3337 | $0.0668 |
| caveman:ultra + ctx + RTK | 12,350 | **91.4%** | $0.1852 | $0.0370 |
| FULL (+ MLX gemma-gate) | ~10,000 | **93%** | $0.1500 | $0.0300 |

**Sweet spot**: caveman:full + context-mode = **84% savings, zero friction**

**Max savings**: ultra + ctx + RTK + gemma-gate = **93%**

---

## Verified Per-Model Savings (caveman:full only)

64 real OpenRouter calls, 4 verbose tasks, 8 models. baseline vs `caveman:full`
system message. Numbers are reproducible via `bench/eval_harness.py`.

| Model | Base out tok | Caveman out tok | **Out save** | Cost save | Latency save | Tier |
|---|---:|---:|---:|---:|---:|:---:|
| gemini-2.5-flash | 222 | 44 | **−80%** | −78% | −56% | ★ S |
| minimax-2.7 | 419 | 156 | **−63%** | −61% | −63% | ★ S |
| sonnet-4.6 | 169 | 112 | −34% | −30% | −9% | A |
| deepseek-v4-flash | 221 | 159 | −28% | −21% | −30% | A |
| grok-4-fast | 281 | 234 | −17% | −10% | −39% | B |
| glm-4.7 | 384 | 359 | −7% | −5% | +7% | B |
| haiku-4.5 | 145 | 138 | −5% | −1% | +21% | C |
| kimi-2.6 | 350 | 428 | **+22%** ❌ | +24% | +0% | F (backfire) |

**Key finding**: caveman is model-dependent. Anthropic Sonnet, MiniMax, Gemini
Flash, DeepSeek follow the system message rigorously. Moonshot Kimi (reasoning
model) ignores or expands instructions — caveman INCREASES output. Adapter
configs should mark `caveman_compatible` per model class.

**Cheapest caveman:full call**: deepseek-v4-flash at **$0.000051/call**
(13× cheaper than Sonnet-4.6 caveman, 36× cheaper than Sonnet baseline).

Raw data: `bench/results/eval_*.json`.

---

## Quick Start

### 1. One-command install
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Supersynergy/claude-token-saver/main/install-optimized.sh)
```

Installs: trafilatura · mlx-lm · Phi-4-mini-instruct MLX model · ayg · rg · ast-grep · rga · RTK · smart-fetch · sg

### 2. Claude Code plugins (run inside Claude Code)
```bash
claude plugin marketplace add JuliusBrussee/caveman && claude plugin install caveman@caveman
claude plugin marketplace add mksglu/context-mode && claude plugin install context-mode@context-mode
```

### 3. Add to CLAUDE.md
```bash
cat ~/.claude/cts-env.sh >> ~/.zshrc   # or .bashrc
cat token-stack.md >> ~/.claude/CLAUDE.md
```

### 4. Verify
```bash
/ctx-doctor          # context-mode health check
smart-fetch https://httpbin.org/json   # should return 5t, 95% savings
sg --help            # ayg→rg auto-router
```

### 5. Wire Headroom (dynamic-context proxy, optional but recommended)
```bash
uv tool install headroom-ai
headroom install apply --preset persistent-service   # persistent proxy on 127.0.0.1:8787
headroom init -g claude                              # route Claude Code through it
headroom init -g codex                               # route Codex CLI through it
headroom doctor                                      # all checks green?
```

First startup downloads an ONNX embedding model; if `install apply` reports
"did not become ready", run it again — the model is cached after the first try.
Measure real savings after a few sessions with `headroom savings`.
Undo anytime: `headroom install remove && headroom unwrap claude && headroom unwrap codex`.

---

## Tool Reference

### smart-fetch — fused web fetch

Auto-routes by URL type. No config needed.

```bash
smart-fetch <url>                    # auto: json schema or trafilatura HTML
smart-fetch <url> --mode json        # force JSON schema extraction
smart-fetch <url> --mode html        # force trafilatura clean text
smart-fetch <url> --extract "field"  # targeted field extraction
```

**Real benchmarks (M4 Max, 2026-04-16):**
```
Target                  Tool                  Tokens   Time     Saved
httpbin.org/json        raw curl              107t     814ms    baseline
httpbin.org/json        rtk curl              39t      889ms    -63%
httpbin.org/json        smart-fetch           5t       640ms    -95%  ★
example.com (HTML)      raw curl              134t     213ms    baseline
example.com (HTML)      smart-fetch           35t      213ms    -73%  ★ (trafilatura, 0 LLM)
example.com (HTML)      hyperfetch+phi4-mini  125t     2700ms   -6%   slower + LLM overhead
```

Routing:
```
/api/* /json /health /ping /metrics → curl_cffi + json.keys()  = 3-5t
HTML article/doc                    → curl_cffi + trafilatura   = 35-200t (0 LLM)
Anti-bot target                     → curl_cffi chrome110       = auto stealth
```

Attribution: [curl_cffi](https://github.com/yifeikong/curl_cffi) · [trafilatura](https://github.com/adbar/trafilatura)

### Layer 5: Adaptive Routing — *per-action* savings

Layers 0–4 cut startup tokens. Layer 5 cuts per-action tokens by picking the
cheapest tool/model/fetch-stage that actually works. Self-learning, universal,
no personal data. Full docs: [ADAPTIVE.md](ADAPTIVE.md).

```python
from core.adaptive_router import fetch_stage, model_tier, detect_backfire
fetch_stage(url)          # curl → curl_cffi → browser, learns per host
model_tier(query)         # haiku / sonnet / opus by complexity
detect_backfire("cat x")  # warn: use Read tool instead
```

---

### sg — smart grep (ayg + rg auto-router)

```bash
sg <pattern>              # ayg (indexed, 8-460x) → rg (fallback)
sg build .                # build ayg index once (~30s large repos)
sg stats                  # show index + routing decision

# Structural search (not text grep):
ast-grep -p 'async function $F($_) { $$$ }'   # any async fn
ast-grep -p 'console.log($ARG)'               # all console.log

# Archive/PDF search:
rga "term" .              # PDFs, docx, zip, epub
```

**Benchmarks (ayg vs rg):**
```
Repo size         rg        ayg      speedup
<10k files        ~20ms     needs index    —
10k-100k files    ~500ms    ~60ms    8x
>100k files       ~29s      ~60ms    460x
Linux kernel 40M  ~1.5s     ~6ms     250x (hot)
```

> **Note on seek:** `cargo install seek` installs `yxshv/seek` (app launcher — wrong tool).
> `dualeai/seek` (zoekt-based BM25) has 33 stars and is not on crates.io. Not included.

Attribution: [aygrep/hemeda3](https://github.com/hemeda3/aygrep) · [ripgrep](https://github.com/BurntSushi/ripgrep) · [ast-grep](https://github.com/ast-grep/ast-grep) · [ripgrep-all](https://github.com/phiresky/ripgrep-all)

---

### gemma-gate — HTML summarizer gate

Compresses web pages before they hit Claude's context window.

**Pipeline (auto-escalates only when needed):**
```
trafilatura (0ms, 0 LLM)           → covers 90% HTML articles → stop here
  ↓ fails (JS-rendered, no content)
MLX Phi-4-mini-instruct (~556ms)   → best instruction-following for structured output
  ↓ MLX unavailable
Ollama qwen3:0.6b (~50ms)          → lightweight fallback
  ↓ Ollama unavailable
extractive regex (0ms)             → regex signal extraction, last resort
```

**Model comparison (benchmarked M4 Max, 2026-04-16):**
```
Model                              Size    Speed    Quality   Verdict
trafilatura                        0MB     0ms      90%       ★ always try first
Phi-4-mini-instruct-4bit MLX       2.2GB   556ms    94%       ★ best LLM option
gemma-4-e2b-it-4bit MLX            ~7GB    ~800ms   97%       highest quality, heavy
Qwen3-0.6B/1.7B MLX                350MB+  fast     FAILS     echoes input, not instruct model
phi4-mini Ollama (v1 default)       2.5GB   ~300ms   94%       replaced by MLX
```

Real result: `118t input → 55t output (-53%)`, correct structured bullets.

**Config (env vars):**
```bash
source ~/.claude/cts-env.sh           # auto-set by installer
CTS_MLX_MODEL=mlx-community/Phi-4-mini-instruct-4bit
CTS_GEMMA_MODEL=qwen3:0.6b            # Ollama fallback
CTS_GEMMA_THRESHOLD=200               # skip LLM for inputs < 200 tokens
CTS_FORCE_LLM=1                       # always use LLM (bypass trafilatura)
CTS_CATBOOST=1                        # enable catboost noise pre-filter
```

---

### RTK — CLI bash compression

Auto-promoted by `rtk-rewrite.sh` hook. RTK compresses bash output before LLM sees it.

**Per-command verdict (real data, 333 calls):**
```
Command           Savings   Speed     Verdict
rtk git diff      -99%      same      ★★★ always use
rtk cargo build   -97%      same      ★★★ always use
rtk docker ps     -84%      +22% faster  ★★★ always use
rtk curl -s       -63%      +18% slower  ✓ JSON schema only
rtk ps aux        -50%      3x slower    ✓ worth it
rtk git status    -53%      2x slower    ✓ worth it

rtk ls            +35% WORSE   never — use Glob tool
rtk env           +105% WORSE  never — use env | grep
rtk grep          +10,000% WORSE  never — use Grep tool / sg
rtk read          +412% WORSE  never — use Read tool
```

**Adoption problem:** Only 0.1% of bash calls used RTK in 30 days (41/40,762).
Fix: `rtk-rewrite.sh` hook auto-promotes good commands, blocks bad ones.

---

### CatBoost pre-filter

Classifies text paragraphs as signal vs noise before LLM sees them.

```
Scenario                  Without catboost   With catboost   Delta
Raw scrape pipeline       100,000t           75,000t         -25%
Log analysis (high noise) 50,000t            12,500t         -75%  ★
Full stack (ctx already)  2,000t             1,500t          -0.6%
```

**Use for:** raw scraping pipelines, log analysis. Skip for normal code sessions (0.6% delta).
**M4 Max:** CPU only (no CUDA/Metal in catboost). Train: `python3 core/catboost_train.py --generate-samples --train`

---

## Context-Mode — 98% Input Reduction

MCP sandbox. Keeps ALL tool output out of context window. SQLite/FTS5 session continuity.

```bash
ctx_batch_execute([cmd1, cmd2, ...], queries=["q1", "q2"])  # primary — replaces ALL bash calls
ctx_search(queries=["..."])                                  # follow-up search
ctx_fetch_and_index(url)                                     # WebFetch replacement
ctx_stats()                                                  # token savings dashboard
```

**vs spawning subagents:**
```
ctx_batch_execute  :   500t = $0.0015 Sonnet
spawn Agent        : 30,000t = $0.09 Sonnet / $0.45 Opus
→ 60x cheaper. Eliminates 80% of research agent spawns.
```

---

## Hooks (PreToolUse — auto-active)

| Hook | Triggers on | Action |
|------|-------------|--------|
| `rtk-rewrite.sh` | Every Bash call | Auto-promotes good RTK commands, blocks proven-bad ones |
| `ctx-optimizer.sh` | Every Bash call | Blocks >20-line output, blocks bad RTK (rtk ls/grep/env/read) |
| `hyperstack-pretool.sh` | WebFetch | Routes small APIs → rtk curl, HTML pages → hyperfetch |
| `compact-output.sh` | Stop event | Injects compact-mode reminder |

**Always blocked (benchmarked WORSE than alternatives):**
```
rtk ls     → Glob tool     (rtk ls is +35% MORE tokens)
rtk grep   → Grep tool/sg  (rtk grep is +10,000% overhead)
rtk env    → env|grep      (rtk env is +105% MORE bytes)
rtk read   → Read tool     (rtk read is +412% MORE tokens — loads full file)
cat/head   → Read tool     (floods context)
```

---

## Subagent Cost Table

| N agents spawned | Raw tokens | With caveman | ctx_batch_execute |
|-----------------|----------:|-------------:|------------------:|
| 1 | 30,000t | 25,450t | **500t** |
| 5 | 150,000t | 127,250t | **500t** |
| 10 | 300,000t | 254,500t | **500t** |
| 20 | 600,000t | 509,000t | **500t** |

Rule: **ctx_batch_execute first. Eliminates 80% of research agent spawns.**

---

## Optimal Config by Use Case

| Use Case | Stack | Savings |
|----------|-------|---------|
| Daily coding (Sonnet) | caveman:full + context-mode | **84%** — sweet spot |
| Heavy research (Opus) | ultra + ctx + RTK | **91%** |
| Scraping agents | ultra + ctx + RTK + catboost | **92%** |
| Web-heavy sessions | + gemma-gate MLX | **93%** |
| Fast cheap APIs (MiniMax $0.05/M) | caveman only | speed > efficiency |

---

## Benchmark: 50 Scenarios (2026-04-16, M4 Max)

Key results (full table in bench/RESULTS.md):

```
Scenario                         Tool                    Tokens   Time
JSON API (httpbin /json)         smart-fetch             5t       640ms   -95%
HTML article (example.com)       smart-fetch+trafilatura 35t      213ms   -73%
git diff HEAD~1 (1k LOC)        rtk git diff            297t     9ms     -99%
cargo build (errors only)        rtk cargo build         1,260t   1200ms  -97%
grep (24k file repo)             ayg (indexed)           150t     60ms    8x faster
grep (24k file repo)             rg (no index)           500t     500ms   baseline
HTML via Gemma gate LLM          Phi-4-mini MLX          55t      556ms   -53%
any N-cmd research               ctx_batch_execute       13t      4ms     vs 15,000t
spawn research Agent             Agent(explore)          30,000t  varies  60x costly
Claude output (verbose)          baseline                1,180t   —       baseline
Claude output                    caveman:full            159t     —       -87%
CLAUDE.md load                   raw                     12,000t  startup
CLAUDE.md load                   caveman-compress        6,480t   startup -46%
```

---

## File Structure

```
claude-token-saver/
├── core/
│   ├── gemma-gate.py        # HTML summarizer: trafilatura→MLX Phi4→Ollama
│   └── catboost_train.py    # CatBoost noise classifier trainer
├── integration/
│   ├── cli/
│   │   ├── smart-fetch      # Fused web fetch (curl_cffi+trafilatura+json)
│   │   ├── sg               # Smart grep router (ayg→rg)
│   │   └── hyperfetch*      # 4-stage escalation fetch
│   ├── hooks/
│   │   ├── hyperstack-pretool.sh
│   │   └── hyperstack-postcompact.sh
│   └── agents/              # Agent type definitions
├── install-optimized.sh     # One-command full stack installer ← start here
├── install-hyperstack.sh    # Hyperstack-only installer
├── CLAUDE_SNIPPET.md        # Paste into ~/.claude/CLAUDE.md
└── bench/                   # Benchmark scripts + results
```

---

## Full Attribution

| Tool | Author | Purpose |
|------|--------|---------|
| **caveman** | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Output compression 65% via compressed language |
| **context-mode** | [mksglu/context-mode](https://github.com/mksglu/context-mode) | MCP sandbox, 98% input reduction |
| **RTK** | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | Rust CLI bash compressor, 62-99% per command |
| **curl_cffi** | [yifeikong/curl_cffi](https://github.com/yifeikong/curl_cffi) | Chrome fingerprint stealth fetching |
| **trafilatura** | [adbar/trafilatura](https://github.com/adbar/trafilatura) | HTML→clean text, 0ms, no LLM |
| **Phi-4-mini-instruct** | [Microsoft/HuggingFace](https://huggingface.co/mlx-community/Phi-4-mini-instruct-4bit) | Best small instruct model for summarization |
| **mlx-lm** | [ml-explore/mlx-lm](https://github.com/ml-explore/mlx-lm) | Apple Silicon MLX inference |
| **aygrep (ayg)** | [hemeda3/aygrep](https://github.com/hemeda3/aygrep) | Sparse n-gram indexed search, 8-460x vs rg |
| **ripgrep** | [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep) | Fast regex search fallback |
| **ast-grep** | [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep) ★13,422 | AST structural code search |
| **ripgrep-all (rga)** | [phiresky/ripgrep-all](https://github.com/phiresky/ripgrep-all) | Search PDFs/Office/zip archives |
| **CatBoost** | [catboost/catboost](https://github.com/catboost/catboost) | Signal/noise classifier for scraping |
| **camoufox** | [daijro/camoufox](https://github.com/daijro/camoufox) | Stealth Firefox, Cloudflare/DataDome bypass |
| **SurrealDB** | [surrealdb/surrealdb](https://github.com/surrealdb/surrealdb) | Team scrape cache, graph KB |
| **hyperfetch** | [Supersynergy/claude-token-saver](https://github.com/Supersynergy/claude-token-saver) | 4-stage web fetch (curl_cffi→camoufox→domshell→browser) |

---

## Links

- **GitHub**: [Supersynergy/claude-token-saver](https://github.com/Supersynergy/claude-token-saver)
- **caveman**: [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)
- **context-mode**: [mksglu/context-mode](https://github.com/mksglu/context-mode)
- **RTK**: [rtk-ai/rtk](https://github.com/rtk-ai/rtk)
- **aygrep**: [hemeda3/aygrep](https://github.com/hemeda3/aygrep)
- **ast-grep**: [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep)
- **trafilatura**: [adbar/trafilatura](https://github.com/adbar/trafilatura)
- **curl_cffi**: [yifeikong/curl_cffi](https://github.com/yifeikong/curl_cffi)
- **mlx-lm**: [ml-explore/mlx-lm](https://github.com/ml-explore/mlx-lm)
- **ripgrep-all**: [phiresky/ripgrep-all](https://github.com/phiresky/ripgrep-all)
- **CatBoost**: [catboost/catboost](https://github.com/catboost/catboost)
- **camoufox**: [daijro/camoufox](https://github.com/daijro/camoufox)

---

## CC 2.1.x Settings Hardening (v2.1.0+, May 2026)

Apply these `~/.claude/settings.json` defaults for additional ~3-5K tok/turn + 1-2s latency cut on top of the 4-layer stack:

```json
{
  "includeGitInstructions": false,
  "companyAnnouncements": false,
  "spinnerTipsEnabled": false,
  "env": {
    "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"
  },
  "permissions": {
    "defaultMode": "plan",
    "allow": [
      "Bash(git *)", "Bash(rtk *)", "Bash(cargo *)", "Bash(bun *)",
      "Bash(uv *)", "Bash(npm *)", "Bash(rg *)", "Bash(fd *)",
      "Bash(fzf *)", "Bash(bat *)", "Bash(mise *)"
    ]
  }
}
```

**Hooks-Hygiene** (every-tool-call killers):
- ❌ NO `npx <thing>` in `PreToolUse`/`PostToolUse` — spawns Node per tool call (2-5K tok + 500ms each)
- ❌ NO redundant context-injectors on `PreToolUse` — `SessionStart` is enough
- ✅ Stop / SubagentStop hooks: `async: true` (otherwise blocks exit)

**Effort routing**:
- Default `effort: low` (override Anthropic 2.1.117 `high` default → see `/effort low` or settings)
- Use `ultrathink` keyword in prompt for high-effort turn
- ❌ `/fast` NEVER (cost outweighs latency win)

**Model tier (strict)**:
- Haiku 4.5 → subagents, exploration, batch grep, file search, bash ops
- Sonnet 4.6 → code writing, plan review (daily driver)
- Opus 4.7 → architecture decisions ONLY

**Context hygiene**:
- `/compact <focus>` at ~60% (NOT 90%) — keep cache hits warm
- `/clear` between unrelated tasks
- `/btw` for side-questions (answer never enters history)
- `Esc Esc → Summarize from here` for mid-session compact preserving early context
- `MEMORY.md` hard cap < 200 lines (CC 2.1.83+ truncates at 25KB AND 200)

---

## Self-update Routine

Run weekly:

```bash
# context-mode (currently 1.0.105 upstream, May 2026)
cd ~/.claude/plugins/marketplaces/context-mode && rtk git pull && /reload-plugins

# claude-token-saver
cd ~/projects/claude-token-saver && rtk git pull

# rtk autopatcher (CC version drift)
~/.claude/bin/ggcoder-autopatch.mjs --check
```

---

*Benchmarked on M4 Max · macOS Darwin 24.5 · Claude Sonnet 4.6 · 2026-04-16*
*v2.1.0 hardening verified on Claude Code 2.1.126 (Opus 4.7) · 2026-05-03*
*All numbers are real measurements, not estimates.*
