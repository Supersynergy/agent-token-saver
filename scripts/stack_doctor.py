#!/usr/bin/env python3
"""Read-only inventory for agent-token-saver profiles."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "stack" / "catalog.json"
DEFAULT_CONFIG = ROOT / "config.json"


def configured_profile() -> str:
    try:
        value = json.loads(DEFAULT_CONFIG.read_text()).get("profile", "lean")
    except (OSError, json.JSONDecodeError, AttributeError):
        return "lean"
    return value if value in {"minimal", "lean", "heavy", "news"} else "lean"


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


def inspect_hooks() -> dict[str, Any]:
    home = Path.home()
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
                        for marker in ("agent-token-saver", "rtk-rewrite", "token-stack-prompt")
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


def build_report(catalog: dict[str, Any], profile: str) -> dict[str, Any]:
    names = catalog["profiles"][profile]
    tools = [inspect_tool(name, catalog["tools"][name]) for name in names]
    missing_required = [
        item["name"] for item in tools if item["required"] and not item["installed"]
    ]
    return {
        "profile": profile,
        "tools": tools,
        "missing_required": missing_required,
        "hooks": inspect_hooks(),
        "healthy": not missing_required,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-token-saver")
    subparsers = parser.add_subparsers(dest="command")
    doctor = subparsers.add_parser("doctor", help="inspect one profile")
    doctor.add_argument(
        "--profile",
        choices=("minimal", "lean", "heavy", "news"),
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
    report = build_report(catalog, profile)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"profile={args.profile} healthy={'yes' if report['healthy'] else 'no'}")
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
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
