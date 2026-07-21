"""Contract tests for scripts/kimi_k3_lane_benchmark.py.

Pure-function coverage (oracle parsing, team aggregation, usage summing,
savings deltas) plus one stubbed end-to-end single arm: a fake ``kimi-worker``
on PATH emits a canned answer and a wire log, so no provider call happens.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import kimi_k3_lane_benchmark as bench  # noqa: E402

# --- oracle parsing -------------------------------------------------------


def test_parse_answer_takes_last_json_object():
    stdout = 'noise {"total_errors": 99} more {"total_errors": 100, "marker_line": 3777}'
    assert bench.parse_answer(stdout) == {"total_errors": 100, "marker_line": 3777}


def test_parse_answer_returns_none_without_json():
    assert bench.parse_answer("I counted them, trust me") is None


def test_fixture_subcount_is_pinned():
    """The seeded fixture puts exactly 44 ERROR lines in lines 2001-4000."""
    assert bench.subcount_errors() == 44


def test_oracle_single_accepts_exact_match():
    assert bench.oracle_single(
        {"total_errors": 100, "marker_line": 3777, "errors_2001_4000": 44}
    )


def test_oracle_single_rejects_lazy_or_wrong():
    assert not bench.oracle_single(None)
    assert not bench.oracle_single(
        {"total_errors": 99, "marker_line": 3777, "errors_2001_4000": 44}
    )
    assert not bench.oracle_single(
        {"total_errors": 100, "marker_line": 3778, "errors_2001_4000": 44}
    )
    assert not bench.oracle_single({"total_errors": 100, "marker_line": 3777})
    # head-only read: right totals, wrong positional subcount
    assert not bench.oracle_single(
        {"total_errors": 100, "marker_line": 3777, "errors_2001_4000": 50}
    )


def test_oracle_team_requires_sum_and_unique_marker():
    answers = [
        {"errors": 40, "marker_line": None},
        {"errors": 32, "marker_line": None},
        {"errors": 28, "marker_line": 3777},
    ]
    assert bench.oracle_team(answers)


def test_oracle_team_rejects_double_marker_and_bad_sum():
    double_marker = [
        {"errors": 40, "marker_line": 3777},
        {"errors": 32, "marker_line": None},
        {"errors": 28, "marker_line": 3777},
    ]
    assert not bench.oracle_team(double_marker)
    bad_sum = [
        {"errors": 40, "marker_line": None},
        {"errors": 31, "marker_line": None},
        {"errors": 28, "marker_line": 3777},
    ]
    assert not bench.oracle_team(bad_sum)
    assert not bench.oracle_team([None, {"errors": 100, "marker_line": 3777}, None])


# --- usage summing (same mapping as the wrapper's ledger export) ----------


def test_parse_wire_usage_sums_newest_wire_log(tmp_path):
    wire_dir = tmp_path / "sessions" / "proj" / "sess"
    wire_dir.mkdir(parents=True)
    rows = [
        {"input_other": 100, "output": 7, "input_cache_read": 900,
         "input_cache_creation": 0},
        {"input_other": 40, "output": 5, "input_cache_read": 1000,
         "input_cache_creation": 0},
    ]
    (wire_dir / "wire.jsonl").write_text(
        "".join(json.dumps({"token_usage": row}) + "\n" for row in rows)
    )
    total, requests = bench.parse_wire_usage(tmp_path)
    assert total == {
        "input_other": 140,
        "input_cache_read": 1900,
        "input_cache_creation": 0,
        "output": 12,
    }
    assert len(requests) == 2


def test_parse_wire_usage_handles_missing_log(tmp_path):
    total, requests = bench.parse_wire_usage(tmp_path)
    assert total == {k: 0 for k in bench.USAGE_KEYS}
    assert requests == []


def test_parse_wire_usage_includes_subagent_wires(tmp_path):
    """Built-in Agent subagents write their own wire.jsonl beside the parent."""
    parent = tmp_path / "sessions" / "proj" / "sess"
    child = parent / "subagents" / "agent-1"
    child.mkdir(parents=True)
    row = {"input_other": 10, "output": 1, "input_cache_read": 0,
           "input_cache_creation": 0}
    (parent / "wire.jsonl").write_text(json.dumps({"token_usage": row}) + "\n")
    (child / "wire.jsonl").write_text(json.dumps({"token_usage": row}) + "\n")
    total, requests = bench.parse_wire_usage(tmp_path)
    assert total["input_other"] == 20
    assert len(requests) == 2


def test_list_price_estimate_uses_k3_list_prices():
    usage = {"input_other": 1_000_000, "input_cache_read": 1_000_000,
             "input_cache_creation": 0, "output": 100_000}
    assert bench.list_price_estimate(usage) == 3.0 + 0.30 + 1.5


# --- savings deltas --------------------------------------------------------


def _arm(gross: int, output: int = 0) -> dict:
    return {"gross_input": gross, "output": output}


def test_savings_computes_headline_deltas():
    arms = {
        "k27-single": _arm(23_000),
        "k3-single": _arm(21_000),
        "k3-team": _arm(63_000),
        "k3-swarm": _arm(90_000),
        "k3-single-nothink": _arm(20_000, output=300),
    }
    out = bench.savings(arms)
    assert out["k3_vs_k27_single_gross"].startswith("-8.7%")
    assert out["k3_team_vs_k3_swarm_gross"].startswith("-30.0%")
    assert out["k3_team_vs_claude_team_0719"].startswith("-84.7%")
    assert "k27_single_drift_vs_0719" in out


def test_savings_skips_missing_arms():
    assert bench.savings({"k3-single": _arm(21_000)}) == {}


# --- stubbed end-to-end single arm ----------------------------------------


def test_arm_single_with_stubbed_worker(tmp_path, monkeypatch):
    share_seen: list[str] = []

    def fake_run(cmd, **kwargs):
        env = kwargs["env"]
        share = Path(env["KIMI_WORKER_SHARE_DIR"])
        share_seen.append(str(share))
        wire_dir = share / "sessions" / "proj" / "sess"
        wire_dir.mkdir(parents=True)
        (wire_dir / "wire.jsonl").write_text(
            json.dumps(
                {
                    "token_usage": {
                        "input_other": 100,
                        "input_cache_read": 900,
                        "input_cache_creation": 0,
                        "output": 7,
                    }
                }
            )
            + "\n"
        )

        class Proc:
            stdout = (
                '{"total_errors": 100, "marker_line": 3777, '
                '"errors_2001_4000": 44}'
            )
            returncode = 0

        return Proc()

    monkeypatch.setattr(bench.subprocess, "run", fake_run)
    bench.run_worker.worker_path = Path("/fake/kimi-worker")
    fixture = tmp_path / "fixture.log"
    fixture.write_text("x\n")
    arm = bench.arm_single(bench.MODEL_K3, fixture, tmp_path / "state")
    assert arm["oracle"] == "PASS"
    assert arm["gross_input"] == 1_000
    assert arm["model"] == bench.MODEL_K3
    assert share_seen and "single" in share_seen[0]


def test_dry_run_packets_do_not_leak_oracle_answers():
    fixture = Path("/tmp/fixture.log")
    single = bench.SINGLE_PACKET.format(fixture=fixture, total=4_000)
    swarm = bench.SWARM_PACKET.format(fixture=fixture, total=4_000)
    slice_packet = bench.SLICE_PACKET.format(fixture=fixture, total=4_000, a=1, b=1333)
    for packet in (single, swarm, slice_packet):
        assert '"total_errors": 100' not in packet
        assert "3777" not in packet
        assert "44" not in packet
    assert "lines 1 to 1333" in slice_packet


@pytest.mark.parametrize("name", sorted(bench.ARMS))
def test_all_arms_callable(name):
    assert callable(bench.ARMS[name])
