"""Contract tests for llmadapter's opt-in swarm extensions.

Every extension here must be invisible unless its flag is passed: AgentMaster
parses the v2 envelope and the capability contract with `deny_unknown_fields`
and a closed terminal enum, so a new key or terminal on the default path would
break the controller it was built for.
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
BUN = shutil.which("bun")

pytestmark = pytest.mark.skipif(BUN is None, reason="bun is required")

AGENTMASTER_TERMINALS = {"succeeded", "failed", "timeout", "output_limit", "cached"}
CONTRACT_KEYS = {
    "schema_version",
    "ask_v2",
    "mode",
    "default_max_workers",
    "max_workers",
    "fanout_max_workers",
    "max_result_tokens",
    "max_result_tokens_semantics",
    "max_prompt_bytes",
    "tools_available",
    "capsule_visible_input_tokens_proxy",
    "route",
    "packet",
}


def run_adapter(
    home: Path,
    *args: str,
    prompt: str | None = None,
    extra: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "ATS_PII_SHIELD": "0"})
    if extra:
        env.update(extra)
    return subprocess.run(
        [BUN, str(ADAPTER), *args],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=timeout,
    )


def install_lanes(
    home: Path,
    script: Path,
    lanes: list[tuple[str, str, str]],
    opt_in: set[str] | None = None,
) -> None:
    opt_in = opt_in or set()
    rows = [
        {
            "name": name,
            "kind": "cli",
            "class": lane_class,
            "cmd": [str(script), mode, name, "__PROMPT__"],
            "stdin_cmd": [str(script), mode, name],
            "local_safe": lane_class == "local",
            "opt_in": name in opt_in,
        }
        for name, lane_class, mode in lanes
    ]
    config = home / ".agent-token-saver" / "local-lanes.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"llmadapter": rows}))
    config.chmod(0o600)


@pytest.fixture
def probe(tmp_path: Path) -> Path:
    path = tmp_path / "probe.sh"
    path.write_text(
        """#!/bin/sh
set -eu
mode="$1"
lane="$2"
case "$mode" in
  ok)
    if [ -n "${ATS_PROMPT_DIR:-}" ]; then
      cat > "$ATS_PROMPT_DIR/$lane.prompt"
    else
      cat >/dev/null
    fi
    printf 'fixture answer for %s\n' "$lane"
    ;;
  slow)
    cat >/dev/null
    sleep 4
    printf 'late answer for %s\n' "$lane"
    ;;
  overflow)
    cat >/dev/null
    exec python3 -c 'import sys; sys.stdout.write("y" * 200000)'
    ;;
esac
"""
    )
    path.chmod(0o755)
    return path


@pytest.fixture
def evidence_provider(tmp_path: Path) -> Path:
    """Host evidence provider stand-in. Mode comes from LLMADAPTER_FIXTURE_MODE."""
    path = tmp_path / "evidence-provider.sh"
    path.write_text(
        """#!/bin/sh
set -eu
cat >/dev/null
case "${LLMADAPTER_FIXTURE_MODE:-ok}" in
  ok)        printf 'FRESH FACT: the release is 4.21 as of today.\n' ;;
  challenge) printf '{"ok": true, "page_status": "challenge"}\n' ;;
  empty)     printf '\n' ;;
  fail)      exit 3 ;;
