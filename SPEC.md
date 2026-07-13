# claude-token-saver — Master Specification
# version: 2.1.0 | 2026-04-17 | author: Maxim Supersynergy
# status: active | model: claude-sonnet-4-6 | latest: claude-opus-4-7

---

## Intent

**Why this exists:**
Every Claude Code session burns tokens on verbose tool output, wrong tool choices,
and agent spawning. This project makes token-efficiency the default, not an afterthought.

**Who uses it:**
- Solo developers running Claude Code daily
- Agent teams (multi-agent orchestration systems)
- CI pipelines invoking Claude for code review / analysis

**What it solves:**
```
Problem                          Before    After    Savings
─────────────────────────────────────────────────────────
Raw Bash output                  1,500t    150t     -90%
WebFetch HTML page               450t       35t     -92%
Research (Agent spawn)          30,000t    500t     -98%
Code search (grep)               747t       15t     -98%
HTML noise in scraped data       100%       25%     -75%
```

---

## Non-Goals

- NOT a general LLM framework (no LangChain, no LlamaIndex)
- NOT a web scraper (use hyperfetch/camoufox for that)
- NOT replacing Claude Code — augmenting it
- NOT GPU-dependent (everything runs on M-series CPU)
- NOT cloud-lock — all local models work offline

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Claude Code Session                │
│                                                     │
│  UserPromptSubmit → smart-context.py (Qdrant)       │
│  PreToolUse[Bash] → ctx-optimizer.sh (block bad)    │
│  PreToolUse[Bash] → rtk-rewrite.sh (promote RTK)   │
│  PreToolUse[Web]  → hyperstack-pretool.sh (block)  │
│  Stop             → compact-output.sh (terse mode) │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                   Tool Layer                        │
│                                                     │
│  smart-fetch   → trafilatura(0ms) + curl_cffi       │
│  sg            → ayg(5ms indexed) | rg(11ms)        │
│  gemma-gate    → trafilatura → Phi-4-mini → Ollama  │
│  agent_guard   → TokenGuard (route + budget track)  │
│  RTK           → compresses Bash output 60-90%      │
│  ctx_batch     → sandboxed multi-cmd execution      │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                  Model Routing                      │
│                                                     │
│  HTML extract  → trafilatura (0ms, no LLM, 90%)    │
│  Summarize     → Phi-4-mini MLX (556ms, CPU)        │
│  Fallback      → qwen3:0.6b Ollama (50ms)           │
│  Classification→ CatBoost (20ms, CPU)               │
│  API cheap     → claude-haiku-4-5 ($0.25/1M in)    │
│  API quality   → claude-sonnet-4-6 ($3/1M in)      │
│  API max       → claude-opus-4-7 ($15/1M in) LATEST│
└─────────────────────────────────────────────────────┘
```

---

## Function Specifications

### `smart-fetch <url>`

**Intent:** Fetch any URL with minimal tokens. Auto-detects content type.

**Preconditions:**
- URL is reachable
- curl_cffi installed (`pip install curl_cffi`)
- trafilatura installed

**Postconditions:**
- JSON API → key list only (5t avg)
- HTML article → clean text via trafilatura (35t avg)
- Anti-bot page → routes to hyperfetch (153t avg)

**Token budget:** ≤ 50t for any single URL
**Failure mode:** If trafilatura returns None → return raw text truncated to 500 chars
**Benchmark:** JSON=5t/640ms | HTML=35t/200ms | Anti-bot=153t/3.3s

**Example:**
```bash
# Input
smart-fetch https://api.github.com/repos/org/repo

