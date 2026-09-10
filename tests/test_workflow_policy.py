import json
from pathlib import Path

from scripts import workflow_policy


def prompt_report(path: Path, *, iterations: int, candidate_output: int = 50) -> Path:
    cells = []
    for variant, usage in (
        (
            "work.full",
            {
                "inputTokens": 100,
                "cacheRead": 900,
                "cacheWrite": 100,
                "outputTokens": 100,
                "reasoningTokens": 0,
                "turns": 20,
                "providerDurationMs": 2000,
            },
        ),
        (
            "work.tiny",
            {
                "inputTokens": 80,
                "cacheRead": 500,
                "cacheWrite": 80,
                "outputTokens": candidate_output,
                "reasoningTokens": 0,
                "turns": 10,
                "providerDurationMs": 1500,
            },
        ),
    ):
        cells.append(
            {
                "target": "claude-test",
                "section": "work",
                "task": "work/exact",
                "variant": variant,
                "iterations": iterations,
                "errors": 0,
                "checkPass": {"exact": iterations},
                "usage": usage,
            }
        )
    path.write_text(json.dumps({"schemaVersion": 4, "status": "pass", "cells": cells}))
    return path


def matrix_report() -> dict:
    return {
        "schema": "agent-token-saver.workflow-matrix-benchmark",
        "offline_matrix": [
            {"name": "baseline_raw", "parent_plus_children_proxy_tokens": 1000},
            {
                "name": "exact_projection",
                "parent_plus_children_proxy_tokens": 100,
                "accepted": True,
            },
            {
                "name": "exact_projection_plus_warm_recall_cache",
                "accepted": True,
                "calls_started": 0,
                "cache_hits": 3,
            },
        ],
        "worker_shapes": {
            "single_local_worker": {"wall_ms_median": 1.0},
            "parallel_local_workers": {"wall_ms_median": 2.0},
        },
        "acceptance": {"live_requested": True, "live_accepted": False},
    }


def test_small_sample_keeps_full_even_when_candidate_is_cheaper(tmp_path: Path) -> None:
    report = prompt_report(tmp_path / "n5.json", iterations=5)

    policy = workflow_policy.build_policy(matrix_report(), [report], None)

    comparison = policy["prompt_comparisons"][0]
    assert comparison["quality_equal"]
    assert comparison["candidate_delta_percent"]["weighted_total"] < 0
    assert comparison["decision"] == "hold_full_insufficient_sample"
    assert policy["prompt_default_decision"] == "keep_current_full_defaults"
    assert not policy["changes_runtime_defaults"]


def test_additive_runs_reach_sample_gate_without_overwriting(tmp_path: Path) -> None:
    first = prompt_report(tmp_path / "n4.json", iterations=4)
    second = prompt_report(tmp_path / "n6.json", iterations=6)

    rows = workflow_policy.compare_prompt_arms(
        [first, second],
        price_profile="anthropic",
        min_trials_per_cell=10,
        max_latency_regression_percent=10.0,
    )

    assert rows[0]["sample_gate"] == {
        "pass": True,
        "required_trials_per_cell": 10,
        "observed_min_trials": 10,
    }
    assert rows[0]["decision"] == "candidate_for_more_shadow_tasks"


def test_quality_failure_rejects_a_shorter_candidate(tmp_path: Path) -> None:
    report = prompt_report(tmp_path / "failed.json", iterations=10)
    value = json.loads(report.read_text())
    value["cells"][1]["checkPass"]["exact"] = 9
    report.write_text(json.dumps(value))

    rows = workflow_policy.compare_prompt_arms(
        [report],
        price_profile="anthropic",
        min_trials_per_cell=10,
        max_latency_regression_percent=10.0,
    )

    assert rows[0]["decision"] == "reject_quality_regression"


def test_adaptive_gate_blocks_raw_prompt_history_without_logged_arms() -> None:
    audit = {
        "raw_prompt_meta_rows": 598,
        "has_pre_treatment_features": False,
        "has_workflow_arm": False,
        "has_propensity": False,
        "has_deterministic_quality_label": False,
        "has_chronological_holdout": False,
        "min_train_per_arm": 0,
        "min_test_per_arm": 0,
        "quality_lift_lower_95_ci": 0,
    }

    result = workflow_policy.adaptive_policy(audit)

    assert result["decision"] == "blocked_insufficient_safe_labels"
    assert not result["activation_allowed"]
    assert not result["requirements"]["no_raw_prompts_in_training_rows"]


def test_matrix_policy_never_calls_proxy_a_provider_saving() -> None:
    result = workflow_policy.matrix_policy(matrix_report())

    assert result["deterministic_projection"]["proxy_reduction_percent"] == 90.0
    assert result["deterministic_projection"]["measurement"].endswith("not_provider_tokens")
    assert result["micro_operation_shape"]["decision"] == "single_worker"
    assert result["live_provider_gate"]["decision"] == "blocked_live_arm_failed"


def test_matrix_policy_separates_green_local_from_blocked_remote() -> None:
    matrix = matrix_report()
    matrix["live_arms"] = [
        {"name": "local_single_cold", "accepted": True},
        {"name": "cheap_parallel_three", "accepted": False},
    ]

    result = workflow_policy.matrix_policy(matrix)["live_provider_gate"]

    assert result["decision"] == "partial_local_pass_remote_blocked"
    assert result["accepted_arms"] == ["local_single_cold"]
    assert result["failed_arms"] == ["cheap_parallel_three"]
