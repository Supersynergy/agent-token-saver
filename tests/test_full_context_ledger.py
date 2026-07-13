import json
from pathlib import Path

from scripts.full_context_ledger import build_ledger, load_components, load_usage


def test_codex_cached_tokens_are_a_subset(tmp_path: Path) -> None:
    usage = tmp_path / "codex.jsonl"
    usage.write_text(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 40,
                    "output_tokens": 20,
                    "reasoning_output_tokens": 5,
                },
            }
        )
        + "\n"
    )
    parsed = load_usage(usage)
    assert parsed["total_input_tokens"] == 100
    assert parsed["reported_total_tokens"] == 120
    assert parsed["cached_input_tokens_subset"] == 40


def test_claude_cache_fields_add_to_total_input(tmp_path: Path) -> None:
    usage = tmp_path / "claude.json"
    usage.write_text(
        json.dumps(
            {
                "usage": {
                    "input_tokens": 2,
                    "cache_creation_input_tokens": 30,
                    "cache_read_input_tokens": 20,
                    "output_tokens": 4,
                }
            }
        )
    )
    parsed = load_usage(usage)
    assert parsed["total_input_tokens"] == 52
    assert parsed["reported_total_tokens"] == 56


def test_ledger_exposes_unattributed_host_context(tmp_path: Path) -> None:
    rules = tmp_path / "AGENTS.md"
    rules.write_bytes(b"x" * 80)
    components = load_components([f"rules={rules}"])
    ledger = build_ledger(
        {
            "input_tokens": 100,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cached_input_tokens_subset": 0,
            "total_input_tokens": 100,
            "output_tokens": 5,
            "reasoning_output_tokens_subset": 0,
            "reported_total_tokens": 105,
        },
        components,
        "fixture",
    )
    assert ledger["estimated_visible_input_tokens"] == 20
    assert ledger["unattributed_input_tokens"] == 80
    assert ledger["attribution_coverage_percent"] == 20.0
