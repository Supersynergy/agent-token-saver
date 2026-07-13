#!/usr/bin/env python3
"""Compare raw and projected prompt fan-out for a generic JSONL news corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .news_projection import load_jsonl, project
except ImportError:  # direct script execution
    from news_projection import load_jsonl, project


def est_tokens(value: object) -> int:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return max(1, round(len(text.encode()) / 4))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--keywords", default="")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--reviewers", type=int, default=2)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 1 <= args.reviewers <= 8:
        parser.error("--reviewers must be between 1 and 8")
    raw_text = args.input.read_text()
    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    evidence = project(load_jsonl(args.input), keywords, args.top)
    raw = est_tokens(raw_text)
    projected = est_tokens(evidence)
    rows = [
        {"arm": "raw-one-strong", "prompt_tokens": raw, "model_calls": 1},
        {"arm": "topk-one-cheap", "prompt_tokens": projected, "model_calls": 1},
        {
            "arm": "topk-parallel-reviewers",
            "prompt_tokens": projected * args.reviewers,
            "model_calls": args.reviewers,
        },
        {"arm": "deterministic-only", "prompt_tokens": 0, "model_calls": 0},
    ]
    payload = {
        "method": "UTF-8 bytes / 4 prompt proxy; excludes output tokens and optional dissent arbiter",
        "records_raw": len(load_jsonl(args.input)),
        "records_projected": len(evidence),
        "arms": rows,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
