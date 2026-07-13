#!/usr/bin/env python3
"""Compare output filters on identical fixtures with signal-preservation oracles.

The benchmark executes each wrapper against fixture-backed fake commands in an
isolated HOME.  It never installs the candidate and never touches agent config.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Fixture:
    name: str
    filename: str
    command: str
    exit_code: int
    rtk_args: tuple[str, ...] | None
    required: tuple[str, ...]
    rtk_pipe_filter: str | None = None


@dataclass(frozen=True)
class Result:
    fixture: str
    stack: str
    tokens: int
    bytes: int
    saved_pct: float
    elapsed_ms: int
    exit_code: int
    expected_exit_code: int
    signal_found: int
    signal_total: int
    accepted: bool
    missing: tuple[str, ...]


FIXTURES = (
    Fixture(
        "pytest-failures",
        "pytest_output.txt",
        "pytest -vv",
        1,
        ("pytest", "-vv"),
        (
            "test_env_override",
            "assert 8080 == 9999",
            "test_missing_file",
            "FileNotFoundError",
            "2 failed",
            "50 passed",
        ),
    ),
    Fixture(
        "git-diff",
        "large_git_diff.txt",
        "git diff",
        0,
        ("git", "diff"),
        (
            "src/auth/login.py",
            "src/auth/session.py",
            "src/api/routes.py",
            "tests/test_auth.py",
            "config/settings.yaml",
            "RateLimiter",
            "LOCKOUT_DURATION",
        ),
        rtk_pipe_filter="git-diff",
    ),
    Fixture(
        "kubectl-pods",
        "kubectl_pods.txt",
        "kubectl get pods -A",
        0,
        ("kubectl", "get", "pods", "-A"),
        (
            "api-staging",
            "CrashLoopBackOff",
            "worker-staging",
            "ImagePullBackOff",
        ),
    ),
    Fixture(
        "npm-install",
        "npm_install.txt",
        "npm install",
        0,
        ("npm", "install"),
        (
            "inflight@1.0.6",
            "eslint@8.57.0",
            "847 packages",
            "3 moderate severity vulnerabilities",
            "npm audit fix",
        ),
    ),
    Fixture(
        "terraform-plan",
        "terraform_plan.txt",
        "terraform plan",
        0,
        None,
        (
            "aws_instance.web_server",
            "aws_security_group.web",
            "aws_wafv2_web_acl.main",
            "13 to add, 1 to change, 1 to destroy",
        ),
    ),
)


def estimated_tokens(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / 4)


def make_fake_command(bin_dir: Path, name: str, fixture: Path, exit_code: int) -> None:
    script = bin_dir / name
    script.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        f"sys.stdout.write(Path({str(fixture)!r}).read_text())\n"
        f"raise SystemExit({exit_code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)


def run(
    command: list[str], env: dict[str, str], input_text: str | None = None
) -> tuple[int, str, int]:
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        input=input_text,
        timeout=30,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    output = proc.stdout
    if proc.stderr:
        output += ("\n" if output else "") + proc.stderr
    return proc.returncode, output, elapsed_ms


def evaluate(
    fixture: Fixture,
    stack: str,
    output: str,
    return_code: int,
    elapsed_ms: int,
    raw_tokens: int,
) -> Result:
    missing = tuple(item for item in fixture.required if item not in output)
    tokens = estimated_tokens(output)
    return Result(
        fixture=fixture.name,
        stack=stack,
        tokens=tokens,
        bytes=len(output.encode("utf-8")),
        saved_pct=round((1 - tokens / raw_tokens) * 100, 2),
        elapsed_ms=elapsed_ms,
        exit_code=return_code,
        expected_exit_code=fixture.exit_code,
        signal_found=len(fixture.required) - len(missing),
        signal_total=len(fixture.required),
        accepted=not missing and return_code == fixture.exit_code,
        missing=missing,
    )


def markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Output-filter benchmark",
        "",
        "Identical fixtures, isolated HOME, UTF-8 bytes / 4 token proxy.",
        "Acceptance requires every named signal and the original exit code.",
        "",
        "| Fixture | Stack | Tokens | Saved | ms | Signal | Exit | Accepted |",
        "|---|---|---:|---:|---:|---:|---:|:--:|",
    ]
    for row in payload["results"]:  # type: ignore[index]
        display_row = {**row, "accepted_label": "yes" if row["accepted"] else "no"}
        lines.append(
            "| {fixture} | {stack} | {tokens:,} | {saved_pct:.2f}% | {elapsed_ms} | "
            "{signal_found}/{signal_total} | {exit_code}/{expected_exit_code} | "
            "{accepted_label} |".format(**display_row)
        )
    lines.extend(
        [
            "",
            "## Decision rule",
            "",
            "A smaller rejected output does not win. Adopt into a default only when it "
            "beats the current accepted stack on representative workloads without adding "
            "a second always-on hook.",
            "",
        ]
    )
    rejected = [row for row in payload["results"] if not row["accepted"]]  # type: ignore[index]
    if rejected:
        lines.extend(["## Rejected outputs", ""])
        for row in rejected:
            lines.append(
                f"- **{row['fixture']} / {row['stack']}**: missing "
                f"{', '.join(row['missing']) or 'none'}; exit "
                f"{row['exit_code']} expected {row['expected_exit_code']}."
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-saver-repo", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()

    candidate = args.token_saver_repo.resolve()
    fixture_dir = candidate / "examples" / "fixtures"
    wrapper = candidate / "scripts" / "wrap.py"
    rtk = shutil.which("rtk")
    if not wrapper.is_file() or not fixture_dir.is_dir():
        parser.error("candidate clone lacks scripts/wrap.py or examples/fixtures")
    if not rtk:
        parser.error("rtk is not installed")

    results: list[Result] = []
    with tempfile.TemporaryDirectory(prefix="agent-token-saver-bench-") as temp:
        temp_root = Path(temp)
        bin_dir = temp_root / "bin"
        home_dir = temp_root / "home"
        bin_dir.mkdir()
        home_dir.mkdir()
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["NO_COLOR"] = "1"

        for fixture in FIXTURES:
            source = fixture_dir / fixture.filename
            raw = source.read_text()
            raw_tokens = estimated_tokens(raw)
            executable = fixture.command.split()[0]
            make_fake_command(bin_dir, executable, source, fixture.exit_code)

            results.append(
                evaluate(fixture, "raw", raw, fixture.exit_code, 0, raw_tokens)
            )

            rc, output, elapsed = run(
                [sys.executable, str(wrapper), fixture.command], env
            )
            results.append(
                evaluate(fixture, "ppgranger/token-saver", output, rc, elapsed, raw_tokens)
            )
            if args.artifact_dir:
                args.artifact_dir.mkdir(parents=True, exist_ok=True)
                (args.artifact_dir / f"{fixture.name}-ppgranger.txt").write_text(output)

            if fixture.rtk_args is None:
                results.append(
                    evaluate(fixture, "RTK unsupported/raw", raw, fixture.exit_code, 0, raw_tokens)
                )
            else:
                rtk_command = [rtk, *fixture.rtk_args]
                rtk_input = None
                if fixture.rtk_pipe_filter:
                    rtk_command = [rtk, "pipe", "--filter", fixture.rtk_pipe_filter]
                    rtk_input = raw
                rc, output, elapsed = run(rtk_command, env, input_text=rtk_input)
                results.append(evaluate(fixture, "RTK", output, rc, elapsed, raw_tokens))
                if args.artifact_dir:
                    (args.artifact_dir / f"{fixture.name}-rtk.txt").write_text(output)

    payload: dict[str, object] = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "method": "fixture-backed wrapper execution; bytes/4 token proxy",
        "candidate": str(candidate),
        "candidate_commit": subprocess.check_output(
            ["git", "-C", str(candidate), "rev-parse", "HEAD"], text=True
        ).strip(),
        "rtk_version": subprocess.check_output([rtk, "--version"], text=True).strip(),
        "results": [asdict(result) for result in results],
    }

    prefix = args.out_prefix
    if prefix:
        prefix.parent.mkdir(parents=True, exist_ok=True)
        prefix.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
        prefix.with_suffix(".md").write_text(markdown(payload))
        print(prefix.with_suffix(".md"))
    else:
        print(markdown(payload))

    candidate_results = [r for r in results if r.stack == "ppgranger/token-saver"]
    return 0 if all(r.accepted for r in candidate_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
