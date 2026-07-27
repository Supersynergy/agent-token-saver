"""Public benchmark fixtures must stay portable and transcript-free."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ROOT / "data" / "benchmarks" / "graphify-code-only-2026-07-27.json",
    ROOT / "data" / "benchmarks" / "graphify-code-only-2026-07-27.md",
    ROOT / "data" / "benchmarks" / "hook-and-capsule-hotpath-2026-07-27.json",
    ROOT / "data" / "benchmarks" / "hook-and-capsule-hotpath-2026-07-27.md",
    ROOT / "data" / "benchmarks" / "swarm-control-2026-07-27.json",
    ROOT / "data" / "benchmarks" / "swarm-control-2026-07-27.md",
    ROOT / "data" / "benchmarks" / "tilth-vs-gmax-2026-07-27.json",
    ROOT / "data" / "benchmarks" / "tilth-vs-gmax-2026-07-27.md",
)
FORBIDDEN = ("/Users/", "synx prime", '"pid"', '"ppid"', "dry_run_plan")


def test_public_benchmark_artifacts_exclude_host_state_and_transcripts() -> None:
    for artifact in ARTIFACTS:
        text = artifact.read_text()
        assert all(marker not in text for marker in FORBIDDEN), artifact
