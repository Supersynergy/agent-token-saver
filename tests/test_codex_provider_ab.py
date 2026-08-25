from scripts.codex_provider_ab import (
    TASKS,
    aggregate,
    parse_codex_jsonl,
    render_markdown,
    summarize_pair,
)


def test_parse_codex_jsonl_extracts_answer_usage_and_commands():
    text = "\n".join(
        [
            '{"type":"item.completed","item":{"type":"command_execution","command":"rtk git diff"}}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"ATS_DIFF_OK"}}',
            '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":40,"output_tokens":5}}',
        ]
    )

    answer, usage, commands = parse_codex_jsonl(text)

    assert answer == "ATS_DIFF_OK"
    assert usage == {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 5}
    assert commands == ["rtk git diff"]


def arm(total_input: int, output: int, accepted: bool, cached: int = 40) -> dict:
    return {
        "accepted": accepted,
        "rtk_observed": False,
        "usage": {
            "input_tokens": total_input,
            "cached_input_tokens": cached,
            "uncached_input_tokens": total_input - cached,
            "output_tokens": output,
            "total_tokens": total_input + output,
        },
    }


def test_aggregate_claims_only_when_every_oracle_passes():
    first = summarize_pair(
        TASKS[0], {"baseline": arm(1_000, 10, True), "lean": arm(500, 10, True)}
    )
    failed = summarize_pair(
        TASKS[1], {"baseline": arm(1_000, 10, True), "lean": arm(1, 1, False)}
    )

    valid = aggregate([first])
    invalid = aggregate([first, failed])

    assert valid["provider_savings_claim_valid"] is True
    assert valid["total_saved_percent"] == 49.5
    assert invalid["provider_savings_claim_valid"] is False
    assert invalid["total_saved_percent"] is None
    assert invalid["ninety_nine_percent_provider_saving"] is False


def test_summarize_pair_reports_weighted_delta_next_to_raw():
    pair = summarize_pair(
        TASKS[0], {"baseline": arm(1_000, 10, True), "lean": arm(500, 10, True)}
    )

    weighted = pair["weighted_delta"]
    # Raw stays visible; weighted is priced against a no-cache counterfactual.
    assert pair["provider_delta"]["input_saved_percent"] == 50.0
    # baseline 960 fresh + 40 read*0.1 = 964; lean 460 + 4 = 464.
    assert weighted["baseline_weighted_input_tokens"] == 964.0
    assert weighted["lean_weighted_input_tokens"] == 464.0
    assert weighted["input_saved_percent"] == 51.87
    assert weighted["total_saved_percent"] == 48.83
    assert weighted["baseline_cache_hit_rate_percent"] == 4.0
    assert weighted["lean_cache_hit_rate_percent"] == 8.0
    assert weighted["cache_hit_rate_delta"] == 4.0
    # Codex harness, so Codex ratios: gpt-5.6-terra, not the Anthropic default.
    assert weighted["profile"]["name"] == "openai-gpt-5.6-terra"
    assert "not an invoice" in weighted["basis"]


def test_weighted_shows_saving_where_raw_shows_regression():
    """Lean converts fresh input into cache reads: raw sum up, bill down."""
    pair = summarize_pair(
        TASKS[0],
        {
            "baseline": arm(10_000, 100, True, cached=0),
            "lean": arm(12_000, 100, True, cached=11_000),
        },
    )

    assert pair["provider_delta"]["input_saved_percent"] == -20.0
    assert pair["provider_delta"]["total_saved_percent"] == -19.8
    # 1,000 fresh + 11,000 reads at 0.1x = 2,100 fresh-equivalents.
    assert pair["weighted_delta"]["lean_weighted_input_tokens"] == 2_100.0
    assert pair["weighted_delta"]["input_saved_percent"] == 79.0
    assert pair["weighted_delta"]["total_saved_percent"] == 74.53

    totals = aggregate([pair])
    assert totals["input_saved_percent"] == -20.0
    assert totals["weighted"]["input_saved_percent"] == 79.0
    assert totals["weighted"]["lean_cache_hit_rate_percent"] == 91.67


def test_render_markdown_shows_raw_and_weighted_and_names_the_profile():
    pair = summarize_pair(
        TASKS[0],
        {
            "baseline": arm(10_000, 100, True, cached=0),
            "lean": arm(12_000, 100, True, cached=11_000),
        },
    )
    markdown = render_markdown(
        {"date": "2026-08-25", "tasks": [pair], "aggregate": aggregate([pair])}
    )

    assert "Input saved (raw)" in markdown
    assert "Input saved (weighted)" in markdown
    assert "-20.00%" in markdown  # raw regression
    assert "79.00%" in markdown  # weighted saving
    assert "Weighted input saved: **79.00%**" in markdown
    assert "profile `openai-gpt-5.6-terra` (verified 2026-08-25)" in markdown
    assert "not an invoice" in markdown
