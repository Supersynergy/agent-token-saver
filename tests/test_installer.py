from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_agent_token_saver.py"


def run_installer(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    project = tmp_path / "project"
    bin_dir = tmp_path / "bin"
    for path in (home / ".codex", home / ".claude", home / ".hermes", home / ".gg", project / ".git", bin_dir):
        path.mkdir(parents=True, exist_ok=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("#!/bin/sh\nexit 0\n")
    rtk.chmod(0o755)
    env = os.environ.copy()
    env.update(HOME=str(home), PATH=f"{bin_dir}:{env['PATH']}")
    return subprocess.run(
        ["python3", str(INSTALLER), "--project", str(project), *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_all_agents_install_without_overwriting_existing_settings(tmp_path: Path) -> None:
    claude_settings = tmp_path / "home" / ".claude" / "settings.json"
    claude_settings.parent.mkdir(parents=True)
    existing_rtk = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "rtk hook claude", "timeout": 10}],
    }
    claude_settings.write_text(
        json.dumps({"theme": "dark", "hooks": {"Stop": [], "PreToolUse": [existing_rtk]}})
    )

    result = run_installer(tmp_path, "--agent", "all")
    assert result.returncode == 0, result.stderr
    home = tmp_path / "home"
    project = tmp_path / "project"
    assert (home / ".codex" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert (home / ".claude" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert (home / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert (home / ".gg" / "skills" / "agent-token-saver.md").is_file()
    assert (project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    config = json.loads((home / ".agent-token-saver" / "config.json").read_text())
    assert config == {
        "schema_version": 1,
        "profile": "lean",
        "agents": ["codex", "claude", "hermes", "ggcoder", "repo"],
    }

    claude = json.loads(claude_settings.read_text())
    assert claude["theme"] == "dark"
    assert "Stop" in claude["hooks"]
    assert claude["hooks"]["PreToolUse"] == [existing_rtk]
    assert claude["hooks"]["UserPromptSubmit"]
    codex = json.loads((home / ".codex" / "hooks.json").read_text())
    assert codex["hooks"]["PreToolUse"]
    assert codex["hooks"]["UserPromptSubmit"]


def test_repeated_install_deduplicates_hooks(tmp_path: Path) -> None:
    first = run_installer(tmp_path, "--agent", "codex")
    second = run_installer(tmp_path, "--agent", "codex")
    assert first.returncode == second.returncode == 0
    hooks = json.loads((tmp_path / "home" / ".codex" / "hooks.json").read_text())["hooks"]
    assert len(hooks["PreToolUse"]) == 1
    assert len(hooks["UserPromptSubmit"]) == 1


def test_dry_run_leaves_home_unchanged(tmp_path: Path) -> None:
    result = run_installer(tmp_path, "--agent", "all", "--dry-run")
    assert result.returncode == 0
    assert not (tmp_path / "home" / ".agent-token-saver").exists()
    assert not (tmp_path / "home" / ".codex" / "hooks.json").exists()
