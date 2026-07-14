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
    assert not (home / ".codex" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    assert not (home / ".claude" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    assert (home / ".agent-token-saver" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert (home / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert (home / ".gg" / "skills" / "agent-token-saver.md").is_file()
    assert (project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert (home / ".local" / "bin" / "agent-token-ledger").is_symlink()
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
    assert codex["hooks"]["PreToolUse"] == []
    assert codex["hooks"]["UserPromptSubmit"]


def test_repeated_install_deduplicates_hooks(tmp_path: Path) -> None:
    first = run_installer(tmp_path, "--agent", "codex")
    second = run_installer(tmp_path, "--agent", "codex")
    assert first.returncode == second.returncode == 0
    hooks = json.loads((tmp_path / "home" / ".codex" / "hooks.json").read_text())["hooks"]
    assert len(hooks["PreToolUse"]) == 0
    assert len(hooks["UserPromptSubmit"]) == 1


def test_existing_host_heavy_launcher_is_preserved(tmp_path: Path) -> None:
    launcher = tmp_path / "home" / ".local" / "bin" / "codex-heavy-context"
    launcher.parent.mkdir(parents=True)
    local_overlay = "#!/bin/sh\n# host-only node_repl overlay\n"
    launcher.write_text(local_overlay)

    result = run_installer(tmp_path, "--agent", "codex")

    assert result.returncode == 0, result.stderr
    assert launcher.read_text() == local_overlay
    portable = (
        tmp_path
        / "home"
        / ".agent-token-saver"
        / "bin"
        / "codex-heavy-context"
    )
    assert portable.is_file()
    assert portable.read_text() == (
        ROOT / "integration" / "cli" / "codex-heavy-context"
    ).read_text()


def test_public_heavy_launcher_has_no_host_paths() -> None:
    launcher = (ROOT / "integration" / "cli" / "codex-heavy-context").read_text()

    assert "/Users/" not in launcher
    assert "/Applications/" not in launcher
    assert "NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S" not in launcher


def test_dry_run_leaves_home_unchanged(tmp_path: Path) -> None:
    result = run_installer(tmp_path, "--agent", "all", "--dry-run")
    assert result.returncode == 0
    assert not (tmp_path / "home" / ".agent-token-saver").exists()
    assert not (tmp_path / "home" / ".codex" / "hooks.json").exists()


def test_old_repo_rtk_hook_is_removed_from_codex(tmp_path: Path) -> None:
    hooks_path = tmp_path / "home" / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        f"{tmp_path}/home/.agent-token-saver/hooks/rtk-rewrite.sh"
                                    ),
                                }
                            ],
                        }
                    ]
                }
            }
        )
    )
    obsolete = tmp_path / "home" / ".agent-token-saver" / "hooks" / "rtk-rewrite.sh"
    obsolete.parent.mkdir(parents=True)
    obsolete.write_text("#!/bin/sh\n")
    result = run_installer(tmp_path, "--agent", "codex")
    assert result.returncode == 0
    hooks = json.loads(hooks_path.read_text())["hooks"]["PreToolUse"]
    assert hooks == []
    assert not obsolete.exists()


def test_claude_uses_native_rtk_hook(tmp_path: Path) -> None:
    result = run_installer(tmp_path, "--agent", "claude")
    assert result.returncode == 0
    settings = json.loads((tmp_path / "home" / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]["PreToolUse"]
    commands = [hook["command"] for entry in hooks for hook in entry["hooks"]]
    assert commands == ["rtk hook claude"]


def test_claude_prompt_merge_preserves_shared_user_hook_and_stays_idempotent(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "home" / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    managed_hook = (
        f"{tmp_path}/home/.agent-token-saver/hooks/token-stack-prompt.py"
    )
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "~/bin/user-prompt-audit",
                                    "timeout": 9,
                                },
                                {
                                    "type": "command",
                                    "command": managed_hook,
                                    "timeout": 6,
                                },
                            ],
                        }
                    ]
                }
            }
        )
    )

    first = run_installer(tmp_path, "--agent", "claude")
    second = run_installer(tmp_path, "--agent", "claude")

    assert first.returncode == second.returncode == 0
    entries = json.loads(settings_path.read_text())["hooks"]["UserPromptSubmit"]
    commands = [hook["command"] for entry in entries for hook in entry["hooks"]]
    assert commands.count("~/bin/user-prompt-audit") == 1
    assert commands.count(managed_hook) == 1


def test_minimal_profile_has_no_visible_skills_or_prompt_hooks(tmp_path: Path) -> None:
    result = run_installer(tmp_path, "--agent", "all", "--profile", "minimal")
    assert result.returncode == 0, result.stderr
    home = tmp_path / "home"
    project = tmp_path / "project"
    assert (home / ".agent-token-saver" / "skills" / "agent-token-saver" / "SKILL.md").is_file()
    assert not (home / ".codex" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    assert not (home / ".claude" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    assert not (home / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    assert not (home / ".gg" / "skills" / "agent-token-saver.md").exists()
    assert not (project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    codex = json.loads((home / ".codex" / "hooks.json").read_text())
    claude = json.loads((home / ".claude" / "settings.json").read_text())
    assert codex["hooks"]["UserPromptSubmit"] == []
    assert claude["hooks"]["UserPromptSubmit"] == []


def test_team_profile_is_a_supported_lean_runtime(tmp_path: Path) -> None:
    result = run_installer(tmp_path, "--agent", "all", "--profile", "teams")

    assert result.returncode == 0, result.stderr
    config = json.loads((tmp_path / "home" / ".agent-token-saver" / "config.json").read_text())
    assert config["profile"] == "teams"
    assert (tmp_path / "home" / ".codex" / "hooks.json").is_file()


def test_switching_to_minimal_removes_only_managed_visible_skills(tmp_path: Path) -> None:
    first = run_installer(tmp_path, "--agent", "all", "--profile", "lean")
    assert first.returncode == 0, first.stderr
    custom = tmp_path / "home" / ".claude" / "skills" / "agent-token-saver" / "SKILL.md"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("---\nname: agent-token-saver\nauthor: Someone Else\n---\n")

    second = run_installer(tmp_path, "--agent", "all", "--profile", "minimal")

    assert second.returncode == 0, second.stderr
    assert custom.is_file()
    assert not (tmp_path / "home" / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md").exists()
    assert not (tmp_path / "home" / ".gg" / "skills" / "agent-token-saver.md").exists()
    assert not (tmp_path / "project" / ".agents" / "skills" / "agent-token-saver" / "SKILL.md").exists()