esac
"""
    )
    path.chmod(0o755)
    return path


def test_default_envelope_carries_no_extension_keys(tmp_path: Path, probe: Path) -> None:
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        prompt="objective without extensions",
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert "first_pass" not in output
    assert "evidence" not in output
    assert "skill_route" not in output
    assert {row["terminal"] for row in output["results"]} <= AGENTMASTER_TERMINALS


def test_contract_default_shape_is_frozen_and_extensions_are_opt_in(tmp_path: Path) -> None:
    default = json.loads(run_adapter(tmp_path, "contract", "check exact source").stdout)
    assert set(default) == CONTRACT_KEYS

    extended = json.loads(
        run_adapter(tmp_path, "contract", "check exact source", "--extended").stdout
    )
    assert set(extended) == CONTRACT_KEYS | {"extensions"}
    assert extended["extensions"]["first_pass"] is True
    assert extended["extensions"]["opt_in_lanes"] == []
    assert extended["extensions"]["terminal_values_extended"] == ["pruned"]


def test_opt_in_lane_stays_out_of_class_and_all_selectors(
    tmp_path: Path,
    probe: Path,
) -> None:
    """`--budget-tokens 1` fails every lane before it spawns, so this observes
    lane SELECTION without touching a provider or a CLI."""
    install_lanes(
        tmp_path,
        probe,
        [("alpha", "local", "ok"), ("heavy", "local", "ok")],
        opt_in={"heavy"},
    )
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--fanout",
        "--cap",
        "64",
        "--lanes",
        "all",
        "--budget-tokens",
        "1",
        "--allow-remote",
        "--allow-paid",
        prompt="objective that never reaches a lane",
    )
    output = json.loads(result.stdout)
    selected = [row["lane"] for row in output["results"]]
    assert "alpha" in selected
    assert "heavy" not in selected
    assert all(row["error"] == "budget_input_exceeds" for row in output["results"])
    assert all(row["call_started"] is False for row in output["results"])


def test_opt_in_lane_is_reachable_by_name(tmp_path: Path, probe: Path) -> None:
    install_lanes(tmp_path, probe, [("heavy", "local", "ok")], opt_in={"heavy"})
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "heavy",
        prompt="explicitly named lane",
    )
    output = json.loads(result.stdout)
    assert [row["lane"] for row in output["results"]] == ["heavy"]
    assert output["results"][0]["ok"] is True
    assert output["results"][0]["kind"] == "cli"
    assert output["results"][0]["cap_mode"] == "advisory_only"


def test_first_pass_prunes_peers_once_one_lane_answers(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(
        tmp_path,
        probe,
        [("fast", "local", "ok"), ("slow1", "local", "slow"), ("slow2", "local", "slow")],
    )
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "fast,slow1,slow2",
        "--first-pass",
        prompt="first answer wins",
    )
    output = json.loads(result.stdout)
    # Pruned peers are lanes without an answer, so the lane-level status is
    # honestly "partial"; the oracle/winner verdict is reported separately.
    assert output["status"] == "partial"
    assert result.returncode == 0
    assert output["first_pass"]["winner"] == "fast"
    assert output["first_pass"]["oracle"] is False
    assert output["first_pass"]["pruned"] >= 1
    assert any(row["terminal"] == "pruned" for row in output["results"])


def test_first_pass_oracle_decides_the_winner(tmp_path: Path, probe: Path) -> None:
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    passing = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        "--first-pass",
        "--oracle",
        'grep -q "fixture answer" "$LLMADAPTER_ANSWER_PATH"',
        prompt="oracle decides",
    )
    accepted = json.loads(passing.stdout)
    assert passing.returncode == 0
    assert accepted["first_pass"]["winner"] == "alpha"
    assert accepted["first_pass"]["oracle_runs"] == 1
    assert accepted["first_pass"]["winner_oracle_exit"] == 0
    answer_dir = Path(accepted["first_pass"]["run_dir"])
    written = list(answer_dir.iterdir())
    assert written, "the oracle answer artifact must exist"
    assert oct(written[0].stat().st_mode & 0o777) == "0o600"

    rejecting = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        "--first-pass",
        "--no-cache",
        "--oracle",
        'grep -q "impossible marker" "$LLMADAPTER_ANSWER_PATH"',
        prompt="oracle decides",
    )
    refused = json.loads(rejecting.stdout)
    # The oracle verdict lives in first_pass.winner, not in the exit code: the
    # v2 contract fixes exit 0 to mean status ok|partial, and the lane did
    # answer. Folding a rejected oracle into the exit code would emit
    # partial+1, which a strict controller refuses.
    assert rejecting.returncode == 0
    assert refused["status"] in {"ok", "partial"}
    assert refused["first_pass"]["winner"] is None
    assert refused["first_pass"]["oracle_runs"] == 1


def test_oracle_env_prefix_lets_a_controller_reuse_its_own_oracle(
    tmp_path: Path,
    probe: Path,
) -> None:
    """Without the alias a controller's oracle reads an empty path, never
    passes, and --first-pass degrades into a full-price run with no pruning."""
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    oracle = 'test -s "$CTRL_ANSWER_PATH"'

    without_alias = json.loads(
        run_adapter(
            tmp_path,
            "ask-v2",
            "--stdin",
            "--swarm",
            "--lanes",
            "alpha",
            "--first-pass",
            "--oracle",
            oracle,
            prompt="controller oracle",
        ).stdout
    )
    assert without_alias["first_pass"]["winner"] is None

    with_alias = json.loads(
        run_adapter(
            tmp_path,
            "ask-v2",
            "--stdin",
            "--swarm",
            "--lanes",
            "alpha",
            "--no-cache",
            "--first-pass",
            "--oracle",
            oracle,
            "--oracle-env-prefix",
            "CTRL",
            prompt="controller oracle",
        ).stdout
    )
    assert with_alias["first_pass"]["winner"] == "alpha"
    assert with_alias["first_pass"]["winner_oracle_exit"] == 0


def test_oracle_env_prefix_is_bounded_and_needs_an_oracle(tmp_path: Path) -> None:
    lonely = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--oracle-env-prefix",
        "CTRL",
        prompt="objective",
    )
    assert lonely.returncode == 64
    assert json.loads(lonely.stdout)["error"] == "oracle_env_prefix_requires_oracle"

    malformed = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--oracle",
        "true",
        "--oracle-env-prefix",
        "bad prefix",
        prompt="objective",
    )
    assert malformed.returncode == 64
    assert json.loads(malformed.stdout)["error"] == "oracle_env_prefix_invalid"


def test_budget_tokens_bounds_a_cli_stream(tmp_path: Path, probe: Path) -> None:
    install_lanes(tmp_path, probe, [("flood", "local", "overflow")])
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "flood",
        # Above the capsule's own input estimate, far below the flood.
        "--budget-tokens",
        "400",
        prompt="short objective",
    )
    output = json.loads(result.stdout)
    row = output["results"][0]
    assert row["terminal"] == "output_limit"
    assert row["error"] == "budget_output_exceeds"
    assert row["call_started"] is True


def test_evidence_is_injected_and_bounded(
    tmp_path: Path,
    probe: Path,
    evidence_provider: Path,
) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        "--evidence",
        "--evidence-bytes",
        "400",
        prompt="what changed in the latest release",
        extra={
            "ATS_PROMPT_DIR": str(prompt_dir),
            "LLMADAPTER_EVIDENCE_CMD": str(evidence_provider),
            "LLMADAPTER_FIXTURE_MODE": "ok",
        },
    )
    output = json.loads(result.stdout)
    assert output["evidence"]["usable"] is True
    assert output["evidence"]["mode"] == "research"
    assert output["evidence"]["bytes"] <= 400
    # The envelope never echoes controller input, evidence target included.
    assert "latest release" not in json.dumps(output)
    capsule = (prompt_dir / "alpha.prompt").read_text()
    assert "FRESH FACT" in capsule
    assert "Cite only from this evidence" in capsule

    # Identical evidence must produce an identical capsule, otherwise the
    # per-lane cache misses on every run.
    second = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        "--evidence",
        "--evidence-bytes",
        "400",
        prompt="what changed in the latest release",
        extra={
            "LLMADAPTER_EVIDENCE_CMD": str(evidence_provider),
            "LLMADAPTER_FIXTURE_MODE": "ok",
        },
    )
    replay = json.loads(second.stdout)
    assert replay["results"][0]["terminal"] == "cached"


def test_evidence_challenge_page_is_not_evidence(
    tmp_path: Path,
    probe: Path,
    evidence_provider: Path,
) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        "--evidence",
        prompt="what changed in the latest release",
        extra={
            "ATS_PROMPT_DIR": str(prompt_dir),
            "LLMADAPTER_EVIDENCE_CMD": str(evidence_provider),
            "LLMADAPTER_FIXTURE_MODE": "challenge",
        },
    )
    output = json.loads(result.stdout)
    assert output["evidence"]["usable"] is False
    assert output["evidence"]["note"] == "page_status_challenge"
    capsule = (prompt_dir / "alpha.prompt").read_text()
    assert "Evidence: unavailable" in capsule
    assert "report BLOCKED" in capsule


def test_evidence_side_flags_require_the_evidence_flag(tmp_path: Path) -> None:
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--evidence-bytes",
        "400",
        prompt="objective",
    )
    assert result.returncode == 64
    assert json.loads(result.stdout)["error"] == "evidence_flags_require_evidence"


def test_evidence_without_a_provider_is_not_evidence(
    tmp_path: Path,
    probe: Path,
) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    result = run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        "--evidence",
        prompt="what changed in the latest release",
        extra={"LLMADAPTER_EVIDENCE_CMD": "", "ATS_PROMPT_DIR": str(prompt_dir)},
    )
    output = json.loads(result.stdout)
    assert output["evidence"]["usable"] is False
    assert output["evidence"]["note"] == "evidence_provider_unset"
    assert "Evidence: unavailable" in (prompt_dir / "alpha.prompt").read_text()


def test_skill_route_is_opt_in_and_fails_open(tmp_path: Path, probe: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    skill = tmp_path / "SKILL.md"
    skill.write_text("# fixture skill\n")
    fake_si = tmp_path / "bin" / "si"
    fake_si.parent.mkdir()
    fake_si.write_text(
        "#!/bin/sh\n"
        'if [ "${SI_FIXTURE_FAIL:-0}" = 1 ]; then exit 1; fi\n'
        f'printf \'{{"selected": [{{"name": "fixture-skill", "path": "{skill}"}}]}}\\n\'\n'
    )
    fake_si.chmod(0o755)
    path_with_si = f"{fake_si.parent}{os.pathsep}{os.environ['PATH']}"

    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    routed = json.loads(
        run_adapter(
            tmp_path,
            "ask-v2",
            "--stdin",
            "--swarm",
            "--lanes",
            "alpha",
            "--skill-route",
            prompt="objective that wants a skill",
            extra={"PATH": path_with_si, "ATS_PROMPT_DIR": str(prompt_dir)},
        ).stdout
    )
    assert routed["skill_route"]["name"] == "fixture-skill"
    assert str(skill) in (prompt_dir / "alpha.prompt").read_text()

    broken = json.loads(
        run_adapter(
            tmp_path,
            "ask-v2",
            "--stdin",
            "--swarm",
            "--lanes",
            "alpha",
            "--skill-route",
            "--no-cache",
            prompt="objective that wants a skill",
            extra={
                "PATH": path_with_si,
                "SI_FIXTURE_FAIL": "1",
                "ATS_PROMPT_DIR": str(prompt_dir),
            },
        ).stdout
    )
    assert "skill_route" not in broken
    assert broken["ok"] == 1


def test_council_adds_one_synthesis_over_the_same_worker_stage(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(
        tmp_path,
        probe,
        [("alpha", "local", "ok"), ("beta", "local", "ok"), ("judge", "local", "ok")],
    )
    result = run_adapter(
        tmp_path,
        "council",
        "--stdin",
        "--lanes",
        "alpha,beta",
        "--synth-lane",
        "judge",
        prompt="objective for the council",
    )
    output = json.loads(result.stdout)
    assert output["schema"] == "llmadapter.council"
    assert output["status"] == "ok"
    assert output["synth_lane"] == "judge"
    assert output["workers"]["ok"] == 2
    assert output["synthesis"]["ok"] is True
    assert "fixture answer for judge" in output["synthesis"]["text"]


def test_council_rejects_an_unknown_synthesis_lane(tmp_path: Path, probe: Path) -> None:
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    result = run_adapter(
        tmp_path,
        "council",
        "--stdin",
        "--lanes",
        "alpha",
        "--synth-lane",
        "nope",
        prompt="objective",
    )
    assert result.returncode == 64
    assert json.loads(result.stdout)["error"] == "synth_lane_unknown"


def test_cache_export_hashes_answers_unless_asked(tmp_path: Path, probe: Path) -> None:
    install_lanes(tmp_path, probe, [("alpha", "local", "ok")])
    run_adapter(
        tmp_path,
        "ask-v2",
        "--stdin",
        "--swarm",
        "--lanes",
        "alpha",
        prompt="objective worth caching",
    )
    out = tmp_path / "export.jsonl"
    summary = json.loads(run_adapter(tmp_path, "cache-export", "--out", str(out)).stdout)
    assert summary["rows"] == 1
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[0]["lane"] == "alpha"
    assert "answer" not in rows[0]
    assert rows[0]["answer_bytes"] > 0

    with_answers = tmp_path / "export-full.jsonl"
    run_adapter(tmp_path, "cache-export", "--out", str(with_answers), "--with-answers")
    full = [json.loads(line) for line in with_answers.read_text().splitlines()]
    assert "fixture answer for alpha" in full[0]["answer"]
