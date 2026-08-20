#!/usr/bin/env python3
"""Validate the default lane rotation against measured ledger outcomes.

The cost routing policy (docs/COST_ROUTING_POLICY.md) claims an ordering.
This script is the oracle for that claim: it reads the llmadapter ledger and
fails if the policy names a lane the measurements do not support.

Exit codes:
    0  policy matches the ledger
    1  at least one violation (a denied lane is rostered, a rostered lane
       fails its reliability floor, or a tier is ordered slower-first)
    2  the ledger is missing or unreadable

Run it through the project env — this repo targets Python 3.11 and the system
interpreter may be older:

    uv run scripts/lane_policy_check.py
    uv run scripts/lane_policy_check.py --window-days 14 --json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

LEDGER_GLOB = "~/.agent-token-saver/ledger/llmadapter-*.jsonl"

# --- policy under test -----------------------------------------------------
# Ordered fastest-acceptable-first WITHIN a tier. The tiers themselves are
# ordered by marginal cost, not by speed: a subscription call is already paid
# for, so it outranks a free call that costs nothing but answers worse.
#
# Every lane here must clear MIN_OK_RATE over the window, or this check fails.
# That is the point: the roster is a claim about measured behaviour.

TIERS: dict[str, list[str]] = {
    # Tier 1 — flat-rate subscriptions. Marginal cost 0 until the plan's own
    # limit. Top-model quality, so these lead for anything that matters.
    "subscription": [
        "claude-haiku",
        "claude-sonnet",
        "claude-opus",
    ],
    # Tier 2 — free OpenRouter lanes. Cost 0, quality below the subscription
    # models. Used for breadth (fan out one question over many opinions) and
    # for a second, independent verifier — not as the primary answer.
    #
    # Rostered on LIFETIME evidence, ordered fastest-first. An earlier roster
    # was picked from a 7-day window and put laguna-s-2.1 (43% lifetime, 26/61)
    # and gemma-4-26b-a4b-it (70%, 78/112) ahead of lanes that are both faster
    # and more reliable over the full record. A window that thin ranks noise.
    "free_fanout": [
        "nemotron-3-nano-omni-30b-a3b-reasoning",  # 89% (31/35), 4.9s
        "nemotron-nano-12b-v2-vl",  # 80% (24/30), 5.3s
        "laguna-xs-2.1",  # 81% (21/26), 7.7s
        "nemotron-3-super-120b-a12b",  # 94% (325/347), 14.3s — aggregator
    ],
}

# Tiers whose whole point is redundancy: the fanout asks several lanes at once,
# so a single lane missing an answer is absorbed by design. These are judged on
# COMBINED availability (see MIN_TIER_AVAILABILITY) on top of the per-lane
# floor, which is the stricter test for a group — not a softer one.
REDUNDANT_TIERS = {"free_fanout"}

# Lanes kept OUT of the default rotation, each with the measurement that
# earned the exclusion. Re-probe before removing an entry from this map.
DENYLIST: dict[str, str] = {
    "ling-3.0-flash": "free slug retired by provider; 0/5 over the window and a live probe returns 'This model is unavailable for free'",
    "gpt-oss-120b": "openrouter credit balance is 0 — live probe returns quota/'Insufficient credits'",
    "gpt-5.6-luna": "openrouter credit balance is 0 — live probe returns quota/'Insufficient credits'",
    "ling-2.6-flash": "openrouter paid band, same zero balance",
    "deepseek-v4-flash-0731": "openrouter paid band, same zero balance",
    "qwen3.7-flash": "openrouter paid band, same zero balance",
    "gpt-5.6-luna-pro": "openrouter paid band, same zero balance",
    "kat-coder-air-v2.5": "openrouter paid band, same zero balance",
    "kimi-k2.5": "openrouter paid band, same zero balance",
    "kimi-k2.7-code": "openrouter paid band, same zero balance",
    "kimi-k3": "openrouter paid band, same zero balance; 0/5 lifetime",
    "gemma-4-31b-it": "9 consecutive exec failures; free endpoint present in catalog but non-functional",
    "laguna-m.1": "removed from provider catalog ('No endpoints found')",
    "gpt-luna": "1/2 lifetime and a live probe fails exec; ChatGPT plan is at its usage limit",
    "agy": "0/1 lifetime, no successful call on record",
    "ollama-gemma4": "local model — excluded by operator preference, not by measurement",
    "gemma4-31b-fast": "local model — excluded by operator preference, not by measurement",
    "nemotron-nano-9b-v2": "56% lifetime (9/16); recovered only after the reasoning-off fix, sample too thin to roster",
    "gpt-oss-20b": "51% lifetime (67/131), still 9/11 in-window — usable as an extra fanout voice, not as a rostered default",
    "laguna-s-2.1": "43% lifetime (26/61) and 17.4s — slower AND less reliable than every rostered fanout lane",
    "gemma-4-26b-a4b-it": "70% lifetime (78/112) at 13.5s — beaten on both axes by the rostered lanes",
    "nemotron-3-nano-30b-a3b": "fastest lane in a 7d window (1.2s, 12/12) but 77% lifetime (78/101); re-probe, it is the strongest promotion candidate",
    "north-mini-code": "49% lifetime (20/41)",
    "nemotron-3-ultra-550b-a55b": "90% lifetime (43/48) but 23.5s — reliable and slow; hold for depth work, not for fanout breadth",
}

# A rostered lane must hold at least this success rate over the window,
# provided it has at least MIN_SAMPLES calls to judge.
#
# A subscription lane answers alone, so it carries the full floor. A fanout
# lane is one voice of several; it gets a lower per-lane floor AND an extra
# group check the solo lanes never face.
MIN_OK_RATE = 0.80
MIN_OK_RATE_REDUNDANT = 0.65
MIN_SAMPLES = 2

# For a redundant tier: probability that at least one rostered lane answers,
# assuming independent failures. Four lanes at 80% give 1 - 0.2^4 = 99.8%.
# A tier that cannot clear this is not redundant, it is just unreliable.
MIN_TIER_AVAILABILITY = 0.99

# Within a SEQUENTIAL tier, a lane may not be slower than the one after it by
# more than this factor. Keeps the roster honest about "fastest first" without
# failing on normal jitter.
ORDER_SLACK = 1.5

# Ceiling for a lane in a parallel fanout tier. A fanout finishes when its
# slowest lane does, so a lane above this makes the whole fanout slower than
# simply asking claude-haiku (19.7s measured), which defeats the purpose.
MAX_FANOUT_SECONDS = 20.0


def ledger_paths() -> list[Path]:
    return sorted(Path(p) for p in glob.glob(os.path.expanduser(LEDGER_GLOB)))


def load_stats(paths: list[Path], window_days: int) -> dict[str, dict[str, Any]]:
    """Aggregate per-lane outcomes, lifetime and inside the window."""
    # Ledger stamps are date-prefixed strings, so a plain local date is the
    # right granularity — and it keeps the script runnable on the system
    # interpreter, not only the project's 3.11 env.
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"all_n": 0, "all_ok": 0, "win_n": 0, "win_ok": 0, "ms": []}
    )
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                lane = row.get("lane")
                if not lane:
                    continue
                ok = bool(row.get("ok"))
                entry = stats[lane]
                entry["all_n"] += 1
                entry["all_ok"] += int(ok)
                stamp = str(row.get("ts") or row.get("time") or "")[:10]
                if stamp >= cutoff:
                    entry["win_n"] += 1
                    entry["win_ok"] += int(ok)
                    if ok and isinstance(row.get("ms"), (int, float)):
                        entry["ms"].append(float(row["ms"]))
    for entry in stats.values():
        entry["avg_s"] = (
            round(sum(entry["ms"]) / len(entry["ms"]) / 1000, 1) if entry["ms"] else None
        )
    return stats


def check(stats: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    notes: list[str] = []

    rostered = {lane for lanes in TIERS.values() for lane in lanes}

    # 1. A denied lane must not appear in the roster.
    for lane in sorted(rostered & DENYLIST.keys()):
        violations.append(f"{lane}: rostered but on the denylist ({DENYLIST[lane]})")

    # 2. A rostered lane must clear the reliability floor for its tier.
    for tier, lanes in TIERS.items():
        floor = MIN_OK_RATE_REDUNDANT if tier in REDUNDANT_TIERS else MIN_OK_RATE
        for lane in lanes:
            entry = stats.get(lane)
            if not entry or entry["win_n"] < MIN_SAMPLES:
                have = entry["win_n"] if entry else 0
                notes.append(f"{tier}/{lane}: only {have} call(s) in window — unproven, not failed")
                continue
            rate = entry["win_ok"] / entry["win_n"]
            if rate < floor:
                violations.append(
                    f"{tier}/{lane}: {entry['win_ok']}/{entry['win_n']} = {rate:.0%} in window, "
                    f"below the {floor:.0%} floor"
                )

    # 2b. A redundant tier must clear a combined-availability bar. One weak
    # lane is tolerable; a roster that fails together is not redundant.
    for tier in REDUNDANT_TIERS & TIERS.keys():
        judged = [
            stats[lane]
            for lane in TIERS[tier]
            if lane in stats and stats[lane]["win_n"] >= MIN_SAMPLES
        ]
        if not judged:
            notes.append(f"{tier}: no lane has enough calls in window to judge availability")
            continue
        miss = 1.0
        for entry in judged:
            miss *= 1 - (entry["win_ok"] / entry["win_n"])
        availability = 1 - miss
        if availability < MIN_TIER_AVAILABILITY:
            violations.append(
                f"{tier}: combined availability {availability:.2%} over {len(judged)} judged "
                f"lane(s), below the {MIN_TIER_AVAILABILITY:.0%} bar"
            )

    # 3. Latency, judged by how the tier is actually executed.
    #
    # A sequential tier is tried in order, so the order has to be fastest
    # first. A redundant tier fans out in PARALLEL — the order is not an
    # execution order at all, and ranking it would be measuring noise. What
    # matters there is the slowest lane, because a fanout finishes when its
    # laggard does.
    for tier, lanes in TIERS.items():
        timed = [(lane, stats.get(lane, {}).get("avg_s")) for lane in lanes]
        timed = [(lane, secs) for lane, secs in timed if secs is not None]
        if tier in REDUNDANT_TIERS:
            for lane, secs in timed:
                if secs > MAX_FANOUT_SECONDS:
                    violations.append(
                        f"{tier}/{lane}: {secs}s exceeds the {MAX_FANOUT_SECONDS}s fanout "
                        f"ceiling — slower than answering on the subscription lane"
                    )
            continue
        for (a_lane, a_secs), (b_lane, b_secs) in zip(timed, timed[1:], strict=False):
            if a_secs > b_secs * ORDER_SLACK:
                violations.append(
                    f"{tier}: {a_lane} ({a_secs}s) is ordered before {b_lane} ({b_secs}s) "
                    f"but is more than {ORDER_SLACK}x slower"
                )

    # 4. A denied lane that has recovered is worth surfacing, not failing on.
    for lane, reason in sorted(DENYLIST.items()):
        entry = stats.get(lane)
        if entry and entry["win_n"] >= MIN_SAMPLES:
            rate = entry["win_ok"] / entry["win_n"]
            if rate >= MIN_OK_RATE:
                notes.append(
                    f"{lane}: denied ({reason.split(';')[0]}) but now {entry['win_ok']}/{entry['win_n']} "
                    f"= {rate:.0%} in window — re-probe before rostering"
                )

    return violations, notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--window-days", type=int, default=7, help="measurement window (default: 7)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    paths = ledger_paths()
    if not paths:
        print(f"no ledger found at {LEDGER_GLOB}", file=sys.stderr)
        return 2

    stats = load_stats(paths, args.window_days)
    violations, notes = check(stats)

    if args.json:
        print(
            json.dumps(
                {
                    "window_days": args.window_days,
                    "ledgers": [str(p) for p in paths],
                    "violations": violations,
                    "notes": notes,
                    "lanes": {
                        lane: {k: v for k, v in entry.items() if k != "ms"}
                        for lane, entry in sorted(stats.items())
                    },
                },
                indent=2,
            )
        )
        return 1 if violations else 0

    print(f"lane policy check · window {args.window_days}d · {len(paths)} ledger file(s)\n")
    for tier, lanes in TIERS.items():
        print(f"[{tier}]")
        for lane in lanes:
            entry = stats.get(lane)
            if not entry:
                print(f"  {lane:38} no ledger record")
                continue
            win = f"{entry['win_ok']}/{entry['win_n']}"
            allt = f"{entry['all_ok']}/{entry['all_n']}"
            avg = f"{entry['avg_s']}s" if entry["avg_s"] is not None else "-"
            print(f"  {lane:38} {win:>7} in window · {allt:>7} lifetime · {avg:>7}")
        print()

    if notes:
        print("notes:")
        for note in notes:
            print(f"  · {note}")
        print()

    if violations:
        print("VIOLATIONS:")
        for violation in violations:
            print(f"  ✗ {violation}")
        return 1

    print(f"OK — roster matches the ledger ({len(TIERS)} tiers, {len(DENYLIST)} lanes denied)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
