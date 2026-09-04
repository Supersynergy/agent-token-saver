"""Contract tests for the OmniRoute gateway lane.

The whole point of this lane is a trust question that is easy to get wrong:
OmniRoute listens on loopback but *forwards* to third-party providers, so
"local address" must not imply "data stays here". These tests pin that, plus
the failure taxonomy that keeps a missing gateway from looking like a network
blip -- or, worse, from masking a PII-shield failure.

See docs/adr/2026-09-03-omniroute-lane.md.
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

pytestmark = pytest.mark.skipif(shutil.which("bun") is None, reason="bun is required")

UNUSED_PORT = 20199  # nothing listens here; a refused connection is the point.


def write_prompt(home: Path, text: str) -> Path:
    """The adapter refuses group/world-readable prompt files, by design."""
    path = home / ".agent-token-saver" / "tmp" / "prompt.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o600)
    return path


def run_lane(
    home: Path,
    lane: str = "omniroute",
    *,
    prompt: str = "probe",
    env: dict[str, str] | None = None,
) -> dict:
    environment = os.environ.copy()
    environment.update({"HOME": str(home), "ATS_PII_SHIELD": "0"})
    environment.pop("LLMADAPTER_OMNIROUTE_URL", None)
    environment.pop("LLMADAPTER_OMNIROUTE_API_KEY", None)
    environment.pop("OMNIROUTE_API_KEY", None)
    if env:
        environment.update(env)
    proc = subprocess.run(
        [
            "bun",
            str(ADAPTER),
            "ask-v2",
            "--swarm",
            "--lanes",
            lane,
            "--prompt-file",
            str(write_prompt(home, prompt)),
            "--allow-remote",
            "--max-tokens",
            "50",
            "--no-cache",
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
        check=False,
    )
    return json.loads(proc.stdout)


def lane_table() -> list[str]:
    proc = subprocess.run(
        ["bun", str(ADAPTER), "lanes"], capture_output=True, text=True, check=False
    )
    return proc.stdout.splitlines()


def test_gateway_lane_is_remote_even_though_it_listens_on_loopback(tmp_path: Path) -> None:
    """The core safety property: a proxy on 127.0.0.1 is not a local lane.

    Without --allow-remote the call must be refused. If this ever passes, the
    lane has been modelled on the ollama branch and the PII shield is being
    skipped for prompts that leave the machine.
    """
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(tmp_path),
            "ATS_PII_SHIELD": "0",
            "LLMADAPTER_OMNIROUTE_URL": f"http://127.0.0.1:{UNUSED_PORT}/v1/chat/completions",
        }
    )
    proc = subprocess.run(
        [
            "bun",
            str(ADAPTER),
            "ask-v2",
            "--swarm",
            "--lanes",
            "omniroute",
            "--prompt-file",
            str(write_prompt(tmp_path, "probe")),
            "--max-tokens",
            "50",
            "--no-cache",
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 64
    assert json.loads(proc.stdout)["error"] == "remote_requires_allow_remote"


def test_unset_gateway_names_the_missing_configuration(tmp_path: Path) -> None:
    report = run_lane(tmp_path)

    result = report["results"][0]
    assert result["error"] == "omniroute_gateway_unset"
    assert result["call_started"] is False


def test_unreachable_gateway_is_named_not_a_generic_lane_error(tmp_path: Path) -> None:
    report = run_lane(
        tmp_path,
        env={"LLMADAPTER_OMNIROUTE_URL": f"http://127.0.0.1:{UNUSED_PORT}/v1/chat/completions"},
    )

    result = report["results"][0]
    assert result["error"] == "omniroute_gateway_unreachable"
    # A dial was genuinely attempted, so the accounting says so. Only the
    # pre-flight rejections below report call_started False.
    assert result["call_started"] is True


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/v1",
        "http://user:secret@127.0.0.1:20128/v1/chat/completions",
    ],
)
def test_unsafe_gateway_urls_are_rejected_before_any_call(tmp_path: Path, url: str) -> None:
    """A non-http scheme or a credential-bearing URL must never be dialled."""
    report = run_lane(tmp_path, env={"LLMADAPTER_OMNIROUTE_URL": url})

    result = report["results"][0]
    assert result["error"] == "omniroute_gateway_url_invalid"
    assert result["call_started"] is False


def test_shield_failure_is_not_reported_as_a_gateway_problem(tmp_path: Path) -> None:
    """The misdiagnosis this taxonomy exists to prevent.

    A missing PII shield throws before any call. Reporting that as
    "gateway unreachable" would send the reader to start a gateway when the
    real fix is to restore the shield -- and would quietly normalise a failure
    of the control that keeps personal data off third-party providers.
    """
    environment = {
        "ATS_PII_SHIELD": "1",
        "ATS_SHIELD_PATH": str(tmp_path / "absent-shield.js"),
        "LLMADAPTER_OMNIROUTE_URL": "http://127.0.0.1:20128/v1/chat/completions",
    }
    report = run_lane(tmp_path, env=environment)

    result = report["results"][0]
    assert result["call_started"] is False, "a failed shield must never reach the wire"
    assert result["error"] != "omniroute_gateway_unreachable"
    assert not result["ok"]


def test_gateway_lanes_are_opt_in_and_excluded_from_class_selectors(tmp_path: Path) -> None:
    """No selector may pull a third-party gateway into a swarm implicitly."""
    for selector in ("free", "all", "cheap"):
        report = run_lane(tmp_path, lane=selector)
        selected = [row["lane"] for row in report.get("results", [])]
        assert not any(name.startswith("omniroute") for name in selected), (
            f"selector {selector!r} pulled in a gateway lane: {selected}"
        )


def test_lane_table_marks_the_gateway_lanes_opt_in() -> None:
    rows = [line for line in lane_table() if "omniroute" in line]

    assert rows, "the gateway lanes should stay listed even when unconfigured"
    for row in rows:
        assert "[opt-in]" in row
