#!/usr/bin/env python3
"""Install the CLI, skill and fail-open hooks without replacing agent config.

Runs on Python 3.11+ and is tested up to the latest stable release. The floor
is a compatibility guarantee, not a recommendation: any newer Python already on
PATH is used automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

MIN_PYTHON = (3, 11)
if sys.version_info < MIN_PYTHON:  # pragma: no cover - depends on interpreter
    # Without this, an old interpreter fails somewhere deep in the stdlib with
    # a message that says nothing about the actual problem.
    sys.exit(
        "agent-token-saver needs Python "
        f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, but this is "
        f"{sys.version_info[0]}.{sys.version_info[1]}. "
        "Install a newer Python, then re-run the installer."
    )

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
INSTALL_HOME = HOME / ".agent-token-saver"
OBSOLETE_INSTALL_FILES = (INSTALL_HOME / "hooks" / "rtk-rewrite.sh",)
SKILL_VERSION = re.compile(r"^version:\s*([^\s]+)", re.MULTILINE)
DEFAULT_POLICY_SOURCE = ROOT / "integration" / "instructions" / "compact-default.md"
DEFAULT_POLICY_START = "<!-- AGENT-TOKEN-SAVER-DEFAULT:START -->"
DEFAULT_POLICY_END = "<!-- AGENT-TOKEN-SAVER-DEFAULT:END -->"


def self_update(dry_run: bool) -> None:
    """Fast-forward the repo checkout so installs always ship the latest version."""
    if os.environ.get("ATS_SKIP_SELF_UPDATE"):
        # A live `git pull` against the real ROOT checkout runs on every
        # install regardless of --project, which makes the test suite
        # non-hermetic: 15+ installer tests each trigger a real network pull
        # within a couple of minutes, and it intermittently hit the 60s
        # timeout even though a single standalone `git pull` took <1s
        # (observed: keychain/subprocess contention under rapid repeat
        # invocation, not a slow network path). Real installs are unaffected;
        # only the test harness sets this.
        print("self-update: skipped (ATS_SKIP_SELF_UPDATE)")
        return
    if not (ROOT / ".git").is_dir() or not shutil.which("git"):
        return
    git = ["git", "-C", str(ROOT)]
    dirty = subprocess.run(
        [*git, "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        print("self-update: skipped (local changes in repo checkout)")
        return
    if dry_run:
        print("would run: git pull --ff-only")
        return
    pull = subprocess.run(
        [*git, "pull", "--ff-only", "--quiet"], capture_output=True, text=True, timeout=60
    )
    head = subprocess.run(
        [*git, "log", "-1", "--format=%h %s"], capture_output=True, text=True
    ).stdout.strip()
    if pull.returncode == 0:
        print(f"self-update: up to date @ {head}")
    else:
        print(f"self-update: pull failed (offline?), installing from local @ {head}")


def atomic_json(path: Path, data: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"would merge {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(
            f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns()}"
        )
        shutil.copy2(path, backup)
        print(f"backup {backup}")
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def atomic_text(path: Path, content: str, dry_run: bool) -> bool:
    if path.exists():
        if not path.is_file():
            raise SystemExit(f"refusing to edit non-file text target: {path}")
        try:
            current = path.read_text(encoding="utf-8")
        except OSError as error:
            raise SystemExit(f"refusing to edit unreadable text target: {path}: {error}") from error
    else:
        current = ""
    if current == content:
        return False
    if path.is_symlink():
        raise SystemExit(f"refusing to replace symlinked text target: {path}")
    if dry_run:
        print(f"would merge compact default into {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    if path.exists():
        backup = path.with_name(
            f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns()}"
        )
        shutil.copy2(path, backup)
        print(f"backup {backup}")
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.chmod(mode)
    os.replace(temporary, path)
    print(f"merged compact default into {path}")
    return True


def merged_default_policy(current: str, *, enabled: bool) -> str:
    start_count = current.count(DEFAULT_POLICY_START)
    end_count = current.count(DEFAULT_POLICY_END)
    if start_count != end_count or start_count > 1:
        raise SystemExit("refusing to edit malformed Agent Token Saver default block")

    block = (
        f"{DEFAULT_POLICY_START}\n"
        f"{DEFAULT_POLICY_SOURCE.read_text(encoding='utf-8').strip()}\n"
        f"{DEFAULT_POLICY_END}"
    )
    if start_count == 0:
        if not enabled:
            return current
        prefix = current.rstrip()
        return f"{prefix}\n\n{block}\n" if prefix else f"{block}\n"

    start = current.index(DEFAULT_POLICY_START)
    end = current.index(DEFAULT_POLICY_END, start) + len(DEFAULT_POLICY_END)
    before = current[:start].rstrip()
    after = current[end:].strip()
    parts = [part for part in (before, block if enabled else "", after) if part]
    return ("\n\n".join(parts) + "\n") if parts else ""


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
            if "token-stack-prompt.py" not in str(hook.get("command", "")):
                kept_hooks.append(hook)
        if kept_hooks:
            entry["hooks"] = kept_hooks
            kept_entries.append(entry)
    entries[:] = kept_entries


def remove_session_guard_hooks(entries: list[Any]) -> None:
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
            if "token-session-guard.py" not in str(hook.get("command", "")):
                kept_hooks.append(hook)
        if kept_hooks:
            entry["hooks"] = kept_hooks
            kept_entries.append(entry)
    entries[:] = kept_entries


def remove_worker_capsule_hooks(entries: list[Any]) -> None:
    """Remove only our old worker hook so profile switches stay idempotent."""
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
            if "agent-worker-capsule.py" not in str(hook.get("command", "")):
                kept_hooks.append(hook)
        if kept_hooks:
            entry["hooks"] = kept_hooks
            kept_entries.append(entry)
    entries[:] = kept_entries


def merge_hooks(path: Path, agent: str, profile: str, dry_run: bool) -> None:
    data = load_json(path)
    hooks = data.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    prompt = hooks.setdefault("UserPromptSubmit", [])
    stop = hooks.setdefault("Stop", [])
    prompt_command = str(INSTALL_HOME / "hooks" / "token-stack-prompt.py")
    guard_command = str(INSTALL_HOME / "hooks" / "token-session-guard.py")
    worker_command = str(INSTALL_HOME / "hooks" / "agent-worker-capsule.py")
    matcher = (
        "Bash"
        if agent == "claude"
        else r"Bash|Shell|shell|shell_command|exec_command|functions\.exec_command"
    )
    remove_repo_rtk_hooks(pre)
    remove_worker_capsule_hooks(pre)
    remove_prompt_hooks(prompt)
    remove_session_guard_hooks(stop)
    if agent == "claude" and shutil.which("rtk") and not has_command(pre, "rtk hook claude"):
        pre.append(hook_entry(matcher, "rtk hook claude", 5))
    if agent == "claude" and profile == "teams":
        pre.append(hook_entry("Agent", worker_command, 4))
    if profile != "minimal":
        prompt.append(hook_entry(None, prompt_command, 6))
        stop.append(hook_entry(None, guard_command, 8))
    atomic_json(path, data, dry_run)


def install_copy(source: Path, target: Path, dry_run: bool, executable: bool = False) -> None:
    if dry_run:
        print(f"would copy {source} -> {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    # Managed targets can be read-only on the host (agents such as Hermes mark
    # installed skills 0444). Restore owner write just long enough to replace
    # our own previous output, so a re-install stays idempotent instead of
    # failing with EACCES halfway through. A symlinked target is refused: a
    # managed asset must never be written through a link we do not control.
    if target.is_symlink():
        raise SystemExit(f"refusing to replace symlinked install target: {target}")
    if target.exists():
        current_mode = stat.S_IMODE(target.stat().st_mode)
        if not current_mode & stat.S_IWUSR:
            target.chmod(current_mode | stat.S_IWUSR)
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
        ROOT / "scripts" / "full_context_ledger.py": INSTALL_HOME / "bin" / "agent-token-ledger",
        # Sibling of the installed ledger: full_context_ledger loads it by path
        # to price the cached prefix, and degrades quietly when it is absent.
        ROOT / "scripts" / "cache_economics.py": INSTALL_HOME / "bin" / "cache_economics.py",
        ROOT / "scripts" / "external_usage_gate.py": INSTALL_HOME / "bin" / "agent-token-audit",
        ROOT / "scripts" / "llmadapter.ts": INSTALL_HOME / "bin" / "llmadapter",
        ROOT / "integration" / "hooks" / "token-stack-prompt.py": INSTALL_HOME
        / "hooks"
        / "token-stack-prompt.py",
        ROOT / "integration" / "hooks" / "token-session-guard.py": INSTALL_HOME
        / "hooks"
        / "token-session-guard.py",
        ROOT / "integration" / "hooks" / "agent-worker-capsule.py": INSTALL_HOME
        / "hooks"
        / "agent-worker-capsule.py",
        ROOT / "skills" / "agent-token-saver" / "SKILL.md": INSTALL_HOME
        / "skills"
        / "agent-token-saver"
        / "SKILL.md",
        ROOT / "integration" / "cli" / "codex-heavy-context": INSTALL_HOME
        / "bin"
        / "codex-heavy-context",
        ROOT / "integration" / "cli" / "kimi-worker": INSTALL_HOME / "bin" / "kimi-worker",
        ROOT / "integration" / "cli" / "ats-verify": INSTALL_HOME / "bin" / "ats-verify",
    }
    for source, target in copies.items():
        install_copy(source, target, dry_run, executable=True)
    install_copy(
        DEFAULT_POLICY_SOURCE,
        INSTALL_HOME / "instructions" / "compact-default.md",
        dry_run,
    )
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
    cache_launcher = HOME / ".local" / "bin" / "ats-cache"
    cache_target = copies[ROOT / "scripts" / "cache_economics.py"]
    if dry_run:
        print(f"would link {cache_launcher} -> {cache_target}")
    else:
        cache_launcher.unlink(missing_ok=True)
        cache_launcher.symlink_to(cache_target)
        print(f"linked {cache_launcher}")
    verify_launcher = HOME / ".local" / "bin" / "ats-verify"
    verify_target = copies[ROOT / "integration" / "cli" / "ats-verify"]
    if dry_run:
        print(f"would link {verify_launcher} -> {verify_target}")
    else:
        verify_launcher.unlink(missing_ok=True)
        verify_launcher.symlink_to(verify_target)
        print(f"linked {verify_launcher}")
    audit_launcher = HOME / ".local" / "bin" / "agent-token-audit"
    audit_target = copies[ROOT / "scripts" / "external_usage_gate.py"]
    if dry_run:
        print(f"would link {audit_launcher} -> {audit_target}")
    else:
        audit_launcher.unlink(missing_ok=True)
        audit_launcher.symlink_to(audit_target)
        print(f"linked {audit_launcher}")
    adapter_launcher = HOME / ".local" / "bin" / "llmadapter"
    adapter_source = ROOT / "scripts" / "llmadapter.ts"
    adapter_target = copies[adapter_source]
    adoptable = not (adapter_launcher.exists() or adapter_launcher.is_symlink())
    if adapter_launcher.is_symlink():
        adoptable = adapter_launcher.resolve(strict=False) in {
            adapter_source.resolve(),
            adapter_target.resolve(),
        }
    if not adoptable:
        print(f"kept user-owned host override {adapter_launcher}")
    elif dry_run:
        print(f"would link {adapter_launcher} -> {adapter_target}")
    else:
        adapter_launcher.unlink(missing_ok=True)
        adapter_launcher.symlink_to(adapter_target)
        print(f"linked {adapter_launcher}")
    heavy_launcher = HOME / ".local" / "bin" / "codex-heavy-context"
    heavy_target = copies[ROOT / "integration" / "cli" / "codex-heavy-context"]
    if heavy_launcher.exists() or heavy_launcher.is_symlink():
        print(f"kept user-owned host override {heavy_launcher}")
    elif dry_run:
        print(f"would link {heavy_launcher} -> {heavy_target}")
    else:
        heavy_launcher.symlink_to(heavy_target)
        print(f"linked {heavy_launcher}")
    kimi_launcher = HOME / ".local" / "bin" / "kimi-worker"
    kimi_target = copies[ROOT / "integration" / "cli" / "kimi-worker"]
    if kimi_launcher.exists() or kimi_launcher.is_symlink():
        print(f"kept user-owned host override {kimi_launcher}")
    elif dry_run:
        print(f"would link {kimi_launcher} -> {kimi_target}")
    else:
        kimi_launcher.symlink_to(kimi_target)
        print(f"linked {kimi_launcher}")


def skill_targets(project: Path) -> dict[str, Path]:
    return {
        "codex": HOME / ".codex" / "skills" / "agent-token-saver" / "SKILL.md",
        "claude": HOME / ".claude" / "skills" / "agent-token-saver" / "SKILL.md",
        "hermes": HOME / ".hermes" / "skills" / "agent-token-saver" / "SKILL.md",
        "ggcoder": HOME / ".gg" / "skills" / "agent-token-saver.md",
        "repo": project / ".agents" / "skills" / "agent-token-saver" / "SKILL.md",
    }


def instruction_targets() -> dict[str, Path]:
    return {
        "codex": HOME / ".codex" / "AGENTS.md",
        "claude": HOME / ".claude" / "CLAUDE.md",
        "hermes": HOME / ".hermes" / "SOUL.md",
        "ggcoder": HOME / "AGENTS.md",
    }


def sync_default_policies(profile: str, agents: list[str], dry_run: bool) -> list[dict[str, str]]:
    targets = instruction_targets()
    enabled = profile != "minimal"
    policy_hash = hashlib.sha256(
        DEFAULT_POLICY_SOURCE.read_text(encoding="utf-8").strip().encode()
    ).hexdigest()
    managed: list[dict[str, str]] = []
    for agent in agents:
        target = targets.get(agent)
        if target is None:
            continue
        if enabled and agent == "hermes" and not target.exists():
            print(
                "kept Hermes built-in identity: no SOUL.md exists; installed skill remains explicit"
            )
            continue
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        desired = merged_default_policy(current, enabled=enabled)
        atomic_text(target, desired, dry_run)
        if enabled:
            managed.append(
                {
                    "agent": agent,
                    "path": str(target.resolve()),
                    "policy_sha256": policy_hash,
                }
            )
    return managed


def install_skill(agent: str, project: Path, dry_run: bool) -> None:
    source = ROOT / "skills" / "agent-token-saver" / "SKILL.md"
    install_copy(source, skill_targets(project)[agent], dry_run)


def remove_visible_skill(agent: str, project: Path, dry_run: bool) -> None:
    target = skill_targets(project)[agent]
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


def write_config(
    profile: str,
    agents: list[str],
    project: Path,
    managed_default_policies: list[dict[str, str]],
    dry_run: bool,
) -> None:
    source = ROOT / "skills" / "agent-token-saver" / "SKILL.md"
    content = source.read_text(errors="replace")
    version_match = SKILL_VERSION.search(content)
    targets = skill_targets(project)
    managed_skill_paths = [
        str(targets[agent].resolve())
        for agent in agents
        if profile != "minimal" and agent in {"hermes", "ggcoder", "repo"}
    ]
    managed_asset_sources = {
        "doctor": ROOT / "scripts" / "stack_doctor.py",
        "ledger": ROOT / "scripts" / "full_context_ledger.py",
        "cache_economics": ROOT / "scripts" / "cache_economics.py",
        "audit": ROOT / "scripts" / "external_usage_gate.py",
        "llmadapter": ROOT / "scripts" / "llmadapter.ts",
        "prompt_hook": ROOT / "integration" / "hooks" / "token-stack-prompt.py",
        "session_guard": ROOT / "integration" / "hooks" / "token-session-guard.py",
        "worker_capsule": ROOT / "integration" / "hooks" / "agent-worker-capsule.py",
        "default_policy": DEFAULT_POLICY_SOURCE,
    }
    managed_asset_targets = {
        "doctor": INSTALL_HOME / "bin" / "agent-token-saver",
        "ledger": INSTALL_HOME / "bin" / "agent-token-ledger",
        "cache_economics": INSTALL_HOME / "bin" / "cache_economics.py",
        "audit": INSTALL_HOME / "bin" / "agent-token-audit",
        "llmadapter": INSTALL_HOME / "bin" / "llmadapter",
        "prompt_hook": INSTALL_HOME / "hooks" / "token-stack-prompt.py",
        "session_guard": INSTALL_HOME / "hooks" / "token-session-guard.py",
        "worker_capsule": INSTALL_HOME / "hooks" / "agent-worker-capsule.py",
        "default_policy": INSTALL_HOME / "instructions" / "compact-default.md",
    }
    atomic_json(
        INSTALL_HOME / "config.json",
        {
            "schema_version": 3,
            "profile": profile,
            "agents": agents,
            "project_root": str(project.resolve()),
            "canonical_skill": {
                "path": str((INSTALL_HOME / "skills" / "agent-token-saver" / "SKILL.md").resolve()),
                "version": version_match.group(1) if version_match else "unknown",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
            "managed_skill_paths": managed_skill_paths,
            "managed_default_policies": managed_default_policies,
            "managed_assets": [
                {
                    "name": name,
                    "path": str(managed_asset_targets[name].resolve()),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for name, path in managed_asset_sources.items()
            ],
        },
        dry_run,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("minimal", "lean", "teams", "heavy"), default="lean")
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
    parser.add_argument(
        "--no-update", action="store_true", help="skip the git fast-forward self-update"
    )
    args = parser.parse_args()
    if not args.no_update:
        self_update(args.dry_run)
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
    managed_default_policies = sync_default_policies(args.profile, agents, args.dry_run)
    write_config(
        args.profile,
        agents,
        args.project.resolve(),
        managed_default_policies,
        args.dry_run,
    )
    print(f"profile={args.profile}")
    print(f"agents={','.join(agents)}")
    print("third-party tools are never installed silently")
    doctor = INSTALL_HOME / "bin" / "agent-token-saver"
    if not args.dry_run and doctor.exists():
        print("== onboarding check ==")
        sys.stdout.flush()
        subprocess.run([sys.executable, str(doctor), "doctor"], timeout=120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
