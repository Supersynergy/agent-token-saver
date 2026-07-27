from scripts import hook_hotpath_benchmark as bench


def test_percentile_uses_nearest_rank() -> None:
    assert bench.percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert bench.percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_summarize_retains_raw_samples_without_stdout() -> None:
    samples = [
        {
            "wall_ms": 10.0,
            "exit_code": 0,
            "output_bytes": 4,
            "output_sha256": "a",
        },
        {
            "wall_ms": 20.0,
            "exit_code": 0,
            "output_bytes": 4,
            "output_sha256": "a",
        },
        {
            "wall_ms": 30.0,
            "exit_code": 0,
            "output_bytes": 4,
            "output_sha256": "a",
        },
    ]

    summary = bench.summarize(samples)

    assert summary["wall_ms"] == [10.0, 20.0, 30.0]
    assert summary["p50_ms"] == 20.0
    assert summary["p95_ms"] == 30.0
    assert "stdout" not in summary
