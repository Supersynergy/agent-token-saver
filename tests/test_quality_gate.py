from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("failed_tool,recipe", [("pytest", "check"), ("osv-scanner", "pre-pr")])
def test_recipe_propagates_verification_failure(tmp_path: Path, failed_tool: str, recipe: str):
    just = shutil.which("just")
    if just is None:
        pytest.skip("just is not installed")
    for tool in ("uv", "gitleaks", "osv-scanner"):
        path = tmp_path / tool
        path.write_text(f'#!/bin/sh\ncase "{tool} $*" in *{failed_tool}*) exit 7;; esac\nexit 0\n')
        path.chmod(0o755)
    result = subprocess.run(
        [just, "--justfile", str(ROOT / "justfile"), recipe],
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "exit code 7" in result.stderr
