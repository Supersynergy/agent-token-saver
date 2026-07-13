from scripts.bench_news_agent_stack import est_tokens as news_tokens
from scripts.graph_query_benchmark import est_tokens as graph_tokens
from scripts.token_stack_matrix_benchmark import (
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
