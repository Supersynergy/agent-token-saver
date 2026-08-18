"""Public benchmark fixtures must stay portable and transcript-free."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "data" / "benchmarks"
SUFFIXES = {".json", ".jsonl", ".md"}
# Absolute home paths leak the maintainer's username and unrelated private
# project names; the rest is host state that must never ship in a public repo.
FORBIDDEN = ("/Users/", "/home/", "synx prime", '"pid"', '"ppid"', "dry_run_plan")


def _artifacts() -> list[Path]:
    return sorted(p for p in BENCHMARKS.rglob("*") if p.is_file() and p.suffix in SUFFIXES)


def test_benchmark_scan_is_not_vacuous() -> None:
    # Guards the guard: an empty scan would make the assertion below meaningless.
    assert len(_artifacts()) >= 8


def test_public_benchmark_artifacts_exclude_host_state_and_transcripts() -> None:
    offenders = {
        str(artifact.relative_to(ROOT)): [
            marker for marker in FORBIDDEN if marker in artifact.read_text()
        ]
        for artifact in _artifacts()
    }
    assert not {path: hits for path, hits in offenders.items() if hits}
