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
    policy = install_home / "instructions" / "compact-default.md"
    canonical.parent.mkdir(parents=True)
    hook.parent.mkdir(parents=True)
    ledger.parent.mkdir(parents=True)
    policy.parent.mkdir(parents=True)
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
    shutil.copy2(ROOT / "integration" / "instructions" / "compact-default.md", policy)
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
                    "Stop": [{"hooks": [{"type": "command", "command": str(guard), "timeout": 8}]}],
                }
            }
        )
    )
    codex_agents = home / ".codex" / "AGENTS.md"
    codex_agents.write_text(
        f"{stack_doctor.DEFAULT_POLICY_START}\n"
        f"{policy.read_text().strip()}\n"
        f"{stack_doctor.DEFAULT_POLICY_END}\n"
    )
    policy_hash = hashlib.sha256(policy.read_text().strip().encode()).hexdigest()
    config = install_home / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "profile": "lean",
                "agents": ["codex"],
                "canonical_skill": {
                    "path": str(canonical),
                    "version": "3.2.0",
                    "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
                },
                "managed_skill_paths": [],
                "managed_default_policies": [
                    {
                        "agent": "codex",
                        "path": str(codex_agents),
                        "policy_sha256": policy_hash,
                    }
                ],
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
                    {
                        "name": "default_policy",
                        "path": str(policy),
                        "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
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
    # Private host-only tool names that must not leak into the public surface.
    # "synapse" is allowed because ats-synapse-prime / ats-synapse-ingest are
    # public CLI helpers backed by the synapse-memory project.
    for marker in ("superweb", "ghmax", "ghgrep"):
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


def test_require_llmadapter_fails_closed_when_adapter_is_not_ready(
    tmp_path: Path,
) -> None:
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }
    report = build_report(
        catalog,
        "lean",
        require_llmadapter=True,
        home=tmp_path,
    )
    assert report["llmadapter"]["ready"] is False
    assert report["llmadapter_required"] is True
    assert report["healthy"] is False
    assert report["status"] == "blocked"


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
    assert (
        hashlib.sha256(managed.read_bytes()).hexdigest()
        != hashlib.sha256(canonical.read_bytes()).hexdigest()
    )


