import json
from pathlib import Path

from scripts.full_context_ledger import (
    build_ledger,
    build_session_guard,
    build_team_accounting,
    load_components,
    load_usage,
    load_usage_sources,
    serialize_ledger,
)


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


def test_compact_json_is_lossless_and_smaller() -> None:
    ledger = {
        "provider_usage": {"input_tokens": 100, "output_tokens": 5},
        "usage_sources": [{"name": "parent", "path": "/tmp/run.jsonl"}],
    }

    pretty = serialize_ledger(ledger, "json")
    compact = serialize_ledger(ledger, "json-compact")

    assert json.loads(pretty) == json.loads(compact) == ledger
    assert len(compact.encode()) < len(pretty.encode())


def test_codex_jsonl_prefers_cumulative_total_over_last_request(tmp_path: Path) -> None:
    usage = tmp_path / "codex.jsonl"
    usage.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1_950_578,
                                    "cached_input_tokens": 1_806_848,
                                    "output_tokens": 12_761,
                                    "reasoning_output_tokens": 3_180,
                                    "total_tokens": 1_963_339,
                                },
                                "last_token_usage": {
                                    "input_tokens": 142_021,
                                    "cached_input_tokens": 132_864,
                                    "output_tokens": 460,
                                    "reasoning_output_tokens": 39,
                                    "total_tokens": 142_481,
                                },
                            },
                        },
                    }
                ),
                json.dumps({"type": "event_msg", "payload": {"type": "task_complete"}}),
            ]
        )
        + "\n"
    )

    parsed = load_usage(usage)

    assert parsed["total_input_tokens"] == 1_950_578
    assert parsed["output_tokens"] == 12_761
    assert parsed["reported_total_tokens"] == 1_963_339
    assert parsed["cached_input_tokens_subset"] == 1_806_848


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


def test_parent_and_child_usage_are_aggregated(tmp_path: Path) -> None:
    parent = tmp_path / "parent.jsonl"
    child = tmp_path / "child.jsonl"
    parent.write_text(json.dumps({"usage": {"input_tokens": 100, "output_tokens": 10}}))
    child.write_text(json.dumps({"usage": {"input_tokens": 40, "output_tokens": 5}}))

    total, sources = load_usage_sources([f"parent={parent}", f"child={child}"])

    assert total["total_input_tokens"] == 140
    assert total["output_tokens"] == 15
    assert total["reported_total_tokens"] == 155
    assert [source["name"] for source in sources] == ["parent", "child"]


def test_team_accounting_detects_missing_spawned_worker_usage(tmp_path: Path) -> None:
    parent = tmp_path / "parent.jsonl"
    parent.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "spawn_agent",
                            "arguments": "{}",
                        },
                    }
                ),
                json.dumps({"usage": {"input_tokens": 100, "output_tokens": 10}}),
            ]
        )
        + "\n"
    )
    _, sources = load_usage_sources([f"parent={parent}"])

    accounting = build_team_accounting(sources)

    assert accounting == {
        "observed_usage_sources": 1,
        "detected_spawned_workers": 1,
        "expected_usage_sources": 2,
        "missing_usage_sources": 1,
        "complete": False,
    }


def test_duplicate_usage_source_is_rejected(tmp_path: Path) -> None:
    usage = tmp_path / "usage.json"
    usage.write_text(json.dumps({"usage": {"input_tokens": 10, "output_tokens": 1}}))

    try:
        load_usage_sources([f"parent={usage}", f"child={usage}"])
    except ValueError as error:
        assert "duplicate usage source" in str(error)
    else:
        raise AssertionError("duplicate usage source must fail closed")


def test_session_guard_requires_checkpoint_for_context_rot(tmp_path: Path) -> None:
    usage = tmp_path / "long.jsonl"
    records = [
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 25_000_000,
                        "cached_input_tokens": 20_000_000,
                        "output_tokens": 1_000,
                        "total_tokens": 25_001_000,
                    }
                },
            },
        },
        {"type": "response_item", "payload": {"type": "compaction"}},
        {"type": "response_item", "payload": {"type": "compaction"}},
    ]
    usage.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    total, sources = load_usage_sources([f"parent={usage}"])

    guard = build_session_guard(total, sources)

    assert guard["action"] == "checkpoint_required"
    assert "provider_total_tokens>=25000000" in guard["reasons"]
    assert "compactions>=2" in guard["reasons"]


def test_duplicate_visible_components_are_reported(tmp_path: Path) -> None:
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_bytes(b"x" * 80)
    two.write_bytes(b"x" * 80)
    components = load_components([f"parent-rules={one}", f"child-rules={two}"])
    usage = {
        "input_tokens": 100,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cached_input_tokens_subset": 0,
        "total_input_tokens": 100,
        "output_tokens": 0,
        "reasoning_output_tokens_subset": 0,
        "reported_total_tokens": 100,
    }

    ledger = build_ledger(usage, components, "fixture")

    assert ledger["estimated_visible_input_tokens"] == 40
    assert ledger["duplicate_visible_input_tokens"] == 20
    assert ledger["unique_visible_input_tokens"] == 20
