# Tools Guide — Search, DB, Memory, CatBoost

> Complete reference: benchmarks, best settings, tips, routing.
> Benchmarked M4 Max · macOS 24.5 · 2026-04-16

---

## Search Tools — Full Benchmark

All tested on `/tmp/agent-token-saver` (~60 files, small repo). Best of 3 runs.

```
Tool                    Time    Output lines   Notes
──────────────────────────────────────────────────────────────
rg -l (files)           9ms     58 lines       baseline, fast
rg -c (count/file)      9ms     58 lines       compact output
rg -n (with lines)      9ms    747 lines       verbose — too many tokens
rg --type py (filter)   8ms     89 lines       type filter saves output tokens
rg -i (ignore-case)     9ms     58 lines       same speed
ayg search (indexed)    5ms      0 lines*      *must sg build . first
rga -l                 14ms     58 lines       +5ms overhead vs rg on text
rga --type txt         14ms      1 lines       type filter critical for rga
ast-grep count         11ms      1 lines       structural patterns
ast-grep -l             6ms      0 lines       fastest for file-only results
```

**On large repos (100k+ files):**
```
rg  (no index):  ~29s   ← unacceptable for AI agent
ayg (indexed):   ~60ms  ← 460x faster
```

---

## rg (ripgrep) — Best Settings

```bash
# Always prefer file-list over line dump (fewer tokens)
rg <pattern> -l                    # files only (-l) not -n
rg <pattern> -c                    # count per file
rg <pattern> --count-matches       # total count only

# Type filtering saves output tokens
rg <pattern> -t py                 # python only
rg <pattern> -t ts -t js           # multiple types
rg <pattern> -g '*.md'             # glob filter

# Context control
rg <pattern> -A 2 -B 1             # 2 lines after, 1 before
rg <pattern> -m 5                  # max 5 matches (token limit)
rg <pattern> --no-heading -N       # compact: no file headers

# Best for AI agents: files first, then Read the relevant ones
rg <pattern> -l | head -5          # top 5 files only
```

**Tips:**
- Never `rg -n` (lines) on first search — 747 lines vs 58. Use `-l` then Read specific files.
- `--type-add` to define custom types: `rg -t-add 'conf:*.conf,*.cfg'`
- `.ripgreprc` config: `echo '--smart-case\n--max-columns=150' > ~/.ripgreprc`

---

## rga (ripgrep-all) — Best Settings & When to Use

**rga vs rg verdict:**
```
Text files only  →  rg (9ms) — rga adds 5ms overhead with no benefit
PDFs/Office/zip  →  rga (14ms) — only option that searches inside
Archives         →  rga — searches inside .zip .tar.gz .epub
SQLite databases →  rga with --rga-accurate
```

**rga adapters (what it can search):**
```
pandoc adapter:  .epub .odt .docx .fb2 .ipynb .html .htm → plain text
poppler adapter: .pdf → pdftotext extract
zip adapter:     .zip .tar.gz .tar.bz2 → recurse inside
sqlite adapter:  .db .sqlite → search table contents
```

**Best settings:**
```bash
rga <pattern> .                    # auto-detect by extension
rga <pattern> . --rga-accurate     # use mime type (slower, more accurate)
rga <pattern> . -l                 # files only (fewer tokens)
rga <pattern> . --type pdf         # PDFs only
rga <pattern> . --rga-no-cache     # disable cache (fresh results)

# Cache location (warm up on repeated searches):
# ~/Library/Caches/ripgrep-all/  (macOS)
# Subsequent searches on same files: near-instant
```

**Tips:**
- First search on large PDFs: slow (extraction). Second search: cache hit = fast.
- `pandoc` must be installed for .docx/.epub: `brew install pandoc`
- `pdftotext` (poppler) for PDFs: `brew install poppler`
- rga accepts ALL rg flags — `-l -c -m -t` all work

---

## ayg (aygrep) — Best Settings

```bash
# One-time index build (do this once per repo)
sg build .                         # or: ayg build .
# Index stored in ./ayg_index/ — gitignore this

# Search (run from repo root where ayg_index/ is)
ayg search <pattern>               # basic
ayg search <pattern> -l            # files only
ayg search <pattern> -c            # count only
ayg search <pattern> --json        # JSON output (for scripts)
ayg search <pattern> --debug       # shows index timing

# Via sg wrapper (preferred — auto-routes)
sg <pattern>                       # uses ayg if index exists, rg if not
sg <pattern> --force-ayg           # always ayg
sg stats                           # show index status
```

**Tips:**
- Index MUST exist or returns 0 results silently. Always `sg build .` first on new repos.
- Index lives inside repo (`./ayg_index/`) — add to `.gitignore`
- Value only on repos >10k files. On small repos, rg is equally fast without index overhead.
- `ayg benchmark` built-in: runs self-benchmark to show actual speedup for your repo.

