#!/usr/bin/env python3
"""Install optional agent-token-saver stack tools.

Installs rtk, tilth, graphify, codegraph, context-mode, and si (skill-router)
using the best available method per platform. Wires each tool into the
detected agent hosts (Claude Code, Codex, Hermes, GG Coder, OpenCode, Devin).

Contract: fail-open (missing package manager -> skip tool, never error) -
idempotent (skip if already installed at or above target version) -
non-destructive (never overwrites user config without backup) -
no silent installs (prints every action).

Runs on Python 3.11+ (same floor as the main installer). The Bash wrapper
``install_stack_tools.sh`` delegates here for ``curl | bash`` users.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

HOME = Path.home()
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

# Tool install order: lightest first.
ALL_TOOLS = ("si", "rtk", "tilth", "context-mode", "graphify", "codegraph")


class Version(NamedTuple):
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, raw: str) -> Version | None:
        """Extract the first ``N.N.N`` triple from *raw*."""
        import re

        match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw)
        if not match:
            return None
        return cls(int(match[1]), int(match[2]), int(match[3]))

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return tuple(self) >= tuple(other)


@dataclass
class PlatformInfo:
    os: str
    arch: str

    @classmethod
    def detect(cls) -> PlatformInfo:
        os_name = platform.system().lower()
        if os_name == "darwin":
            os_name = "darwin"
        elif os_name == "linux":
            os_name = "linux"
        arch = platform.machine().lower()
        if arch in ("arm64", "aarch64"):
            arch = "arm64"
        elif arch in ("x86_64", "amd64"):
            arch = "amd64"
        return cls(os=os_name, arch=arch)


@dataclass
class ToolStatus:
    name: str
    installed: bool
    version: str = ""
    path: str = ""


def have(command: str) -> bool:
    return shutil.which(command) is not None


def get_latest_tag(repo: str) -> str:
    """Fetch the latest release tag from GitHub, stripped of leading ``v``."""
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        return tag.lstrip("v")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return ""


def version_ge(installed: str, target: str) -> bool:
    """Return True if *installed* >= *target* using tuple comparison."""
    if not installed or installed == "unknown":
        return False
    if not target:
        return True
    v_installed = Version.parse(installed)
    v_target = Version.parse(target)
    if v_installed is None or v_target is None:
        return installed == target
    return v_installed >= v_target


def backup_file(path: Path, dry_run: bool = False) -> Path | None:
    """Copy *path* to a timestamped backup. Returns the backup path or None."""
    if not path.exists():
        return None
    bak = path.with_suffix(f"{path.suffix}.bak.{time.strftime('%Y%m%d%H%M%S')}")
    if not dry_run:
        shutil.copy2(path, bak)
        log(f"backed up {path} -> {bak}")
    return bak


# ── logging ──────────────────────────────────────────────────────────────


def log(msg: str) -> None:
    print(f"\033[0;34m==\033[0m {msg}")


def ok(msg: str) -> None:
    print(f"\033[0;32m✓\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"\033[0;33m⚠\033[0m {msg}")


def skip(msg: str) -> None:
    print(f"\033[0;90m⊘\033[0m {msg}")


def err(msg: str) -> None:
    print(f"\033[0;31m✗\033[0m {msg}")


# ── host detection ────────────────────────────────────────────────────────


def detect_hosts(
    requested: str = "",
    env_hosts: str = "",
) -> list[str]:
    """Return the list of agent hosts to wire tools into."""
    if requested:
        return [h.strip() for h in requested.split(",") if h.strip()]
    if env_hosts:
        return [h.strip() for h in env_hosts.split(",") if h.strip()]
    found: list[str] = []
    if (HOME / ".claude").is_dir():
        found.append("claude")
    if (HOME / ".codex").is_dir():
        found.append("codex")
    if (HOME / ".hermes").is_dir() or have("hermes"):
        found.append("hermes")
    if (HOME / ".gg").is_dir() or have("ggcoder"):
        found.append("ggcoder")
    if (HOME / ".config" / "opencode").is_dir():
        found.append("opencode")
    if os.environ.get("DEVIN") or (HOME / ".devin").is_dir():
        found.append("devin")
    return found or ["claude"]


# ── tool status ───────────────────────────────────────────────────────────


def check_tool(name: str) -> ToolStatus:
    """Check if *name* is installed and return its status."""
    if not have(name):
        return ToolStatus(name=name, installed=False)
    version = ""
    path = shutil.which(name) or ""
    try:
        if name == "si":
            version = "runtime"
        elif name == "rtk":
            version = (
                subprocess.run([name, "--version"], capture_output=True, text=True, timeout=4)
                .stdout.strip()
                .split("\n")[0]
            )
        elif name == "tilth":
            version = (
                subprocess.run([name, "--version"], capture_output=True, text=True, timeout=4)
                .stdout.strip()
                .split("\n")[0]
            )
        elif name == "context-mode":
            version = "installed"
        elif name == "graphify":
            version = (
                subprocess.run([name, "--version"], capture_output=True, text=True, timeout=4)
                .stdout.strip()
                .split("\n")[0]
            )
        elif name == "codegraph":
            version = (
                subprocess.run([name, "version"], capture_output=True, text=True, timeout=4)
                .stdout.strip()
                .split("\n")[0]
            )
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ToolStatus(name=name, installed=True, version=version, path=path)


def check_all_tools() -> list[ToolStatus]:
    return [check_tool(name) for name in ALL_TOOLS]


# ── tool installers ──────────────────────────────────────────────────────


def install_si(dry_run: bool = False) -> bool:
    log("si (skill-router)")
    if have("si"):
        skip(f"si already installed at {shutil.which('si')}")
        return True
    url = "https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh"
    if dry_run:
        log(f"would: curl -fsSL {url} | bash -s -- all")
        return False
    if not have("curl"):
        warn("curl not found, skipping si")
        return False
    subprocess.run(
        ["bash", "-c", f"curl -fsSL {url} | bash -s -- all"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if have("si"):
        ok("si installed")
        return True
    err("si install failed")
    return False


def install_rtk(dry_run: bool = False, method: str = "") -> bool:
    log("rtk (token-compression proxy)")
    latest = get_latest_tag("rtk-ai/rtk")
    if have("rtk"):
        status = check_tool("rtk")
        if version_ge(status.version, latest):
            skip(f"rtk {status.version} >= {latest}")
            return True
        log(f"rtk {status.version} < {latest}, upgrading")
    if not method:
        pf = PlatformInfo.detect()
        method = "brew" if pf.os == "darwin" and have("brew") else "cargo"
    if dry_run:
        log(f"would: install rtk via {method} ({latest})")
        return False
    if method == "brew":
        subprocess.run(["brew", "install", "rtk"], timeout=120)
    elif method == "cargo":
        if not have("cargo"):
            warn("cargo not found, skipping rtk (install Rust or use brew on macOS)")
            return False
        subprocess.run(["cargo", "install", "rtk", "--locked"], timeout=600)
    else:
        err(f"unknown rtk method: {method}")
        return False
    if have("rtk"):
        ok(f"rtk installed: {check_tool('rtk').version}")
        return True
    return False


def install_tilth(dry_run: bool = False) -> bool:
    log("tilth (AST code retrieval)")
    latest = get_latest_tag("jahala/tilth")
    if have("tilth"):
        status = check_tool("tilth")
        if version_ge(status.version, latest):
            skip(f"tilth {status.version} >= {latest}")
            return True
        log(f"tilth {status.version} < {latest}, upgrading")
    if dry_run:
        log(f"would: cargo install tilth --locked ({latest})")
        return False
    if not have("cargo"):
        warn("cargo not found, skipping tilth (install Rust toolchain first)")
        return False
    subprocess.run(["cargo", "install", "tilth", "--locked", "--force"], timeout=600)
    if have("tilth"):
        ok(f"tilth installed: {check_tool('tilth').version}")
        return True
    return False


def install_context_mode(dry_run: bool = False) -> bool:
    log("context-mode (FTS5 session sandbox)")
    if have("context-mode"):
        skip(f"context-mode already installed at {shutil.which('context-mode')}")
        return True
    if dry_run:
        log("would: install context-mode (npm or bun)")
        return False
    if have("npm"):
        subprocess.run(["npm", "install", "-g", "context-mode"], timeout=120)
    elif have("bun"):
        subprocess.run(["bun", "install", "-g", "context-mode"], timeout=120)
    else:
        warn("context-mode needs npm or bun; skipping")
        return False
    if have("context-mode"):
        ok("context-mode installed")
        return True
    return False


def install_graphify(dry_run: bool = False, method: str = "uv") -> bool:
    log("graphify (persistent knowledge graph)")
    latest = get_latest_tag("Graphify-Labs/graphify")
    if have("graphify"):
        status = check_tool("graphify")
        if version_ge(status.version, latest):
            skip(f"graphify {status.version} >= {latest}")
        else:
            log(f"graphify {status.version} < {latest}, upgrading")
            _graphify_upgrade(dry_run, method)
    else:
        _graphify_install(dry_run, latest, method)
    _graphify_install_skills(dry_run)
    return have("graphify")


def _graphify_install(dry_run: bool, version: str, method: str) -> None:
    if dry_run:
        log(f"would: install graphify via {method} ({version})")
        return
    if method == "uv" and have("uv"):
        subprocess.run(["uv", "tool", "install", "graphifyy"], timeout=120)
    elif have("pip"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "graphifyy"],
            timeout=120,
        )
    else:
        warn("uv or pip not found, skipping graphify")


def _graphify_upgrade(dry_run: bool, method: str) -> None:
    if dry_run:
        log("would: upgrade graphify")
        return
    if method == "uv" and have("uv"):
        subprocess.run(["uv", "tool", "upgrade", "graphifyy"], timeout=120)
    elif have("pip"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "--upgrade", "graphifyy"],
            timeout=120,
        )


_GRAPHIFY_PLATFORMS = {
    "claude",
    "codex",
    "hermes",
    "opencode",
    "kilo",
    "aider",
    "copilot",
    "claw",
    "droid",
    "trae",
    "kiro",
    "kimi",
    "amp",
    "agents",
    "devin",
    "gemini",
    "cursor",
}


def _graphify_install_skills(dry_run: bool) -> None:
    if not have("graphify"):
        warn("graphify not installed, skipping skill refresh")
        return
    if dry_run:
        log("would: graphify install --platform <each host>")
        return
    hosts = detect_hosts()
    for host in hosts:
        if host in _GRAPHIFY_PLATFORMS:
            log(f"graphify install --platform {host}")
            subprocess.run(
                ["graphify", "install", "--platform", host],
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            skip(f"graphify: {host} not a supported platform")


def install_codegraph(dry_run: bool = False) -> bool:
    log("codegraph (code knowledge graph MCP)")
    latest = get_latest_tag("colbymchenry/codegraph")
    if have("codegraph"):
        status = check_tool("codegraph")
        if version_ge(status.version, latest):
            skip(f"codegraph {status.version} >= {latest}")
            return True
        log(f"codegraph {status.version} < {latest}, upgrading")
        if not dry_run:
            subprocess.run(["codegraph", "upgrade"], timeout=120)
        if have("codegraph"):
            ok(f"codegraph upgraded: {check_tool('codegraph').version}")
            return True
        return False
    if dry_run:
        log(f"would: install codegraph via install.sh ({latest})")
        return False
    if not have("curl"):
        warn("curl not found, skipping codegraph")
        return False
    subprocess.run(
        [
            "bash",
            "-c",
            "curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh",
        ],
        timeout=120,
    )
    if have("codegraph"):
        ok(f"codegraph installed: {check_tool('codegraph').version}")
        return True
    return False


# ── host wiring ───────────────────────────────────────────────────────────


def _load_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_settings(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def _has_hook(
    settings: dict[str, Any],
    event: str,
    needle: str,
) -> bool:
    for entry in settings.get("hooks", {}).get(event, []):
        for hook in entry.get("hooks", []):
            if needle in hook.get("command", ""):
                return True
    return False


def wire_rtk_hook(dry_run: bool = False) -> None:
    """Add ``rtk hook claude`` to PreToolUse[Bash] in Claude Code settings."""
    settings_path = HOME / ".claude" / "settings.json"
    if not settings_path.exists() or not have("rtk"):
        return
    settings = _load_settings(settings_path)
    if _has_hook(settings, "PreToolUse", "rtk hook claude"):
        skip("rtk hook claude already wired")
        return
    if dry_run:
        log(f"would: add rtk hook claude to PreToolUse in {settings_path}")
        return
    backup_file(settings_path)
    pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    for entry in pre:
        if entry.get("matcher") == "Bash":
            entry.setdefault("hooks", []).append({"type": "command", "command": "rtk hook claude"})
            break
    else:
        pre.append(
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}
        )
    _save_settings(settings_path, settings)
    ok("wired rtk hook claude")


def wire_si_observe_hook(dry_run: bool = False) -> None:
    """Add ``si observe`` to PostToolUse in Claude Code settings."""
    settings_path = HOME / ".claude" / "settings.json"
    if not settings_path.exists() or not have("si"):
        return
    settings = _load_settings(settings_path)
    if _has_hook(settings, "PostToolUse", "si observe"):
        skip("si observe already wired")
        return
    if dry_run:
        log(f"would: add si observe to PostToolUse in {settings_path}")
        return
    backup_file(settings_path)
    si_path = shutil.which("si") or "si"
    matcher = (
        "Bash|Shell|shell|shell_command|exec_command|functions.exec_command"
        "|Read|read_file|view_file"
    )
    post = settings.setdefault("hooks", {}).setdefault("PostToolUse", [])
    for entry in post:
        if entry.get("matcher") == matcher:
            entry.setdefault("hooks", []).append(
                {"type": "command", "command": f"{si_path} observe", "timeout": 3}
            )
            break
    else:
        post.append(
            {
                "matcher": matcher,
                "hooks": [{"type": "command", "command": f"{si_path} observe", "timeout": 3}],
            }
        )
    _save_settings(settings_path, settings)
    ok("wired si observe")


def wire_codegraph_mcp(dry_run: bool = False, hosts: list[str] | None = None) -> None:
    """Wire codegraph MCP server into detected agent configs."""
    if not have("codegraph"):
        return
    hosts = hosts or detect_hosts()
    target_map = {
        "claude": "claude",
        "codex": "codex",
        "hermes": "hermes",
        "opencode": "opencode",
    }
    targets = [target_map[h] for h in hosts if h in target_map]
    if not targets:
        return
    target_list = ",".join(targets)
    if dry_run:
        log(f"would: codegraph install --target {target_list} --yes")
        return
    log(f"codegraph install --target {target_list} --yes")
    subprocess.run(
        ["codegraph", "install", "--target", target_list, "--yes"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def wire_all(dry_run: bool = False, hosts: list[str] | None = None) -> None:
    """Wire all tools into detected hosts."""
    hosts = hosts or detect_hosts()
    log("wiring tools into detected hosts")
    log(f"hosts: {' '.join(hosts)}")
    for host in hosts:
        if host == "claude":
            wire_rtk_hook(dry_run)
            wire_si_observe_hook(dry_run)
    wire_codegraph_mcp(dry_run, hosts=hosts)


# ── install orchestration ─────────────────────────────────────────────────


def install_tool(name: str, dry_run: bool = False) -> bool:
    """Install a single tool by name. Returns True if installed after the call."""
    installers = {
        "si": install_si,
        "rtk": install_rtk,
        "tilth": install_tilth,
        "context-mode": install_context_mode,
        "graphify": install_graphify,
        "codegraph": install_codegraph,
    }
    installer = installers.get(name)
    if installer is None:
        warn(f"unknown tool: {name}")
        return False
    return installer(dry_run=dry_run)


def install_all(
    tools: list[str] | None = None,
    dry_run: bool = False,
    skip: list[str] | None = None,
    hosts: list[str] | None = None,
) -> list[ToolStatus]:
    """Install all (or a subset of) stack tools. Returns final status list."""
    to_install = tools or list(ALL_TOOLS)
    if skip:
        to_install = [t for t in to_install if t not in skip]
    resolved_hosts = hosts or detect_hosts()
    pf = PlatformInfo.detect()
    log(f"platform: {pf.os}/{pf.arch}")
    log(f"tools: {' '.join(to_install)}")
    log(f"hosts: {' '.join(resolved_hosts)}")
    if dry_run:
        log("DRY RUN - no changes will be made")
    for tool in to_install:
        install_tool(tool, dry_run=dry_run)
    wire_all(dry_run=dry_run, hosts=resolved_hosts)
    log("post-install check")
    statuses = check_all_tools()
    for s in statuses:
        if s.installed:
            ok(f"{s.name}: {s.version}")
        else:
            warn(f"{s.name}: NOT INSTALLED")
    ok("stack tools installer complete")
    return statuses


# ── uninstall ────────────────────────────────────────────────────────────


def uninstall_tools() -> None:
    """Best-effort removal of installed stack tools."""
    log("uninstalling stack tools (best-effort)")
    if have("si"):
        si_path = Path(HOME / ".local" / "bin" / "si")
        if si_path.exists():
            si_path.unlink()
            ok("removed si wrapper")
    if have("rtk"):
        if have("brew"):
            subprocess.run(["brew", "uninstall", "rtk"], timeout=60)
        elif have("cargo"):
            subprocess.run(["cargo", "uninstall", "rtk"], timeout=60)
    if have("tilth") and have("cargo"):
        subprocess.run(["cargo", "uninstall", "tilth"], timeout=60)
    if have("graphify") and have("uv"):
        subprocess.run(["uv", "tool", "uninstall", "graphifyy"], timeout=60)
    if have("codegraph"):
        subprocess.run(["codegraph", "uninstall"], timeout=60)
    warn("context-mode: remove manually from Claude Code plugins")


# ── CLI ──────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install optional agent-token-saver stack tools.",
    )
    parser.add_argument(
        "--tool",
        default="",
        help="comma-separated tool list (default: all)",
    )
    parser.add_argument(
        "--host",
        default="",
        help="comma-separated host list (default: auto-detect)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)

    if os.environ.get("ATS_STACK_DRY_RUN"):
        args.dry_run = True

    if args.check:
        statuses = check_all_tools()
        all_ok = True
        for s in statuses:
            if s.installed:
                ok(f"{s.name}: {s.version}")
            else:
                warn(f"{s.name}: NOT INSTALLED")
                all_ok = False
        return 0 if all_ok else 1

    if args.uninstall:
        uninstall_tools()
        return 0

    tools = [t.strip() for t in args.tool.split(",") if t.strip()] if args.tool else list(ALL_TOOLS)
    skip_env = os.environ.get("ATS_SKIP_TOOLS", "")
    skip_list = [s.strip() for s in skip_env.split(",") if s.strip()] if skip_env else []
    hosts = [h.strip() for h in args.host.split(",") if h.strip()] if args.host else None

    install_all(tools=tools, dry_run=args.dry_run, skip=skip_list, hosts=hosts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
