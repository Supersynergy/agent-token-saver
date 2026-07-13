#!/usr/bin/env python3
"""Install the CLI, skill and fail-open hooks without replacing agent config."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
INSTALL_HOME = HOME / ".agent-token-saver"


def atomic_json(path: Path, data: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"would merge {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"backup {backup}")
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise SystemExit(f"refusing to edit invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"refusing to edit non-object JSON: {path}")
    return value


def hook_entry(matcher: str | None, command: str, timeout: int) -> dict[str, Any]:
    entry: dict[str, Any] = {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}
    if matcher:
        entry["matcher"] = matcher
    return entry


def has_command(entries: list[Any], *needles: str) -> bool:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            command = str(hook.get("command", "")) if isinstance(hook, dict) else ""
            if any(needle in command for needle in needles):
                return True
    return False


def merge_hooks(path: Path, agent: str, dry_run: bool) -> None:
    data = load_json(path)
    hooks = data.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    prompt = hooks.setdefault("UserPromptSubmit", [])
    rtk_command = str(INSTALL_HOME / "hooks" / "rtk-rewrite.sh")
    prompt_command = str(INSTALL_HOME / "hooks" / "token-stack-prompt.py")
    matcher = (
        "Bash"
        if agent == "claude"
        else r"Bash|Shell|shell|shell_command|exec_command|functions\.exec_command"
    )
    if shutil.which("rtk") and not has_command(pre, "rtk-rewrite.sh", "rtk hook"):
        pre.append(hook_entry(matcher, rtk_command, 5))
    if not has_command(prompt, "token-stack-prompt.py"):
        prompt.append(hook_entry(None, prompt_command, 6))
    atomic_json(path, data, dry_run)


def install_copy(source: Path, target: Path, dry_run: bool, executable: bool = False) -> None:
    if dry_run:
        print(f"would copy {source} -> {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if executable:
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
    print(f"installed {target}")


def install_files(dry_run: bool) -> None:
    copies = {
        ROOT / "stack" / "catalog.json": INSTALL_HOME / "stack" / "catalog.json",
        ROOT / "scripts" / "stack_doctor.py": INSTALL_HOME / "bin" / "agent-token-saver",
        ROOT / "integration" / "hooks" / "rtk-rewrite.sh": INSTALL_HOME
        / "hooks"
        / "rtk-rewrite.sh",
        ROOT / "integration" / "hooks" / "token-stack-prompt.py": INSTALL_HOME
        / "hooks"
        / "token-stack-prompt.py",
        ROOT / "integration" / "cli" / "codex-heavy-context": INSTALL_HOME
        / "bin"
        / "codex-heavy-context",
    }
    for source, target in copies.items():
        install_copy(source, target, dry_run, executable=True)
    launcher = HOME / ".local" / "bin" / "agent-token-saver"
    if dry_run:
        print(f"would link {launcher} -> {copies[ROOT / 'scripts' / 'stack_doctor.py']}")
    else:
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.unlink(missing_ok=True)
        launcher.symlink_to(copies[ROOT / "scripts" / "stack_doctor.py"])
        print(f"linked {launcher}")
    heavy_launcher = HOME / ".local" / "bin" / "codex-heavy-context"
    heavy_target = copies[ROOT / "integration" / "cli" / "codex-heavy-context"]
    if heavy_launcher.exists() or heavy_launcher.is_symlink():
        print(f"kept existing {heavy_launcher}")
    elif dry_run:
        print(f"would link {heavy_launcher} -> {heavy_target}")
    else:
        heavy_launcher.symlink_to(heavy_target)
        print(f"linked {heavy_launcher}")


def install_skill(agent: str, project: Path, dry_run: bool) -> None:
    source = ROOT / "skills" / "agent-token-saver" / "SKILL.md"
    targets = {
        "codex": HOME / ".codex" / "skills" / "agent-token-saver" / "SKILL.md",
        "claude": HOME / ".claude" / "skills" / "agent-token-saver" / "SKILL.md",
        "hermes": HOME / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md",
        "ggcoder": HOME / ".gg" / "skills" / "agent-token-saver.md",
        "repo": project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md",
    }
    install_copy(source, targets[agent], dry_run)


def detected_agents(requested: str, project: Path) -> list[str]:
    if requested in {"codex", "claude", "hermes", "ggcoder", "repo"}:
        return [requested]
    if requested == "all":
        return ["codex", "claude", "hermes", "ggcoder", "repo"]
    found: list[str] = []
    if (HOME / ".codex").is_dir():
        found.append("codex")
    if (HOME / ".claude").is_dir():
        found.append("claude")
    if (HOME / ".hermes").is_dir() or shutil.which("hermes"):
        found.append("hermes")
    if (HOME / ".gg").is_dir() or shutil.which("ggcoder"):
        found.append("ggcoder")
    if (project / ".git").exists():
        found.append("repo")
    return found or ["repo"]


def write_config(profile: str, agents: list[str], dry_run: bool) -> None:
    atomic_json(
        INSTALL_HOME / "config.json",
        {"schema_version": 1, "profile": profile, "agents": agents},
        dry_run,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("minimal", "lean", "heavy", "news"), default="lean")
    parser.add_argument(
        "--agent",
        choices=("auto", "codex", "claude", "hermes", "ggcoder", "repo", "all"),
        default="auto",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="project root used by --agent repo (default: current directory)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    install_files(args.dry_run)
    targets = {
        "codex": HOME / ".codex" / "hooks.json",
        "claude": HOME / ".claude" / "settings.json",
    }
    agents = detected_agents(args.agent, args.project.resolve())
    for agent in agents:
        install_skill(agent, args.project.resolve(), args.dry_run)
        if agent in targets:
            merge_hooks(targets[agent], agent, args.dry_run)
    write_config(args.profile, agents, args.dry_run)
    print(f"profile={args.profile}")
    print(f"agents={','.join(agents)}")
    print(
        "third-party tools are never installed silently; run agent-token-saver doctor after apply"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
