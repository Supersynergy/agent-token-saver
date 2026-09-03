"""The benchmark must not reward a documentation lane for saying nothing.

A refusal ("No exact local docs matched") is the smallest output freshdocs can
produce.  Scored naively it would top the savings table, which would rank
"said nothing" above "was correct" -- the exact mistake this repo already made
once when a filter that dropped a failing test looked like a 100% saving.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import benchmark_freshdocs_lane as bench  # noqa: E402

REFUSAL = """FRESHDOCS CONTEXT
query: how do I enable strict mode
libraries: typescript 7.0.2 (explicit/cache version)

No exact local docs matched. Run this command before relying on third-party API details:
freshdocs context "how do I enable strict mode" --sync-stale
"""

ANSWER = """FRESHDOCS CONTEXT
query: how do I add a dev dependency
libraries: uv 0.12.9 (explicit/cache version)

[1] uv 0.12.9 fetched 2026-09-03 exact-ref - Add ipykernel as a dev dependency.
source: https://raw.githubusercontent.com/astral-sh/uv/0.12.9/docs/guides/x.md
Some documentation body.
"""


def test_refusal_is_detected_and_never_counted_as_an_answer() -> None:
    assert bench.REFUSAL_RE.search(REFUSAL)
    assert not bench.REFUSAL_RE.search(ANSWER)


def test_answered_library_and_version_are_read_from_the_pack() -> None:
    assert bench.served_library(ANSWER) == "uv"
    assert bench.context_version(ANSWER, "uv") == "0.12.9"


def test_version_verdict_names_drift_with_both_numbers() -> None:
    assert bench.verdict("0.14.14", "0.14.14") == "match"
    assert bench.verdict("0.12.9", "0.11.5") == "drift(0.12.9 vs 0.11.5)"
    assert bench.verdict(None, "1.0.0") == "no-version"
    assert bench.verdict("1.0.0", None) == "unknown"


def test_markdown_excludes_a_refusal_from_the_savings_columns() -> None:
    payload = {
        "date": "2026-09-03",
        "freshdocs_version": "freshdocs 0.2.0",
        "live_fetches": 0,
        "results": [
            {
                "library": "typescript",
                "mode": "lib",
                "query": "strict mode",
                "answered_from": None,
                "refused": True,
                "on_topic": False,
                "context_tokens": 123,
                "raw_tokens": 0,
                "saved_pct": 0.0,
                "elapsed_ms": 70,
                "sources": 0,
                "installed_version": "7.0.2",
                "served_version": None,
                "fidelity": "no-version",
            },
            {
                "library": "uv",
                "mode": "lib",
                "query": "dev dependency",
                "answered_from": "uv",
                "refused": False,
                "on_topic": True,
                "context_tokens": 923,
                "raw_tokens": 9950,
                "saved_pct": 90.7,
                "elapsed_ms": 70,
                "sources": 3,
                "installed_version": "0.11.5",
                "served_version": "0.12.9",
                "fidelity": "drift(0.12.9 vs 0.11.5)",
            },
        ],
    }
    report = bench.markdown(payload)

    # The refusal row must be labelled as such and claim no saving at all.
    refusal_row = next(line for line in report.splitlines() if line.startswith("| typescript"))
    assert "refusal, not an answer" in refusal_row
    assert refusal_row.count("n/a") >= 2, refusal_row
    assert "%" not in refusal_row, "a refusal must never report a saving percentage"

    # The genuine answer keeps its measured saving.
    answer_row = next(
        line for line in report.splitlines() if line.startswith("| uv | `--lib` | 923")
    )
    assert "90.7%" in answer_row

    assert "Honest refusals: **1 / 2**" in report
    assert "Off-topic answers: **0 / 2**" in report
    assert "Version drift: **1 / 2**" in report
    assert "drift(0.12.9 vs 0.11.5)" in report


def test_token_proxy_matches_the_repo_convention() -> None:
    assert bench.tokens("12345678") == 2
