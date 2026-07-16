from scripts.bench_news_agent_stack import est_tokens as news_tokens
from scripts.graph_query_benchmark import est_tokens as graph_tokens
from scripts.token_stack_matrix_benchmark import (
    build_matrix_row,
    extract_version,
    parse_json_object,
    process_fixture,
)


def test_token_proxies_match_bytes_over_four():
    assert news_tokens("12345678") == 2
    assert graph_tokens(b"12345678") == 2


def test_version_extraction_handles_cli_labels_and_prereleases():
    assert extract_version("codex-cli 0.144.3") == "0.144.3"
    assert extract_version("tool version 1.2.3-alpha.4") == "1.2.3-alpha.4"
    assert extract_version("no version here") is None


def test_json_object_parser_fails_closed_to_empty_mapping():
    assert parse_json_object('{"selected": []}') == {"selected": []}
    assert parse_json_object("[]") == {}
    assert parse_json_object("broken") == {}


def test_process_fixture_is_stable_and_contains_acceptance_signal():
    first = process_fixture(12)
    assert first == process_fixture(12)
    assert "critical-worker" in first
    assert len(first.splitlines()) == 13


def test_matrix_row_labels_proxy_input_without_provider_overclaim():
    row = build_matrix_row(
        "lean",
        120,
        8,
        output_is_provider_reported=True,
        accepted=True,
        note="fixture",
    )

    assert row["estimated_visible_input_tokens"] == 120
    assert row["input_measurement"] == "utf8_bytes_div_4_proxy"
    assert row["observed_output_tokens"] == 8
    assert row["output_measurement"] == "provider_reported_average"
    assert row["combined_payload_tokens"] == 128
    assert "provider_input_tokens" not in row
    assert "cost_index_vs_none" not in row
