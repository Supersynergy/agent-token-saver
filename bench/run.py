#!/usr/bin/env python3
# Hyperstack benchmark — measures token + latency savings across configurations.
# Runs each URL through: baseline, stage1-raw, stage1-mlfilter, stage1-gemma,
# stage1-all, and cache-hit. Outputs JSON + markdown.

import json
import subprocess
import time
import hashlib
import os
import sys
from pathlib import Path

HOME = Path.home()
HYPERFETCH = HOME / ".cts" / "bin" / "hyperfetch"
STAGE_HELPER = HOME / ".cts" / "bin" / "hyperfetch-stage.py"
SANDBOX = HOME / "agent-token-saver" / "plugins" / "team-sandbox.sh"
ML_FILTER = HOME / "agent-token-saver" / "core" / "ml-filter.py"
GEMMA_GATE = HOME / "agent-token-saver" / "core" / "gemma-gate.py"
VENV_PY = HOME / ".cts" / "venv" / "bin" / "python"

URLS = [
    ("tiny-static",       "https://example.com"),
    ("tiny-static-2",     "https://example.org"),
    ("medium-html",       "https://httpbin.org/html"),
    ("json-api",          "https://api.github.com"),
    ("plaintext",         "https://raw.githubusercontent.com/torvalds/linux/master/README"),
    ("wiki-article",      "https://en.wikipedia.org/wiki/Token"),
    ("hn-front",          "https://news.ycombinator.com"),
]


