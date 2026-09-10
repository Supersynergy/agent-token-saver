"""Tests for the Python stack-tools installer core.

Covers version comparison, host detection, tool registry, and the
check/install orchestration logic. Network and filesystem mutations are
mocked so the suite stays fast and hermetic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from scripts import install_stack_tools as stack

# ── Version comparison ────────────────────────────────────────────────────


class TestVersion:
    def test_parse_simple(self) -> None:
        v = stack.Version.parse("1.2.3")
        assert v == stack.Version(1, 2, 3)

    def test_parse_with_prefix(self) -> None:
        v = stack.Version.parse("rtk 0.48.0")
        assert v == stack.Version(0, 48, 0)

    def test_parse_no_match(self) -> None:
        assert stack.Version.parse("unknown") is None

    def test_ge_same(self) -> None:
        assert stack.Version(1, 2, 3) >= stack.Version(1, 2, 3)

    def test_ge_higher_patch(self) -> None:
        assert stack.Version(1, 2, 4) >= stack.Version(1, 2, 3)

    def test_ge_higher_minor(self) -> None:
        assert stack.Version(1, 3, 0) >= stack.Version(1, 2, 9)

    def test_ge_lower(self) -> None:
        assert not (stack.Version(1, 2, 2) >= stack.Version(1, 2, 3))


class TestVersionGe:
    def test_empty_installed(self) -> None:
        assert not stack.version_ge("", "1.0.0")

    def test_empty_target(self) -> None:
        assert stack.version_ge("1.0.0", "")

    def test_equal(self) -> None:
        assert stack.version_ge("1.2.3", "1.2.3")

    def test_higher(self) -> None:
        assert stack.version_ge("1.2.4", "1.2.3")

    def test_lower(self) -> None:
        assert not stack.version_ge("1.2.2", "1.2.3")

    def test_unknown_string(self) -> None:
        assert not stack.version_ge("unknown", "1.0.0")

    def test_unparseable_fallback(self) -> None:
        assert stack.version_ge("same", "same")


# ── Platform detection ───────────────────────────────────────────────────


class TestPlatformInfo:
    def test_detect_returns_os_and_arch(self) -> None:
        pf = stack.PlatformInfo.detect()
        assert pf.os in ("darwin", "linux")
        assert pf.arch in ("arm64", "amd64")


# ── Host detection ────────────────────────────────────────────────────────


class TestDetectHosts:
    def test_requested_overrides(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        result = stack.detect_hosts(requested="claude,codex")
        assert result == ["claude", "codex"]

    def test_env_overrides(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        result = stack.detect_hosts(env_hosts="hermes,opencode")
        assert result == ["hermes", "opencode"]

    def test_auto_detect_fallback(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: False)
        monkeypatch.delenv("DEVIN", raising=False)
        result = stack.detect_hosts()
        assert result == ["claude"]  # fallback when nothing found

    def test_auto_detect_claude(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".claude").mkdir()
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: False)
        monkeypatch.delenv("DEVIN", raising=False)
        result = stack.detect_hosts()
        assert "claude" in result


# ── Tool registry ────────────────────────────────────────────────────────


class TestToolRegistry:
    def test_all_tools_defined(self) -> None:
        assert set(stack.ALL_TOOLS) == {
            "si",
            "rtk",
            "tilth",
            "context-mode",
            "graphify",
            "codegraph",
        }

    def test_install_tool_unknown(self, capsys) -> None:
        result = stack.install_tool("nonexistent", dry_run=True)
        assert result is False

    def test_install_tool_dry_run(self, capsys) -> None:
        with patch.dict(os.environ, {}, clear=False):
            stack.install_tool("rtk", dry_run=True)
        captured = capsys.readouterr()
        assert "rtk" in captured.out


# ── Check mode ───────────────────────────────────────────────────────────


class TestCheckTool:
    def test_check_tool_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(stack, "have", lambda c: False)
        status = stack.check_tool("rtk")
        assert not status.installed
        assert status.name == "rtk"

    def test_check_tool_present(self, monkeypatch) -> None:
        monkeypatch.setattr(stack, "have", lambda c: True)
        monkeypatch.setattr(stack.shutil, "which", lambda c: "/fake/bin/" + c)
        monkeypatch.setattr(
            stack.subprocess,
            "run",
            lambda *a, **kw: type("R", tuple(), {"stdout": "rtk 0.48.0", "stderr": ""})(),
        )
        status = stack.check_tool("rtk")
        assert status.installed
        assert "0.48.0" in status.version


class TestCheckAllTools:
    def test_returns_all_statuses(self, monkeypatch) -> None:
        monkeypatch.setattr(stack, "have", lambda c: False)
        statuses = stack.check_all_tools()
        assert len(statuses) == len(stack.ALL_TOOLS)
        assert all(not s.installed for s in statuses)


# ── Host wiring ──────────────────────────────────────────────────────────


class TestWireRtkHook:
    def test_skip_if_rtk_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: c != "rtk")
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({"hooks": {}}))
        stack.wire_rtk_hook()
        # Should return without modifying anything

    def test_skip_if_already_wired(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: True)
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [{"type": "command", "command": "rtk hook claude"}],
                            }
                        ]
                    }
                }
            )
        )
        stack.wire_rtk_hook(dry_run=False)
        data = json.loads(settings_path.read_text())
        pre = data["hooks"]["PreToolUse"]
        assert len(pre[0]["hooks"]) == 1  # not duplicated

    def test_adds_hook_when_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: True)
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({"hooks": {"PreToolUse": []}}))
        stack.wire_rtk_hook(dry_run=False)
        data = json.loads(settings_path.read_text())
        pre = data["hooks"]["PreToolUse"]
        assert any(
            "rtk hook claude" in h.get("command", "")
            for entry in pre
            for h in entry.get("hooks", [])
        )


class TestWireSiObserveHook:
    def test_skip_if_si_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: c != "si")
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({"hooks": {}}))
        stack.wire_si_observe_hook()

    def test_adds_hook_when_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(stack, "HOME", tmp_path)
        monkeypatch.setattr(stack, "have", lambda c: True)
        monkeypatch.setattr(stack.shutil, "which", lambda c: "/fake/bin/si")
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({"hooks": {"PostToolUse": []}}))
        stack.wire_si_observe_hook(dry_run=False)
        data = json.loads(settings_path.read_text())
        post = data["hooks"]["PostToolUse"]
        assert any(
            "si observe" in h.get("command", "") for entry in post for h in entry.get("hooks", [])
        )


# ── CLI ──────────────────────────────────────────────────────────────────


class TestCli:
    def test_check_mode(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(stack, "have", lambda c: False)
        result = stack.main(["--check"])
        assert result == 1  # not all installed

    def test_check_mode_all_installed(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(stack, "have", lambda c: True)
        monkeypatch.setattr(stack.shutil, "which", lambda c: "/fake/bin/" + c)
        monkeypatch.setattr(
            stack.subprocess,
            "run",
            lambda *a, **kw: type("R", tuple(), {"stdout": "1.0.0", "stderr": ""})(),
        )
        result = stack.main(["--check"])
        assert result == 0

    def test_dry_run_does_not_error(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(stack, "have", lambda c: False)
        result = stack.main(["--dry-run"])
        assert result == 0
