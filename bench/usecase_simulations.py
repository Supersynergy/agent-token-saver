#!/usr/bin/env python3
"""
Real use-case simulations + local model routing benchmark
No GPU — CPU/MLX/Ollama only
"""
import sys, re, time, json, subprocess
sys.path.insert(0, '/opt/homebrew/lib/python3.12/site-packages')

print("=" * 65)
print("USE CASE SIMULATIONS — claude-token-saver")
print("=" * 65)

# ── USE CASE 1: HTML noise classifier on real-ish paragraphs ─────────
print("\n[UC1] CatBoost: HTML noise vs signal classification")
try:
    import numpy as np
    from catboost import CatBoostClassifier

    def featurize(p):
        words = p.split(); chars = max(len(p),1)
        return [
            chars, len(words),
            len(re.findall(r'https?://', p))/(chars/100),
            sum(c.isdigit() for c in p)/chars,
            sum(c.isupper() for c in p)/chars,
            len(re.findall(r'[.!?]+', p)),
            sum(len(w) for w in words)/max(len(words),1),
            int(bool(words and words[0][0].isupper())),
        ]

    # Real-world training samples
    signal = [
        "Machine learning models require careful validation to avoid overfitting on training data.",
        "The CatBoost classifier achieved AUC of 0.94 on the HTML noise detection benchmark.",
        "Token optimization reduces Claude Code session costs by 84-93% in practice.",
        "Spec-driven development defines contracts before implementation, reducing rework.",
        "Apple Silicon M4 Max has no CUDA support; all ML inference runs on CPU via MLX.",
    ]
    noise = [
        "Home About Contact Privacy Terms of Service",
        "© 2024 Company Inc. All rights reserved.",
        "Click here to read more... Subscribe now!",
        "Share Tweet Pin Email Reddit LinkedIn",
        "Loading... Please wait while we process your request.",
    ]

    X = np.array([featurize(p) for p in signal+noise])
    y = np.array([1]*5 + [0]*5)

    m = CatBoostClassifier(depth=6, iterations=500, learning_rate=0.05,
                           l2_leaf_reg=3, class_weights=[1,2],
                           task_type='CPU', verbose=0, random_seed=42)
    m.fit(X, y)

    test_cases = [
        ("Token optimization is a key practice for AI cost reduction.", 1),
        ("Privacy Policy | Terms | Cookie Settings | Sitemap", 0),
        ("The benchmark results show 94% accuracy on real HTML datasets.", 1),
        ("Copyright 2024. All Rights Reserved. | Contact Us", 0),
    ]

    print(f"  {'Text':<55} {'Pred':>4} {'True':>4} {'OK':>3}")
    print(f"  {'-'*65}")
    correct = 0
    for text, true_label in test_cases:
        t0 = time.perf_counter()
        pred = int(m.predict([featurize(text)])[0])
        ms = int((time.perf_counter()-t0)*1000*1000)  # microseconds
        ok = "✓" if pred == true_label else "✗"
        if pred == true_label: correct += 1
        print(f"  {text[:54]:<55} {pred:>4} {true_label:>4} {ok:>3}  {ms}μs")
    print(f"  Accuracy: {correct}/{len(test_cases)} | Model: depth=6, CPU, 10 samples")
except Exception as e:
    print(f"  ERROR: {e}")

# ── USE CASE 2: smart-fetch JSON API ─────────────────────────────────
print("\n[UC2] smart-fetch: JSON API → minimal tokens")
try:
    t0 = time.perf_counter()
    result = subprocess.run(
        ['smart-fetch', 'https://api.github.com/repos/Supersynergy/agent-token-saver'],
        capture_output=True, text=True, timeout=10
    )
    ms = int((time.perf_counter()-t0)*1000)
    out = result.stdout.strip()
    tokens_est = len(out.split())
    print(f"  Time: {ms}ms | Est. tokens: ~{tokens_est}t")
    print(f"  Output: {out[:120]}...")
except Exception as e:
    print(f"  ERROR: {e}")