# Output (5 tokens)
keys: id, name, full_name, private, owner, html_url, description, stargazers_count
```

**Given/When/Then:**
```
Given: URL is a JSON API endpoint
When:  smart-fetch is called
Then:  output is key list only, ≤10t, <1s
```

---

### `sg <pattern> [path]`

**Intent:** Fastest code search. Automatically routes to ayg (indexed) or rg (fallback).

**Preconditions:**
- ripgrep installed (always available as fallback)
- For ayg path: `sg build .` must have been run in target dir

**Postconditions:**
- Returns file list (-l mode) not line dump
- On indexed repo: ≤10ms
- On unindexed repo: ≤15ms

**Token budget:** ≤20t for file list results
**Failure mode:** If ayg index missing → silently falls back to rg
**Non-goal:** NOT a replacement for ast-grep (use that for AST patterns)

**Example:**
```bash
sg "featurize" /tmp/agent-token-saver
# → /tmp/agent-token-saver/core/catboost_50tests.py
# → /tmp/agent-token-saver/core/agent_token_guard.py
```

**Given/When/Then:**
```
Given: text pattern and directory
When:  sg is called
Then:  file list returned in <15ms, ≤20t
```

---

### `gemma-gate <html_or_url>`

**Intent:** Convert noisy HTML → clean compact text. No GPU required.

**Pipeline (waterfall, first success wins):**
```
1. trafilatura   0ms   90% coverage   → if text > 50 words: DONE
2. Phi-4-mini    556ms 94% accuracy   → if MLX available: DONE  
3. qwen3:0.6b    50ms  fallback       → if Ollama running: DONE
4. extractive    0ms   regex          → always works: DONE
```

**Preconditions:**
- Python 3.12+ with trafilatura
- At least one of: MLX (Apple Silicon) or Ollama running

**Postconditions:**
- Output ≤ 200 tokens regardless of input size
- Structured: title + summary + key_points[]
- No HTML tags, no navigation, no boilerplate

**Token budget:** Output hard-capped at 200t
**Failure mode:** extractive fallback always fires → never returns empty

**Example:**
```bash
CTS_CATBOOST=1 python3 core/gemma-gate.py https://example.com/article
# → {"title":"...", "summary":"...", "key_points":["...","..."]}
```

---

### `TokenGuard.route(query)`  [core/agent_token_guard.py]

**Intent:** Route any agent query to cheapest correct tool. Enforce token budgets.

**Preconditions:**
- Query is a natural language string describing agent task

**Postconditions:**
- Returns (tool, reason, estimated_tokens) tuple
- Never recommends agent_spawn as first choice
- Blocks agent_spawn + bash when budget >80% used

**Token budget:** Routing itself: 0t (pure Python, no LLM call)
**Failure mode:** Unknown query type → defaults to 'grep' (cheapest)

**Query routing rules (precedence order):**
```
Pattern match                      → Tool          Cost
──────────────────────────────────────────────────────
find/search/grep/import/function   → grep          15t
http/url/website/fetch/scrape      → web_fetch     35t
read file/open/content/cat         → read          80t
run/execute/build/compile/git/npm  → bash         150t
research/investigate/5+ sources    → ctx_batch    500t
spawn agent/delegate/subagent      → ctx_batch    500t  ← never agent_spawn
```

**Budget guard:**
```
< 80% used  → normal routing
≥ 80% used  → block bash + agent_spawn, force grep/read/ctx
≥ 95% used  → block everything except grep (15t)
```

**Given/When/Then:**
```
Given: agent query "find all TODO in src/"
When:  guard.route(query) called
Then:  returns ('grep', 'code search', 15), budget updated

Given: budget at 82% used
When:  guard.route("run npm test")
Then:  returns ('grep', 'budget_guard: forced cheap', 15) — bash blocked
```

---

### `CatBoostClassifier` [core/catboost_train.py]

**Intent:** Binary classifier — HTML signal (1) vs noise (0). CPU-only.

**Features (8 baseline / 14 extended / 18 full):**
```python
v1 (8):  chars, word_count, link_density, digit_ratio, upper_ratio,
         sentence_count, avg_word_len, starts_capital
v2 (+6): punct_ratio, unique_ratio, pipe_count, copyright_flag,
         nav_word_flag, avg_sentence_len
v3 (+4): short_word_ratio, long_word_ratio, starts_lower, has_ellipsis
```

**Optimal config (50-test benchmark, 2026-04-17):**
```python
CatBoostClassifier(
    depth=6, iterations=500, learning_rate=0.05,
    l2_leaf_reg=3, class_weights=[1.0, 2.0],
    task_type='CPU', eval_metric='AUC',
    early_stopping_rounds=50, random_seed=42
)
```

**Performance:**
- Training: 20ms (2k samples, M4 Max CPU)
- Inference: <1ms per paragraph
- AUC: 1.0 on synthetic | 0.85-0.95 on real HTML

**Token budget:** 0t (local inference, no API call)
**Failure mode:** If model file missing → skip classification, pass all text through

---

## Model Routing Decision Tree

```
Task type?
├── HTML extraction / summarization
│   ├── <500 chars or simple?  → trafilatura (0ms, 0t)
│   ├── Complex article?       → Phi-4-mini MLX (556ms, 0t)
│   └── MLX unavailable?       → qwen3:0.6b Ollama (50ms, 0t)
│
├── Code search / analysis
│   ├── Text pattern?          → sg / Grep tool (5-15ms, 15t)
│   ├── AST pattern?           → ast-grep (16ms, 15t)
│   └── PDF / archive?         → rga (14ms, 15t)
│
├── Classification / routing
│   ├── Query routing?         → TokenGuard rules (0ms, 0t)
│   ├── HTML noise filter?     → CatBoost CPU (20ms, 0t)
│   └── Semantic search?       → Qdrant + all-minilm (5ms, 0t)
│
└── LLM reasoning required?
    ├── Simple / fast?         → claude-haiku-4-5 ($0.25/1M)
    ├── Code / balanced?       → claude-sonnet-4-6 ($3/1M)
    └── Complex reasoning?     → claude-opus-4-7 ($15/1M) ← LATEST, 1M ctx
    └── Offline / free?        → phi4-mini Ollama (2.5GB, 0$)