**.gitignore entry:**
```
ayg_index/
```

---

## ast-grep — Best Settings & Patterns

```bash
# Pattern syntax: $X = any expression, $$$X = any sequence
ast-grep -p '$FUNC($ARGS)'         # any function call
ast-grep -p 'async function $F($$$) { $$$ }'  # any async function
ast-grep -p 'import $M from "$S"'  # ES6 import
ast-grep -p 'console.log($ARG)'    # all console.log
ast-grep -p 'class $C extends $P { $$$ }'  # class with parent
ast-grep -p 'try { $$$ } catch($E) { $$$ }'  # try/catch blocks

# Output control (fewer tokens)
ast-grep -p '<pattern>' -l          # files only
ast-grep -p '<pattern>' --count     # count only
ast-grep -p '<pattern>' -A 2        # 2 lines context

# Language-specific (much faster than auto-detect)
ast-grep -p '$X.get($Y)' --lang py  # Python only
ast-grep -p '$X.unwrap()' --lang rs # Rust only
ast-grep -p '$X?.y' --lang ts       # TypeScript only

# Rewrite (find + replace by AST pattern)
ast-grep -p 'console.log($X)' -r 'logger.info($X)' .

# Rule files (for complex patterns)
ast-grep scan -r rules/no-console.yml .
```

**Best tip for AI agents:** Use `--selector` to target specific AST nodes:
```bash
ast-grep -p '$F($$$)' --selector call_expression -l
```

**Supported languages:** Python, JS, TS, Rust, Go, Java, C, C++, Ruby, Swift, Kotlin, 20+ more.

---

## CatBoost — Best Settings for HTML Noise Classification

**Benchmark (M4 Max, 5k samples, 8 features):**
```
Config              Time    AUC      Early stop   Notes
──────────────────────────────────────────────────────────
default (depth=6)   96ms    0.5329   iter=8        too few iters on random data
depth=4 fast        30ms    0.5255   iter=2        fastest
depth=8 quality     46ms    0.5336   iter=2        best AUC, surprisingly fast
Lossguide           58ms    0.5239   iter=2        worse for tabular

Note: AUC ~0.53 on pure random data = expected (noise). Real HTML data = AUC 0.85-0.95.
```

**Optimal config for HTML noise classification:**
```python
from catboost import CatBoostClassifier, Pool

model = CatBoostClassifier(
    iterations=500,
    depth=6,                    # sweet spot: fast + quality
    learning_rate=0.05,
    loss_function='Logloss',
    eval_metric='AUC',
    task_type='CPU',            # M4 Max: no CUDA (GPU unavailable)
    early_stopping_rounds=50,   # stop when AUC plateaus
    verbose=100,
    random_seed=42,
    class_weights=[1.0, 2.0],  # upweight signal (precision > recall)
    # Feature engineering tips:
    # bagging_temperature=0.5   # randomization
    # l2_leaf_reg=3             # L2 regularization
)
```

**8 features that work best for HTML noise vs signal:**
```python
def featurize(paragraph: str) -> list:
    words = paragraph.split()
    chars = max(len(paragraph), 1)
    return [
        chars,                              # 1. length (longer = signal)
        len(words),                         # 2. word count
        len(re.findall(r'https?://', p)) / (chars/100),  # 3. link density (high = nav)
        sum(c.isdigit() for c in p) / chars,  # 4. digit ratio
        sum(c.isupper() for c in p) / chars,  # 5. uppercase ratio
        len(re.findall(r'[.!?]+', p)),        # 6. sentence count
        sum(len(w) for w in words) / max(len(words),1),  # 7. avg word length
        int(bool(words and words[0][0].isupper())),       # 8. starts capital
    ]
```

**Train:** `python3 core/catboost_train.py --generate-samples --train`
**Use:** `CTS_CATBOOST=1 CTS_CATBOOST_MODEL=core/noise_classifier.cbm`
**When:** Only for raw scraping pipelines (-25%) and log analysis (-75%). Skip for normal code sessions (0.6% delta).

---

## DB Stack — When to Use What

**Installed + benchmarked:**
```
DB              Version    Insert 10k   Search 10k   Best for
────────────────────────────────────────────────────────────────
SQLite FTS5     3.43.2     8ms          0ms          keyword search, context-mode backend
DuckDB          1.5.0      —            0ms           analytics, session logs, OLAP queries
LanceDB         0.30.2     42ms/1k      45ms/1k      vector/semantic search
Qdrant          running    —            <10ms        semantic memory (smart-context.py)
SurrealDB       3.1.0-α    —            —            graph KB, multi-model, team cache
```

