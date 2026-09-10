import json
from pathlib import Path

from scripts import workflow_matrix_benchmark as bench


def test_fixtures_and_exact_projections_are_stable_and_accepted() -> None:
    first = bench.build_fixtures()
    second = bench.build_fixtures()

    assert [bench.sha256_text(item.raw) for item in first] == [
        bench.sha256_text(item.raw) for item in second
    ]
    assert all(
        bench.projection_passes(fixture, bench.project_fixture(fixture)) for fixture in first
    )
    assert all(
        bench.token_proxy(bench.project_fixture(fixture)) < bench.token_proxy(fixture.raw)
        for fixture in first
    )


def test_live_oracle_accepts_only_exact_named_json_object(tmp_path: Path) -> None:
    exact = json.dumps(bench.EXPECTED_LIVE)
    assert bench.live_oracle(exact)
    assert bench.live_oracle(f"```json\n{exact}\n```")
    assert not bench.live_oracle(json.dumps({**bench.EXPECTED_LIVE, "extra": True}))
    assert not bench.live_oracle(json.dumps({**bench.EXPECTED_LIVE, "actual": 145}))

    answer = tmp_path / "answer.json"
    answer.write_text(exact)
    assert bench.live_oracle(answer.read_text())


def test_projection_cache_has_reproducible_cold_and_warm_contract() -> None:
    cache = bench.ProjectionCache()
    fixture = bench.orders_fixture()

    cold, cold_hit = cache.get_or_project(fixture)
    warm, warm_hit = cache.get_or_project(fixture)

    assert not cold_hit
    assert warm_hit
    assert cold == warm
    assert bench.projection_passes(fixture, warm)


def test_offline_matrix_keeps_provider_counters_unavailable() -> None:
    fixtures = bench.build_fixtures()
    components, matrix, _ = bench.offline_matrix(fixtures, None)

    assert all(component["accepted"] for component in components)
    assert all(row["accepted"] for row in matrix)
    assert all(row["provider_counter_status"] == "unavailable_offline" for row in matrix)
    assert all(row["provider_input_tokens"] is None for row in matrix)
    warm = next(row for row in matrix if "warm_recall_cache" in row["name"])
    assert warm["calls_started"] == 0
    assert warm["cache_hits"] == len(fixtures)


def test_provider_totals_keep_reported_estimated_unknown_separate() -> None:
    totals = bench.usage_team_totals(
        {
            "calls_started": 3,
            "calls_completed": 3,
            "cache_hits": 0,
            "input_tokens": {"reported": 120, "estimated": 30, "unknown_calls": 1},
            "output_tokens": {"reported": 20, "estimated": 10, "unknown_calls": 1},
        }
    )

    combined = totals["parent_plus_children"]
    assert combined == {
        "reported_tokens": 140,
        "estimated_tokens": 40,
        "unknown_calls": 1,
        "counter_status": "mixed",
    }
    assert totals["parent"]["calls_started"] == 0


def test_live_command_gates_remote_paid_and_uses_real_oracle(tmp_path: Path) -> None:
    usage = tmp_path / "usage.json"
    cheap = bench.llmadapter_command(
        "llmadapter",
        usage,
        lanes="cheap",
        cap=3,
        deadline=60,
        no_cache=True,
        first_pass_oracle=True,
    )
    local = bench.llmadapter_command(
        "llmadapter",
        usage,
        lanes="local",
        cap=1,
        deadline=60,
        no_cache=False,
        first_pass_oracle=False,
    )

    assert "--allow-remote" in cheap and "--allow-paid" in cheap
    assert "--first-pass" in cheap and "--oracle" in cheap
    assert "--tier" not in cheap
    assert "--allow-remote" not in local and "--allow-paid" not in local


def test_make_report_offline_writes_no_provider_claims(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bench, "inventory_tools", lambda *_: {"stub": True})
    monkeypatch.setattr(bench, "git_commit", lambda: "deadbeef")

    report = bench.make_report(
        tmp_path,
        samples=2,
        live_local=False,
        live_cheap=False,
        live_first_pass=False,
        deadline=30,
        llmadapter_path=None,
        rtk_path=None,
        reused_live=None,
    )

    assert report["acceptance"]["overall_accepted"]
    assert report["live_arms"] == []
    assert "billing" in report["method"]["local_tokens"]


def test_reused_live_arms_are_preserved_without_calls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bench, "inventory_tools", lambda *_: {"stub": True})
    monkeypatch.setattr(bench, "git_commit", lambda: "deadbeef")
    reused = [{"name": "local_single_warm", "accepted": True}]

    report = bench.make_report(
        tmp_path,
        samples=1,
        live_local=False,
        live_cheap=False,
        live_first_pass=False,
        deadline=30,
        llmadapter_path=None,
        rtk_path=None,
        reused_live=reused,
    )

    assert report["live_arms"] == reused
    assert report["acceptance"]["live_requested"]
    assert report["acceptance"]["overall_accepted"]
