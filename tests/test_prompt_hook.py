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
    env.pop("ATS_ROUTER", None)
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


def test_empty_router_falls_back_for_token_tasks(tmp_path: Path) -> None:
    skill = (
        tmp_path
        / ".agent-token-saver"
        / "skills"
        / "agent-token-saver"
        / "SKILL.md"
    )
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: agent-token-saver\n---\n")
    router = tmp_path / "router.py"
    router.write_text("print('{\"selected\": []}')\n")

    output = run_hook(tmp_path, "Compress this noisy log without wasting context tokens", router)

    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert str(skill) in context


def test_skill_metadata_covers_token_stack_router_intents() -> None:
    skill = (ROOT / "skills" / "agent-token-saver" / "SKILL.md").read_text()
    tags_line = next(line for line in skill.splitlines() if "tags:" in line)
    tags = set(tags_line.partition("[")[2].rstrip("]").replace(" ", "").split(","))

    assert {"benchmark", "compress", "log", "noisy", "output", "subagent"} <= tags


def test_router_is_limited_to_one_primary_skill(tmp_path: Path) -> None:
    first = tmp_path / "first" / "SKILL.md"
    second = tmp_path / "second" / "SKILL.md"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("---\nname: first\n---\n")
    second.write_text("---\nname: second\n---\n")
    router = tmp_path / "router.py"
    router_payload = json.dumps(
        {
            "selected": [
                {"name": "first", "path": str(first)},
                {"name": "second", "path": str(second)},
            ]
        }
    )
    router.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "assert sys.argv[-4:] == ['--max', '1', '--strict', '--json']\n"
        f"print({router_payload!r})\n"
    )
    output = run_hook(tmp_path, "Build and test this project", router)
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert str(first) in context
    assert str(second) not in context
    assert "Do not auto-load a second skill" in context


def test_invalid_router_json_fails_open(tmp_path: Path) -> None:
    router = tmp_path / "router.py"
    router.write_text("print('{broken')\n")

    assert run_hook(tmp_path, "Build and test this project", router) == ""


def test_si_launcher_is_discovered_without_legacy_skill_copy(tmp_path: Path) -> None:
    skill = tmp_path / "selected" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: selected\n---\n")
    router = tmp_path / ".local" / "bin" / "si"
    router.parent.mkdir(parents=True)
    payload = json.dumps({"selected": [{"name": "selected", "path": str(skill)}]})
    router.write_text(f"print({payload!r})\n")

    output = run_hook(tmp_path, "Build and test this project")
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]

    assert str(skill) in context


def test_si_launcher_wins_over_legacy_alias(tmp_path: Path) -> None:
    selected = tmp_path / "selected" / "SKILL.md"
    legacy_selected = tmp_path / "legacy" / "SKILL.md"
    selected.parent.mkdir()
    legacy_selected.parent.mkdir()
    selected.write_text("---\nname: selected\n---\n")
    legacy_selected.write_text("---\nname: legacy\n---\n")
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "si").write_text(
        f"print({json.dumps({'selected': [{'name': 'selected', 'path': str(selected)}]})!r})\n"
    )
    (bin_dir / "agent-skill-route").write_text(
        f"print({json.dumps({'selected': [{'name': 'legacy', 'path': str(legacy_selected)}]})!r})\n"
    )

    output = run_hook(tmp_path, "Build and test this project")
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]

    assert str(selected) in context
    assert str(legacy_selected) not in context