def test_end_to_end_integrity_rejects_managed_default_policy_drift(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    agents = home / ".codex" / "AGENTS.md"
    agents.write_text(
        agents.read_text().replace(
            "First command filters/aggregates",
            "First command dumps every raw result",
        )
    )
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert "managed_default_policy_hash_mismatch:codex" in report["integrity"]["errors"]


def test_end_to_end_integrity_reports_verified_default_policy(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["integrity"]["default_policy"]["expected_agents"] == ["codex"]
    assert report["integrity"]["default_policy"]["verified_agents"] == ["codex"]
    assert report["integrity"]["default_policy"]["policy_sha256"]


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


def test_end_to_end_integrity_rejects_synx_doctor_in_active_hook(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_fixture(home)
    hooks_path = home / ".codex" / "hooks.json"
    hooks = json.loads(hooks_path.read_text())
    hooks["hooks"]["PreToolUse"] = [
        {"hooks": [{"type": "command", "command": "synx doctor --quick", "timeout": 6}]}
    ]
    hooks_path.write_text(json.dumps(hooks))
    catalog = {
        "profiles": {"lean": ["native"]},
        "tools": {"native": {"kind": "builtin", "required": True}},
    }

    report = build_report(catalog, "lean", check_integrations=True, home=home)

    assert report["healthy"] is False
    assert "forbidden_hot_path_synx_doctor:codex" in report["integrity"]["errors"]
    assert report["hooks"]["codex"]["hot_path"]["synx_doctor"] == 1
    assert report["integrity"]["hot_path"]["synx_doctor"] == {"codex": 1}


def test_hot_path_counter_does_not_match_synxp() -> None:
    assert stack_doctor.hot_path_counts(["synxp 'doctor state'"])["synx_doctor"] == 0


def test_doctor_reports_private_incremental_guard_state_without_transcript(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state = home / ".local" / "state" / "agent-token-saver"
    state.mkdir(parents=True)
    latest = state / "session-guard-latest.json"
    latest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "action": "checkpoint_required",
                "transcript_id": "hash-only",
                "cursor": {"byte_offset": 99},
            }
        )
    )
    latest.chmod(0o600)

    report = stack_doctor.inspect_session_guard_state(home)

    assert report == {
        "present": True,
        "safe": True,
        "mode": "incremental",
        "schema_version": 2,
        "action": "checkpoint_required",
    }


def test_doctor_reports_unsafe_guard_state_without_reading_it(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state = home / ".local" / "state" / "agent-token-saver"
    state.mkdir(parents=True)
    latest = state / "session-guard-latest.json"
    latest.write_text('{"schema_version":2,"action":"warn"}')
    latest.chmod(0o666)

    assert stack_doctor.inspect_session_guard_state(home) == {
        "present": True,
        "safe": False,
        "mode": "unsafe",
    }


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


def codex_hook_home(tmp_path: Path, *, trusted: bool) -> Path:
    home = tmp_path / "home"
    hooks_path = home / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    command = str(home / ".agent-token-saver" / "hooks" / "token-stack-prompt.py")
    hooks_path.write_text(
        json.dumps(
            {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": command}]}]}}
        )
    )
    key = f"{hooks_path}:user_prompt_submit:0:0" if trusted else "other:stop:0:0"
    (home / ".codex" / "config.toml").write_text(
        f'[hooks.state."{key}"]\ntrusted_hash = "sha256:deadbeef"\n'
    )
    return home


def test_doctor_reports_codex_hook_trust(tmp_path: Path) -> None:
    """Codex refuses untrusted hooks, so a merged hooks.json proves nothing."""
    report = stack_doctor.inspect_hooks(codex_hook_home(tmp_path, trusted=True))
    assert report["codex"]["trust"] == {"status": "ok", "trusted": 1, "untrusted": []}


def test_doctor_flags_codex_hooks_that_lost_their_trust_entry(tmp_path: Path) -> None:
    report = stack_doctor.inspect_hooks(codex_hook_home(tmp_path, trusted=False))
    trust = report["codex"]["trust"]
    assert trust["status"] == "untrusted"
    assert trust["untrusted"] == [
        f"{tmp_path / 'home' / '.codex' / 'hooks.json'}:user_prompt_submit:0:0"
    ]


def test_doctor_stays_quiet_when_codex_has_no_trust_table(tmp_path: Path) -> None:
    home = codex_hook_home(tmp_path, trusted=True)
    (home / ".codex" / "config.toml").write_text("model = 'gpt-5.6'\n")
    assert stack_doctor.inspect_hooks(home)["codex"]["trust"]["status"] == "unknown"


def test_command_is_exact_file_accepts_a_pinned_interpreter_that_exists(tmp_path: Path) -> None:
    """`<interpreter> <hook>` is ours only while the interpreter is still there."""
    command_is_exact_file = stack_doctor.command_is_exact_file

    hook = tmp_path / "hook.py"
    hook.write_text("#!/usr/bin/env python3\n")
    interpreter = tmp_path / "python3"
    interpreter.write_text("")

    assert command_is_exact_file(str(hook), hook)
    assert command_is_exact_file(f"{interpreter} {hook}", hook)
    # A pinned interpreter removed by a Python upgrade is a dead hook.
    assert not command_is_exact_file(f"{tmp_path / 'gone'} {hook}", hook)
    # Extra words are not our command shape.
    assert not command_is_exact_file(f"{interpreter} -X utf8 {hook}", hook)
    assert not command_is_exact_file(f"{interpreter} {tmp_path / 'other.py'}", hook)
