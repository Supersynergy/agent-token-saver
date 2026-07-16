from scripts.codex_provider_ab import (
    TASKS,
    aggregate,
    parse_codex_jsonl,
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


def arm(total_input: int, output: int, accepted: bool) -> dict:
    return {
        "accepted": accepted,
        "usage": {
            "input_tokens": total_input,
            "cached_input_tokens": 40,
            "uncached_input_tokens": total_input - 40,
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
