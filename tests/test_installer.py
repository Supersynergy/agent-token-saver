from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Read the canonical version instead of hardcoding it; test_skill_doc_drift
# already proves every release site agrees, so a bump stays a one-line change.
VERSION = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)
INSTALLER = ROOT / "scripts" / "install_agent_token_saver.py"


def run_installer(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    project = tmp_path / "project"
    bin_dir = tmp_path / "bin"
    for path in (
        home / ".codex",
        home / ".claude",
        home / ".hermes",
        home / ".gg",
        project / ".git",
        bin_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    soul = home / ".hermes" / "SOUL.md"
    if not soul.exists():
        soul.write_text("# Hermes fixture\n")
    rtk = bin_dir / "rtk"
    rtk.write_text("#!/bin/sh\nexit 0\n")
    rtk.chmod(0o755)
    env = os.environ.copy()
    env.update(HOME=str(home), PATH=f"{bin_dir}:{env['PATH']}")
    # self_update() runs a real `git pull` against the actual repo checkout
    # (not the --project fixture) on every install; 15+ installer tests each
    # doing that made the suite non-hermetic and intermittently timeout-flaky.
    env["ATS_SKIP_SELF_UPDATE"] = "1"
    return subprocess.run(
        # sys.executable, not "python3": the test prepends bin_dir to PATH, so a
        # bare name resolves to whatever interpreter happens to come first and
        # silently escapes the version matrix.
        [sys.executable, str(INSTALLER), "--project", str(project), *args],
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
    assert (home / ".local" / "bin" / "agent-token-audit").is_symlink()
    assert (home / ".local" / "bin" / "llmadapter").is_symlink()
    config = json.loads((home / ".agent-token-saver" / "config.json").read_text())
    assert config["schema_version"] == 3
    assert config["profile"] == "lean"
    assert config["agents"] == ["codex", "claude", "hermes", "ggcoder", "repo"]
    assert config["project_root"] == str(project.resolve())
    assert config["canonical_skill"]["version"] == VERSION
    assert (
        config["canonical_skill"]["sha256"]
        == hashlib.sha256(
            (ROOT / "skills" / "agent-token-saver" / "SKILL.md").read_bytes()
        ).hexdigest()
    )
    assert set(config["managed_skill_paths"]) == {
        str((home / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md").resolve()),
        str((home / ".gg" / "skills" / "agent-token-saver.md").resolve()),
        str((project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md").resolve()),
    }
    assert {entry["agent"] for entry in config["managed_default_policies"]} == {
        "codex",
        "claude",
        "hermes",
        "ggcoder",
    }
    policy_hash = hashlib.sha256(
        (ROOT / "integration" / "instructions" / "compact-default.md").read_text().strip().encode()
    ).hexdigest()
    for entry in config["managed_default_policies"]:
        assert Path(entry["path"]).is_file()
        assert entry["policy_sha256"] == policy_hash
        text = Path(entry["path"]).read_text()
        assert text.count("<!-- AGENT-TOKEN-SAVER-DEFAULT:START -->") == 1
        assert text.count("<!-- AGENT-TOKEN-SAVER-DEFAULT:END -->") == 1
        assert "Cache-aware handoff" in text
    assert {asset["name"] for asset in config["managed_assets"]} == {
        "doctor",
        "ledger",
        "cache_economics",
        "audit",
        "llmadapter",
        "prompt_hook",
        "session_guard",
        "worker_capsule",
        "default_policy",
    }
    for asset in config["managed_assets"]:
        assert Path(asset["path"]).is_file()
        assert hashlib.sha256(Path(asset["path"]).read_bytes()).hexdigest() == asset["sha256"]

    claude = json.loads(claude_settings.read_text())
    assert claude["theme"] == "dark"
    assert "Stop" in claude["hooks"]
    assert any(
        "token-session-guard.py" in hook["command"]
        for entry in claude["hooks"]["Stop"]
        for hook in entry["hooks"]
    )
    assert claude["hooks"]["PreToolUse"] == [existing_rtk]
    assert claude["hooks"]["UserPromptSubmit"]
    codex = json.loads((home / ".codex" / "hooks.json").read_text())
    assert codex["hooks"]["PreToolUse"] == []
    assert codex["hooks"]["UserPromptSubmit"]
    assert any(
        "token-session-guard.py" in hook["command"]
        for entry in codex["hooks"]["Stop"]
        for hook in entry["hooks"]
    )


def test_installed_ledger_still_prices_the_cached_prefix(tmp_path: Path) -> None:
    """The ledger loads its pricing module as a sibling, so both must ship.

    Installing only the ledger degrades it to cache-unaware output silently,
    which is exactly the mispricing this project set out to remove.
    """
    assert run_installer(tmp_path, "--agent", "codex").returncode == 0
    ledger = tmp_path / "home" / ".agent-token-saver" / "bin" / "agent-token-ledger"
    assert (ledger.parent / "cache_economics.py").is_file()

    usage = tmp_path / "usage.json"
    usage.write_text(
        json.dumps(
            {
                "usage": {
                    "input_tokens": 100,
                    "cache_creation_input_tokens": 500,
                    "cache_read_input_tokens": 9_000,
                    "output_tokens": 200,
                }
            }
        )
    )
    result = subprocess.run(
        [sys.executable, str(ledger), "--usage", f"parent={usage}", "--provider", "codex"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "cache_economics" in result.stdout


def test_cache_pricer_is_callable_from_path(tmp_path: Path) -> None:
    """Hosts that cannot source a shell file still need the cache pricer.

    Codex, Claude and generic CLI agents run commands, not shell functions, so
    a pricer reachable only through the sourced helper is invisible to them.
    """
    assert run_installer(tmp_path, "--agent", "codex").returncode == 0
    launcher = tmp_path / "home" / ".local" / "bin" / "ats-cache"
    assert launcher.is_symlink()

    usage = tmp_path / "usage.json"
    usage.write_text(json.dumps({"input_tokens": 1_000, "cache_read_input_tokens": 9_000}))
    result = subprocess.run(
        [sys.executable, str(launcher), str(usage), "--format", "line"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "cache 90.00% hit" in result.stdout


def test_repeated_install_deduplicates_hooks(tmp_path: Path) -> None:
    first = run_installer(tmp_path, "--agent", "codex")
    second = run_installer(tmp_path, "--agent", "codex")
    assert first.returncode == second.returncode == 0
    hooks = json.loads((tmp_path / "home" / ".codex" / "hooks.json").read_text())["hooks"]
    assert len(hooks["PreToolUse"]) == 0
    assert len(hooks["UserPromptSubmit"]) == 1
    assert len(hooks["Stop"]) == 1


def test_reinstall_replaces_read_only_managed_skill(tmp_path: Path) -> None:
    """Hosts such as Hermes mark installed skills 0444; a re-install must still
    refresh them instead of dying with EACCES halfway through."""
    first = run_installer(tmp_path, "--agent", "hermes")
    assert first.returncode == 0

    skill = tmp_path / "home" / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md"
    assert skill.is_file()
    skill.chmod(0o644)
    skill.write_text("stale content\n")
    skill.chmod(0o444)

    second = run_installer(tmp_path, "--agent", "hermes")
    assert second.returncode == 0, second.stderr
    expected = (ROOT / "skills" / "agent-token-saver" / "SKILL.md").read_text()
    assert skill.read_text() == expected


def test_repeated_install_preserves_user_instructions_and_deduplicates_default(
    tmp_path: Path,
) -> None:
    agents = tmp_path / "home" / ".codex" / "AGENTS.md"
    agents.parent.mkdir(parents=True)
    agents.write_text("# My rules\n\nKeep this exact sentence.\n")

    first = run_installer(tmp_path, "--agent", "codex")
    second = run_installer(tmp_path, "--agent", "codex")

    assert first.returncode == second.returncode == 0
    text = agents.read_text()
    assert "# My rules" in text
    assert "Keep this exact sentence." in text
    assert text.count("<!-- AGENT-TOKEN-SAVER-DEFAULT:START -->") == 1
    assert text.count("<!-- AGENT-TOKEN-SAVER-DEFAULT:END -->") == 1
    assert len(list(agents.parent.glob("AGENTS.md.bak-*"))) == 1


def test_existing_host_heavy_launcher_is_preserved(tmp_path: Path) -> None:
    launcher = tmp_path / "home" / ".local" / "bin" / "codex-heavy-context"
    launcher.parent.mkdir(parents=True)
    local_overlay = "#!/bin/sh\n# host-only node_repl overlay\n"
    launcher.write_text(local_overlay)

    result = run_installer(tmp_path, "--agent", "codex")

    assert result.returncode == 0, result.stderr
    assert launcher.read_text() == local_overlay
    portable = tmp_path / "home" / ".agent-token-saver" / "bin" / "codex-heavy-context"
    assert portable.is_file()
    assert (
        portable.read_text() == (ROOT / "integration" / "cli" / "codex-heavy-context").read_text()
    )


def test_existing_llmadapter_override_is_preserved_but_canonical_copy_is_installed(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "home" / ".local" / "bin" / "llmadapter"
    launcher.parent.mkdir(parents=True)
    override = "#!/bin/sh\nprintf custom\n"
    launcher.write_text(override)

    result = run_installer(tmp_path, "--agent", "codex")

    assert result.returncode == 0, result.stderr
    assert launcher.read_text() == override
    canonical = tmp_path / "home" / ".agent-token-saver" / "bin" / "llmadapter"
    assert canonical.read_text() == (ROOT / "scripts" / "llmadapter.ts").read_text()


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
    assert not (tmp_path / "home" / ".codex" / "AGENTS.md").exists()
    assert (
        "AGENT-TOKEN-SAVER-DEFAULT" not in (tmp_path / "home" / ".hermes" / "SOUL.md").read_text()
    )


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
    managed_hook = f"{tmp_path}/home/.agent-token-saver/hooks/token-stack-prompt.py"
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
    # Exactly one managed entry, in the `<interpreter> <hook>` shape: the
    # interpreter must be a real file and never a shim or a project venv.
    managed = [c for c in commands if c.endswith(f" {managed_hook}")]
    assert len(managed) == 1, commands
    interpreter = Path(managed[0].split(" ", 1)[0])
    assert interpreter.is_file()
    assert "shims" not in interpreter.parts
    assert ".venv" not in interpreter.parts


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
    assert codex["hooks"]["Stop"] == []
    assert claude["hooks"]["Stop"] == []


def test_team_profile_is_a_supported_lean_runtime(tmp_path: Path) -> None:
    result = run_installer(tmp_path, "--agent", "all", "--profile", "teams")

    assert result.returncode == 0, result.stderr
    config = json.loads((tmp_path / "home" / ".agent-token-saver" / "config.json").read_text())
    assert config["profile"] == "teams"
    assert (tmp_path / "home" / ".codex" / "hooks.json").is_file()


def test_teams_profile_registers_worker_capsule_once_for_claude(tmp_path: Path) -> None:
    first = run_installer(tmp_path, "--agent", "claude", "--profile", "teams")
    second = run_installer(tmp_path, "--agent", "claude", "--profile", "teams")
    assert first.returncode == second.returncode == 0

    hooks = json.loads((tmp_path / "home" / ".claude" / "settings.json").read_text())["hooks"]
    entries = [
        entry
        for entry in hooks["PreToolUse"]
        if entry.get("matcher") == "Agent"
        and any("agent-worker-capsule.py" in hook.get("command", "") for hook in entry["hooks"])
    ]
    assert len(entries) == 1
    command = entries[0]["hooks"][0]["command"]
    interpreter, script = command.split(" ", 1)
    assert Path(interpreter).is_file()
    assert "shims" not in Path(interpreter).parts
    assert Path(script).is_file()


def test_switching_to_minimal_removes_only_managed_visible_skills(tmp_path: Path) -> None:
    first = run_installer(tmp_path, "--agent", "all", "--profile", "lean")
    assert first.returncode == 0, first.stderr
    custom = tmp_path / "home" / ".claude" / "skills" / "agent-token-saver" / "SKILL.md"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("---\nname: agent-token-saver\nauthor: Someone Else\n---\n")

    second = run_installer(tmp_path, "--agent", "all", "--profile", "minimal")

    assert second.returncode == 0, second.stderr
    assert custom.is_file()
    assert not (
        tmp_path / "home" / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md"
    ).exists()
    assert not (tmp_path / "home" / ".gg" / "skills" / "agent-token-saver.md").exists()
    assert not (
        tmp_path / "project" / ".agents" / "skills" / "agent-token-saver" / "SKILL.md"
    ).exists()
    for path in (
        tmp_path / "home" / ".codex" / "AGENTS.md",
        tmp_path / "home" / ".claude" / "CLAUDE.md",
        tmp_path / "home" / ".hermes" / "SOUL.md",
        tmp_path / "home" / "AGENTS.md",
    ):
        assert "AGENT-TOKEN-SAVER-DEFAULT" not in path.read_text()
    assert (tmp_path / "home" / ".hermes" / "SOUL.md").read_text() == "# Hermes fixture\n"


def test_hook_interpreter_meets_the_installer_floor_and_is_never_a_shim() -> None:
    """The fresh-machine failure: a stock 3.9 pinned for hooks the CLI cannot run on."""
    import sys

    sys.path.insert(0, str(INSTALLER.parent))
    import install_agent_token_saver as installer

    chosen = installer.hook_interpreter()
    assert Path(chosen).is_file()
    assert "shims" not in Path(chosen).parts
    assert ".venv" not in Path(chosen).parts
    assert installer.interpreter_meets_floor(chosen)


def test_bootstrap_script_picks_a_qualifying_python_over_a_stale_python3(tmp_path: Path) -> None:
    """A stock macOS resolves `python3` to 3.9 beside a qualifying Homebrew Python."""
    import shutil
    import stat

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # A `python3` that reports 3.9, and a `python3.12` that is the real thing.
    stale = bin_dir / "python3"
    stale.write_text(
        "#!/bin/sh\n"
        'case "$1" in --version) echo "Python 3.9.6";; esac\n'
        "exit 1\n"
    )
    stale.chmod(stale.stat().st_mode | stat.S_IXUSR)
    real = bin_dir / "python3.12"
    real.symlink_to(sys.executable)
    # The script needs a few coreutils. Link exactly those, and nothing else,
    # so a system python3.X in /usr/bin cannot leak into the search -- it did
    # on the Ubuntu CI runner, which ships /usr/bin/python3.12.
    for tool in ("dirname", "mktemp", "rm", "cat", "git"):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    # A stand-in installer that reports which interpreter ran it.
    probe_root = tmp_path / "repo" / "scripts"
    probe_root.mkdir(parents=True)
    (probe_root / "install_agent_token_saver.py").write_text(
        "import sys; print('RAN_WITH', sys.executable)\n"
    )
    shutil.copy(INSTALLER.parents[1] / "install-universal.sh", tmp_path / "repo" / "install-universal.sh")

    result = subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(tmp_path / "repo" / "install-universal.sh"), "--dry-run"],
        capture_output=True,
        text=True,
        env={"PATH": str(bin_dir), "HOME": str(tmp_path)},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "RAN_WITH" in result.stdout
    assert "python3.9" not in result.stdout

    # With only the stale one, the message names what was found and how to fix it.
    real.unlink()
    result = subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(tmp_path / "repo" / "install-universal.sh"), "--dry-run"],
        capture_output=True,
        text=True,
        env={"PATH": str(bin_dir), "HOME": str(tmp_path)},
        check=False,
    )
    assert result.returncode == 1
    assert "3.11+" in result.stderr
    assert "found:" in result.stderr
    assert "brew install" in result.stderr