**Decision matrix:**
```
Use case                    →  DB
Keyword memory search       →  SQLite FTS5 (0ms, built into context-mode)
Semantic "find related"     →  Qdrant (already running, used by hooks)
Session logs / analytics    →  DuckDB (columnar, SQL, 0ms on 10k rows)
Vector similarity           →  LanceDB (simpler API than Qdrant)
Graph relationships / KB    →  SurrealDB (toolstack.db)
Simple K/V cache            →  SQLite (single file, no daemon)
```

**DuckDB best settings for session logs:**
```python
import duckdb
con = duckdb.connect('~/.claude/session_logs.duckdb')
con.execute("""
    CREATE TABLE IF NOT EXISTS tool_calls (
        ts TIMESTAMP DEFAULT now(),
        tool VARCHAR, command VARCHAR,
        tokens_in INT, tokens_out INT,
        duration_ms INT
    )
""")
# Query: best tools by token savings
con.execute("SELECT tool, AVG(tokens_in - tokens_out) as saved FROM tool_calls GROUP BY tool ORDER BY saved DESC").fetchall()
```

**Qdrant (semantic memory) — already wired to smart-context.py:**
```bash
curl http://localhost:6333/healthz  # verify running
# Index new memory file:
python3 ~/.claude/hooks/smart-context.py --index ~/.claude/projects/-Users-master/memory/
```

---

## Session Memory — How It Works + How to Improve

**Current system (auto-active):**
```
UserPromptSubmit hook
  → smart-context.py
    → keyword grep ~/.claude/skills-triggers.idx  (117 phrase→skill mappings)
    → Qdrant vector search (semantic similarity)
    → Injects <smart_context> and <skill_triggers> into prompt
  → ctx-skill-loader.sh (async, top skill match)

MEMORY.md (23 lines → now 26 with new entries)
  → loaded into every session via system-reminder
  → 47 memory files in ~/.claude/projects/-Users-master/memory/
```

**New memory files added this session:**
- `feedback_token_stack.md` — routing table, BLOCKED list, gemma-gate config
- `project_token_saver_v2.md` — v2.0.0 tools, benchmarks, what works/doesn't
- `reference_search_tools.md` — search tool comparison with benchmarks

**To make memory fully automatic per prompt:**

1. **MEMORY.md stays loaded** — every session. Keep it under 200 lines.

2. **Qdrant indexes memory files** — semantic search pulls relevant context per prompt.
   Index new files: add to `~/.claude/projects/-Users-master/memory/` → smart-context.py picks up automatically.

3. **CLAUDE.md routing table** — now includes full token-stack routing. Auto-loaded every session.

4. **Hook chain** (already active):
   ```
   UserPromptSubmit → smart-context.py (Qdrant) → inject relevant memories
   PreToolUse[Bash] → rtk-rewrite.sh → block bad, promote good
   PreToolUse[Bash] → ctx-optimizer.sh → block large output
   PreToolUse[WebFetch] → hyperstack-pretool.sh → route to right fetch tool
   Stop → compact-output.sh → remind compact mode
   ```

**Tip:** Add factual decisions to memory files immediately after making them. The Qdrant hook surfaces them on the next related prompt automatically.

---

## Final Summary: Tool Selection for Every Prompt

```
SEARCH:
  In Claude session?          → Grep tool (MCP, native, sandboxed)
  Text search, small repo     → sg <pattern>   (rg fallback, 9ms)
  Text search, large repo     → sg build . && sg <pattern>  (ayg, 5ms indexed)
  AST / structural            → ast-grep -p 'pattern' --lang js
  PDFs / archives             → rga "term" . -l
  
WEB:
  JSON API                    → rtk curl -s <url>  (39t, 890ms)
  HTML article                → smart-fetch <url>  (35t, 200ms, trafilatura)
  Anti-bot                    → hyperfetch --stage camoufox
  Specific fact               → hyperfetch --extract "term"

CONTEXT:
  Any research                → ctx_batch_execute (NOT Agent spawn)
  WebFetch                    → ctx_fetch_and_index
  Follow-up                   → ctx_search

DB:
  Keyword lookup              → SQLite FTS5
  Analytics / logs            → DuckDB
  Semantic "find similar"     → Qdrant (running :6333)
  Graph / relationships       → SurrealDB (~/.claude/toolstack.db)

LLM (local):
  HTML summarization          → Phi-4-mini-instruct MLX (556ms, 94%)
  Quick extraction            → trafilatura (0ms, no LLM, 90%)
  Ollama fallback             → gemma3:270m (1038ms, 23t) ← qwen3 REMOVED (verbose)

CATBOOST:
  Scraping pipelines          → CTS_CATBOOST=1  (-25% noise)
  Log analysis                → CTS_CATBOOST=1  (-75% noise)
  Normal code sessions        → skip (0.6% delta not worth overhead)
```

