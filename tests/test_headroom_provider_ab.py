from scripts.codex_provider_ab import TASKS
from scripts.headroom_provider_ab import summarize


def arm(total_input: int, cached: int, output: int, accepted: bool) -> dict:
    return {
        "accepted": accepted,
        "usage": {
            "input_tokens": total_input,
            "cached_input_tokens": cached,
            "uncached_input_tokens": total_input - cached,
            "output_tokens": output,
            "total_tokens": total_input + output,
        },
    }


def test_summarize_claims_only_when_both_arms_accept():
    valid = summarize(TASKS[1], {"off": arm(1_000, 100, 10, True), "on": arm(500, 100, 10, True)})
    invalid = summarize(TASKS[1], {"off": arm(1_000, 100, 10, True), "on": arm(1, 0, 1, False)})

    assert valid["accepted"] is True
    assert valid["provider_delta"]["input_saved_percent"] == 50.0
    assert valid["provider_delta"]["uncached_input_saved_percent"] == 55.56
    assert invalid["accepted"] is False
    assert invalid["provider_delta"]["input_saved_percent"] is None
    assert invalid["provider_delta"]["total_saved_percent"] is None


def test_summarize_reports_signed_deltas():
    summary = summarize(
        TASKS[1], {"off": arm(1_000, 100, 10, True), "on": arm(1_200, 100, 20, True)}
    )

    assert summary["provider_delta"]["input_tokens"] == 200
    assert summary["provider_delta"]["output_tokens"] == 10
    assert summary["provider_delta"]["input_saved_percent"] == -20.0