```

---

## Local Model Routing (No GPU)

All models run on Apple M-series CPU via MLX or Ollama:

```
Model                  Size    Ollama pull           Speed    Use case
─────────────────────────────────────────────────────────────────────────
smollm2:360m           725MB   ollama pull smollm2   ~20ms    Ultra-fast extraction
gemma3:270m            291MB   ollama pull gemma3    ~30ms    Best tiny model
qwen3:0.6b             522MB   ollama pull qwen3     ~50ms    Fallback (base, not instruct)
phi4-mini (MLX)        2.2GB   already cached        ~556ms   Best quality/size ratio
phi4-mini (Ollama)     2.5GB   ollama pull phi4-mini ~800ms   MLX unavailable fallback
granite3.2:2b          1.5GB   already pulled        ~200ms   Code tasks
```

**Routing (no GPU, cheapest first):**
```python
LOCAL_MODEL_ROUTE = [
    ("trafilatura",   lambda: True,           "html_extract"),   # 0ms, always
    ("catboost",      lambda: MODEL_EXISTS,   "classification"), # 20ms, no LLM
    ("smollm2:360m",  lambda: OLLAMA_UP,      "ultra_fast"),     # 20ms
    ("gemma3:270m",   lambda: OLLAMA_UP,      "tiny_quality"),   # 30ms
    ("phi4-mini MLX", lambda: MLX_AVAIL,      "best_quality"),   # 556ms
    ("haiku-4-5 API", lambda: API_KEY_SET,    "cheap_api"),      # ~500ms, $0.25/1M
]
```

---

## Hook Architecture

```
Event                  Hook file                    Action
──────────────────────────────────────────────────────────────────────────
UserPromptSubmit       smart-context.py             Inject memory + skills
PreToolUse[Bash]       ctx-optimizer.sh             Block >20 line commands
PreToolUse[Bash]       rtk-rewrite.sh               Promote RTK commands
PreToolUse[WebFetch]   hyperstack-pretool.sh        Block → use hyperfetch
PreToolUse[Bash/curl]  hyperstack-pretool.sh        Block raw curl → hyperfetch
Stop                   compact-output.sh            Enforce terse mode

BLOCKED by hooks:
  rtk ls, rtk grep, rtk env, rtk read    → wrong tools (benchmark proven)
  raw curl/wget external                 → hyperstack-pretool blocks
  WebFetch any URL                       → hyperstack-pretool blocks
  Bash > 20 lines output                 → ctx-optimizer blocks
  Agent spawn for research               → ctx_batch_execute instead
```

---

## Acceptance Criteria

- [ ] Fresh install completes in <5 min: `bash install-optimized.sh`
- [ ] All 13 tools verify green in install check
- [ ] smart-fetch JSON API: ≤10t output
- [ ] smart-fetch HTML: ≤50t output  
- [ ] sg pattern search: ≤15ms
- [ ] gemma-gate: output ≤200t, never empty
- [ ] TokenGuard: routes agent_spawn → ctx_batch always
- [ ] CatBoost inference: <1ms per paragraph
- [ ] Hook chain: no false-positive blocks on normal commands
- [ ] ctx_batch_execute: 2+ commands always in single call

---

## Changelog

```
v2.1.0 (2026-04-17)  SPEC.md + agent_token_guard + 50-test CatBoost benchmark
                     Local model routing table + no-GPU decision tree
                     Hook architecture documented + seek false-positive fixed
v2.0.0 (2026-04-16)  Full rewrite. Phi-4-mini MLX default. Real benchmarks.
                     install-optimized.sh. TOOLS_GUIDE.md. CatBoost CPU.
v1.x               RTK + context-mode. Basic gemma-gate. No ML routing.
```
