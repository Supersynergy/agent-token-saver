from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "integration" / "cli" / "ats-verify"

NOISY_PYTEST = """collected 300 items
tests/test_a.py ....................................................... [ 20%]
tests/test_b.py ....................................................... [ 40%]
tests/test_c.py ....................................................... [ 60%]
=================================== FAILURES ===================================
_________________________________ test_session _________________________________
    def test_session():
>       assert 8080 == 9999
E       assert 8080 == 9999
tests/test_c.py:42: AssertionError
=========================== short test summary info ============================
FAILED tests/test_c.py::test_session - assert 8080 == 9999
2 failed, 298 passed in 12.31s
"""


def run(tmp_path: Path, script: str, exit_code: int, *flags: str):
    command = [
        sys.executable,
        str(VERIFY),
        *flags,
        "--",
        sys.executable,
        "-c",
        f"import sys; sys.stdout.write({script!r}); raise SystemExit({exit_code})",
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        env={**os.environ, "ATS_VERIFY_LOG_DIR": str(tmp_path / "logs")},
        check=False,
    )


def test_red_keeps_every_decisive_line_in_source_order(tmp_path: Path) -> None:
    result = run(tmp_path, NOISY_PYTEST, 1)

    assert result.returncode == 1
    shown = result.stderr
    for signal in ("assert 8080 == 9999", "tests/test_c.py:42", "2 failed, 298 passed"):
        assert signal in shown
    assert shown.index("_________________________________ test_session") < shown.index(
        "2 failed, 298 passed"
    )
    assert len(shown) < len(NOISY_PYTEST)
    assert "ats-verify: red exit=1" in shown


def test_green_is_compact_but_keeps_the_verdict(tmp_path: Path) -> None:
    result = run(tmp_path, "lots of noise\n" * 200 + "288 passed in 44.90s\n", 0)

    assert result.returncode == 0
    assert "288 passed in 44.90s" in result.stdout
    assert len(result.stdout) < 600
    assert result.stderr == ""


def test_a_silent_failure_still_reports_evidence(tmp_path: Path) -> None:
    """The failure mode this wrapper exists for: red with an empty log."""
    result = run(tmp_path, "", 3)

    assert result.returncode == 3
    assert "no output" in result.stderr
    assert "ats-verify: red exit=3" in result.stderr


def test_floor_falls_back_to_raw_tail_when_no_signal_matches(tmp_path: Path) -> None:
    body = "".join(f"opaque line {index}\n" for index in range(50))
    result = run(tmp_path, body, 2, "--floor", "5")

    assert result.returncode == 2
    assert "opaque line 49" in result.stderr
    assert result.stderr.count("opaque line") >= 5


def test_json_mode_is_machine_readable_and_keeps_the_raw_log(tmp_path: Path) -> None:
    result = run(tmp_path, NOISY_PYTEST, 1, "--json")

    payload = json.loads(result.stdout)
    assert payload["status"] == "red"
    assert payload["exit_code"] == 1
    assert payload["total_lines"] == len(NOISY_PYTEST.splitlines())
    raw = Path(payload["raw_log"])
    assert raw.read_text() == NOISY_PYTEST
    assert raw.is_relative_to(tmp_path / "logs")


def test_missing_binary_is_a_named_failure_not_a_crash(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY), "--", "definitely-not-a-real-command"],
        capture_output=True,
        text=True,
        env={**os.environ, "ATS_VERIFY_LOG_DIR": str(tmp_path / "logs")},
        check=False,
    )

    assert result.returncode == 127
    assert "cannot run" in result.stderr


def test_repeated_identical_errors_collapse_with_a_count(tmp_path: Path) -> None:
    result = run(tmp_path, "error: boom\n" * 30, 1)

    assert "(x30)" in result.stderr
    assert result.stderr.count("error: boom") <= 2
