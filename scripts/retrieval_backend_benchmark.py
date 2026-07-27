#!/usr/bin/env python3
"""Measure the real local cost boundary between Tilth and Gmax.

This is deliberately a CLI benchmark, not a provider-token claim.  It records
wall/CPU/RSS/I/O figures emitted by macOS ``/usr/bin/time -lp``, visible output
and mutations below Gmax's documented state root.  Gmax is queried without
``--sync``: indexing is a separate, explicit cost.

Run from an already indexed project:

    uv run python scripts/retrieval_backend_benchmark.py --repeat 3

It does not start a filesystem watcher itself, delete a Gmax daemon, reindex,
or modify project source.  Gmax may still retain its own daemon and append its
own log/cache state; that is measured rather than hidden.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "benchmarks"
TIME = Path("/usr/bin/time")
GMAX_HOME = Path.home() / ".gmax"

METRIC_RE = re.compile(r"^\s*([\d.]+)\s+(.+?)\s*$")
SIMPLE_TIME_RE = re.compile(r"^(real|user|sys)\s+([\d.]+)$")
TIME_METRICS = {
    "real",
    "user",
    "sys",
    "maximum resident set size",
    "block input operations",
    "block output operations",
    "page reclaims",
    "page faults",
    "voluntary context switches",
    "involuntary context switches",
    "peak memory footprint",
}


@dataclass(frozen=True)
class Probe:
    name: str
    class_name: str
    command: tuple[str, ...]
    oracle: str


PROBES = (
    Probe(
        "symbol_neighborhood_tilth",
        "same-symbol",
        ("tilth", "--scope", str(ROOT), "--budget", "600", "--json", "build_report"),
        "return 0; JSON output mentions build_report",
    ),
    Probe(
        "symbol_neighborhood_gmax",
        "same-symbol",
        ("gmax", "peek", "build_report", "--agent"),
        "return 0; output mentions build_report",
    ),
    Probe(
        "natural_language_tilth",
        "semantic-recall",
        (
            "tilth",
            "--scope",
            str(ROOT),
            "--budget",
            "600",
            "--json",
            "provider usage parsing and A/B acceptance gate",
        ),
        "return 0; output names external_usage_gate.py (expected to fail: Tilth is literal/structural)",
    ),
    Probe(
        "natural_language_gmax",
        "semantic-recall",
        (
            "gmax",
            "search",
            "provider usage parsing and A/B acceptance gate",
            "--agent",
            "-m",
            "3",
            "--plain",
        ),
        "return 0; output names external_usage_gate.py",
    ),
)


def est_tokens(value: str) -> int:
    """Transparent visible-output proxy, never provider-reported usage."""
    return (len(value.encode("utf-8", errors="ignore")) + 3) // 4


def snapshot(path: Path) -> dict[str, tuple[int, int]]:
    """Small metadata fingerprint of a tool-owned state directory."""
    if not path.is_dir():
        return {}
    result: dict[str, tuple[int, int]] = {}
    for child in path.rglob("*"):
        try:
            stat = child.stat()
        except OSError:
            continue
        if child.is_file():
            result[str(child.relative_to(path))] = (stat.st_size, stat.st_mtime_ns)
    return result


def changed_paths(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[str]:
    return sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))


def parse_time(stderr: str) -> tuple[dict[str, float | int], str]:
    """Split tool stderr from macOS time -lp metrics."""
    metrics: dict[str, float | int] = {}
    other: list[str] = []
    for line in stderr.splitlines():
        simple = SIMPLE_TIME_RE.match(line)
        if simple:
            metrics[simple.group(1)] = float(simple.group(2))
            continue
        match = METRIC_RE.match(line)
        if not match or match.group(2) not in TIME_METRICS:
            other.append(line)
            continue
        raw, name = match.groups()
        metrics[name] = float(raw) if name in {"real", "user", "sys"} else int(float(raw))
    return metrics, "\n".join(other).strip()


def passed(probe: Probe, stdout: str, return_code: int) -> bool:
    if return_code != 0 or "build_report" not in stdout and "natural_language" not in probe.name:
        return False
    if probe.name == "natural_language_tilth":
        return "external_usage_gate.py" in stdout
    if probe.name == "natural_language_gmax":
        return "external_usage_gate.py" in stdout
    return True


def run_probe(probe: Probe, *, root: Path) -> dict[str, Any]:
    before = snapshot(GMAX_HOME)
    started = time.monotonic()
    result = subprocess.run(
        [str(TIME), "-lp", *probe.command],
        cwd=root,
        env={**os.environ, "NO_COLOR": "1", "TILTH_THREADS": "1"},
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    after = snapshot(GMAX_HOME)
    metrics, _tool_stderr = parse_time(result.stderr)
    return {
        "return_code": result.returncode,
        "accepted": passed(probe, result.stdout, result.returncode),
        "wall_ms": elapsed_ms,
        "output_bytes": len(result.stdout.encode("utf-8", errors="ignore")),
        "visible_output_tokens_estimate": est_tokens(result.stdout),
        "time_lp": metrics,
        "gmax_state_changed_paths": changed_paths(before, after),
    }


def median(values: list[int]) -> int | None:
    if not values:
        return None
    return sorted(values)[len(values) // 2]


def gmax_processes() -> list[dict[str, int | str]]:
    """Read aggregate Gmax process data without persisting host process IDs."""
    result = subprocess.run(
        ["ps", "-ax", "-o", "pid=,ppid=,rss=,comm="],
        text=True,
        capture_output=True,
        check=False,
    )
    rows: list[dict[str, int | str]] = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 3)
        if len(fields) != 4 or Path(fields[3]).name not in {"gmax-daemon", "gmax-worker"}:
            continue
        try:
            rows.append({"role": Path(fields[3]).name, "rss_kib": int(fields[2])})
        except ValueError:
            continue
    return rows


def public_command(command: tuple[str, ...]) -> list[str]:
    """Keep benchmark artifacts portable; the repo root is represented as '.'."""
    return ["." if part == str(ROOT) else part for part in command]


def render(payload: dict[str, Any]) -> str:
    lines = [
        f"# Tilth vs Gmax local retrieval — {payload['date']}",
        "",
        "Measured with real installed CLIs on the already-indexed repository. ",
        "Gmax receives no `--sync`; index/update cost is intentionally excluded and must be run explicitly.",
        "`/usr/bin/time -lp` block I/O is OS-reported; visible tokens are UTF-8 bytes/4 proxy, not provider billing.",
        "First = first request in this run; warm median = repetitions 2..n. It is a daemon-cold measurement only when no Gmax daemon was running beforehand.",
        f"Gmax background: {len(payload['gmax_processes_before'])} process(es) before, "
        f"{len(payload['gmax_processes_after'])} after; post-run RSS sum "
        f"{payload['gmax_process_rss_kib_after']:,} KiB.",
        "",
        "| Probe | Accepted | First wall | Warm median | Visible tokens~ | Peak RSS (median) | Block R/W (median) | Gmax-state mutations |",
        "|---|:--:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["probes"]:
        samples = row["samples"]
        first_wall = samples[0]["wall_ms"]
        warm_wall = median([sample["wall_ms"] for sample in samples[1:] or samples])
        tokens = median([sample["visible_output_tokens_estimate"] for sample in samples])
        peak = median([int(sample["time_lp"].get("peak memory footprint", 0)) for sample in samples])
        reads = median([int(sample["time_lp"].get("block input operations", 0)) for sample in samples])
        writes = median([int(sample["time_lp"].get("block output operations", 0)) for sample in samples])
        mutations = sum(bool(sample["gmax_state_changed_paths"]) for sample in samples)
        accepted = all(sample["accepted"] for sample in samples)
        lines.append(
            f"| {row['name']} | {'yes' if accepted else 'no'} | {first_wall} ms | {warm_wall} ms | {tokens} | "
            f"{peak:,} B | {reads}/{writes} | {mutations}/{len(samples)} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation rule",
            "",
            "- Gmax wins only for natural-language semantic recall or its prebuilt call graph; it is not a cheaper Tilth replacement.",
            "- Tilth wins for bounded symbol/file structure when a persistent daemon/index is not justified.",
            "- A non-empty Gmax-state mutation list is a real tool-side write signal even when macOS reports zero block output operations (writes may be buffered or page-cached).",
            "- Do not replace Lean Codex's safe, scope-gated Tilth MCP with Gmax MCP based on this CLI-only benchmark. Gmax stays explicit CLI/on-demand.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 5:
        parser.error("--repeat must be between 1 and 5")
    rows: list[dict[str, Any]] = []
    gmax_before = gmax_processes()
    for probe in PROBES:
        rows.append(
            {
                "name": probe.name,
                "class": probe.class_name,
                "command": public_command(probe.command),
                "oracle": probe.oracle,
                "samples": [run_probe(probe, root=ROOT) for _ in range(args.repeat)],
            }
        )
    payload = {
        "date": time.strftime("%Y-%m-%d"),
        "root": ".",
        "repeat": args.repeat,
        "gmax_state_root": "~/.gmax",
        "gmax_processes_before": gmax_before,
        "gmax_processes_after": gmax_processes(),
        "probes": rows,
    }
    payload["gmax_process_rss_kib_after"] = sum(
        int(process["rss_kib"]) for process in payload["gmax_processes_after"]
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"tilth-vs-gmax-{payload['date']}"
    (args.out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2) + "\n")
    (args.out_dir / f"{stem}.md").write_text(render(payload))
    print(args.out_dir / f"{stem}.md")
    return 0 if all(sample["return_code"] == 0 for row in rows for sample in row["samples"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
