#!/usr/bin/env python3
"""Turn workflow benchmark evidence into a fail-closed offline policy report.

The report never changes a host default. Deterministic transformations may be
recommended when their executable oracle passes. Model or prompt changes stay
on the current full arm until sample, workload-diversity, and quality gates pass.
Adaptive routing additionally requires pre-treatment features, logged arms and
propensities, deterministic quality labels, and a chronological holdout.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.cache_economics import build as build_cache_economics
except ModuleNotFoundError:  # Direct execution from scripts/.
    from cache_economics import build as build_cache_economics


USAGE_FIELDS = (
    "inputTokens",
    "cacheRead",
    "cacheWrite",
    "outputTokens",
    "reasoningTokens",
    "turns",
    "providerDurationMs",
)


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def _percent_delta(candidate: float, baseline: float) -> float | None:
    if baseline <= 0:
        return None
    return round((candidate / baseline - 1) * 100, 2)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def aggregate_prompt_cells(paths: list[Path]) -> list[dict[str, Any]]:
    """Merge additive prompt-bench cells from independent schema-v4 runs."""
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in paths:
        report = load_object(path)
        if int(report.get("schemaVersion") or 0) < 4:
            raise ValueError(f"prompt-bench schema v4 required: {path}")
        cells = report.get("cells")
        if not isinstance(cells, list):
            raise ValueError(f"prompt-bench cells missing: {path}")
        for raw in cells:
            if not isinstance(raw, dict):
                raise ValueError(f"invalid prompt-bench cell: {path}")
            try:
                key = tuple(str(raw[field]) for field in ("target", "section", "task", "variant"))
            except KeyError as error:
                raise ValueError(f"prompt-bench cell missing {error.args[0]}: {path}") from error
            if key not in merged:
                merged[key] = {
                    "target": key[0],
                    "section": key[1],
                    "task": key[2],
                    "variant": key[3],
                    "iterations": 0,
                    "errors": 0,
                    "checkPass": {},
                    "usage": {field: 0.0 for field in USAGE_FIELDS},
                    "sources": [],
                }
            cell = merged[key]
            cell["iterations"] += int(_number(raw.get("iterations")))
            cell["errors"] += int(_number(raw.get("errors")))
            checks = raw.get("checkPass")
            if not isinstance(checks, dict):
                raise ValueError(f"prompt-bench checkPass missing: {path}")
            for name, count in checks.items():
                cell["checkPass"][str(name)] = cell["checkPass"].get(str(name), 0) + int(
                    _number(count)
                )
            usage = raw.get("usage")
            if not isinstance(usage, dict):
                raise ValueError(f"prompt-bench usage missing: {path}")
            for field in USAGE_FIELDS:
                cell["usage"][field] += _number(usage.get(field))
            cell["sources"].append(str(path.resolve()))
    return sorted(merged.values(), key=lambda row: (row["target"], row["task"], row["variant"]))


def cell_quality_passes(cell: dict[str, Any]) -> bool:
    iterations = int(cell["iterations"])
    checks = cell["checkPass"]
    return (
        iterations > 0
        and int(cell["errors"]) == 0
        and bool(checks)
        and all(int(count) == iterations for count in checks.values())
    )


def summarize_cell(cell: dict[str, Any], price_profile: str) -> dict[str, Any]:
    iterations = int(cell["iterations"])
    usage = cell["usage"]
    economics = build_cache_economics(usage, price_profile)
    processed = usage["inputTokens"] + usage["cacheRead"] + usage["cacheWrite"]
    divisor = iterations or 1
    return {
        **{field: cell[field] for field in ("target", "section", "task", "variant")},
        "iterations": iterations,
        "errors": int(cell["errors"]),
        "quality_pass": cell_quality_passes(cell),
        "rubric_passes": int(sum(cell["checkPass"].values())),
        "rubric_total": iterations * len(cell["checkPass"]),
        "averages": {
            "processed_input_tokens": round(processed / divisor, 2),
            "weighted_total_fresh_input_equivalents": round(
                float(economics["weighted_total_tokens"]) / divisor, 2
            ),
            "output_tokens": round(usage["outputTokens"] / divisor, 2),
            "turns": round(usage["turns"] / divisor, 2),
            "provider_duration_ms": round(usage["providerDurationMs"] / divisor, 2),
        },
        "price_profile": {
            "name": economics["profile"]["name"],
            "verified": economics["profile"]["verified"],
            "source": economics["profile"]["source"],
            "basis": economics["basis"],
        },
        "sources": cell["sources"],
    }


def compare_prompt_arms(
    paths: list[Path],
    *,
    price_profile: str,
    min_trials_per_cell: int,
    max_latency_regression_percent: float,
) -> list[dict[str, Any]]:
    cells = [summarize_cell(cell, price_profile) for cell in aggregate_prompt_cells(paths)]
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        groups[(cell["target"], cell["section"], cell["task"])].append(cell)
    comparisons: list[dict[str, Any]] = []
    for (target, section, task), rows in sorted(groups.items()):
        baseline = next((row for row in rows if row["variant"] == f"{section}.full"), None)
        if baseline is None:
            raise ValueError(f"full baseline missing for {target}/{task}")
        for candidate in (row for row in rows if row is not baseline):
            base_avg = baseline["averages"]
            cand_avg = candidate["averages"]
            quality_equal = baseline["quality_pass"] and candidate["quality_pass"]
            sample_gate = (
                min(baseline["iterations"], candidate["iterations"]) >= min_trials_per_cell
            )
            weighted_delta = _percent_delta(
                cand_avg["weighted_total_fresh_input_equivalents"],
                base_avg["weighted_total_fresh_input_equivalents"],
            )
            latency_delta = _percent_delta(
                cand_avg["provider_duration_ms"], base_avg["provider_duration_ms"]
            )
            if not quality_equal:
                decision = "reject_quality_regression"
            elif not sample_gate:
                decision = "hold_full_insufficient_sample"
            elif weighted_delta is None or weighted_delta >= 0:
                decision = "keep_full_no_weighted_cost_gain"
            elif latency_delta is not None and latency_delta > max_latency_regression_percent:
                decision = "keep_full_latency_regression"
            else:
                decision = "candidate_for_more_shadow_tasks"
            comparisons.append(
                {
                    "target": target,
                    "section": section,
                    "task": task,
                    "baseline": baseline,
                    "candidate": candidate,
                    "quality_equal": quality_equal,
                    "sample_gate": {
                        "pass": sample_gate,
                        "required_trials_per_cell": min_trials_per_cell,
                        "observed_min_trials": min(baseline["iterations"], candidate["iterations"]),
                    },
                    "candidate_delta_percent": {
                        "processed_input": _percent_delta(
                            cand_avg["processed_input_tokens"], base_avg["processed_input_tokens"]
                        ),
                        "weighted_total": weighted_delta,
                        "output": _percent_delta(
                            cand_avg["output_tokens"], base_avg["output_tokens"]
                        ),
                        "turns": _percent_delta(cand_avg["turns"], base_avg["turns"]),
                        "provider_duration": latency_delta,
                    },
                    "decision": decision,
                }
            )
    return comparisons


def matrix_policy(matrix: dict[str, Any]) -> dict[str, Any]:
    if matrix.get("schema") != "agent-token-saver.workflow-matrix-benchmark":
        raise ValueError("workflow matrix schema mismatch")
    rows = {row["name"]: row for row in matrix.get("offline_matrix", [])}
    baseline = rows.get("baseline_raw")
    projected = rows.get("exact_projection")
    warm = rows.get("exact_projection_plus_warm_recall_cache")
    if not baseline or not projected or not warm:
        raise ValueError("workflow matrix required arms missing")
    baseline_tokens = _number(baseline.get("parent_plus_children_proxy_tokens"))
    projected_tokens = _number(projected.get("parent_plus_children_proxy_tokens"))
    shapes = matrix.get("worker_shapes") or {}
    single = shapes.get("single_local_worker") or {}
    parallel = shapes.get("parallel_local_workers") or {}
    live_requested = bool((matrix.get("acceptance") or {}).get("live_requested"))
    live_accepted = (matrix.get("acceptance") or {}).get("live_accepted")
    live_arms = matrix.get("live_arms") if isinstance(matrix.get("live_arms"), list) else []
    accepted_live = [
        str(row.get("name")) for row in live_arms if isinstance(row, dict) and row.get("accepted")
    ]
    failed_live = [
        str(row.get("name"))
        for row in live_arms
        if isinstance(row, dict) and not row.get("accepted")
    ]
    return {
        "deterministic_projection": {
            "decision": "adopt_for_supported_exact_parsers"
            if projected.get("accepted")
            else "blocked_oracle_failed",
            "proxy_reduction_percent": (
                round((1 - projected_tokens / baseline_tokens) * 100, 2)
                if baseline_tokens
                else None
            ),
            "measurement": "utf8_bytes_div_4_proxy_not_provider_tokens",
        },
        "exact_recall": {
            "decision": "adopt_only_on_exact_fingerprint_hit"
            if warm.get("accepted") and int(warm.get("calls_started") or 0) == 0
            else "blocked_oracle_failed",
            "observed_cache_hits": int(warm.get("cache_hits") or 0),
        },
        "rtk": {
            "decision": "fallback_filter_only_when_supported_and_smaller",
            "reason": "exact projection is smaller in this fixture; RTK remains a source-aware fallback",
        },
        "micro_operation_shape": {
            "decision": "single_worker"
            if _number(single.get("wall_ms_median")) <= _number(parallel.get("wall_ms_median"))
            else "parallel_workers",
            "single_median_ms": single.get("wall_ms_median"),
            "parallel_median_ms": parallel.get("wall_ms_median"),
            "scope": "three deterministic local micro-operations; wall time only",
        },
        "live_provider_gate": {
            "requested": live_requested,
            "accepted": live_accepted,
            "accepted_arms": accepted_live,
            "failed_arms": failed_live,
            "decision": (
                "accepted_for_this_exact_oracle"
                if live_requested and live_accepted
                else "partial_local_pass_remote_blocked"
                if live_requested and accepted_live and failed_live
                else "blocked_live_arm_failed"
                if live_requested
                else "not_measured"
            ),
        },
    }


def adaptive_policy(audit: dict[str, Any] | None) -> dict[str, Any]:
    if audit is None:
        return {"decision": "blocked_no_audit", "activation_allowed": False}
    requirements = {
        "pre_treatment_features": bool(audit.get("has_pre_treatment_features")),
        "workflow_arm": bool(audit.get("has_workflow_arm")),
        "propensity": bool(audit.get("has_propensity")),
        "deterministic_quality_label": bool(audit.get("has_deterministic_quality_label")),
        "chronological_holdout": bool(audit.get("has_chronological_holdout")),
        "train_per_arm_at_least_30": int(_number(audit.get("min_train_per_arm"))) >= 30,
        "test_per_arm_at_least_10": int(_number(audit.get("min_test_per_arm"))) >= 10,
        "quality_lower_95_ci_positive": _number(audit.get("quality_lift_lower_95_ci")) > 0,
        "no_raw_prompts_in_training_rows": int(_number(audit.get("raw_prompt_meta_rows"))) == 0,
    }
    allowed = all(requirements.values())
    return {
        "decision": "shadow_candidate_only" if allowed else "blocked_insufficient_safe_labels",
        "activation_allowed": False,
        "requirements": requirements,
        "observed": audit,
        "next_gate": (
            "independent review before any activation"
            if allowed
            else "log redacted pre-treatment features, arm, propensity, deterministic quality, and chronological holdout"
        ),
        "engine": "SuperML/AutoLearn may race offline only after these gates; never train directly on raw prompts",
    }


def build_policy(
    matrix: dict[str, Any],
    prompt_paths: list[Path],
    audit: dict[str, Any] | None,
    *,
    price_profile: str = "anthropic",
    min_trials_per_cell: int = 10,
    min_tasks_per_default: int = 3,
    max_latency_regression_percent: float = 10.0,
) -> dict[str, Any]:
    comparisons = compare_prompt_arms(
        prompt_paths,
        price_profile=price_profile,
        min_trials_per_cell=min_trials_per_cell,
        max_latency_regression_percent=max_latency_regression_percent,
    )
    eligible = [row for row in comparisons if row["decision"] == "candidate_for_more_shadow_tasks"]
    by_variant: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in eligible:
        by_variant[(row["target"], row["section"], row["candidate"]["variant"])] += 1
    default_candidates = [
        {"target": key[0], "section": key[1], "variant": key[2], "eligible_tasks": count}
        for key, count in sorted(by_variant.items())
        if count >= min_tasks_per_default
    ]
    return {
        "schema": "agent-token-saver.workflow-policy",
        "schema_version": 1,
        "mode": "offline_report_only",
        "changes_runtime_defaults": False,
        "gates": {
            "min_trials_per_cell": min_trials_per_cell,
            "min_independent_tasks_per_default": min_tasks_per_default,
            "max_latency_regression_percent": max_latency_regression_percent,
            "quality_first": True,
        },
        "matrix_policy": matrix_policy(matrix),
        "prompt_comparisons": comparisons,
        "default_prompt_candidates": default_candidates,
        "prompt_default_decision": (
            "candidate_requires_independent_review"
            if default_candidates
            else "keep_current_full_defaults"
        ),
        "adaptive_policy": adaptive_policy(audit),
        "workflow_order": [
            "project_or_filter_raw_input with an executable completeness oracle",
            "reuse only an exact content fingerprint",
            "run one capable model by default",
            "parallelize only independent operations when their measured duration exceeds bootstrap overhead",
            "use sequential tiers only for true stage dependencies",
            "use controller plus workers only for independently bounded long lanes and sum every usage source",
            "change a default only after quality, sample, temporal holdout, latency, token-class, and cost gates",
        ],
    }


def markdown(policy: dict[str, Any]) -> str:
    matrix = policy["matrix_policy"]
    lines = [
        "# Offline workflow policy",
        "",
        "Report-only. No runtime default or model selector was changed.",
        "",
        "## Deterministic path",
        "",
        f"- Projection: `{matrix['deterministic_projection']['decision']}` "
        f"({matrix['deterministic_projection']['proxy_reduction_percent']}% local proxy reduction).",
        f"- Exact recall: `{matrix['exact_recall']['decision']}`.",
        f"- RTK: `{matrix['rtk']['decision']}`.",
        f"- Micro-operation shape: `{matrix['micro_operation_shape']['decision']}`; "
        f"single {matrix['micro_operation_shape']['single_median_ms']} ms versus parallel "
        f"{matrix['micro_operation_shape']['parallel_median_ms']} ms median.",
        f"- Live provider gate: `{matrix['live_provider_gate']['decision']}`.",
        "",
        "## Prompt comparisons",
        "",
        "| Target | Task | Candidate | N/cell | Quality | Processed input delta | Weighted total delta | Provider-time delta | Decision |",
        "|---|---|---|---:|:--:|---:|---:|---:|---|",
    ]
    for row in policy["prompt_comparisons"]:
        delta = row["candidate_delta_percent"]
        n = row["sample_gate"]["observed_min_trials"]
        lines.append(
            f"| {row['target']} | {row['task']} | {row['candidate']['variant']} | {n} | "
            f"{'yes' if row['quality_equal'] else 'no'} | {delta['processed_input']}% | "
            f"{delta['weighted_total']}% | {delta['provider_duration']}% | `{row['decision']}` |"
        )
    lines.extend(
        [
            "",
            f"Prompt default: **{policy['prompt_default_decision']}**.",
            "",
            "## Adaptive gate",
            "",
            f"Decision: **{policy['adaptive_policy']['decision']}**. Activation allowed: **no**.",
            "",
            "## Operating order",
            "",
        ]
    )
    lines.extend(f"{index}. {step}." for index, step in enumerate(policy["workflow_order"], 1))
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ats-workflow-policy")
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--prompt-bench", required=True, action="append", type=Path)
    parser.add_argument("--adaptive-audit", type=Path)
    parser.add_argument("--price-profile", default="anthropic")
    parser.add_argument("--min-trials-per-cell", type=int, default=10)
    parser.add_argument("--min-tasks-per-default", type=int, default=3)
    parser.add_argument("--max-latency-regression-percent", type=float, default=10.0)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_trials_per_cell < 1 or args.min_tasks_per_default < 1:
        raise SystemExit("sample gates must be positive integers")
    try:
        policy = build_policy(
            load_object(args.matrix),
            args.prompt_bench,
            load_object(args.adaptive_audit) if args.adaptive_audit else None,
            price_profile=args.price_profile,
            min_trials_per_cell=args.min_trials_per_cell,
            min_tasks_per_default=args.min_tasks_per_default,
            max_latency_regression_percent=args.max_latency_regression_percent,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n")
    args.out_md.write_text(markdown(policy))
    print(json.dumps({"json": str(args.out_json), "markdown": str(args.out_md)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
