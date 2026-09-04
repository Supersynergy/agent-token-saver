#!/usr/bin/env python3
"""Read-only inventory for agent-token-saver profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "stack" / "catalog.json"
DEFAULT_CONFIG = ROOT / "config.json"
LEGACY_PROFILE_ALIASES = {"news": "teams"}
DEFAULT_POLICY_START = "<!-- AGENT-TOKEN-SAVER-DEFAULT:START -->"
DEFAULT_POLICY_END = "<!-- AGENT-TOKEN-SAVER-DEFAULT:END -->"
HOT_PATH_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("synx_doctor", re.compile(r"(?<![\w-])synx\s+doctor\b", re.IGNORECASE)),
)


def configured_profile() -> str:
    try:
        value = str(json.loads(DEFAULT_CONFIG.read_text()).get("profile", "lean"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return "lean"
    value = LEGACY_PROFILE_ALIASES.get(value, value)
    return value if value in {"minimal", "lean", "teams", "heavy"} else "lean"


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


def first_line(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0][:240] if output else "unknown"


def inspect_tool(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    kind = spec.get("kind")
    result: dict[str, Any] = {
        "name": name,
        "installed": False,
        "location": None,
        "version": None,
        "required": bool(spec.get("required")),
        "activation": spec.get("activation", "on demand"),
    }
    if kind == "builtin":
        result.update(installed=True, location="stdlib", version="builtin")
        return result
    if kind == "path":
        for candidate in spec.get("paths", []):
            path = expand_path(candidate)
            if path.is_file():
                result.update(installed=True, location=str(path), version="file")
                break
        return result
    if kind == "command":
        location = shutil.which(str(spec.get("command", name)))
        if not location:
            return result
        version_args = [str(arg) for arg in spec.get("version_args", ["--version"])]
        result.update(
            installed=True,
            location=location,
            version=first_line([location, *version_args]),
        )
        return result
    return result


RECON_SIDECARS = (
    ("gmax", ("gmax", "grepmax"), "bun add -g grepmax  (or: npm i -g grepmax)"),
    ("ghx", ("ghx",), "bun add -g @gkoreli/ghx  (or: npm i -g @gkoreli/ghx)"),
    ("supacrawl", ("supacrawl",), "uv tool install supacrawl  (or: pip install supacrawl)"),
)


def inspect_recon() -> list[dict[str, Any]]:
    result = []
    for name, probes, hint in RECON_SIDECARS:
        location = next((shutil.which(p) for p in probes if shutil.which(p)), None)
        result.append(
            {"name": name, "installed": bool(location), "location": location, "install": hint}
        )
    return result


def hook_commands(hooks: Any) -> list[str]:
    """Extract active hook commands without printing unrelated user commands."""
    if not isinstance(hooks, dict):
        return []
    commands: list[str] = []
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []):
                command = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(command, str):
                    commands.append(command)
    return commands


def hot_path_counts(commands: list[str]) -> dict[str, int]:
    """Count forbidden commands in active hooks; never execute them."""
    return {
        name: sum(bool(pattern.search(command)) for command in commands)
        for name, pattern in HOT_PATH_RULES
    }


def codex_event_key(event: str) -> str:
    """Codex trust keys use snake_case for the CamelCase hook event names."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", event).lower()


