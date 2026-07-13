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
from contextlib import suppress
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
INSTALL_HOME = HOME / ".agent-token-saver"
OBSOLETE_INSTALL_FILES = (
    INSTALL_HOME / "hooks" / "rtk-rewrite.sh",
)


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


def remove_repo_rtk_hooks(entries: list[Any]) -> None:
    kept_entries: list[Any] = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept_entries.append(entry)
            continue
        kept_hooks = []
        for hook in entry.get("hooks", []):
            if not isinstance(hook, dict):
                kept_hooks.append(hook)
                continue
            current = str(hook.get("command", ""))
            repo_hook = "agent-token-saver" in current and (
                "rtk-rewrite.sh" in current or "rtk_rewrite.py" in current
            )
            if not repo_hook:
                kept_hooks.append(hook)
        if kept_hooks:
            entry["hooks"] = kept_hooks
            kept_entries.append(entry)
    entries[:] = kept_entries


def remove_prompt_hooks(entries: list[Any]) -> None:
    entries[:] = [
        entry
        for entry in entries
        if not (
            isinstance(entry, dict)
            and has_command([entry], "token-stack-prompt.py")
        )
    ]


def merge_hooks(path: Path, agent: str, profile: str, dry_run: bool) -> None:
    data = load_json(path)
    hooks = data.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    prompt = hooks.setdefault("UserPromptSubmit", [])
    prompt_command = str(INSTALL_HOME / "hooks" / "token-stack-prompt.py")
    matcher = (
        "Bash"
        if agent == "claude"
        else r"Bash|Shell|shell|shell_command|exec_command|functions\.exec_command"
    )
    remove_repo_rtk_hooks(pre)
    remove_prompt_hooks(prompt)
    if agent == "claude" and shutil.which("rtk") and not has_command(pre, "rtk hook claude"):
        pre.append(hook_entry(matcher, "rtk hook claude", 5))
    if profile != "minimal":
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


def remove_obsolete_install_files(dry_run: bool) -> None:
    """Prune files written by older universal installers, never user config."""
    for path in OBSOLETE_INSTALL_FILES:
        if not (path.exists() or path.is_symlink()):
            continue
        if dry_run:
            print(f"would remove obsolete {path}")
            continue
        path.unlink()
        print(f"removed obsolete {path}")


def install_files(dry_run: bool) -> None:
    copies = {
        ROOT / "stack" / "catalog.json": INSTALL_HOME / "stack" / "catalog.json",
        ROOT / "scripts" / "stack_doctor.py": INSTALL_HOME / "bin" / "agent-token-saver",
        ROOT / "scripts" / "full_context_ledger.py": INSTALL_HOME
        / "bin"
        / "agent-token-ledger",
        ROOT / "integration" / "hooks" / "token-stack-prompt.py": INSTALL_HOME
        / "hooks"
        / "token-stack-prompt.py",
        ROOT / "skills" / "agent-token-saver" / "SKILL.md": INSTALL_HOME
        / "skills"
        / "agent-token-saver"
        / "SKILL.md",
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
    ledger_launcher = HOME / ".local" / "bin" / "agent-token-ledger"
    ledger_target = copies[ROOT / "scripts" / "full_context_ledger.py"]
    if dry_run:
        print(f"would link {ledger_launcher} -> {ledger_target}")
    else:
        ledger_launcher.unlink(missing_ok=True)
        ledger_launcher.symlink_to(ledger_target)
        print(f"linked {ledger_launcher}")
    heavy_launcher = HOME / ".local" / "bin" / "codex-heavy-context"
    heavy_target = copies[ROOT / "integration" / "cli" / "codex-heavy-context"]
    if heavy_launcher.exists() or heavy_launcher.is_symlink():
        print(f"kept user-owned host override {heavy_launcher}")
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


def remove_visible_skill(agent: str, project: Path, dry_run: bool) -> None:
    targets = {
        "codex": HOME / ".codex" / "skills" / "agent-token-saver" / "SKILL.md",
        "claude": HOME / ".claude" / "skills" / "agent-token-saver" / "SKILL.md",
        "hermes": HOME / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md",
        "ggcoder": HOME / ".gg" / "skills" / "agent-token-saver.md",
        "repo": project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md",
    }
    target = targets[agent]
    if not target.exists():
        return
    try:
        content = target.read_text(errors="replace")
    except OSError:
        print(f"kept unreadable skill {target}")
        return
    managed = "name: agent-token-saver" in content and "author: Supersynergy" in content
    if not managed:
        print(f"kept unmanaged skill {target}")
        return
    if dry_run:
        print(f"would remove fixed-context skill {target}")
        return
    target.unlink()
    with suppress(OSError):
        target.parent.rmdir()
    print(f"removed fixed-context skill {target}")


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
    remove_obsolete_install_files(args.dry_run)
    install_files(args.dry_run)
    targets = {
        "codex": HOME / ".codex" / "hooks.json",
        "claude": HOME / ".claude" / "settings.json",
    }
    agents = detected_agents(args.agent, args.project.resolve())
    for agent in agents:
        if agent in {"codex", "claude"} or args.profile == "minimal":
            remove_visible_skill(agent, args.project.resolve(), args.dry_run)
        elif args.profile != "minimal":
            install_skill(agent, args.project.resolve(), args.dry_run)
        if agent in targets:
            merge_hooks(targets[agent], agent, args.profile, args.dry_run)
    write_config(args.profile, agents, args.dry_run)
    print(f"profile={args.profile}")
    print(f"agents={','.join(agents)}")
    print(
        "third-party tools are never installed silently; run agent-token-saver doctor after apply"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