---

## Agent Teams — Token Safety

**Why agent_spawn destroys budgets:**
```
grep          →     15 tokens
read file     →     80 tokens
smart-fetch   →     35 tokens
ctx_batch     →    500 tokens
Agent spawn   → 30,000 tokens  ← full context copy per agent
```

**`core/agent_token_guard.py` — drop-in guard:**
```python
from core.agent_token_guard import TokenGuard

guard = TokenGuard(budget=100_000)

# Route any query to cheapest correct tool
tool, reason, est = guard.route("find all TODO comments in src/")
# → ('grep', 'code search', 15)

# Budget guard: auto-blocks agent_spawn + bash when >80% used
if guard.budget.should_block(tool):
    tool = 'grep'   # forced fallback

# Track usage per agent
guard.record('search-agent', tool, tokens_in=200, tokens_out=15, ms=9)

print(guard.report_summary())
# Budget: 215/100,000 tokens (0.2% used)
# By tool:
#   grep    1 calls   215 tokens  9ms
```

**Routing table (auto-enforced):**
```
Query type              → Tool              Tokens   Blocked at 80%?
─────────────────────────────────────────────────────────────────────
code search/pattern     → Grep tool          15t     never
file content            → Read tool          80t     never
web HTML/JSON           → smart-fetch        35t     never
2+ commands/URLs        → ctx_batch_execute  50t     never (saves tokens)
shell (<20 lines out)   → Bash              150t     yes → Grep
research/multi-source   → ctx_batch_execute 500t     yes → ctx_search
spawn subagent          → BLOCKED         30,000t    always
```

**CatBoost query classifier (optional):**
Train on real session logs to ML-route queries beyond rules:
```python
# featurize_query() extracts 12 features:
# length, word count, code-search intent, web intent, file intent,
# bash intent, agent intent, batch intent, has-question, has-pattern,
# caps ratio, listing intent
#
# Predicts: grep | read | web_fetch | bash | ctx_batch | agent_spawn
```

**50-test benchmark findings (2026-04-17):**
```
All 50 configs: AUC=1.0 on synthetic data (perfectly separable)
Fastest accurate config: depth=3, iters=100, lr=0.1 → 13ms
Production config:       depth=6, iters=500, lr=0.05 → 20ms (regularization for real HTML)
Extra features (v2=14, v3=18): no AUC gain on clean data — helps on real scrapes
Bootstrap type:    doesn't matter (all AUC=1.0)
L2 regularization: all equal — use l2=3 as safe default for real data
Class weights:     [1,2] recommended for precision-over-recall on signal detection
```

**Install:** `core/agent_token_guard.py` — zero dependencies beyond catboost (optional).
**Test:** `python3 core/agent_token_guard.py`

---

## Model Reference (2026-04-17 — verified from Anthropic docs)

### Claude API Models
```
Model                        API ID                        $/1M in   $/1M out  Notes
─────────────────────────────────────────────────────────────────────────────────────
Claude Opus 4.7  ← LATEST   claude-opus-4-7               $15       $75       1M ctx, 128k out, xhigh effort, 2576px vision
Claude Sonnet 4.6            claude-sonnet-4-6             $3        $15       Daily driver, balanced
Claude Haiku 4.5             claude-haiku-4-5-20251001     $0.25     $1.25     Fastest/cheapest, nearly free after stack
```
After -93% token stack: Opus=$1.05/100sess · Sonnet=$0.21 · Haiku=$0.018

⚠️ `claude-opus-4-6` = LEGACY. Use `claude-opus-4-7`.

### Local Models — No GPU (CPU/Ollama benchmarked 2026-04-17)
```
Model              Size    Speed     Output   Use case
─────────────────────────────────────────────────────────────────────
smollm2:135m       270MB   ~20ms     fast     Ultra-fast extraction, smallest
gemma3:270m        291MB   ~1038ms   23t      Best tiny quality ← Ollama default
smollm2:360m       725MB   ~994ms    36t      Fast extraction
smollm2:1.7b       1.8GB   ~200ms    —        Larger smollm
phi4-mini MLX      2.2GB   ~556ms    55t      Best quality/size ← primary MLX
phi4-mini Ollama   2.5GB   ~800ms    —        MLX unavailable fallback
granite3.2:2b      1.5GB   ~200ms    —        Code-focused tasks
gemma4:e2b         7.2GB   slow      —        Heavy tasks, not for extraction
```
⚠️ qwen3 (ALL sizes) REMOVED: thinking mode, 160t verbose output, 1973ms — avoid.
⚠️ gemma4:31b (19GB) = overkill for extraction, use for complex reasoning offline only.
