from __future__ import annotations

from scripts.external_usage_gate import (
    candidate_environment,
    canonical_usage,
    command_parts,
    compare_usage,
    normalize_aiusage,
    normalize_codeburn,
    normalize_splitrail,
    normalize_tokscale,
)

CANONICAL = {
    "input_total": 1_000,
    "input_uncached": 200,
    "cache_read": 800,
    "cache_write": 0,
    "output": 50,
    "reasoning": 10,
}


def test_canonical_codex_usage_treats_cached_input_as_subset() -> None:
    ledger = {
        "provider_usage": {
            "input_tokens": 1_000,
            "total_input_tokens": 1_000,
            "cached_input_tokens_subset": 800,
            "output_tokens": 50,
            "reasoning_output_tokens_subset": 10,
        }
    }

    assert canonical_usage(ledger) == CANONICAL


def test_splitrail_normalization_matches_ledger_semantics() -> None:
    data = {
        "analyzer_stats": [
            {
                "analyzer_name": "Codex CLI",
                "daily_stats": {
                    "2026-07-14": {
                        "stats": {
                            "inputTokens": 200,
                            "cachedTokens": 800,
                            "outputTokens": 50,
                            "reasoningTokens": 10,
                        }
                    }
                },
            }
        ]
    }

    observed = normalize_splitrail(data)

    assert observed == CANONICAL
    assert compare_usage(CANONICAL, observed)["exact"] is True


def test_tokscale_normalization_sums_reasoning_entries() -> None:
    observed = normalize_tokscale(
        {
            "totalInput": 200,
            "totalCacheRead": 800,
            "totalCacheWrite": 0,
            "totalOutput": 50,
            "entries": [{"reasoning": 4}, {"reasoning": 6}],
        }
    )

    assert observed == CANONICAL


def test_codeburn_can_pass_without_reasoning_coverage() -> None:
    observed = normalize_codeburn(
        {
            "overview": {
                "tokens": {
                    "input": 200,
                    "cacheRead": 800,
                    "cacheWrite": 0,
                    "output": 50,
                }
            }
        }
    )

    assert observed["reasoning"] is None
    assert compare_usage(CANONICAL, observed)["exact"] is True


def test_aiusage_raw_export_removes_native_double_count() -> None:
    observed = normalize_aiusage(
        [
            {
                "tool": "codex",
                "inputTokens": 600,
                "cacheReadTokens": 500,
                "outputTokens": 20,
                "thinkingTokens": 4,
            },
            {
                "tool": "codex",
                "inputTokens": 400,
                "cacheReadTokens": 300,
                "outputTokens": 30,
                "thinkingTokens": 6,
            },
        ]
    )

    assert observed == CANONICAL
    assert compare_usage(CANONICAL, observed)["exact"] is True


def test_comparison_rejects_input_mismatch() -> None:
    observed = {**CANONICAL, "input_uncached": 201}

    result = compare_usage(CANONICAL, observed)

    assert result["exact"] is False
    assert result["delta"]["input_uncached"] == 1


def test_package_runners_require_exact_versions() -> None:
    assert command_parts("bunx --bun tokscale@4.0.6")[-1] == "tokscale@4.0.6"

    try:
        command_parts("bunx --bun tokscale@latest")
    except ValueError as error:
        assert "@latest" in str(error)
    else:
        raise AssertionError("latest package command must be rejected")


def test_candidate_environment_does_not_inherit_credentials(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("PATH", "/test/bin")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")

    env = candidate_environment(tmp_path)

    assert env["PATH"] == "/test/bin"
    assert env["HOME"] == str(tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
