"""Executable parity checks for the bounded TypeScript swarm path.

All lane commands are local fixtures. No provider, cache or real user HOME is
touched, so the test proves packet shape and fan-out limits rather than model
quality or billing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "llmadapter.ts"
PIPE = ROOT / "integration" / "cli" / "ats-pipe"

pytestmark = pytest.mark.skipif(
    shutil.which("bun") is None, reason="bun is required for llmadapter"
)


def run_adapter(
    home: Path, *args: str, extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "ATS_PII_SHIELD": "0"})  # fixture has no PII
    if extra:
        env.update(extra)
    return subprocess.run(
        ["bun", str(ADAPTER), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def install_probe_lanes(home: Path, probe_dir: Path, count: int = 4) -> list[str]:
    probe = probe_dir / "probe.sh"
    probe.write_text(
        '#!/bin/sh\nset -eu\nprintf \'%s\' "$2" > "$ATS_PROBE_DIR/$1.txt"\nprintf \'STATUS: PASS; EVIDENCE: %s; HANDOFF: none\\n\' "$1"\n'
    )
    probe.chmod(0o755)
    names = [f"worker-{number}" for number in range(1, count + 1)]
    lanes = [
        {
            "name": name,
            "kind": "cli",
            "class": "cli",
            "cmd": [str(probe), name, "__PROMPT__"],
        }
        for name in names
    ]
    config = home / ".agent-token-saver" / "local-lanes.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"llmadapter": lanes}))
    config.chmod(0o600)
    return names


def test_contract_matches_python_worker_shape_and_stays_bounded(tmp_path: Path) -> None:
    result = run_adapter(
        tmp_path,
        "contract",
        "Trace imports for this source function and fix its test. " + "ö" * 4_000,
    )

    assert result.returncode == 0, result.stderr
    packet = json.loads(result.stdout)
    assert packet["mode"] == "swarm"
    assert packet["max_workers"] == 3
    assert packet["max_result_tokens"] == 500
    assert packet["route"] == "local source"
    assert packet["capsule_visible_input_tokens_proxy"] <= 700
    assert packet["tools_available"] is False
    assert "Reasoning-only lane" in packet["packet"]
    assert "tilth" not in packet["packet"]
    assert "max 500 tokens" in packet["packet"]
    assert "STATUS: PASS|FAIL|BLOCKED" in packet["packet"]
    assert "HANDOFF: none" in packet["packet"]


def test_swarm_caps_lanes_and_sends_the_same_compact_packet(tmp_path: Path) -> None:
    probe_dir = tmp_path / "probe"
    probe_dir.mkdir(exist_ok=True)
    names = install_probe_lanes(tmp_path, probe_dir, count=14)
    result = run_adapter(
        tmp_path,
        "ask",
        "Trace imports for this source function and fix its test.",
        "--swarm",
        "--lanes",
        ",".join(names),
        "--no-cache",
        "--json",
        extra={"ATS_PROBE_DIR": str(probe_dir)},
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["total"] == 3
    assert {row["lane"] for row in report["results"]} == set(names[:3])
    assert "using 3/14 lanes" in result.stderr
    assert not (probe_dir / "worker-14.txt").exists()

    packets = [(probe_dir / f"{name}.txt").read_text() for name in names[:3]]
    assert len(set(packets)) == 1
    assert "Tool lane: local source" in packets[0]
    assert "STATUS: PASS|FAIL|BLOCKED" in packets[0]


def test_wide_fanout_requires_an_explicit_flag(tmp_path: Path) -> None:
    probe_dir = tmp_path / "probe"
    probe_dir.mkdir()
    names = install_probe_lanes(tmp_path, probe_dir)
    result = run_adapter(
        tmp_path,
        "ask",
        "Trace imports for this source function.",
        "--swarm",
        "--fanout",
        "--lanes",
        ",".join(names),
        "--no-cache",
        "--json",
        extra={"ATS_PROBE_DIR": str(probe_dir)},
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["total"] == 4
    assert "using 3/" not in result.stderr


def test_ats_pipe_uses_bounded_ts_swarm_by_default(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    captured = tmp_path / "llmadapter-args.txt"
    (bin_dir / "ats-recon").write_text("#!/bin/sh\nprintf 'small local context'\n")
    (bin_dir / "llmadapter").write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {captured}\nprintf 'fixture result\\n'\n"
    )
    for command in (bin_dir / "ats-recon", bin_dir / "llmadapter"):
        command.chmod(0o755)

    env = os.environ.copy()
    env.update({"PATH": f"{bin_dir}:{env['PATH']}", "ATS_PIPE_ENGINE": "llmadapter"})
    result = subprocess.run(
        [str(PIPE), "Trace source imports"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    args = captured.read_text().splitlines()
    assert args[:1] == ["ask"]
    assert "--swarm" in args
    assert "--fanout" not in args
