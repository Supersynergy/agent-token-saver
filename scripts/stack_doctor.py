#!/usr/bin/env python3
"""Read-only inventory for agent-token-saver profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "stack" / "catalog.json"
DEFAULT_CONFIG = ROOT / "config.json"
LEGACY_PROFILE_ALIASES = {"news": "teams"}


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
            report[agent] = {"path": str(path), "exists": path.is_file(), "commands": []}
            continue
        hooks = data.get("hooks", {})
        for entries in hooks.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                for hook in entry.get("hooks", []) if isinstance(entry, dict) else []:
                    command = hook.get("command") if isinstance(hook, dict) else None
                    if command and any(
                        marker in command
                        for marker in (
                            "agent-token-saver",
                            "rtk-rewrite",
                            "rtk hook claude",
                            "token-stack-prompt",
                        )
                    ):
                        commands.append(command)
        report[agent] = {"path": str(path), "exists": True, "commands": commands}
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


def command_is_exact_file(command: str, target: Path | None) -> bool:
    if target is None:
        return False
    try:
        parts = shlex.split(command)
        resolved = Path(parts[0]).expanduser().resolve(strict=True) if len(parts) == 1 else None
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
    if int(config.get("schema_version", 0) or 0) < 2:
        errors.append("install_config_schema_version<2")
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
    }


def build_report(
    catalog: dict[str, Any],
    profile: str,
    *,
    check_integrations: bool = False,
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
    healthy = not missing_required and integrity["ok"]
    profile_complete = healthy and not missing_optional
    return {
        "profile": profile,
        "tools": tools,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "hooks": hooks,
        "integrity": integrity,
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
    args = parser.parse_args()
    if args.command != "doctor":
        parser.print_help()
        return 0
    catalog = json.loads(args.catalog.read_text())
    profile = args.profile or configured_profile()
    report = build_report(catalog, profile, check_integrations=True)
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
        for agent, hook in report["hooks"].items():
            if hook.get("integration") == "skill":
                marker = "installed" if hook["exists"] else "optional"
                print(f"skill    {agent:18} {marker}")
            else:
                print(f"hooks    {agent:18} {len(hook['commands'])} agent-token-saver entries")
        for error in report["integrity"]["errors"]:
            print(f"BLOCKED  integrity          {error}")
        for warning in report["integrity"]["warnings"]:
            print(f"warning  integrity          {warning}")
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
