#!/usr/bin/env python3
"""Local token-saver stack benchmark.

No provider API calls. No Python requests. Uses installed CLIs and simple token proxy
(bytes / 4) so the benchmark is reproducible without model credentials.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
OUT_DIR = ROOT / "data" / "benchmarks"
OUT_JSON = OUT_DIR / "token-saver-local-2026-07-09.json"
OUT_MD = OUT_DIR / "token-saver-local-2026-07-09.md"


def est_tokens(text: str | bytes) -> int:
    if isinstance(text, str):
        text = text.encode("utf-8", errors="ignore")
    return max(1, len(text) // 4)


@dataclass
class Case:
    name: str
    baseline_tokens: int
    optimized_tokens: int
    baseline_ms: int
    optimized_ms: int
    ok: bool
    detail: str

    @property
    def saved_pct(self) -> float:
        if self.baseline_tokens <= 0:
            return 0.0
        return round((1 - self.optimized_tokens / self.baseline_tokens) * 100, 1)

    @property
    def factor(self) -> float:
        if self.optimized_tokens <= 0:
            return float("inf")
        return round(self.baseline_tokens / self.optimized_tokens, 2)


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str, int]:
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        return p.returncode, p.stdout, p.stderr, ms
    except subprocess.TimeoutExpired as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        return 124, exc.stdout or "", exc.stderr or "timeout", ms
    except FileNotFoundError as exc:
        return 127, "", str(exc), 0


def case_rtk_ps() -> Case:
    rc1, out1, err1, ms1 = run(["ps", "aux"], cwd=HOME, timeout=20)
    rc2, out2, err2, ms2 = run(["rtk", "ps", "aux"], cwd=HOME, timeout=30)
    return Case(
        "RTK shell-output filter: ps aux",
        est_tokens(out1 + err1),
        est_tokens(out2 + err2),
        ms1,
        ms2,
        rc1 == 0 and rc2 == 0,
        "Compares raw process table against rtk-filtered output.",
    )


def case_tilth_read() -> Case:
    target = ROOT / "README.md"
    raw = target.read_text(errors="ignore")
    rc, out, err, ms = run(["tilth", str(target), "--budget", "800", "--scope", str(ROOT)], timeout=30)
    return Case(
        "Tilth smart file read: README outline",
        est_tokens(raw),
        est_tokens(out + err),
        0,
        ms,
        rc == 0 and bool(out.strip()),
        "Compares full README.md with Tilth budgeted structural view.",
    )


def case_context_mode_search() -> Case:
    target = ROOT / "README.md"
    raw = target.read_text(errors="ignore")
    run(["context-mode", "index", str(target), "--project", str(ROOT), "--source", "token-saver-bench"], timeout=40)
    rc, out, err, ms = run(
        ["context-mode", "search", "token savings", "--project", str(ROOT), "--limit", "3"],
        timeout=30,
    )
    return Case(
        "context-mode FTS retrieval: search not full-file",
        est_tokens(raw),
        est_tokens(out + err),
        0,
        ms,
        rc == 0 and bool((out + err).strip()),
        "Indexes README once, then retrieves only the three relevant chunks.",
    )


def case_superweb_fetch() -> Case:
    url = "https://example.com"
    rc1, out1, err1, ms1 = run(["curl", "-fsSL", url], cwd=HOME, timeout=30)
    if shutil.which("hyperfetch"):
        cmd = ["hyperfetch", url, "--markdown"]
        label = "hyperfetch markdown"
    else:
        cmd = ["superweb", "fetch", url, "--mode", "html"]
        label = "superweb fetch"
    rc2, out2, err2, ms2 = run(cmd, cwd=HOME, timeout=60)
    return Case(
        f"Web prefilter: curl HTML vs {label}",
        est_tokens(out1 + err1),
        est_tokens(out2 + err2),
        ms1,
        ms2,
        rc1 == 0 and rc2 == 0,
        "Compares raw HTML fetch with markdown/extracted fetch path.",
    )


def case_mcp_schema_slimming() -> Case:
    verbose = {
        "tools": [
            {
                "name": "create_jira_issue_with_full_enterprise_metadata_and_audit_context",
                "description": "Create a Jira issue. Includes long guidance, examples, caveats, project policy, audit logging, security constraints, and workflow explanation that should not be repeated in every model turn.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string", "description": "Jira project key, for example OPS or ENG."},
                        "summary": {"type": "string", "description": "Concise issue title."},
                        "description": {"type": "string", "description": "Full markdown issue body."},
                        "priority": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"], "description": "Business priority."},
                    },
                    "required": ["project_key", "summary", "description"],
                },
            }
            for _ in range(20)
        ]
    }
    slim = {
        "tools": [
            {"name": "jira_create", "parameters": {"project_key": "str", "summary": "str", "description": "str", "priority": "enum"}}
            for _ in range(20)
        ],
        "detail_ref": "mcp://schema/jira/full#retrieve-on-demand",
    }
    baseline = json.dumps(verbose, ensure_ascii=False, indent=2)
    optimized = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    return Case(
        "MCP schema slimming: verbose tools vs on-demand refs",
        est_tokens(baseline),
        est_tokens(optimized),
        0,
        0,
        True,
        "Static deterministic proxy for StackOne/Atlassian-style tool schema compaction.",
    )


def case_headroom_profile() -> Case:
    rc, out, err, ms = run(["headroom", "agent-savings", "--format", "json"], cwd=HOME, timeout=40)
    observed = out + err
    observed_tokens = est_tokens(observed)
    return Case(
        "Headroom availability: agent-90 profile render",
        observed_tokens,
        observed_tokens,
        0,
        ms,
        rc == 0 and bool(out.strip()),
        "Local config check only; real token savings require proxy-routed Claude/Codex traffic.",
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        case_rtk_ps(),
        case_tilth_read(),
        case_context_mode_search(),
        case_superweb_fetch(),
        case_mcp_schema_slimming(),
        case_headroom_profile(),
    ]
    payload = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "repo": str(ROOT),
        "cases": [{**asdict(c), "saved_pct": c.saved_pct, "factor": c.factor} for c in cases],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    lines = [
        "# Local Token-Saver Benchmark — 2026-07-09",
        "",
        "No provider API calls. Token estimate = UTF-8 bytes / 4.",
        "",
        "| Case | Base tok | Opt tok | Saved | Factor | Base ms | Opt ms | OK |",
        "|---|---:|---:|---:|---:|---:|---:|:--:|",
    ]
    for c in cases:
        lines.append(
            f"| {c.name} | {c.baseline_tokens} | {c.optimized_tokens} | {c.saved_pct}% | {c.factor}x | {c.baseline_ms} | {c.optimized_ms} | {'✅' if c.ok else '⚠️'} |"
        )
    lines += ["", "## Notes", ""]
    for c in cases:
        lines.append(f"- **{c.name}**: {c.detail}")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(OUT_MD)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if all(c.ok for c in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
