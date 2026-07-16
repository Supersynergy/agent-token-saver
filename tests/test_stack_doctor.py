import hashlib
import json
import shutil
from pathlib import Path

import scripts.stack_doctor as stack_doctor
from scripts.stack_doctor import build_report, same_resolved_path

ROOT = Path(__file__).resolve().parents[1]


def install_fixture(home: Path, *, stale_route: bool = False) -> None:
    install_home = home / ".agent-token-saver"
    canonical = install_home / "skills" / "agent-token-saver" / "SKILL.md"
    hook = install_home / "hooks" / "token-stack-prompt.py"
    guard = install_home / "hooks" / "token-session-guard.py"
    ledger = install_home / "bin" / "agent-token-ledger"
    canonical.parent.mkdir(parents=True)
    hook.parent.mkdir(parents=True)
    ledger.parent.mkdir(parents=True)
    canonical.write_text("---\nname: agent-token-saver\nversion: 3.2.0\n---\n")
    if stale_route:
        stale = home / ".agents" / "skills" / "agent-token-saver" / "SKILL.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("---\nname: agent-token-saver\nversion: 3.1.5\n---\n")
        hook.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            f"print(json.dumps({{'hookSpecificOutput': {{'additionalContext': 'Primary skill={stale}'}}}}))\n"
        )
    else:
        shutil.copy2(ROOT / "integration" / "hooks" / "token-stack-prompt.py", hook)
    shutil.copy2(ROOT / "integration" / "hooks" / "token-session-guard.py", guard)
    shutil.copy2(ROOT / "scripts" / "full_context_ledger.py", ledger)
    hook.chmod(0o755)
    guard.chmod(0o755)
    ledger.chmod(0o755)
    hooks = home / ".codex" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {"hooks": [{"type": "command", "command": str(hook), "timeout": 6}]}
                    ],
                    "Stop": [
                        {"hooks": [{"type": "command", "command": str(guard), "timeout": 8}]}
                    ],
                }
            }
        )
    )
    config = install_home / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "profile": "lean",
                "agents": ["codex"],
                "canonical_skill": {
                    "path": str(canonical),
                    "version": "3.2.0",
                    "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
                },
                "managed_skill_paths": [],
                "managed_assets": [
                    {
                        "name": "prompt_hook",
                        "path": str(hook),
                        "sha256": hashlib.sha256(hook.read_bytes()).hexdigest(),
                    },
                    {
                        "name": "session_guard",
                        "path": str(guard),
                        "sha256": hashlib.sha256(guard.read_bytes()).hexdigest(),
                    },
                    {
                        "name": "ledger",
                        "path": str(ledger),
                        "sha256": hashlib.sha256(ledger.read_bytes()).hexdigest(),
                    },
                ],
            }
        )
    )


def test_minimal_profile_reports_builtin(tmp_path: Path):
    catalog = {
        "profiles": {"minimal": ["native"]},
        "tools": {
            "native": {
                "kind": "builtin",
                "required": True,
                "activation": "default",
            }
        },
    }
    report = build_report(catalog, "minimal")
    assert report["healthy"] is True
    assert report["tools"][0]["version"] == "builtin"


def test_integrity_paths_accept_filesystem_alias(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)

    assert same_resolved_path(real / "asset", alias / "asset") is True


def test_catalog_profiles_reference_known_tools():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "stack" / "catalog.json").read_text())
    known = set(catalog["tools"])
    for tools in catalog["profiles"].values():
        assert set(tools) <= known


def test_catalog_contains_no_dead_profile_entries():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "stack" / "catalog.json").read_text())
    referenced = {name for profile in catalog["profiles"].values() for name in profile}

    assert set(catalog["tools"]) == referenced
    assert catalog["profiles"]["minimal"] == ["native-projection"]
    assert catalog["profiles"]["teams"] == catalog["profiles"]["lean"]
    assert "news" not in catalog["profiles"]
    assert "superweb" not in catalog["tools"]


