from scripts import swarm_control_benchmark as bench
from scripts.swarm_control_benchmark import est_tokens, reduction_percent


def test_visible_token_proxy_rounds_up_utf8_bytes() -> None:
    assert est_tokens("1234") == 1
    assert est_tokens("12345") == 2
    assert est_tokens("ä") == 1


def test_reduction_is_bounded_and_handles_empty_baseline() -> None:
    assert reduction_percent(1_000, 250) == 75.0
    assert reduction_percent(0, 1) == 0.0


def test_report_keeps_raw_controller_output_out_of_artifacts(monkeypatch) -> None:
    outputs = iter(['[{"name":"cheap"}]', "lanes: one\nprivate transcript"])
    monkeypatch.setattr(bench, "command_text", lambda _command: next(outputs))
    monkeypatch.setattr(
        bench,
        "worker_context",
        lambda case, _prompt, *, compact: (
            f"delta Tool lane: {case}."
            if compact
            else f"full worker contract with repeated rules Tool lane: {case}."
        ),
    )

    report = bench.make_report("agentmaster")

    assert report["agentmaster"] == {"model_count": 1, "dry_run_has_lanes": True}
    assert "private transcript" not in str(report)
    assert report["acceptance"]["compact_complete_packets_smaller"] is True
    assert (
        report["worker_context"]["routed_capsules_plus_compact_hook"]
        < report["worker_context"]["routed_capsules_plus_full_hook"]
    )