def codex_trust(home: Path, hooks: Any, path: Path) -> dict[str, Any]:
    """Report whether Codex has persisted trust for the managed hook entries.

    Codex refuses to run an untrusted hook, so a merged `hooks.json` is not
    proof that the gate or the guard ever executes. Trust is keyed by position,
    so another tool inserting an entry ahead of ours invalidates it silently.
    """
    config = home / ".codex" / "config.toml"
    try:
        state = tomllib.loads(config.read_text()).get("hooks", {}).get("state", {})
    except (OSError, tomllib.TOMLDecodeError, AttributeError):
        return {"status": "unknown", "reason": "unreadable_config"}
    if not isinstance(state, dict) or not state:
        return {"status": "unknown", "reason": "no_trust_table"}
    if not isinstance(hooks, dict):
        return {"status": "none", "trusted": 0, "untrusted": []}
    untrusted: list[str] = []
    trusted = 0
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry_index, entry in enumerate(entries):
            hook_list = entry.get("hooks", []) if isinstance(entry, dict) else []
            for hook_index, hook in enumerate(hook_list):
                command = hook.get("command") if isinstance(hook, dict) else None
                if not isinstance(command, str) or "agent-token-saver" not in command:
                    continue
                key = f"{path}:{codex_event_key(str(event))}:{entry_index}:{hook_index}"
                if key in state:
                    trusted += 1
                else:
                    untrusted.append(key)
    if not trusted and not untrusted:
        return {"status": "none", "trusted": 0, "untrusted": []}
    return {
        "status": "ok" if not untrusted else "untrusted",
        "trusted": trusted,
        "untrusted": untrusted,
    }


def inspect_hooks(home: Path | None = None) -> dict[str, Any]:
    home = home or Path.home()
    targets = {
        "codex": home / ".codex" / "hooks.json",
        "claude": home / ".claude" / "settings.json",
    }
    report: dict[str, Any] = {}
    for agent, path in targets.items():
        commands: list[str] = []
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            report[agent] = {
                "path": str(path),
                "exists": path.is_file(),
                "commands": [],
                "hot_path": hot_path_counts([]),
            }
            continue
        all_commands = hook_commands(data.get("hooks", {}))
        commands = [
            command
            for command in all_commands
            if any(
                marker in command
                for marker in (
                    "agent-token-saver",
                    "rtk-rewrite",
                    "rtk hook claude",
                    "token-stack-prompt",
                )
            )
        ]
        report[agent] = {
            "path": str(path),
            "exists": True,
            "commands": commands,
            "hot_path": hot_path_counts(all_commands),
        }
        if agent == "codex":
            report[agent]["trust"] = codex_trust(home, data.get("hooks", {}), path)
    skill_targets = {
        "hermes": home / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md",
        "ggcoder": home / ".gg" / "skills" / "agent-token-saver.md",
    }
    for agent, path in skill_targets.items():
        report[agent] = {
            "path": str(path),
            "exists": path.is_file(),
            "commands": [],
            "integration": "skill",
        }
    return report


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_resolved_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve(strict=False) == right.expanduser().resolve(strict=False)


def owned_nonwritable_file(path: Path) -> bool:
    try:
        metadata = path.stat()
    except OSError:
        return False
    return path.is_file() and metadata.st_uid == os.getuid() and not metadata.st_mode & 0o022


def instruction_targets(home: Path) -> dict[str, Path]:
    return {
        "codex": home / ".codex" / "AGENTS.md",
        "claude": home / ".claude" / "CLAUDE.md",
        "hermes": home / ".hermes" / "SOUL.md",
        "ggcoder": home / "AGENTS.md",
    }