def test_legacy_news_config_maps_to_team_profile(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"profile":"news"}')
    monkeypatch.setattr(stack_doctor, "DEFAULT_CONFIG", config)

    assert stack_doctor.configured_profile() == "teams"


def test_active_public_surface_excludes_private_host_tools() -> None:
    root = Path(__file__).resolve().parents[1]
    active_files = (
        root / "README.md",
        root / "skills" / "agent-token-saver" / "SKILL.md",
        root / "stack" / "catalog.json",
        root / "docs" / "CLI_FIRST_POLICY.md",
        root / "integration" / "hooks" / "token-stack-prompt.py",
    )

    text = "\n".join(path.read_text().lower() for path in active_files)
    for marker in ("superweb", "synapse", "ghmax", "ghgrep"):
        assert marker not in text


def test_missing_optional_tool_is_core_ready(monkeypatch):
    monkeypatch.setattr("scripts.stack_doctor.shutil.which", lambda _command: None)
    catalog = {
        "profiles": {"lean": ["native", "optional-cli"]},
        "tools": {
            "native": {"kind": "builtin", "required": True},
            "optional-cli": {
                "kind": "command",
                "command": "optional-cli",
                "required": False,
            },
        },
    }
    report = build_report(catalog, "lean")
    assert report["healthy"] is True
    assert report["profile_complete"] is False
    assert report["status"] == "core-ready"
    assert report["missing_optional"] == ["optional-cli"]


def test_end_to_end_integrity_accepts_canonical_hook_route(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is True
    assert report["integrity"]["errors"] == []
    assert report["integrity"]["prompt_hook_smoke"]["canonical_route"] is True
    assert report["integrity"]["session_guard_smoke"]["valid"] is True


def test_end_to_end_integrity_rejects_stale_hook_route(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home, stale_route=True)
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert "prompt_hook_canonical_route_mismatch" in report["integrity"]["errors"]


def test_end_to_end_integrity_rejects_managed_skill_hash_drift(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    canonical = home / ".agent-token-saver" / "skills" / "agent-token-saver" / "SKILL.md"
    managed = home / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md"
    managed.parent.mkdir(parents=True)
    managed.write_text("---\nname: agent-token-saver\nversion: 3.1.4\n---\n")
    config = home / ".agent-token-saver" / "config.json"
    payload = json.loads(config.read_text())
    payload["managed_skill_paths"] = [str(managed)]
    config.write_text(json.dumps(payload))
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert f"managed_skill_hash_mismatch:{managed}" in report["integrity"]["errors"]
    assert hashlib.sha256(managed.read_bytes()).hexdigest() != hashlib.sha256(
        canonical.read_bytes()
    ).hexdigest()


def test_end_to_end_integrity_rejects_missing_session_guard_wiring(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    hooks_path = home / ".codex" / "hooks.json"
    hooks = json.loads(hooks_path.read_text())
    hooks["hooks"]["Stop"] = []
    hooks_path.write_text(json.dumps(hooks))
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert "session_guard_hook_missing" in report["integrity"]["errors"]


def test_end_to_end_integrity_rejects_unsafe_managed_asset(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    guard = home / ".agent-token-saver" / "hooks" / "token-session-guard.py"
    guard.chmod(0o777)
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert "managed_asset_unsafe_owner_or_mode:session_guard" in report["integrity"]["errors"]
    assert report["integrity"]["session_guard_smoke"]["exit_code"] is None


def test_end_to_end_integrity_does_not_execute_unmanaged_hook_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    marker = tmp_path / "executed"
    unmanaged = tmp_path / "evil-token-stack-prompt.py"
    unmanaged.write_text(f"#!/bin/sh\ntouch {marker}\n")
    unmanaged.chmod(0o755)
    hooks_path = home / ".codex" / "hooks.json"
    hooks = json.loads(hooks_path.read_text())
    hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] = str(unmanaged)
    hooks_path.write_text(json.dumps(hooks))
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert "prompt_hook_command_path_mismatch" in report["integrity"]["errors"]
    assert not marker.exists()
