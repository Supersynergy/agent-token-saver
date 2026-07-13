from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integration" / "hooks" / "token-stack-prompt.py"


def run_hook(home: Path, prompt: str, router: Path | None = None) -> str:
    env = os.environ.copy()
    env["HOME"] = str(home)
    if router is not None:
        env["ATS_ROUTER"] = str(router)
    result = subprocess.run(
        ["python3", str(HOOK)],
        input=json.dumps({"prompt": prompt}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_trivial_prompt_emits_nothing(tmp_path: Path) -> None:
    assert run_hook(tmp_path, "What is 2 plus 2?") == ""


def test_hidden_fallback_is_gated_to_token_tasks(tmp_path: Path) -> None:
    skill = (
        tmp_path
        / ".agent-token-saver"
        / "skills"
        / "agent-token-saver"
        / "SKILL.md"
    )
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: agent-token-saver\n---\n")

    assert run_hook(tmp_path, "Write a friendly README") == ""
    output = run_hook(tmp_path, "Compress this noisy log without wasting context tokens")
    payload = json.loads(output)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert str(skill) in context


def test_router_is_limited_to_one_primary_skill(tmp_path: Path) -> None:
    router = tmp_path / "router.py"
    router.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "assert sys.argv[-3:] == ['--max', '1', '--strict']\n"
        "print('- first: primary (/tmp/first/SKILL.md)')\n"
        "print('- second: reserve (/tmp/second/SKILL.md)')\n"
    )
    output = run_hook(tmp_path, "Build and test this project", router)
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert "/tmp/first/SKILL.md" in context
    assert "/tmp/second/SKILL.md" not in context
