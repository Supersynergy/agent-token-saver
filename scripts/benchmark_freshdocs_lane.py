#!/usr/bin/env python3
"""Benchmark the documentation lane: freshdocs vs raw source vs model memory.

Phase 4 of the playbook says "read the installed thing, never your memory of
it".  This measures whether that advice pays, and where it does not.

Three lanes answer the same question:

  memory      0 bytes, unverifiable, silently version-blind
  raw-source  fetch the upstream doc for the pinned ref
  freshdocs   local version-pinned context pack

Size alone would be a dishonest scoreboard -- memory would win every row at
zero bytes while being wrong.  So the deciding metric is **version fidelity**:
does the lane hand the agent documentation for the version actually installed?
A cheap answer about the wrong version is not a saving, it is a defect with a
low token count.

Network is optional.  Without --allow-network the raw-source lane reads from
cached fixtures and reports which rows were measured live.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RE = re.compile(r"^source:\s*(\S+)", re.MULTILINE)
# freshdocs fails closed: when nothing is indexed it refuses and names the
# command to fix it, instead of answering from something adjacent.  A refusal
# is tiny, so it must never be scored as a cheap win -- it answered nothing.
REFUSAL_RE = re.compile(r"No exact local docs matched", re.IGNORECASE)
LIB_LINE_RE = re.compile(r"^libraries:\s*(.+)$", re.MULTILINE)
CTX_VERSION_RE = re.compile(r"^\[\d+\]\s+(\S+)\s+(\S+)\s", re.MULTILINE)


@dataclass(frozen=True)
class Probe:
    """One documentation question, plus how to learn the truth locally."""

    library: str
    query: str
    # Command that reports the version actually installed here, or None when
    # no local ground truth exists (then version fidelity is "unknown").
    version_cmd: tuple[str, ...] | None
    version_pattern: str


PROBES = (
    Probe("ruff", "how do I configure lint rules", ("uv", "run", "ruff", "--version"), r"(\d+\.\d+\.\d+)"),
    Probe("uv", "how do I add a dev dependency", ("uv", "--version"), r"(\d+\.\d+\.\d+)"),
    Probe("typescript", "how do I enable strict mode", ("tsc", "--version"), r"(\d+\.\d+\.\d+)"),
    Probe("bun", "how do I run a test file", ("bun", "--version"), r"(\d+\.\d+\.\d+)"),
    Probe("vitest", "how do I configure a test environment", None, r""),
    Probe("zod", "how do I parse an optional field", None, r""),
)


def tokens(text: str) -> int:
    """UTF-8 bytes / 4.  A proxy, stated as such, used identically everywhere."""
    return math.ceil(len(text.encode("utf-8")) / 4)


def installed_version(probe: Probe) -> str | None:
    if not probe.version_cmd or not shutil.which(probe.version_cmd[0]):
        return None
    try:
        proc = subprocess.run(
            list(probe.version_cmd), capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(probe.version_pattern, proc.stdout or proc.stderr)
    return match.group(1) if match else None


def freshdocs_context(
    query: str, limit: int, project: Path | None = None, lib: str | None = None
) -> tuple[str, int]:
    """Run one context pack.

    freshdocs has two retrieval modes and they fail differently, so the
    benchmark exercises both rather than picking the flattering one:

      --project  scopes to libraries declared in the project manifest.  Version
                 fidelity is excellent, but a query about a library the project
                 does not declare is answered from whatever *is* declared --
                 silently, and off-topic.
      --lib      targets a named library from the registry cache.  Always on
                 topic, but the version is the registry's, which may not be the
                 version installed on this machine.
    """
    command = ["freshdocs", "context", query, "--limit", str(limit)]
    if project is not None:
        command += ["--project", str(project)]
    if lib is not None:
        command += ["--lib", lib]
    started = time.perf_counter()
    proc = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    elapsed = round((time.perf_counter() - started) * 1000)
    return proc.stdout, elapsed


def served_library(context: str) -> str | None:
    """Which library the pack actually answered from."""
    for name, _version in CTX_VERSION_RE.findall(context):
        return name
    match = LIB_LINE_RE.search(context)
    if match:
        parts = match.group(1).split()
        return parts[0] if parts else None
    return None


def fetch(url: str, cache_dir: Path, allow_network: bool) -> tuple[str | None, bool]:
    """Return (text, was_live).  Cached fixtures keep reruns offline and cheap."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:]
    cached = cache_dir / f"{slug}.txt"
    if cached.is_file():
        return cached.read_text(encoding="utf-8", errors="replace"), False
    if not allow_network or not shutil.which("curl"):
        return None, False
    proc = subprocess.run(
        ["curl", "-sL", "--max-time", "30", url], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, False
    cached.write_text(proc.stdout)
    return proc.stdout, True


def context_version(context: str, library: str) -> str | None:
    for name, version in CTX_VERSION_RE.findall(context):
        if name == library:
            return version.lstrip("v")
    match = LIB_LINE_RE.search(context)
    if match:
        for entry in match.group(1).split(","):
            parts = entry.strip().split()
            if len(parts) == 2 and parts[0] == library:
                return parts[1].lstrip("v")
    return None


def verdict(served: str | None, installed: str | None) -> str:
    if installed is None:
        return "unknown"
    if served is None:
        return "no-version"
    return "match" if served == installed else f"drift({served} vs {installed})"


def markdown(payload: dict) -> str:
    rows = payload["results"]
    lines = [
        "# Documentation-lane benchmark — freshdocs vs raw source vs memory",
        "",
        f"- date: {payload['date']}",
        f"- freshdocs: {payload['freshdocs_version']}",
        "- token proxy: UTF-8 bytes / 4, applied identically to every lane",
        f"- raw-source rows fetched live this run: {payload['live_fetches']}",
        "",
        "## Cost",
        "",
        "| Library | Mode | freshdocs tok | raw-source tok | Saved | ms |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["refused"]:
            lines.append(
                f"| {row['library']} | `--{row['mode']}` | "
                f"{row['context_tokens']:,} (refusal, not an answer) | n/a | n/a | "
                f"{row['elapsed_ms']} |"
            )
            continue
        raw = f"{row['raw_tokens']:,}" if row["raw_tokens"] else "n/a"
        saved = f"{row['saved_pct']:.1f}%" if row["raw_tokens"] else "n/a"
        lines.append(
            f"| {row['library']} | `--{row['mode']}` | {row['context_tokens']:,} | "
            f"{raw} | {saved} | {row['elapsed_ms']} |"
        )
    lines += [
        "",
        "## Correctness — the metric that decides the lane",
        "",
        "Two independent ways a documentation lane can be wrong while looking cheap:",
        "answering from the wrong library, or from the wrong version.",
        "",
        "| Library | Mode | Answered from | On topic | Installed | Served | Version verdict |",
        "|---|---|---|:--:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['library']} | `--{row['mode']}` | "
            f"{'refused (fail-closed)' if row['refused'] else (row['answered_from'] or 'n/a')} | "
            f"{'yes' if row['on_topic'] else ('n/a' if row['refused'] else 'NO')} | "
            f"{row['installed_version'] or 'n/a'} | "
            f"{row['served_version'] or 'n/a'} | {row['fidelity']} |"
        )
    off_topic = [r for r in rows if not r["on_topic"] and not r["refused"]]
    drifted = [r for r in rows if r["fidelity"].startswith("drift")]
    lines += [
        "",
        f"Off-topic answers: **{len(off_topic)} / {len(rows)}**. "
        f"Version drift: **{len(drifted)} / {len(rows)}**. "
        f"Honest refusals: **{len([r for r in rows if r['refused']])} / {len(rows)}**.",
        "",
        "A refusal is a *good* outcome and is excluded from the saving columns on",
        "purpose. It is the smallest output in the run, and scoring it as the",
        "cheapest answer would rank 'said nothing' above 'was correct'.",
        "",
        "Memory is absent from the cost table on purpose: it costs zero tokens and",
        "carries zero fidelity, so ranking it by size would reward being wrong.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp/freshdocs-bench-cache"))
    parser.add_argument("--out-prefix", type=Path)
    args = parser.parse_args()

    if not shutil.which("freshdocs"):
        parser.error("freshdocs is not installed")

    version = subprocess.run(
        ["freshdocs", "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()

    results = []
    live = 0
    for probe in PROBES:
        installed = installed_version(probe)
        for mode in ("project", "lib"):
            context, elapsed = freshdocs_context(
                probe.query,
                args.limit,
                project=args.project if mode == "project" else None,
                lib=probe.library if mode == "lib" else None,
            )
            sources = SOURCE_RE.findall(context)
            raw_text = ""
            for url in dict.fromkeys(sources[: args.limit]):
                body, was_live = fetch(url, args.cache_dir, args.allow_network)
                live += int(was_live)
                if body:
                    raw_text += body
            refused = bool(REFUSAL_RE.search(context))
            answered = None if refused else served_library(context)
            served = context_version(context, probe.library)
            context_tokens = tokens(context)
            raw_tokens = tokens(raw_text) if raw_text else 0
            results.append(
                {
                    "library": probe.library,
                    "mode": mode,
                    "query": probe.query,
                    "answered_from": answered,
                    "refused": refused,
                    "on_topic": (not refused) and answered == probe.library,
                    "context_tokens": context_tokens,
                    "raw_tokens": raw_tokens,
                    "saved_pct": (
                        round((1 - context_tokens / raw_tokens) * 100, 2) if raw_tokens else 0.0
                    ),
                    "elapsed_ms": elapsed,
                    "sources": len(sources),
                    "installed_version": installed,
                    "served_version": served,
                    "fidelity": verdict(served, installed),
                }
            )

    payload = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "freshdocs_version": version,
        "method": "freshdocs context vs concatenated upstream sources; bytes/4 proxy",
        "live_fetches": live,
        "results": results,
    }

    if args.out_prefix:
        args.out_prefix.parent.mkdir(parents=True, exist_ok=True)
        args.out_prefix.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
        args.out_prefix.with_suffix(".md").write_text(markdown(payload))
        print(args.out_prefix.with_suffix(".md"))
    else:
        print(markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
