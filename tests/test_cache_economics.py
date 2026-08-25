"""Cache economics: weighting, both usage conventions, and A/B comparison."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import cache_economics as ce  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cache_economics.py"


# --- normalization: the two vendor conventions must not be conflated --------


def test_anthropic_convention_treats_classes_as_disjoint():
    """input_tokens excludes cache, so total is the sum of all three."""
    usage = ce.normalize_usage(
        {
            "input_tokens": 100,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 9_000,
            "output_tokens": 42,
        }
    )
    assert usage["total_input_tokens"] == 9_600
    assert usage["cache_read_tokens"] == 9_000
    assert usage["cache_write_tokens"] == 500
    assert usage["uncached_input_tokens"] == 100
    assert usage["output_tokens"] == 42


def test_openai_convention_treats_cached_as_subset():
    """input_tokens already includes the cached part; do not add it twice."""
    usage = ce.normalize_usage(
        {"input_tokens": 10_000, "cached_input_tokens": 9_000, "output_tokens": 42}
    )
    assert usage["total_input_tokens"] == 10_000
    assert usage["cache_read_tokens"] == 9_000
    assert usage["uncached_input_tokens"] == 1_000


def test_ledger_subset_field_name_is_accepted():
    """full_context_ledger renames the subset field; honour that spelling."""
    usage = ce.normalize_usage(
        {"input_tokens": 10_000, "cached_input_tokens_subset": 4_000}
    )
    assert usage["cache_read_tokens"] == 4_000
    assert usage["uncached_input_tokens"] == 6_000


def test_explicit_total_input_is_respected():
    usage = ce.normalize_usage(
        {"input_tokens": 100, "cache_read_input_tokens": 900, "total_input_tokens": 1_000}
    )
    assert usage["total_input_tokens"] == 1_000
    assert usage["uncached_input_tokens"] == 100


def test_totals_never_go_negative_on_inconsistent_input():
    usage = ce.normalize_usage(
        {"total_input_tokens": 10, "cache_read_input_tokens": 900, "input_tokens": -5}
    )
    assert usage["uncached_input_tokens"] == 0
    assert usage["total_input_tokens"] >= usage["cache_read_tokens"]


# --- weighting --------------------------------------------------------------


def test_weighted_input_applies_published_ratios():
    """1000 fresh + 1000 write@1.25 + 10000 read@0.1 = 1000 + 1250 + 1000."""
    economics = ce.build(
        {
            "input_tokens": 1_000,
            "cache_creation_input_tokens": 1_000,
            "cache_read_input_tokens": 10_000,
            "output_tokens": 0,
        },
        "anthropic",
    )
    assert economics["weighted_input_tokens"] == pytest.approx(3_250.0)
    assert economics["nocache_input_tokens"] == pytest.approx(12_000.0)
    assert economics["cache_saving_percent"] == pytest.approx(72.92, abs=0.01)


def test_one_hour_profile_doubles_the_write_ratio():
    usage = {"input_tokens": 0, "cache_creation_input_tokens": 1_000}
    five_minute = ce.build(usage, "anthropic")
    one_hour = ce.build(usage, "anthropic-1h")
    assert five_minute["weighted_input_tokens"] == pytest.approx(1_250.0)
    assert one_hour["weighted_input_tokens"] == pytest.approx(2_000.0)


def test_hit_rate_is_share_of_total_input():
    economics = ce.build({"input_tokens": 10_000, "cached_input_tokens": 9_500})
    assert economics["cache_hit_rate_percent"] == pytest.approx(95.0)


def test_hit_rate_is_none_without_input():
    assert ce.build({"output_tokens": 10})["cache_hit_rate_percent"] is None
    assert ce.build({"output_tokens": 10})["cache_saving_percent"] is None


def test_output_is_weighted_into_the_total():
    economics = ce.build({"input_tokens": 100, "output_tokens": 100}, "anthropic")
    assert economics["weighted_output_tokens"] == pytest.approx(500.0)
    assert economics["weighted_total_tokens"] == pytest.approx(600.0)


def test_profile_provenance_is_carried_into_the_result():
    profile = ce.build({"input_tokens": 1})["profile"]
    assert profile["cache_read_ratio"] == 0.1
    assert profile["cache_write_ratio"] == 1.25
    assert profile["verified"] == "2026-08-25"
    assert profile["source"].startswith("https://")


def test_openai_profiles_match_their_published_prices():
    """Ratios must stay derivable from the vendor's per-MTok list prices.

    OpenAI charges an explicit 1.25x cache write, so a write is not free there;
    output differs per model, which is why each model gets its own profile.
    """
    published = {  # (input, cached, write, output) USD per MTok, short context
        "openai-gpt-5.6-terra": (2.00, 0.20, 2.50, 12.00),
        "openai-gpt-5.6-sol": (4.00, 0.40, 5.00, 20.00),
        "openai-gpt-5.6-luna": (0.20, 0.02, 0.25, 1.20),
    }
    for name, (base, cached, write, output) in published.items():
        profile = ce.PROFILES[name]
        assert profile.cache_read == pytest.approx(cached / base)
        assert profile.cache_write == pytest.approx(write / base)
        assert profile.output == pytest.approx(output / base)
        assert profile.base_input_usd_per_mtok == pytest.approx(base)


def test_anthropic_profiles_keep_the_documented_write_premium():
    assert ce.PROFILES["anthropic"].cache_write == 1.25  # 5-minute TTL
    assert ce.PROFILES["anthropic-1h"].cache_write == 2.0  # 1-hour TTL
    assert ce.PROFILES["anthropic"].cache_read == ce.PROFILES["anthropic-1h"].cache_read


def test_unknown_profile_is_rejected():
    with pytest.raises(KeyError):
        ce.build({"input_tokens": 1}, "no-such-profile")


def test_estimate_is_labelled_as_not_an_invoice():
    assert "not an invoice" in ce.build({"input_tokens": 1})["basis"]


# --- the regression this module exists to prevent ---------------------------


def test_shifting_fresh_input_into_cache_reads_reads_as_a_saving():
    """The core bug: raw counts call this a regression, weighting does not.

    Both arms do the same work. The candidate moves 9k fresh input tokens into
    cache reads and pays a one-off write. Raw input goes *up*; the bill goes
    down.
    """
    baseline = {"input_tokens": 10_000, "output_tokens": 500}
    candidate = {
        "input_tokens": 1_000,
        "cache_creation_input_tokens": 1_000,
        "cache_read_input_tokens": 9_000,
        "output_tokens": 500,
    }
    result = ce.compare(baseline, candidate, "anthropic")

    assert result["raw_input_saved_percent"] < 0  # raw says "worse"
    assert result["weighted_input_saved_percent"] > 0  # weighted says "cheaper"
    assert result["cache_hit_rate_delta"] > 0


def test_compare_reports_none_against_an_empty_baseline():
    result = ce.compare({}, {"input_tokens": 10})
    assert result["weighted_input_saved_percent"] is None
    assert result["raw_input_saved_percent"] is None


# --- rendering --------------------------------------------------------------


def test_render_line_is_single_line_and_names_the_classes():
    line = ce.render_line(ce.build({"input_tokens": 10_000, "cached_input_tokens": 9_000}))
    assert "\n" not in line
    assert "read" in line and "write" in line and "fresh" in line


def test_render_markdown_states_ratios_and_counterfactual():
    markdown = ce.render_markdown(ce.build({"input_tokens": 10_000, "cached_input_tokens": 9_000}))
    assert "Cache hit rate" in markdown
    assert "no cache" in markdown
    assert "not an invoice" in markdown
    assert "0.1x" in markdown


def test_render_handles_a_missing_hit_rate():
    assert "n/a" in ce.render_line(ce.build({"output_tokens": 5}))


# --- CLI --------------------------------------------------------------------


def _run(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_cli_reads_stdin_and_emits_json():
    result = _run(["-", "--format", "json"], json.dumps({"input_tokens": 100}))
    assert result.returncode == 0
    assert json.loads(result.stdout)["total_input_tokens"] == 100


def test_cli_unwraps_a_nested_usage_block():
    payload = json.dumps({"usage": {"input_tokens": 10_000, "cached_input_tokens": 9_000}})
    result = _run(["-", "--format", "json"], payload)
    assert json.loads(result.stdout)["cache_hit_rate_percent"] == pytest.approx(90.0)


def test_cli_compares_two_files(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"input_tokens": 10_000}))
    candidate.write_text(
        json.dumps({"input_tokens": 1_000, "cache_read_input_tokens": 9_000})
    )
    result = _run([str(candidate), "--against", str(baseline), "--format", "json"])
    assert result.returncode == 0
    assert json.loads(result.stdout)["weighted_input_saved_percent"] > 0


def test_cli_fails_cleanly_on_malformed_json():
    result = _run(["-"], "not json")
    assert result.returncode == 1
    assert "cache_economics:" in result.stderr


def test_cli_fails_cleanly_on_a_missing_file():
    result = _run(["/nonexistent/usage.json"])
    assert result.returncode == 1
