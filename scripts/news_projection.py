#!/usr/bin/env python3
"""Deduplicate and rank JSONL news into bounded evidence packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = re.compile(r"^(?:utm_.+|fbclid|gclid|mc_cid|mc_eid)$", re.I)
SPACE = re.compile(r"\s+")


def canonical_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return value.strip()
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not TRACKING.match(k)))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def clean_text(value: Any, limit: int) -> str:
    return SPACE.sub(" ", str(value or "")).strip()[:limit]


def parse_time(value: str) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def normalize(record: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    url = canonical_url(str(record.get("url") or record.get("link") or ""))
    title = clean_text(record.get("title") or record.get("headline"), 240)
    text = clean_text(record.get("summary") or record.get("text") or record.get("content"), 1200)
    source = clean_text(record.get("source") or record.get("publisher"), 120)
    published = clean_text(
        record.get("published_at") or record.get("published") or record.get("date"), 80
    )
    haystack = f"{title} {text}".lower()
    hits = sorted({keyword for keyword in keywords if keyword.lower() in haystack})
    primary = bool(record.get("primary_source") or record.get("official"))
    score = len(hits) * 10 + (8 if primary else 0) + (3 if url.startswith("https://") else 0)
    identity = url or title.lower()
    return {
        "id": hashlib.sha256(identity.encode()).hexdigest()[:16],
        "url": url,
        "title": title,
        "summary": text,
        "source": source,
        "published_at": published,
        "primary_source": primary,
        "keyword_hits": hits,
        "score": score,
        "_time": parse_time(published),
    }


def project(
    records: Iterable[dict[str, Any]], keywords: list[str], top: int
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        item = normalize(record, keywords)
        if not item["url"] and not item["title"]:
            continue
        previous = deduped.get(item["id"])
        if previous is None or (item["score"], item["_time"]) > (
            previous["score"],
            previous["_time"],
        ):
            deduped[item["id"]] = item
    ranked = sorted(
        deduped.values(), key=lambda item: (item["score"], item["_time"], item["id"]), reverse=True
    )
    for item in ranked:
        item.pop("_time", None)
    return ranked[:top]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    handle = sys.stdin if str(path) == "-" else path.open()
    try:
        rows = []
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {number}: expected JSON object")
            rows.append(value)
        return rows
    finally:
        if handle is not sys.stdin:
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--keywords", default="")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--format", choices=("jsonl", "json"), default="jsonl")
    args = parser.parse_args()
    if not 1 <= args.top <= 500:
        parser.error("--top must be between 1 and 500")
    keywords = [value.strip() for value in args.keywords.split(",") if value.strip()]
    rows = project(load_jsonl(args.input), keywords, args.top)
    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