def extract_default_policy(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    start_count = text.count(DEFAULT_POLICY_START)
    end_count = text.count(DEFAULT_POLICY_END)
    if start_count == end_count == 0:
        return None
    if start_count != 1 or end_count != 1:
        raise ValueError("malformed managed default block")
    start = text.index(DEFAULT_POLICY_START) + len(DEFAULT_POLICY_START)
    end = text.index(DEFAULT_POLICY_END, start)
    return text[start:end].strip()


def inspect_llmadapter(home: Path, *, allow_probe: bool) -> dict[str, Any]:
    canonical = home / ".agent-token-saver" / "bin" / "llmadapter"
    launcher = home / ".local" / "bin" / "llmadapter"
    bun = shutil.which("bun")
    report: dict[str, Any] = {
        "installed": canonical.is_file(),
        "canonical": str(canonical),
        "launcher": str(launcher),
        "launcher_canonical": same_resolved_path(launcher, canonical)
        if launcher.exists() or launcher.is_symlink()
        else False,
        "runtime": bun,
        "ready": False,
        "capability": None,
        "error": None,
    }
    if not report["installed"]:
        report["error"] = "canonical_missing"
        return report
    if not owned_nonwritable_file(canonical):
        report["error"] = "canonical_unsafe_owner_or_mode"
        return report
    if not report["launcher_canonical"]:
        report["error"] = "launcher_path_mismatch"
        return report
    if not bun:
        report["error"] = "bun_missing"
        return report
    if not allow_probe:
        report["error"] = "probe_blocked_by_integrity"
        return report
    try:
        result = subprocess.run(
            [bun, str(canonical), "contract", "agent-token-saver doctor probe"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        capability = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        report["error"] = "capability_probe_failed"
        return report
    workers = capability.get("max_workers")
    result_tokens = capability.get("max_result_tokens")
    prompt_bytes = capability.get("max_prompt_bytes")
    valid = (
        result.returncode == 0
        and capability.get("schema_version") == 2
        and capability.get("ask_v2") is True
        and isinstance(workers, int)
        and not isinstance(workers, bool)
        and 1 <= workers <= 3
        and isinstance(result_tokens, int)
        and not isinstance(result_tokens, bool)
        and 1 <= result_tokens <= 500
        and isinstance(prompt_bytes, int)
        and not isinstance(prompt_bytes, bool)
        and 1 <= prompt_bytes <= 1_800
    )
    report["capability"] = {
        key: capability.get(key)
        for key in (
            "schema_version",
            "ask_v2",
            "max_workers",
            "max_result_tokens",
            "max_prompt_bytes",
        )
    }
    report["ready"] = valid
    report["error"] = None if valid else "capability_contract_mismatch"
    return report


def command_is_exact_file(command: str, target: Path | None) -> bool:
    """Accept `<hook>` or `<interpreter> <hook>`; anything else is not ours.

    The installer pins a real interpreter in front of each hook so no call
    pays a version-manager shim. That interpreter must still exist: a pinned
    binary that was removed with a Python upgrade fails silently in the host,
    which is the one failure a fail-open hook cannot report by itself.
    """
    if target is None:
        return False
    try:
        parts = shlex.split(command)
        if len(parts) == 1:
            script = parts[0]
        elif len(parts) == 2 and Path(parts[0]).expanduser().is_file():
            script = parts[1]
        else:
            return False
        resolved = Path(script).expanduser().resolve(strict=True)
        expected = target.expanduser().resolve(strict=True)
    except (OSError, ValueError):
        return False
    return resolved == expected


def skill_version(path: Path) -> str:
    try:
        for line in path.read_text(errors="replace").splitlines()[:20]:
            if line.startswith("version:"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return "unknown"


def inspect_session_guard_state(home: Path) -> dict[str, Any]:
    """Describe only bounded guard state metadata; never expose transcript data."""
    path = home / ".local" / "state" / "agent-token-saver" / "session-guard-latest.json"
    report: dict[str, Any] = {"present": path.is_file(), "safe": False, "mode": "absent"}
    if not path.is_file():
        return report
    if not owned_nonwritable_file(path):
        report["mode"] = "unsafe"
        return report
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        report["mode"] = "invalid"
        return report
    if not isinstance(value, dict):
        report["mode"] = "invalid"
        return report
    schema_version = value.get("schema_version")
    action = value.get("action")
    if schema_version not in {1, 2} or action not in {"continue", "warn", "checkpoint_required"}:
        report["mode"] = "invalid"
        return report
    report.update(
        safe=True,
        mode="incremental" if schema_version == 2 else "subprocess_fallback",
        schema_version=schema_version,
        action=action,
    )
    return report


def inspect_integrity(profile: str, hooks: dict[str, Any], home: Path) -> dict[str, Any]:
    install_home = home / ".agent-token-saver"
    config_path = install_home / "config.json"
    canonical = install_home / "skills" / "agent-token-saver" / "SKILL.md"
    errors: list[str] = []
    warnings: list[str] = []
    try:
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError, AttributeError):
        config = {}
        errors.append("missing_or_invalid_install_config")
    config_safe = config_path.exists() and owned_nonwritable_file(config_path)
    if config_path.exists() and not config_safe:
        errors.append("install_config_unsafe_owner_or_mode")
    if int(config.get("schema_version", 0) or 0) < 3:
        errors.append("install_config_schema_version<3")
    if not canonical.is_file():
        errors.append("canonical_skill_missing")
        canonical_hash = ""
        canonical_version = "unknown"
    else:
        canonical_hash = file_sha256(canonical)
        canonical_version = skill_version(canonical)
        if not owned_nonwritable_file(canonical):
            errors.append("canonical_skill_unsafe_owner_or_mode")
    manifest = config.get("canonical_skill") if isinstance(config, dict) else None
    if not isinstance(manifest, dict):
        errors.append("canonical_skill_manifest_missing")
    else:
        if not same_resolved_path(Path(str(manifest.get("path") or "")), canonical):
            errors.append("canonical_skill_manifest_path_mismatch")
        if str(manifest.get("sha256") or "") != canonical_hash:
            errors.append("canonical_skill_manifest_hash_mismatch")
        if str(manifest.get("version") or "") != canonical_version:
            errors.append("canonical_skill_manifest_version_mismatch")
    for raw_path in config.get("managed_skill_paths", []) if isinstance(config, dict) else []:
        path = Path(str(raw_path)).expanduser()
        if not path.is_file():
            errors.append(f"managed_skill_missing:{path}")
        elif not owned_nonwritable_file(path):
            errors.append(f"managed_skill_unsafe_owner_or_mode:{path}")
        elif file_sha256(path) != canonical_hash:
            errors.append(f"managed_skill_hash_mismatch:{path}")
    asset_paths: dict[str, Path] = {}
    asset_integrity: dict[str, bool] = {}
    for asset in config.get("managed_assets", []) if isinstance(config, dict) else []:
        if not isinstance(asset, dict):
            errors.append("invalid_managed_asset_manifest")
            continue
        path = Path(str(asset.get("path") or "")).expanduser()
        name = str(asset.get("name") or "unknown")
        asset_paths[name] = path
        asset_integrity[name] = False
        if not path.is_file():
            errors.append(f"managed_asset_missing:{name}")
        elif not owned_nonwritable_file(path):
            errors.append(f"managed_asset_unsafe_owner_or_mode:{name}")
        elif file_sha256(path) != str(asset.get("sha256") or ""):
            errors.append(f"managed_asset_hash_mismatch:{name}")
        else:
            asset_integrity[name] = True

    configured_agents = set(config.get("agents", [])) if isinstance(config, dict) else set()
    target_paths = instruction_targets(home)
    expected_default_agents = configured_agents & set(target_paths)
    if not target_paths["hermes"].exists():
        expected_default_agents.discard("hermes")
    if profile == "minimal":
        expected_default_agents.clear()
    default_policy_report: dict[str, Any] = {
        "expected_agents": sorted(expected_default_agents),
        "verified_agents": [],
        "policy_sha256": "",
    }
    canonical_policy = asset_paths.get("default_policy")
    if canonical_policy is not None and asset_integrity.get("default_policy", False):
        canonical_policy_body = canonical_policy.read_text(encoding="utf-8").strip()
        canonical_policy_hash = hashlib.sha256(canonical_policy_body.encode()).hexdigest()
        default_policy_report["policy_sha256"] = canonical_policy_hash
    else:
        canonical_policy_hash = ""

    managed_defaults = (
        config.get("managed_default_policies", []) if isinstance(config, dict) else []
    )
    if not isinstance(managed_defaults, list):
        errors.append("invalid_managed_default_policy_manifest")
        managed_defaults = []
    entries_by_agent: dict[str, dict[str, Any]] = {}
    for entry in managed_defaults:
        if not isinstance(entry, dict):
            errors.append("invalid_managed_default_policy_manifest")
            continue
        agent = str(entry.get("agent") or "")
        if agent not in target_paths or agent in entries_by_agent:
            errors.append(f"invalid_managed_default_policy_agent:{agent or 'unknown'}")
            continue
        entries_by_agent[agent] = entry

    if profile == "minimal":
        if entries_by_agent:
            errors.append("minimal_profile_has_default_policy_manifest")
        for agent in sorted(configured_agents & set(target_paths)):
            path = target_paths[agent]
            if not path.is_file():
                continue
            try:
                body = extract_default_policy(path)
            except (OSError, UnicodeError, ValueError):
                errors.append(f"managed_default_policy_malformed:{agent}")
                continue
            if body is not None:
                errors.append(f"minimal_profile_has_default_policy:{agent}")
    else:
        for agent in sorted(expected_default_agents):
            entry = entries_by_agent.get(agent)
            path = target_paths[agent]
            if entry is None:
                errors.append(f"managed_default_policy_manifest_missing:{agent}")
                continue
            if not same_resolved_path(Path(str(entry.get("path") or "")), path):
                errors.append(f"managed_default_policy_path_mismatch:{agent}")
                continue
            if str(entry.get("policy_sha256") or "") != canonical_policy_hash:
                errors.append(f"managed_default_policy_manifest_hash_mismatch:{agent}")
                continue
            if not owned_nonwritable_file(path):
                errors.append(f"managed_default_policy_unsafe_owner_or_mode:{agent}")
                continue
            try:
                body = extract_default_policy(path)
            except (OSError, UnicodeError, ValueError):
                errors.append(f"managed_default_policy_malformed:{agent}")
                continue
            if body is None:
                errors.append(f"managed_default_policy_missing:{agent}")
            elif hashlib.sha256(body.encode()).hexdigest() != canonical_policy_hash:
                errors.append(f"managed_default_policy_hash_mismatch:{agent}")
            else:
                default_policy_report["verified_agents"].append(agent)
        for agent in sorted(set(entries_by_agent) - expected_default_agents):
            errors.append(f"unexpected_managed_default_policy:{agent}")

    hot_path = {
        agent: int(hooks.get(agent, {}).get("hot_path", {}).get("synx_doctor", 0))
        for agent in sorted(configured_agents & {"codex", "claude"})
    }
    for agent, count in hot_path.items():
        if count:
            errors.append(f"forbidden_hot_path_synx_doctor:{agent}")
    prompt_commands = [
        command
        for agent in configured_agents & {"codex", "claude"}
        for command in hooks.get(agent, {}).get("commands", [])
        if "token-stack-prompt.py" in command
    ]
    prompt_smoke: dict[str, Any] = {
        "commands": len(prompt_commands),
        "exit_code": None,
        "canonical_route": profile == "minimal",
    }
    if profile == "minimal":
        if prompt_commands:
            errors.append("minimal_profile_has_prompt_hook")
    elif not prompt_commands:
        errors.append("prompt_hook_missing")
    else:
        if len(prompt_commands) != len(configured_agents & {"codex", "claude"}):
            warnings.append("prompt_hook_count_differs_from_configured_agents")
        command = prompt_commands[0]
        if not config_safe or not asset_integrity.get("prompt_hook", False):
            prompt_smoke["canonical_route"] = False
        elif not all(
            command_is_exact_file(candidate, asset_paths.get("prompt_hook"))
            for candidate in prompt_commands
        ):
            errors.append("prompt_hook_command_path_mismatch")
            prompt_smoke["canonical_route"] = False
        else:
            try:
                result = subprocess.run(
                    shlex.split(command),
                    input=json.dumps({"prompt": "Audit token context compression safely"}),
                    capture_output=True,
                    text=True,
                    timeout=6,
                    check=False,
                    env={**os.environ, "HOME": str(home)},
                )
                prompt_smoke["exit_code"] = result.returncode
                payload = json.loads(result.stdout) if result.stdout else {}
                context = str(payload.get("hookSpecificOutput", {}).get("additionalContext", ""))
                prompt_smoke["canonical_route"] = (
                    result.returncode == 0 and str(canonical.resolve()) in context
                )
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                prompt_smoke["canonical_route"] = False
        if (
            not prompt_smoke["canonical_route"]
            and config_safe
            and asset_integrity.get("prompt_hook", False)
            and "prompt_hook_command_path_mismatch" not in errors
        ):
            errors.append("prompt_hook_canonical_route_mismatch")
    guard_commands = [
        command
        for agent in configured_agents & {"codex", "claude"}
        for command in hooks.get(agent, {}).get("commands", [])
        if "token-session-guard.py" in command
    ]
    guard_smoke: dict[str, Any] = {
        "commands": len(guard_commands),
        "exit_code": None,
        "valid": profile == "minimal",
    }
    if profile == "minimal":
        if guard_commands:
            errors.append("minimal_profile_has_session_guard_hook")
    elif not guard_commands:
        errors.append("session_guard_hook_missing")
    else:
        if len(guard_commands) != len(configured_agents & {"codex", "claude"}):
            warnings.append("session_guard_hook_count_differs_from_configured_agents")
        if not config_safe or not asset_integrity.get("session_guard", False):
            guard_smoke["valid"] = False
        elif not all(
            command_is_exact_file(candidate, asset_paths.get("session_guard"))
            for candidate in guard_commands
        ):
            errors.append("session_guard_command_path_mismatch")
            guard_smoke["valid"] = False
        else:
            try:
                with tempfile.TemporaryDirectory(prefix="ats-doctor-") as directory:
                    temporary = Path(directory)
                    transcript = temporary / "run.jsonl"
                    transcript.write_text(
                        json.dumps(
                            {
                                "usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 40,
                                    "output_tokens": 5,
                                }
                            }
                        )
                        + "\n"
                    )
                    transcript.chmod(0o600)
                    result = subprocess.run(
                        shlex.split(guard_commands[0]),
                        input=json.dumps(
                            {
                                "hook_event_name": "Stop",
                                "session_id": "agent-token-saver-doctor",
                                "transcript_path": str(transcript),
                            }
                        ),
                        capture_output=True,
                        text=True,
                        timeout=8,
                        check=False,
                        env={
                            **os.environ,
                            "HOME": str(home),
                            "ATS_TRANSCRIPT_ROOTS": str(temporary),
                            "ATS_GUARD_STATE_DIR": str(temporary / "state"),
                        },
                    )
                    guard_smoke["exit_code"] = result.returncode
                    payload = json.loads(result.stdout) if result.stdout else None
                    guard_smoke["valid"] = result.returncode == 0 and payload == {}
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                guard_smoke["valid"] = False
        if (
            not guard_smoke["valid"]
            and config_safe
            and asset_integrity.get("session_guard", False)
            and "session_guard_command_path_mismatch" not in errors
        ):
            errors.append("session_guard_hook_smoke_failed")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "canonical_skill": {
            "path": str(canonical),
            "version": canonical_version,
            "sha256": canonical_hash,
        },
        "prompt_hook_smoke": prompt_smoke,
        "session_guard_smoke": guard_smoke,
        "session_guard_state": inspect_session_guard_state(home),
        "default_policy": default_policy_report,
        "hot_path": {"synx_doctor": hot_path},
    }


def build_report(
    catalog: dict[str, Any],
    profile: str,
    *,
    check_integrations: bool = False,
    require_llmadapter: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    names = catalog["profiles"][profile]
    tools = [inspect_tool(name, catalog["tools"][name]) for name in names]
    missing_required = [
        item["name"] for item in tools if item["required"] and not item["installed"]
    ]
    missing_optional = [
        item["name"] for item in tools if not item["required"] and not item["installed"]
    ]
    installed_count = sum(bool(item["installed"]) for item in tools)
    home = home or Path.home()
    hooks = inspect_hooks(home)
    integrity = (
        inspect_integrity(profile, hooks, home)
        if check_integrations
        else {"ok": True, "errors": [], "warnings": [], "prompt_hook_smoke": {}}
    )
    llmadapter = inspect_llmadapter(home, allow_probe=integrity["ok"])
    healthy = (
        not missing_required and integrity["ok"] and (llmadapter["ready"] or not require_llmadapter)
    )
    profile_complete = healthy and not missing_optional
    return {
        "profile": profile,
        "tools": tools,
        "recon": inspect_recon(),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "hooks": hooks,
        "integrity": integrity,
        "llmadapter": llmadapter,
        "llmadapter_required": require_llmadapter,
        "healthy": healthy,
        "profile_complete": profile_complete,
        "status": "full" if profile_complete else ("core-ready" if healthy else "blocked"),
        "coverage_percent": round(installed_count / len(tools) * 100, 2) if tools else 100.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-token-saver")
    subparsers = parser.add_subparsers(dest="command")
    doctor = subparsers.add_parser("doctor", help="inspect one profile")
    doctor.add_argument(
        "--profile",
        choices=("minimal", "lean", "teams", "heavy"),
        default=None,
        help="profile to inspect (default: installed profile, else lean)",
    )
    doctor.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument(
        "--require-llmadapter",
        action="store_true",
        help="fail unless the managed v2 adapter and Bun runtime are ready",
    )
    args = parser.parse_args()
    if args.command != "doctor":
        parser.print_help()
        return 0
    catalog = json.loads(args.catalog.read_text())
    profile = args.profile or configured_profile()
    report = build_report(
        catalog,
        profile,
        check_integrations=True,
        require_llmadapter=args.require_llmadapter,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"profile={profile} status={report['status']} "
            f"coverage={report['coverage_percent']:.0f}%"
        )
        for item in report["tools"]:
            marker = "ok" if item["installed"] else ("MISSING" if item["required"] else "optional")
            version = f" | {item['version']}" if item["version"] else ""
            print(f"{marker:8} {item['name']:18} {item['activation']}{version}")
        for item in report["recon"]:
            if item["installed"]:
                print(f"recon    {item['name']:18} ok | {item['location']}")
            else:
                print(f"recon    {item['name']:18} MISSING → {item['install']}")
        for agent, hook in report["hooks"].items():
            if hook.get("integration") == "skill":
                marker = "installed" if hook["exists"] else "optional"
                print(f"skill    {agent:18} {marker}")
            else:
                trust = hook.get("trust", {})
                suffix = ""
                if trust.get("status") == "untrusted":
                    suffix = f" · {len(trust['untrusted'])} UNTRUSTED (codex will not run them)"
                elif trust.get("status") == "ok":
                    suffix = f" · {trust['trusted']} trusted"
                print(
                    f"hooks    {agent:18} {len(hook['commands'])} "
                    f"agent-token-saver entries{suffix}"
                )
        default_policy = report["integrity"]["default_policy"]
        print(
            f"default  compact-policy     "
            f"{len(default_policy['verified_agents'])}/"
            f"{len(default_policy['expected_agents'])} verified"
        )
        guard_state = report["integrity"]["session_guard_state"]
        action = f" action={guard_state['action']}" if guard_state.get("safe") else ""
        print(f"guard    session-state       {guard_state['mode']}{action}")
        recon_ok = sum(1 for r in report["recon"] if r["installed"])
        layers_ok = sum(1 for t in report["tools"] if t["installed"])
        summary = (
            f"onboarding: {layers_ok}/{len(report['tools'])} layers · "
            f"{recon_ok}/{len(report['recon'])} recon sidecars"
        )
        if recon_ok < len(report["recon"]) or layers_ok < len(report["tools"]):
            summary += " — install MISSING lines above, then rerun: agent-token-saver doctor"
        print(summary)
        for error in report["integrity"]["errors"]:
            print(f"BLOCKED  integrity          {error}")
        for warning in report["integrity"]["warnings"]:
            print(f"warning  integrity          {warning}")
        adapter = report["llmadapter"]
        print(f"adapter  llmadapter         {'ready' if adapter['ready'] else adapter['error']}")
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
