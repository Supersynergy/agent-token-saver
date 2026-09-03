"""Per-filter proof that the compact-on-green / complete-on-red contract holds.

RTK 0.46 ships a per-tool `pipe` filter for most verification tools.  These are
adopted by measurement, never by assertion: for every tool we run the same
fixture through `ats-verify` and require that the emitted projection still
names the failure and preserves the exit code.  When RTK is absent, or its
filter would drop the evidence, the builtin projection must carry the run.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "integration" / "cli" / "ats-verify"
HAS_RTK = shutil.which("rtk") is not None

# tool -> (argv, green fixture, red fixture, signals that must survive red)
# Signals are chosen to be rendering-independent: a filter may regroup or
# re-label a diagnostic (RTK's mypy filter prints a file header plus `L31:`
# rather than `file.py:31:`), but it may never lose the file, the location or
# the reason.  Asserting the exact byte layout would test RTK's formatting
# instead of the contract that matters here.
FILTERS: dict[str, tuple[list[str], str, str, tuple[str, ...]]] = {
    "pytest": (
        ["pytest", "-q"],
        "tests/test_a.py ....\n4 passed in 0.31s\n",
        (
            "tests/test_a.py .F..\n"
            "=================================== FAILURES ===================================\n"
            "________________________________ test_session __________________________________\n"
            ">       assert 8080 == 9999\n"
            "E       assert 8080 == 9999\n"
            "tests/test_a.py:42: AssertionError\n"
            "=========================== short test summary info ============================\n"
            "FAILED tests/test_a.py::test_session - assert 8080 == 9999\n"
            "1 failed, 3 passed in 0.31s\n"
        ),
        ("8080", "9999"),
    ),
    "ruff": (
        ["ruff", "check", "."],
        "All checks passed!\n",
        (
            "F821 Undefined name `undefined_name`\n"
            " --> src/app.py:4:10\n"
            "  |\n"
            "4 |   return undefined_name\n"
            "  |          ^^^^^^^^^^^^^^\n"
            "  |\n"
            "Found 1 error.\n"
        ),
        ("F821", "app.py", "undefined_name"),
    ),
    "mypy": (
        ["mypy", "src"],
        "Success: no issues found in 12 source files\n",
        (
            'src/session.py:31: error: Argument 1 to "store" has incompatible type '
            '"str"; expected "int"  [arg-type]\n'
            "src/session.py:44: error: Missing return statement  [return]\n"
            "Found 2 errors in 1 file (checked 12 source files)\n"
        ),
        ("session.py", "31", "arg-type", "incompatible type"),
    ),
    "cargo": (
        ["cargo", "test"],
        "running 18 tests\ntest result: ok. 18 passed; 0 failed; 0 ignored\n",
        (
            "running 18 tests\n"
            "test auth::tests::rejects_expired ... FAILED\n"
            "failures:\n"
            "---- auth::tests::rejects_expired stdout ----\n"
            "thread 'auth::tests::rejects_expired' panicked at src/auth.rs:88:\n"
            "assertion `left == right` failed\n"
            "  left: 401\n"
            " right: 200\n"
            "test result: FAILED. 17 passed; 1 failed; 0 ignored\n"
        ),
        ("rejects_expired", "auth.rs", "88"),
    ),
    "tsc": (
        ["tsc", "--noEmit"],
        "",
        (
            "src/api/routes.ts(18,7): error TS2322: Type 'string' is not assignable "
            "to type 'number'.\n"
            "src/api/routes.ts(31,3): error TS2554: Expected 2 arguments, but got 1.\n"
            "Found 2 errors in 1 file.\n"
        ),
        ("TS2322", "routes.ts", "18"),
    ),
    "uv": (
        ["uv", "run", "pytest", "-q"],
        "12 passed in 1.02s\n",
        (
            "=================================== FAILURES ===================================\n"
            "E       assert 1 == 2\n"
            "tests/test_x.py:9: AssertionError\n"
            "FAILED tests/test_x.py::test_x - assert 1 == 2\n"
            "1 failed, 11 passed in 1.02s\n"
        ),
        ("test_x.py", "assert 1 == 2"),
    ),
}


def fake_tool(bin_dir: Path, name: str, output: str, exit_code: int) -> None:
    """A stand-in that reproduces the fixture byte-for-byte, then exits."""
    script = bin_dir / name
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({output!r})\n"
        f"raise SystemExit({exit_code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def run_verify(tmp_path: Path, tool: str, output: str, exit_code: int, *flags: str):
    argv = FILTERS[tool][0]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    # `uv run pytest` must reach the inner tool, so the runner forwards to it.
    if argv[0] == "uv":
        fake_tool(bin_dir, "uv", output, exit_code)
    else:
        fake_tool(bin_dir, argv[0], output, exit_code)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ATS_VERIFY_LOG_DIR": str(tmp_path / "logs"),
    }
    return subprocess.run(
        [sys.executable, str(VERIFY), "--json", *flags, "--", *argv],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("tool", sorted(FILTERS))
@pytest.mark.parametrize("no_rtk", [False, True], ids=["with-rtk", "builtin-only"])
def test_red_run_keeps_the_failure_and_the_exit_code(
    tmp_path: Path, tool: str, no_rtk: bool
) -> None:
    _, _, red, signals = FILTERS[tool]
    flags = ("--no-rtk",) if no_rtk else ()
    result = run_verify(tmp_path, tool, red, 1, *flags)

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "red"
    assert payload["exit_code"] == 1
    shown = "\n".join(payload["shown_lines"])
    assert shown.strip(), f"{tool}: red projection was empty"
    for signal in signals:
        assert signal in shown, f"{tool} via {payload['projector']} dropped {signal!r}"


@pytest.mark.parametrize("tool", sorted(FILTERS))
def test_green_run_is_compact_and_never_larger_than_raw(tmp_path: Path, tool: str) -> None:
    _, green, _, _ = FILTERS[tool]
    result = run_verify(tmp_path, tool, green, 0)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "green"
    assert len("\n".join(payload["shown_lines"])) <= max(len(green), 80)


@pytest.mark.parametrize("tool", sorted(FILTERS))
def test_raw_log_always_holds_the_complete_output(tmp_path: Path, tool: str) -> None:
    _, _, red, _ = FILTERS[tool]
    result = run_verify(tmp_path, tool, red, 1)

    payload = json.loads(result.stdout)
    assert Path(payload["raw_log"]).read_text() == red


@pytest.mark.skipif(not HAS_RTK, reason="rtk not installed")
@pytest.mark.parametrize("tool", sorted(FILTERS))
def test_rtk_is_only_adopted_when_it_beats_the_builtin(tmp_path: Path, tool: str) -> None:
    """Adoption is a measurement, not a preference: smaller, or it is not used."""
    _, _, red, _ = FILTERS[tool]
    with_rtk = json.loads(run_verify(tmp_path, tool, red, 1).stdout)
    builtin = json.loads(run_verify(tmp_path, tool, red, 1, "--no-rtk").stdout)

    chosen = len("\n".join(with_rtk["shown_lines"]))
    fallback = len("\n".join(builtin["shown_lines"]))
    assert chosen <= fallback
    if with_rtk["projector"] == "builtin":
        assert chosen == fallback
    else:
        assert with_rtk["projector"].startswith("rtk:")
        assert chosen < fallback


def test_a_filter_that_swallows_the_failure_is_rejected(tmp_path: Path) -> None:
    """The guarantee that matters: a silent filter must not become the output.

    A stub `rtk` that prints a cheerful nothing is exactly the observed RTK
    pytest-wrapper bug; ats-verify must fall back to its own projection.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    liar = bin_dir / "rtk"
    liar.write_text("#!/usr/bin/env python3\nprint('ok')\n")
    liar.chmod(liar.stat().st_mode | stat.S_IXUSR)
    _, _, red, signals = FILTERS["pytest"]
    fake_tool(bin_dir, "pytest", red, 1)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ATS_VERIFY_LOG_DIR": str(tmp_path / "logs"),
    }
    result = subprocess.run(
        [sys.executable, str(VERIFY), "--json", "--", "pytest", "-q"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert payload["projector"] == "builtin"
    shown = "\n".join(payload["shown_lines"])
    assert "ok" != shown.strip()
    for signal in signals:
        assert signal in shown
