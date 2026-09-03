import json
from pathlib import Path

import pytest

from scripts import full_context_ledger
from scripts.full_context_ledger import (
    build_ledger,
    build_session_guard,
    build_team_accounting,
    inspect_usage_accumulator,
    inspect_usage_suffix,
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


def test_incremental_suffix_matches_full_replay(tmp_path: Path) -> None:
    usage = tmp_path / "codex.jsonl"
    first = {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 2}},
        },
    }
    second = {
        "type": "response_item",
        "payload": {"type": "function_call_output", "output": "synthetic"},
    }
    usage.write_text(json.dumps(first) + "\n")
    accumulator = inspect_usage_accumulator(usage)
    offset = usage.stat().st_size
    usage.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")

    result = inspect_usage_suffix(usage, offset, accumulator)

    assert result is not None
    incremental, cursor = result
    full = inspect_usage_accumulator(usage)
    assert cursor == usage.stat().st_size
    assert incremental == full


def test_incremental_suffix_rejects_partial_line(tmp_path: Path) -> None:
    usage = tmp_path / "codex.jsonl"
    usage.write_text(json.dumps({"usage": {"input_tokens": 10, "output_tokens": 2}}) + "\n")
    accumulator = inspect_usage_accumulator(usage)
    offset = usage.stat().st_size
    with usage.open("a") as handle:
        handle.write('{"usage":')

    assert inspect_usage_suffix(usage, offset, accumulator) is None


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


CACHE_USAGE = {
    "input_tokens": 100,
    "cache_creation_input_tokens": 500,
    "cache_read_input_tokens": 9_000,
    "cached_input_tokens_subset": 0,
    "total_input_tokens": 9_600,
    "output_tokens": 40,
    "reasoning_output_tokens_subset": 0,
    "reported_total_tokens": 9_640,
}


def test_ledger_prices_the_cached_prefix() -> None:
    ledger = build_ledger(CACHE_USAGE, [], "fixture")

    cache = ledger["cache_economics"]
    assert cache["cache_hit_rate_percent"] == 93.75
    assert cache["cache_read_tokens"] == 9_000
    assert cache["cache_write_tokens"] == 500
    assert cache["uncached_input_tokens"] == 100
    # 100 fresh + 500 * 1.25 write + 9000 * 0.1 read.
    assert cache["weighted_input_tokens"] == 1_625.0
    assert cache["nocache_input_tokens"] == 9_600.0
    assert cache["cache_saving_percent"] == 83.07
    assert "not an invoice" in cache["basis"]
    assert "not an invoice" in ledger["method"]["cache_economics"]


def test_ledger_works_without_cache_economics_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(full_context_ledger, "CACHE_ECONOMICS", None)

    ledger = build_ledger(CACHE_USAGE, [], "fixture")

    assert "cache_economics" not in ledger
    assert "cache_economics" not in ledger["method"]
    assert ledger["provider_usage"]["total_input_tokens"] == 9_600
    assert json.loads(serialize_ledger(ledger, "json")) == ledger
    assert "Cache hit rate" not in serialize_ledger(ledger, "markdown")


def test_broken_cache_economics_module_never_breaks_the_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Broken:
        @staticmethod
        def build(usage, profile):
            raise RuntimeError("boom")

    monkeypatch.setattr(full_context_ledger, "CACHE_ECONOMICS", Broken)

    ledger = build_ledger(CACHE_USAGE, [], "fixture")

    assert "cache_economics" not in ledger


def test_markdown_reports_cache_rows() -> None:
    markdown = serialize_ledger(build_ledger(CACHE_USAGE, [], "fixture"), "markdown")

    assert "| Cache hit rate | 93.75% | reported ratio |" in markdown
    assert "| — input served from cache | 9,000 | reported |" in markdown
    assert "| — input written to cache | 500 | reported |" in markdown
    assert "| — fresh input | 100 | reported |" in markdown
    assert "| Weighted input (fresh-equivalents) | 1,625 | list-ratio estimate |" in markdown
    assert "| Same stream with no cache | 9,600 | counterfactual |" in markdown
    assert "| Input saved by cache | 83.07% | list-ratio estimate |" in markdown
    assert "not an invoice" in markdown


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


def _codex_call(call_id: str, cmd: str) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "exec_command",
            "call_id": call_id,
            "arguments": json.dumps({"cmd": cmd}),
        },
    }


def _codex_output(call_id: str, exit_code: int) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": f"Chunk ID: x\nProcess exited with code {exit_code}\nOutput:\n...",
        },
    }


def test_verification_tracks_last_test_exit_status_codex(tmp_path: Path) -> None:
    usage = tmp_path / "codex.jsonl"
    records = [
        {"usage": {"input_tokens": 10, "output_tokens": 2}},
        _codex_call("c1", "uv run pytest -q"),
        _codex_output("c1", 1),
        _codex_call("c2", "ls -la"),
        _codex_output("c2", 1),
        _codex_call("c3", "uv run pytest -q tests/test_x.py"),
        _codex_output("c3", 0),
    ]
    usage.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    accumulator = inspect_usage_accumulator(usage)
    metadata = accumulator["metadata"]
    assert metadata["verify_calls"] == 2
    assert metadata["verify_failures"] == 1
    assert metadata["last_verify_failed"] == 0
    assert accumulator["pending_verify_calls"] == []

    guard = build_session_guard(load_usage(usage), [{"metadata": metadata}])
    assert guard["observed"]["verify_status"] == "green"
    assert "last_verification_failed" not in guard["warnings"]


def test_verification_red_warns_and_marks_saving_unproven_claude(tmp_path: Path) -> None:
    usage = tmp_path / "claude.jsonl"
    records = [
        {
            "type": "assistant",
            "message": {
                "usage": {"input_tokens": 10, "output_tokens": 2},
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": {"command": "cargo test"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "boom",
                        "is_error": True,
                    }
                ]
            },
        },
    ]
    usage.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    accumulator = inspect_usage_accumulator(usage)
    guard = build_session_guard(load_usage(usage), [{"metadata": accumulator["metadata"]}])
    observed = guard["observed"]
    assert (observed["verify_calls"], observed["verify_failures"], observed["verify_status"]) == (
        1,
        1,
        "red",
    )
    assert guard["action"] == "warn"
    assert "last_verification_failed" in guard["warnings"]
    assert "unproven" in serialize_ledger(
        build_ledger(
            load_usage(usage),
            [],
            "claude",
            usage_sources=[
                {
                    "name": "p",
                    "path": "p",
                    "usage": load_usage(usage),
                    "metadata": accumulator["metadata"],
                }
            ],
        ),
        "markdown",
    )


def test_pending_verify_calls_stay_bounded(tmp_path: Path) -> None:
    usage = tmp_path / "codex.jsonl"
    records = [{"usage": {"input_tokens": 10, "output_tokens": 2}}]
    records += [_codex_call(f"c{i}", "pytest") for i in range(50)]
    usage.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    accumulator = inspect_usage_accumulator(usage)
    assert len(accumulator["pending_verify_calls"]) == full_context_ledger.MAX_PENDING_VERIFY
    assert accumulator["metadata"]["verify_calls"] == 0
