#!/usr/bin/env python3
"""Price a cached prefix instead of counting raw tokens.

Raw token sums misprice a cached prefix. A policy that converts fresh input
into cache reads lowers the bill while *raising* the raw input count, so an
unweighted comparison reports a regression for a run that actually got
cheaper. This module weights each token class by its published price ratio and
states the saving against an explicit counterfactual.

Ratios, not dollars, are the primary unit: the ratio between cached and fresh
input has been stable across vendor price changes, while absolute prices move
every few months. Absolute USD is available but is always a labelled
list-price estimate, never an invoice.

Verified 2026-08-25 from the vendor pricing table at
https://platform.claude.com/docs/en/build-with-claude/prompt-caching:
every active Claude model prices a 5-minute cache write at 1.25x base input,
a 1-hour write at 2.0x, and a cache read at 0.1x.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PriceProfile:
    """Published price ratios relative to one fresh (uncached) input token."""

    name: str
    cache_read: float
    cache_write: float
    output: float
    source: str
    verified: str
    note: str = ""
    base_input_usd_per_mtok: float | None = None


# Anthropic ratios are read directly off the vendor pricing table; the same
# 1.25x / 0.1x pair holds for every active model, and output is 5x base input
# for Opus 5, Sonnet 5 and Haiku 4.5 alike.
_ANTHROPIC_SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"
_OPENAI_SOURCE = "https://developers.openai.com/api/docs/pricing"

PROFILES: dict[str, PriceProfile] = {
    "anthropic": PriceProfile(
        name="anthropic",
        cache_read=0.1,
        cache_write=1.25,
        output=5.0,
        source=_ANTHROPIC_SOURCE,
        verified="2026-08-25",
        note="5-minute cache write. Ratios identical across active Claude models.",
    ),
    "anthropic-1h": PriceProfile(
        name="anthropic-1h",
        cache_read=0.1,
        cache_write=2.0,
        output=5.0,
        source=_ANTHROPIC_SOURCE,
        verified="2026-08-25",
        note="1-hour TTL cache write at 2.0x base input.",
    ),
    # OpenAI publishes an explicit cache-write price, so a write is no longer
    # free there; the read ratio matches Anthropic's at 0.1x. Output ratios
    # differ per model, so the benchmarked model gets its own profile rather
    # than one averaged "openai" number.
    "openai-gpt-5.6-terra": PriceProfile(
        name="openai-gpt-5.6-terra",
        cache_read=0.1,
        cache_write=1.25,
        output=6.0,
        source=_OPENAI_SOURCE,
        verified="2026-08-25",
        note="Short context: $2.00 input / $0.20 cached / $2.50 write / $12.00 output.",
        base_input_usd_per_mtok=2.0,
    ),
    "openai-gpt-5.6-sol": PriceProfile(
        name="openai-gpt-5.6-sol",
        cache_read=0.1,
        cache_write=1.25,
        output=5.0,
        source=_OPENAI_SOURCE,
        verified="2026-08-25",
        note="Short context: $4.00 input / $0.40 cached / $5.00 write / $20.00 output.",
        base_input_usd_per_mtok=4.0,
    ),
    "openai-gpt-5.6-luna": PriceProfile(
        name="openai-gpt-5.6-luna",
        cache_read=0.1,
        cache_write=1.25,
        output=6.0,
        source=_OPENAI_SOURCE,
        verified="2026-08-25",
        note="Short context: $0.20 input / $0.02 cached / $0.25 write / $1.20 output.",
        base_input_usd_per_mtok=0.2,
    ),
    # Kept for the existing K3 lane benchmark, whose vendor list prices are
    # already pinned in scripts/kimi_k3_lane_benchmark.py.
    "kimi-k3": PriceProfile(
        name="kimi-k3",
        cache_read=0.1,
        cache_write=1.0,
        output=5.0,
        source="scripts/kimi_k3_lane_benchmark.py PRICE_PER_M",
        verified="2026-07-21",
        note="$3 input / $0.30 cache hit / $15 output per MTok.",
        base_input_usd_per_mtok=3.0,
    ),
}

DEFAULT_PROFILE = "anthropic"


def _int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


CAMEL_ALIASES = {
    "inputTokens": "input_tokens",
    "promptTokens": "prompt_tokens",
    "outputTokens": "output_tokens",
    "completionTokens": "completion_tokens",
    "cacheRead": "cache_read_input_tokens",
    "cacheReadInputTokens": "cache_read_input_tokens",
    "cachedInputTokens": "cached_input_tokens",
    "cacheWrite": "cache_creation_input_tokens",
    "cacheCreationInputTokens": "cache_creation_input_tokens",
    "cacheWriteInputTokens": "cache_write_input_tokens",
    "totalInputTokens": "total_input_tokens",
}


KNOWN_COUNTERS = set(CAMEL_ALIASES.values()) | {
    "cached_input_tokens_subset",
    "cache_read_tokens",
    "cache_write_tokens",
    "uncached_input_tokens",
}


def canonical_keys(usage: dict[str, Any]) -> dict[str, Any]:
    """Accept camelCase usage blocks from JS hosts such as GG Coder.

    An unknown key name is not a zero-token turn: reading one as the other
    reports a perfect 0-vs-0 run and hides the very mispricing this module
    exists to catch.
    """
    merged = dict(usage)
    for camel, snake in CAMEL_ALIASES.items():
        if camel in usage and snake not in merged:
            merged[snake] = usage[camel]
    return merged


def normalize_usage(usage: dict[str, Any]) -> dict[str, int]:
    """Fold both vendor usage conventions into one shape.

    Anthropic reports ``input_tokens`` *excluding* cache, with
    ``cache_read_input_tokens`` and ``cache_creation_input_tokens`` alongside
    it. OpenAI and Codex report ``input_tokens`` *including* cache, with
    ``cached_input_tokens`` as a subset of it. Treating one like the other
    silently double-counts or drops the cached prefix, so detect which is in
    play before doing any arithmetic.
    """
    usage = canonical_keys(usage)
    input_tokens = _int(usage.get("input_tokens", usage.get("prompt_tokens")))
    # Anthropic bills cache writes as their own class alongside input_tokens;
    # Codex reports cache_write_input_tokens as a subset of input_tokens, the
    # same way it reports cached_input_tokens. Adding the subset field to the
    # total would double-count it, and ignoring it hides every write.
    disjoint_write = _int(usage.get("cache_creation_input_tokens"))
    subset_write = _int(usage.get("cache_write_input_tokens"))
    cache_write = disjoint_write or subset_write
    explicit_read = _int(usage.get("cache_read_input_tokens"))
    subset_read = _int(usage.get("cached_input_tokens"))
    if not subset_read:
        # full_context_ledger._normalize_usage renames the subset field.
        subset_read = _int(usage.get("cached_input_tokens_subset"))
    cache_read = explicit_read or subset_read

    total_input = _int(usage.get("total_input_tokens"))
    if not total_input:
        if explicit_read or disjoint_write:
            # Anthropic convention: the three classes are disjoint.
            total_input = input_tokens + disjoint_write + explicit_read
        else:
            # Subset convention: input_tokens already contains the cached part.
            total_input = input_tokens
    total_input = max(total_input, cache_read + cache_write)

    return {
        "total_input_tokens": total_input,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "uncached_input_tokens": max(0, total_input - cache_read - cache_write),
        "output_tokens": _int(usage.get("output_tokens", usage.get("completion_tokens"))),
    }


def resolve_profile(profile: str | PriceProfile | None) -> PriceProfile:
    if isinstance(profile, PriceProfile):
        return profile
    key = (profile or DEFAULT_PROFILE).strip().lower()
    if key not in PROFILES:
        known = ", ".join(sorted(PROFILES))
        raise KeyError(f"unknown price profile {key!r}; known profiles: {known}")
    return PROFILES[key]


def weighted_input(usage: dict[str, int], profile: PriceProfile) -> float:
    """Input tokens expressed in fresh-input-equivalents."""
    return (
        usage["uncached_input_tokens"]
        + usage["cache_write_tokens"] * profile.cache_write
        + usage["cache_read_tokens"] * profile.cache_read
    )


def cache_hit_rate(usage: dict[str, int]) -> float | None:
    """Share of input tokens served from cache, or None when there is no input."""
    total = usage["total_input_tokens"]
    if total <= 0:
        return None
    return round(usage["cache_read_tokens"] / total * 100, 2)


def diagnose(usage: dict[str, int]) -> dict[str, str]:
    """Name the cache failure mode the counters describe.

    A hit rate alone does not say whether a run is broken: a prefix that is
    re-written every turn reports a low rate and a *negative* saving, which
    reads like a rounding detail rather than the 1.25x penalty it is. The two
    documented causes are a breakpoint that drifts past the vendor lookback
    window and a mid-wave tool, catalog or compaction change that invalidates
    the prefix from the first changed token.
    """
    read = usage["cache_read_tokens"]
    write = usage["cache_write_tokens"]
    if usage["total_input_tokens"] <= 0:
        return {"verdict": "unknown", "detail": "no input tokens in this record"}
    if not read and not write:
        return {
            "verdict": "uncached",
            "detail": "no cached prefix at all; every input token billed fresh",
        }
    if not read:
        return {
            "verdict": "write-only",
            "detail": (
                f"{write:,} tokens written to cache, none read back. Expected once on a "
                "cold start; across a run it means the prefix is re-written every turn "
                "at the write ratio. Check breakpoint placement, lookback drift and "
                "mid-wave tool or catalog changes."
            ),
        }
    if write > read:
        return {
            "verdict": "rewriting",
            "detail": (
                f"{write:,} written vs {read:,} read: the prefix changes faster than it "
                "is reused, so cache writes cost more than the reads save."
            ),
        }
    return {
        "verdict": "healthy",
        "detail": f"{read:,} tokens served from cache against {write:,} written",
    }


def build(usage: dict[str, Any], profile: str | PriceProfile | None = None) -> dict[str, Any]:
    """Cache economics for one usage record."""
    resolved = resolve_profile(profile)
    normalized = normalize_usage(usage)

    weighted_in = weighted_input(normalized, resolved)
    weighted_out = normalized["output_tokens"] * resolved.output
    # Counterfactual: the same token stream with no cache at all, so every
    # input token is billed fresh at 1.0x. This is what the saving is against.
    nocache_in = float(normalized["total_input_tokens"])

    saving = None
    if nocache_in > 0:
        saving = round((1 - weighted_in / nocache_in) * 100, 2)

    economics: dict[str, Any] = {
        **normalized,
        "cache_hit_rate_percent": cache_hit_rate(normalized),
        "diagnosis": diagnose(normalized),
        "weighted_input_tokens": round(weighted_in, 2),
        "weighted_output_tokens": round(weighted_out, 2),
        "weighted_total_tokens": round(weighted_in + weighted_out, 2),
        "nocache_input_tokens": round(nocache_in, 2),
        "cache_saving_percent": saving,
        "profile": {
            "name": resolved.name,
            "cache_read_ratio": resolved.cache_read,
            "cache_write_ratio": resolved.cache_write,
            "output_ratio": resolved.output,
            "source": resolved.source,
            "verified": resolved.verified,
            "note": resolved.note,
        },
        "basis": (
            "List-ratio estimate against a no-cache counterfactual, not an invoice. "
            "Provider counters remain authoritative."
        ),
    }
    if resolved.base_input_usd_per_mtok is not None:
        economics["est_cost_usd_list"] = round(
            (weighted_in + weighted_out) * resolved.base_input_usd_per_mtok / 1_000_000, 6
        )
    return economics


def _percent_delta(baseline: float, candidate: float) -> float | None:
    if baseline <= 0:
        return None
    return round((1 - candidate / baseline) * 100, 2)


def compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    profile: str | PriceProfile | None = None,
) -> dict[str, Any]:
    """Weighted A/B comparison of two usage records.

    Raw token deltas are kept alongside the weighted ones precisely because
    they can disagree: shifting fresh input into cache reads raises the raw
    input count while lowering the weighted cost.
    """
    resolved = resolve_profile(profile)
    base = build(baseline, resolved)
    cand = build(candidate, resolved)
    return {
        "baseline": base,
        "candidate": cand,
        "weighted_input_saved_percent": _percent_delta(
            base["weighted_input_tokens"], cand["weighted_input_tokens"]
        ),
        "weighted_total_saved_percent": _percent_delta(
            base["weighted_total_tokens"], cand["weighted_total_tokens"]
        ),
        "raw_input_saved_percent": _percent_delta(
            base["total_input_tokens"], cand["total_input_tokens"]
        ),
        "cache_hit_rate_delta": (
            None
            if base["cache_hit_rate_percent"] is None or cand["cache_hit_rate_percent"] is None
            else round(cand["cache_hit_rate_percent"] - base["cache_hit_rate_percent"], 2)
        ),
        "profile": base["profile"],
    }


def _fmt_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def render_line(economics: dict[str, Any]) -> str:
    """One-line summary, short enough for a statusline."""
    hit = _fmt_percent(economics["cache_hit_rate_percent"])
    saved = _fmt_percent(economics["cache_saving_percent"])
    verdict = economics["diagnosis"]["verdict"]
    return (
        f"cache {hit} hit | "
        f"{economics['cache_read_tokens']:,} read / "
        f"{economics['cache_write_tokens']:,} write / "
        f"{economics['uncached_input_tokens']:,} fresh | "
        f"weighted in {economics['weighted_input_tokens']:,.0f} "
        f"vs {economics['nocache_input_tokens']:,.0f} uncached ({saved} saved)"
        + ("" if verdict == "healthy" else f" | {verdict}")
    )


def render_markdown(economics: dict[str, Any]) -> str:
    profile = economics["profile"]
    lines = [
        "## Cache economics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Input tokens (total) | {economics['total_input_tokens']:,} |",
        f"| — served from cache | {economics['cache_read_tokens']:,} |",
        f"| — written to cache | {economics['cache_write_tokens']:,} |",
        f"| — fresh | {economics['uncached_input_tokens']:,} |",
        f"| Cache hit rate | {_fmt_percent(economics['cache_hit_rate_percent'])} |",
        f"| Verdict | {economics['diagnosis']['verdict']} |",
        f"| Output tokens | {economics['output_tokens']:,} |",
        f"| Weighted input (fresh-equivalents) | {economics['weighted_input_tokens']:,.0f} |",
        f"| Same stream with no cache | {economics['nocache_input_tokens']:,.0f} |",
        f"| Input saved by cache | {_fmt_percent(economics['cache_saving_percent'])} |",
        f"| Weighted total (incl. output) | {economics['weighted_total_tokens']:,.0f} |",
    ]
    if "est_cost_usd_list" in economics:
        lines.append(f"| List-price estimate | ${economics['est_cost_usd_list']:.6f} |")
    lines.extend(
        [
            "",
            f"Ratios: cache read {profile['cache_read_ratio']}x, "
            f"cache write {profile['cache_write_ratio']}x, "
            f"output {profile['output_ratio']}x base input "
            f"(profile `{profile['name']}`, verified {profile['verified']}).",
            "",
            economics["diagnosis"]["detail"],
            "",
            economics["basis"],
        ]
    )
    return "\n".join(lines) + "\n"


def _load(source: str) -> dict[str, Any]:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object of usage counters")
    # Accept a whole ledger as well as a bare usage record.
    for key in ("usage", "totals", "provider_usage"):
        nested = data.get(key)
        if isinstance(nested, dict):
            data = nested
            break
    if not KNOWN_COUNTERS & set(canonical_keys(data)):
        raise ValueError(
            "no known token counters in this payload; "
            "expected input_tokens/cache_read_input_tokens or their camelCase form"
        )
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Weight provider usage by published cache price ratios.",
    )
    parser.add_argument(
        "usage",
        nargs="?",
        default="-",
        help="JSON file of usage counters, or - for stdin (default: -)",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        choices=sorted(PROFILES),
        help=f"price ratio profile (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--against",
        help="second usage JSON to compare the first against as a baseline",
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=("markdown", "json", "line"),
        help="output format (default: markdown)",
    )
    args = parser.parse_args(argv)

    try:
        usage = _load(args.usage)
        if args.against:
            payload: dict[str, Any] = compare(_load(args.against), usage, args.profile)
        else:
            payload = build(usage, args.profile)
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as error:
        print(f"cache_economics: {error}", file=sys.stderr)
        return 1

    if args.format == "json":
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    elif args.format == "line":
        print(render_line(payload.get("candidate", payload)))
    else:
        if args.against:
            sys.stdout.write(render_markdown(payload["candidate"]))
            sys.stdout.write(
                "\nWeighted vs baseline: "
                f"input {_fmt_percent(payload['weighted_input_saved_percent'])} saved, "
                f"total {_fmt_percent(payload['weighted_total_saved_percent'])} saved "
                f"(raw input {_fmt_percent(payload['raw_input_saved_percent'])}).\n"
            )
        else:
            sys.stdout.write(render_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