def est_tokens(n_bytes: int) -> int:
    return max(1, n_bytes // 4)


def run(cmd, stdin=None, timeout=60):
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        ms = (time.perf_counter() - t0) * 1000
        return r.returncode, r.stdout, r.stderr, ms
    except subprocess.TimeoutExpired:
        return 124, "", "timeout", (time.perf_counter() - t0) * 1000


def baseline_fetch(url: str) -> dict:
    """Raw curl_cffi fetch — simulates what WebFetch returns (full HTML)."""
    rc, out, err, ms = run(
        [str(VENV_PY), str(STAGE_HELPER), "--stage", "curl_cffi", "--url", url],
        timeout=30,
    )
    if rc != 0 or not out:
        return {"ok": False, "bytes": 0, "tokens": 0, "latency_ms": ms, "error": err[:200]}
    try:
        data = json.loads(out)
        body = data.get("body", "")
        b = len(body.encode("utf-8"))
        return {"ok": True, "bytes": b, "tokens": est_tokens(b), "latency_ms": ms, "stage": data.get("stage"), "status": data.get("status")}
    except Exception as e:
        return {"ok": False, "bytes": 0, "tokens": 0, "latency_ms": ms, "error": str(e)[:200]}


def hyperfetch_call(url: str, *flags) -> dict:
    cmd = [str(HYPERFETCH), url] + list(flags)
    rc, out, err, ms = run(cmd, timeout=90)
    if rc != 0 or not out:
        return {"ok": False, "bytes": 0, "tokens": 0, "latency_ms": ms, "error": err[:200] or out[:200]}
    try:
        data = json.loads(out.strip().splitlines()[-1])
        return {
            "ok": data.get("stage") not in (None, "failed"),
            "bytes": data.get("bytes", 0),
            "tokens": data.get("tokens", 0),
            "latency_ms": ms,
            "stage": data.get("stage"),
            "cached": data.get("cached", False),
            "preview_len": len(data.get("preview", "")),
        }
    except Exception as e:
        return {"ok": False, "bytes": 0, "tokens": 0, "latency_ms": ms, "error": str(e)[:200]}


def apply_mlfilter(text: str) -> dict:
    """Simulate: pipe raw body through ml-filter, count kept chars."""
    t0 = time.perf_counter()
    rc, out, err, ms = run([str(VENV_PY), str(ML_FILTER), "--classify"], stdin=text[:65536])
    try:
        r = json.loads(out)
        keep = r.get("keep", True)
        category = r.get("category", "unknown")
    except Exception:
        keep, category = True, "unknown"
    kept_bytes = len(text.encode("utf-8")) if keep else 200
    return {
        "keep": keep,
        "category": category,
        "kept_bytes": kept_bytes,
        "kept_tokens": est_tokens(kept_bytes),
        "filter_ms": (time.perf_counter() - t0) * 1000,
    }


def apply_gemma(text: str) -> dict:
    """Pipe text through gemma-gate, measure output."""
    env = {**os.environ, "CTS_GEMMA_THRESHOLD": "100"}
    t0 = time.perf_counter()
    r = subprocess.run(
        [str(VENV_PY), str(GEMMA_GATE), "--summarize"],
        input=text[:131072], capture_output=True, text=True, timeout=90, env=env,
    )
    ms = (time.perf_counter() - t0) * 1000
    summary = r.stdout if r.returncode == 0 else text
    b = len(summary.encode("utf-8"))
    return {
        "summary_bytes": b,
        "summary_tokens": est_tokens(b),
        "gemma_ms": ms,
        "summary_preview": summary[:120],
    }


def purge_cache():
    subprocess.run(
        ["bash", str(SANDBOX), "purge", "0"],
        env={**os.environ, "CTS_TEAM_NS": "bench"},
        capture_output=True,
    )


def fmt_k(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def run_benchmark():
    purge_cache()
    results = []

    for label, url in URLS:
        print(f"\n=== {label}: {url}", file=sys.stderr)
        row = {"label": label, "url": url}

        # 1. Baseline — raw HTML, what WebFetch would pump into context
        print("  [1/5] baseline (raw curl_cffi, full body)", file=sys.stderr)
        b = baseline_fetch(url)
        row["baseline"] = b
        if not b["ok"]:
            row["error"] = b.get("error", "baseline failed")
            results.append(row)
            continue
        raw_body = None
        if b["ok"]:
            # re-fetch once to get the raw text for ml/gemma stages
            rc, out, err, _ = run(
                [str(VENV_PY), str(STAGE_HELPER), "--stage", "curl_cffi", "--url", url],
                timeout=30,
            )
            try:
                raw_body = json.loads(out).get("body", "")
            except Exception:
                raw_body = ""

        # 2. Stage-1 raw hyperfetch (no cache, no summary) — just escalation chain
        print("  [2/5] hyperfetch --no-cache --no-summary", file=sys.stderr)
        os.environ["CTS_TEAM_NS"] = "bench-raw"
        row["stage1_raw"] = hyperfetch_call(url, "--team-ns", "bench-raw", "--no-cache", "--no-summary")

        # 3. Stage-1 + ml-filter only (simulated)
        print("  [3/5] stage1 + ml-filter", file=sys.stderr)
        if raw_body:
            ml = apply_mlfilter(raw_body)
            row["stage1_ml"] = {
                "bytes": ml["kept_bytes"],
                "tokens": ml["kept_tokens"],
                "category": ml["category"],
                "filter_ms": round(ml["filter_ms"], 1),
            }

        # 4. Stage-1 + gemma summarize only (simulated)
        print("  [4/5] stage1 + gemma summary", file=sys.stderr)
        if raw_body:
            g = apply_gemma(raw_body)
            row["stage1_gemma"] = {
                "bytes": g["summary_bytes"],
                "tokens": g["summary_tokens"],
                "gemma_ms": round(g["gemma_ms"], 1),
                "preview": g["summary_preview"],
            }

        # 5. Full hyperfetch (cached=false first) — all optimizations active
        print("  [5/5] full hyperfetch (cache + ml + gemma)", file=sys.stderr)
        os.environ["CTS_TEAM_NS"] = "bench-full"
        row["full_cold"] = hyperfetch_call(url, "--team-ns", "bench-full", "--no-cache")

        # 6. Cache hit — call again, should be instant
        print("  [6/6] cache hit (same url, same ns)", file=sys.stderr)
        row["cache_hit"] = hyperfetch_call(url, "--team-ns", "bench-full")

        results.append(row)

    return results


def render_markdown(results):
    out = ["# Hyperstack Benchmark Results", ""]
    out.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"**Machine**: {os.uname().sysname} {os.uname().machine}")
    out.append("")

    out.append("## Per-URL Savings")
    out.append("")
    out.append("| URL | Baseline | Stage1 Raw | + ML Filter | + Gemma | Full Cold | Cache Hit | Best Factor |")
    out.append("|-----|---------:|-----------:|------------:|--------:|----------:|----------:|------------:|")

    totals = {"baseline_tok": 0, "stage1_tok": 0, "ml_tok": 0, "gemma_tok": 0, "full_tok": 0, "cache_tok": 0}

    for r in results:
        if "error" in r:
            out.append(f"| {r['label']} | ERROR | — | — | — | — | — | — |")
            continue
        bt = r["baseline"]["tokens"]
        s1 = r.get("stage1_raw", {}).get("tokens", 0)
        ml = r.get("stage1_ml", {}).get("tokens", 0)
        gm = r.get("stage1_gemma", {}).get("tokens", 0)
        fc = r.get("full_cold", {}).get("tokens", 0)
        ch = r.get("cache_hit", {}).get("tokens", 0)
        best = max(1, bt) / max(1, min(x for x in [s1, ml, gm, fc, ch] if x > 0) or 1)
        totals["baseline_tok"] += bt
        totals["stage1_tok"] += s1
        totals["ml_tok"] += ml or bt
        totals["gemma_tok"] += gm or bt
        totals["full_tok"] += fc
        totals["cache_tok"] += ch

        out.append(
            f"| {r['label']} | {fmt_k(bt)} | {fmt_k(s1)} | {fmt_k(ml)} | {fmt_k(gm)} | {fmt_k(fc)} | {fmt_k(ch)} | **{best:.0f}x** |"
        )

    out.append("")
    out.append("## Totals Across All URLs")
    out.append("")
    out.append("| Config | Total Tokens | vs Baseline | Savings |")
    out.append("|--------|-------------:|-------------|--------:|")
    bt = totals["baseline_tok"]
    for label, key in [
        ("Baseline (raw WebFetch)", "baseline_tok"),
        ("Stage1 Raw (escalation only)", "stage1_tok"),
        ("Stage1 + ML Filter", "ml_tok"),
        ("Stage1 + Gemma Summary", "gemma_tok"),
        ("Full Cold (ml + gemma)", "full_tok"),
        ("Cache Hit (warm team)", "cache_tok"),
    ]:
        t = totals[key]
        factor = (bt / max(1, t)) if t > 0 else float("inf")
        saved = max(0, bt - t)
        out.append(f"| {label} | {fmt_k(t)} | {factor:.1f}x | {fmt_k(saved)} tokens |")

    out.append("")
    out.append("## Latency Profile")
    out.append("")
    out.append("| URL | Stage1 ms | Full Cold ms | Cache Hit ms | ML ms | Gemma ms |")
    out.append("|-----|----------:|-------------:|-------------:|------:|---------:|")
    for r in results:
        if "error" in r:
            continue
        out.append(
            f"| {r['label']} "
            f"| {r.get('stage1_raw',{}).get('latency_ms',0):.0f} "
            f"| {r.get('full_cold',{}).get('latency_ms',0):.0f} "
            f"| {r.get('cache_hit',{}).get('latency_ms',0):.0f} "
            f"| {r.get('stage1_ml',{}).get('filter_ms',0):.0f} "
            f"| {r.get('stage1_gemma',{}).get('gemma_ms',0):.0f} |"
        )

    out.append("")
    out.append("## Sample Gemma Summaries (quality check)")
    out.append("")
    for r in results:
        if "error" in r or "stage1_gemma" not in r:
            continue
        out.append(f"### {r['label']} — {r['url']}")
        out.append("```")
        out.append(r["stage1_gemma"]["preview"])
        out.append("```")
        out.append("")

    return "\n".join(out)


def main():
    print("==> Hyperstack benchmark starting...", file=sys.stderr)
    results = run_benchmark()

    out_dir = Path(__file__).parent
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    md = render_markdown(results)
    (out_dir / "RESULTS.md").write_text(md)

    print(f"\n==> Results written to {out_dir}/RESULTS.md", file=sys.stderr)
    print(md)


if __name__ == "__main__":
    main()