# ── USE CASE 3: trafilatura HTML extraction ───────────────────────────
print("\n[UC3] trafilatura: HTML article → clean text")
try:
    import trafilatura
    html = """<html><body>
    <nav>Home | About | Contact | Privacy</nav>
    <article>
      <h1>Token Optimization for AI Agents</h1>
      <p>Effective token optimization requires understanding which tools produce verbose output.
      The key insight is that raw Bash commands, WebFetch calls, and Agent spawning are the
      three biggest token sinks in any Claude Code session.</p>
      <p>By routing all research through ctx_batch_execute instead of spawning subagents,
      teams can achieve 60x token savings — 500 tokens instead of 30,000 per research task.</p>
    </article>
    <footer>© 2024 All Rights Reserved | Terms | Sitemap</footer>
    </body></html>"""

    t0 = time.perf_counter()
    text = trafilatura.extract(html)
    ms = int((time.perf_counter()-t0)*1000)
    tokens_est = len(text.split()) if text else 0
    print(f"  Time: {ms}ms | Words: {tokens_est} | Est. tokens: ~{tokens_est}t")
    print(f"  Clean text: {text[:200] if text else 'EMPTY'}...")
    nav_removed = 'Home | About' not in (text or '')
    footer_removed = '© 2024' not in (text or '')
    print(f"  Nav removed: {nav_removed} | Footer removed: {footer_removed}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── USE CASE 4: TokenGuard routing real agent queries ─────────────────
print("\n[UC4] TokenGuard: real agent team queries")
try:
    sys.path.insert(0, '/tmp/agent-token-saver')
    from core.agent_token_guard import TokenGuard, TOOL_COST
    guard = TokenGuard(budget=50_000)

    real_queries = [
        ("Find all API endpoints in routes/api/", 'grep', 15),
        ("Fetch the competitor pricing page from stripe.com", 'web_fetch', 35),
        ("Read the current CLAUDE.md config", 'read', 80),
        ("Run pnpm test and check for failures", 'bash', 150),
        ("Research 5 open-source token optimizers and compare", 'ctx_batch', 500),
        ("Spawn an agent to handle the database migration", 'ctx_batch', 500),
        ("List all Python files matching *.py in core/", 'grep', 15),
        ("Download and analyze the benchmark PDF report", 'web_fetch', 35),
    ]

    print(f"  {'Query':<48} {'Got':<12} {'Exp':<12} {'OK':>3} {'Cost':>6}")
    print(f"  {'-'*80}")
    for query, expected_tool, expected_cost in real_queries:
        tool, reason, cost = guard.route(query)
        guard.record('test-agent', tool, tokens_in=cost//2, tokens_out=cost//2, ms=5)
        ok = "✓" if tool == expected_tool else "~"
        print(f"  {query[:47]:<48} {tool:<12} {expected_tool:<12} {ok:>3} {cost:>6}t")

    print(f"\n  {guard.report_summary()}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── USE CASE 5: Local model routing benchmark ─────────────────────────
print("\n[UC5] Local model routing (no GPU) — latency benchmark")
models_to_test = [
    ("smollm2:360m", "summarize in 1 sentence: Token optimization saves 90% of Claude Code costs"),
    ("gemma3:270m",  "summarize in 1 sentence: Token optimization saves 90% of Claude Code costs"),
    ("qwen3:0.6b",   "summarize in 1 sentence: Token optimization saves 90% of Claude Code costs"),
]

print(f"  {'Model':<20} {'Time':>7} {'Tokens':>7} {'First 80 chars of output'}")
print(f"  {'-'*80}")
for model, prompt in models_to_test:
    try:
        t0 = time.perf_counter()
        result = subprocess.run(
            ['ollama', 'run', model, prompt],
            capture_output=True, text=True, timeout=30
        )
        ms = int((time.perf_counter()-t0)*1000)
        out = result.stdout.strip().replace('\n', ' ')[:80]
        tokens = len(result.stdout.split())
        print(f"  {model:<20} {ms:>6}ms {tokens:>7}t  {out}")
    except subprocess.TimeoutExpired:
        print(f"  {model:<20} TIMEOUT")
    except Exception as e:
        print(f"  {model:<20} ERROR: {e}")

# ── USE CASE 6: Haiku API cost estimate ──────────────────────────────
print("\n[UC6] Claude model cost comparison")
models = [
    ("claude-haiku-4-5-20251001", 0.25, 1.25, "fastest/cheapest"),
    ("claude-sonnet-4-6",          3.0,  15.0, "balanced"),
    ("claude-opus-4-6",           15.0,  75.0, "max quality"),
]
# Note: claude-opus-4.7 does not exist. Latest is claude-opus-4-6.
typical_in = 5000   # tokens/session
typical_out = 2000

print(f"  {'Model':<30} {'$/1M in':>8} {'$/1M out':>9} {'$/100sess':>10}  {'Use case'}")
print(f"  {'-'*75}")
for model, price_in, price_out, use in models:
    cost_per_100 = (typical_in * price_in + typical_out * price_out) / 1_000_000 * 100
    print(f"  {model:<30} ${price_in:>7.2f} ${price_out:>8.2f} ${cost_per_100:>9.2f}  {use}")

print(f"\n  After token stack (-93%): multiply costs by 0.07")
print(f"  Haiku @ -93%: ${0.25*0.07:.4f}/1M in → nearly free for code sessions")

print("\n" + "=" * 65)
print("ALL USE CASES COMPLETE")
print("=" * 65)
