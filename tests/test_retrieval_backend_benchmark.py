from __future__ import annotations

from scripts import retrieval_backend_benchmark as bench


def test_parse_time_keeps_tool_stderr_separate() -> None:
    metrics, other = bench.parse_time(
        "gmax warning\nreal 0.33\n  0 block input operations\n  12 peak memory footprint\n"
    )
    assert metrics == {"real": 0.33, "block input operations": 0, "peak memory footprint": 12}
    assert other == "gmax warning"


def test_changed_paths_reports_only_metadata_delta() -> None:
    assert bench.changed_paths({"same": (1, 2)}, {"same": (1, 2)}) == []
    assert bench.changed_paths({"old": (1, 1)}, {"new": (2, 2)}) == ["new", "old"]


def test_literal_semantic_probe_is_not_false_positive() -> None:
    probe = next(item for item in bench.PROBES if item.name == "natural_language_tilth")
    assert not bench.passed(probe, "# Search: 0 matches", 0)


def test_gmax_processes_ignores_unrelated_processes(monkeypatch) -> None:
    class Result:
        stdout = "10 1 200 /tmp/gmax-daemon\n11 10 300 gmax-worker\n12 1 400 tilth\n"

    monkeypatch.setattr(bench.subprocess, "run", lambda *args, **kwargs: Result())
    assert bench.gmax_processes() == [
        {"role": "gmax-daemon", "rss_kib": 200},
        {"role": "gmax-worker", "rss_kib": 300},
    ]


def test_public_command_replaces_repo_root() -> None:
    assert bench.public_command(("tilth", "--scope", str(bench.ROOT))) == [
        "tilth",
        "--scope",
        ".",
    ]
