#!/usr/bin/env python3
"""Measure raw graph payload versus a bounded Graphify query."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def est_tokens(value: str | bytes) -> int:
    data = value if isinstance(value, bytes) else value.encode()
    return max(1, round(len(data) / 4))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--budget", type=int, default=800)
    parser.add_argument("--require", action="append", default=[])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    graph = args.graph_json.resolve()
    if graph.name != "graph.json" or graph.parent.name != "graphify-out":
        parser.error("graph_json must end in graphify-out/graph.json")
    started = time.perf_counter()
    result = subprocess.run(
        ["graphify", "query", args.query, "--budget", str(args.budget)],
        cwd=graph.parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    output = result.stdout + result.stderr
    missing = [term for term in args.require if term.lower() not in output.lower()]
    raw_bytes = graph.read_bytes()
    raw_tokens = est_tokens(raw_bytes)
    query_tokens = est_tokens(output)
    payload = {
        "graph": str(graph),
        "query": args.query,
        "budget": args.budget,
        "raw_bytes": len(raw_bytes),
        "raw_est_tokens": raw_tokens,
        "query_est_tokens": query_tokens,
        "reduction_percent": round((1 - query_tokens / raw_tokens) * 100, 2),
        "ratio": round(raw_tokens / query_tokens, 1),
        "elapsed_ms": elapsed_ms,
        "exit_code": result.returncode,
        "missing_required_terms": missing,
        "accepted": result.returncode == 0 and not missing,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
