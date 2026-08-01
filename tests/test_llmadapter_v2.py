"""Providerless contract tests for llmadapter's AgentMaster protocol."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "llmadapter.ts"

pytestmark = pytest.mark.skipif(shutil.which("bun") is None, reason="bun is required")


def run_v2(
    home: Path,
    *args: str,
    prompt: str = "private prompt marker 97f91",
    extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "ATS_PII_SHIELD": "0"})
    if extra:
        env.update(extra)
    return subprocess.run(
        ["bun", str(ADAPTER), "ask-v2", *args],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=10,
    )


def install_lanes(home: Path, script: Path, lanes: list[tuple[str, str, str]]) -> None:
    """Install (name, class, mode) local fixture lanes with stdin transport."""
    rows = [
        {
            "name": name,
            "kind": "cli",
            "class": lane_class,
            "cmd": [str(script), mode, name, "__PROMPT__"],
            "stdin_cmd": [str(script), mode, name],
            "local_safe": lane_class == "local",
        }
        for name, lane_class, mode in lanes
    ]
    config = home / ".agent-token-saver" / "local-lanes.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"llmadapter": rows}))
    config.chmod(0o600)


def test_contract_advertises_v2_without_breaking_existing_fields(tmp_path: Path) -> None:
    env = {**os.environ, "HOME": str(tmp_path)}
    result = subprocess.run(
        ["bun", str(ADAPTER), "contract", "check exact source"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    contract = json.loads(result.stdout)
    assert contract["schema_version"] == 2
    assert contract["ask_v2"] is True
    assert contract["mode"] == "swarm"
    assert contract["default_max_workers"] == 3
    assert contract["max_workers"] == 3
    assert contract["fanout_max_workers"] == 64
    assert contract["max_result_tokens"] == 500
    assert contract["max_result_tokens_semantics"] == "requested_ceiling_by_capability"
    assert contract["max_prompt_bytes"] == 1800
    assert contract["tools_available"] is False
    assert "Reasoning-only lane" in contract["packet"]
    assert "`tilth" not in contract["packet"]
    assert "packet" in contract


@pytest.fixture
def probe(tmp_path: Path) -> Path:
    path = tmp_path / "probe.sh"
    path.write_text(
        """#!/bin/sh
set -eu
mode="$1"
lane="$2"
if [ -n "${ATS_ARGV_DIR:-}" ]; then
  printf '%s\n' "$*" > "$ATS_ARGV_DIR/$lane.argv"
fi
case "$mode" in
  ok)
    if [ -n "${ATS_PROMPT_DIR:-}" ]; then
      cat > "$ATS_PROMPT_DIR/$lane.prompt"
    else
      cat >/dev/null
    fi
    if [ "${ATS_PROBE_FAIL:-0}" = 1 ]; then
      exit 7
    fi
    printf 'fixture answer for %s\n' "$lane"
    ;;
  fail)
    cat >/dev/null
    printf 'bounded fixture diagnostic\n' >&2
    exit 7
    ;;
  overflow)
    cat >/dev/null
    exec python3 -c 'import sys; sys.stdout.write("x" * 300000)'
    ;;
  sleep)
    cat >/dev/null
    exec sleep 5
    ;;
  child)
    cat >/dev/null
    python3 -c 'import os,time; open(os.environ["ATS_CHILD_PID"], "w").write(str(os.getpid())); time.sleep(30)' &
    wait
    ;;
esac
"""
    )
    path.chmod(0o755)
    return path


def test_stdin_prompt_is_not_argv_or_result_metadata(
    tmp_path: Path,
    probe: Path,
) -> None:
    argv_dir = tmp_path / "argv"
    argv_dir.mkdir()
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    marker = "private prompt marker 97f91"
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        extra={"ATS_ARGV_DIR": str(argv_dir)},
        prompt=marker,
    )

    assert result.returncode == 0, result.stdout
    assert len(result.stdout.splitlines()) == 1
    report = json.loads(result.stdout)
    assert report["schema"] == "llmadapter.result"
    assert report["schema_version"] == 2
    assert report["prompt"]["bytes"] == len(marker)
    assert marker not in result.stdout
    assert marker not in result.stderr
    assert marker not in (argv_dir / "fixture-one.argv").read_text()
    assert report["results"][0]["cap_mode"] == "advisory_only"


def test_three_lane_default_bound_and_complete_private_usage(
    tmp_path: Path,
    probe: Path,
) -> None:
    names = [f"fixture-{number}" for number in range(1, 5)]
    install_lanes(tmp_path, probe, [(name, "local", "ok") for name in names])
    usage = tmp_path / "private" / "usage.json"
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        ",".join(names),
        "--no-cache",
        "--usage-out",
        str(usage),
    )

    assert result.returncode == 0, result.stdout
    report = json.loads(result.stdout)
    assert report["lanes"] == {
        "requested": ",".join(names),
        "selected": 3,
        "cap": 3,
        "fanout": False,
    }
    assert report["total"] == report["ok"] == 3
    assert all(item["call_started"] is True for item in report["results"])
    assert usage.exists()
    assert stat.S_IMODE(usage.stat().st_mode) == 0o600
    accounting = json.loads(usage.read_text())
    assert accounting == report["accounting"]
    assert accounting["terminal_records_complete"] is True
    assert accounting["calls_started"] == accounting["calls_completed"] == 3
    assert accounting["estimated_cost_usd"] is None
    assert accounting["input_tokens"]["estimated"] > 0


def test_fanout_is_required_to_select_more_than_three_lanes(
    tmp_path: Path,
    probe: Path,
) -> None:
    names = [f"fixture-{number}" for number in range(1, 5)]
    install_lanes(tmp_path, probe, [(name, "local", "ok") for name in names])
    bounded = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        ",".join(names),
        "--cap",
        "4",
        "--no-cache",
    )
    assert bounded.returncode == 0, bounded.stdout
    bounded_report = json.loads(bounded.stdout)
    assert bounded_report["total"] == 3
    assert bounded_report["lanes"]["cap"] == 3

    allowed = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        ",".join(names),
        "--cap",
        "4",
        "--fanout",
        "--no-cache",
    )
    assert allowed.returncode == 0, allowed.stdout
    report = json.loads(allowed.stdout)
    assert report["total"] == 4
    assert report["lanes"]["fanout"] is True


def test_usage_and_prompt_file_symlinks_are_rejected_before_workers(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    usage_target = tmp_path / "usage-target.json"
    usage_target.write_text("untouched")
    usage_link = tmp_path / "usage-link.json"
    usage_link.symlink_to(usage_target)
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--usage-out",
        str(usage_link),
    )
    assert result.returncode == 64
    assert json.loads(result.stdout)["error"] == "usage_out_unsafe"
    assert usage_target.read_text() == "untouched"

    prompt_target = tmp_path / "prompt.txt"
    prompt_target.write_text("secret")
    prompt_link = tmp_path / "prompt-link.txt"
    prompt_link.symlink_to(prompt_target)
    result = run_v2(
        tmp_path,
        "--prompt-file",
        str(prompt_link),
        "--swarm",
        "--lanes",
        "fixture-one",
        prompt="",
    )
    assert result.returncode == 64
    assert json.loads(result.stdout)["error"] == "prompt_file_unsafe"


def test_prompt_transport_is_bounded_and_private_file_only(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    oversized = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        prompt="x" * 1801,
    )
    assert oversized.returncode == 64
    assert json.loads(oversized.stdout)["error"] == "prompt_too_large"

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("private file prompt")
    prompt_file.chmod(0o644)
    unsafe = run_v2(
        tmp_path,
        "--prompt-file",
        str(prompt_file),
        "--swarm",
        "--lanes",
        "fixture-one",
        prompt="",
    )
    assert unsafe.returncode == 64
    assert json.loads(unsafe.stdout)["error"] == "prompt_file_unsafe"

    prompt_file.chmod(0o600)
    safe = run_v2(
        tmp_path,
        "--prompt-file",
        str(prompt_file),
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        prompt="",
    )
    assert safe.returncode == 0, safe.stdout
    assert json.loads(safe.stdout)["prompt"]["transport"] == "prompt_file"


@pytest.mark.parametrize(
    ("mode", "terminal", "error"),
    [
        ("fail", "failed", "cli_exit_7"),
        ("overflow", "output_limit", "output_limit"),
        ("sleep", "timeout", "global_deadline"),
    ],
)
def test_cli_failures_are_bounded_terminal_records(
    tmp_path: Path,
    probe: Path,
    mode: str,
    terminal: str,
    error: str,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", mode)])
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        "--deadline-secs",
        "1",
    )

    assert result.returncode != 0
    assert len(result.stdout.splitlines()) == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["results"][0]["terminal"] == terminal
    assert report["results"][0]["call_started"] is True
    assert report["results"][0]["error"] == error
    assert len(result.stderr.encode()) <= 16 * 1024
    assert report["accounting"]["terminal_records_complete"] is True


def test_deadline_kills_detached_cli_process_group(
    tmp_path: Path,
    probe: Path,
) -> None:
    child_pid_file = tmp_path / "child.pid"
    install_lanes(tmp_path, probe, [("fixture-one", "local", "child")])
    started = time.monotonic()
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        "--deadline-secs",
        "1",
        extra={"ATS_CHILD_PID": str(child_pid_file)},
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 1
    assert elapsed < 3
    assert json.loads(result.stdout)["results"][0]["terminal"] == "timeout"
    child_pid = int(child_pid_file.read_text())
    alive = True
    for _ in range(20):
        status = subprocess.run(
            ["ps", "-p", str(child_pid), "-o", "stat="],
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        alive = bool(status and not status.startswith("Z"))
        if not alive:
            break
        time.sleep(0.05)
    if alive:
        os.kill(child_pid, 9)
    assert not alive


def test_total_failure_still_writes_complete_usage(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "fail")])
    usage = tmp_path / "usage.json"
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        "--usage-out",
        str(usage),
    )
    assert result.returncode == 1
    accounting = json.loads(usage.read_text())
    assert accounting["failed"] is True
    assert accounting["terminal_records_complete"] is True
    assert accounting["calls_started"] == accounting["calls_completed"] == 1


def test_cli_class_is_remote_without_explicit_local_safe(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    config = tmp_path / ".agent-token-saver" / "local-lanes.json"
    payload = json.loads(config.read_text())
    payload["llmadapter"][0]["local_safe"] = False
    config.write_text(json.dumps(payload))

    blocked = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
    )
    assert blocked.returncode == 64
    assert json.loads(blocked.stdout)["error"] == "remote_requires_allow_remote"

    allowed = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--allow-remote",
        "--no-cache",
    )
    assert allowed.returncode == 0, allowed.stdout


def test_remote_preflight_failure_is_not_counted_as_a_started_call(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("remote-fixture", "cli", "ok")])
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "remote-fixture",
        "--allow-remote",
        "--no-cache",
        extra={
            "ATS_PII_SHIELD": "1",
            "ATS_SHIELD_PATH": str(tmp_path / "missing-shield.mjs"),
        },
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["results"][0]["call_started"] is False
    assert report["accounting"]["calls_started"] == 0
    assert report["accounting"]["calls_completed"] == 0


def test_impossible_lane_class_and_remote_ollama_are_not_trusted(
    tmp_path: Path,
    probe: Path,
) -> None:
    config = tmp_path / ".agent-token-saver" / "local-lanes.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "llmadapter": [
                    {
                        "name": "bad-openrouter",
                        "kind": "openrouter",
                        "class": "local",
                        "model": "fixture/model",
                        "cmd": [str(probe), "ok", "bad-openrouter", "__PROMPT__"],
                    }
                ]
            }
        )
    )
    config.chmod(0o600)
    invalid = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "bad-openrouter",
        "--allow-remote",
        "--no-cache",
    )
    assert invalid.returncode == 64
    assert json.loads(invalid.stdout)["error"] == "openrouter_lane_config_invalid"

    remote_ollama = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "ollama-gemma4",
        "--no-cache",
        extra={"LLMADAPTER_OLLAMA_URL": "https://models.example.invalid/api/generate"},
    )
    assert remote_ollama.returncode == 64
    assert json.loads(remote_ollama.stdout)["error"] == "remote_requires_allow_remote"


def test_remote_and_paid_lanes_require_explicit_gates(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(
        tmp_path,
        probe,
        [("remote-fixture", "cli", "ok"), ("paid-fixture", "paid", "ok")],
    )
    remote = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "remote-fixture",
        "--no-cache",
    )
    assert remote.returncode == 64
    assert json.loads(remote.stdout)["error"] == "remote_requires_allow_remote"

    paid = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "paid-fixture",
        "--allow-remote",
        "--no-cache",
    )
    assert paid.returncode == 64
    assert json.loads(paid.stdout)["error"] == "paid_requires_allow_remote_and_allow_paid"

    allowed = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "paid-fixture",
        "--allow-remote",
        "--allow-paid",
        "--no-cache",
    )
    assert allowed.returncode == 0
    assert json.loads(allowed.stdout)["ok"] == 1


@pytest.mark.parametrize("unsupported", ["--first", "--aggregate", "--verify", "--tier"])
def test_v1_controller_flags_are_rejected(unsupported: str, tmp_path: Path) -> None:
    result = run_v2(tmp_path, "--stdin", "--swarm", unsupported)
    assert result.returncode == 64
    report = json.loads(result.stdout)
    assert report["status"] == "invalid"
    assert report["error"].endswith("_unsupported")


@pytest.mark.parametrize(
    "args",
    [
        ("--swarm",),
        ("--stdin", "--prompt-file", "prompt.txt", "--swarm"),
        ("secret positional prompt", "--stdin", "--swarm"),
    ],
)
def test_prompt_transport_is_exactly_one_non_argv_channel(
    args: tuple[str, ...],
    tmp_path: Path,
) -> None:
    result = run_v2(tmp_path, *args)
    assert result.returncode == 64
    report = json.loads(result.stdout)
    assert report["status"] == "invalid"
    assert "private prompt marker" not in result.stdout


def test_ollama_receives_native_num_predict(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            requests.append(json.loads(self.rfile.read(length)))
            body = json.dumps(
                {
                    "response": "fixture ollama answer",
                    "prompt_eval_count": 4,
                    "eval_count": 5,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_v2(
            tmp_path,
            "--stdin",
            "--swarm",
            "--lanes",
            "ollama-gemma4",
            "--max-tokens",
            "123",
            "--no-cache",
            extra={
                "LLMADAPTER_OLLAMA_URL": (
                    f"http://127.0.0.1:{server.server_address[1]}/api/generate"
                )
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result.returncode == 0, result.stdout
    assert requests[0]["options"] == {"num_predict": 123}
    assert "Reasoning-only lane" in str(requests[0]["prompt"])
    assert "tilth" not in str(requests[0]["prompt"])
    report = json.loads(result.stdout)
    assert report["results"][0]["cap_mode"] == "local_native"
    assert report["results"][0]["token_count_source"] == "provider_reported"


def test_loopback_ollama_redirect_cannot_reach_a_second_sink(tmp_path: Path) -> None:
    sink_requests: list[bytes] = []

    class SinkHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            sink_requests.append(self.rfile.read(length))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    sink = ThreadingHTTPServer(("127.0.0.1", 0), SinkHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(307)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{sink.server_address[1]}/sink",
            )
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in (sink, redirect)
    ]
    for thread in threads:
        thread.start()
    try:
        result = run_v2(
            tmp_path,
            "--stdin",
            "--swarm",
            "--lanes",
            "ollama-gemma4",
            "--no-cache",
            extra={
                "LLMADAPTER_OLLAMA_URL": (
                    f"http://127.0.0.1:{redirect.server_address[1]}/api/generate"
                )
            },
        )
    finally:
        for server in (redirect, sink):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)

    assert result.returncode == 1
    assert sink_requests == []
    report = json.loads(result.stdout)
    assert report["results"][0]["call_started"] is True


def test_tool_hint_requires_explicit_lane_capability(
    tmp_path: Path,
    probe: Path,
) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    pure = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        prompt="Trace imports for this source function.",
        extra={"ATS_PROMPT_DIR": str(prompt_dir)},
    )
    assert pure.returncode == 0, pure.stdout
    packet = (prompt_dir / "fixture-one.prompt").read_text()
    assert "Reasoning-only lane" in packet
    assert "tilth" not in packet

    config = tmp_path / ".agent-token-saver" / "local-lanes.json"
    payload = json.loads(config.read_text())
    payload["llmadapter"][0]["tools"] = True
    config.write_text(json.dumps(payload))
    tool_lane = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
        prompt="Trace imports for this source function.",
        extra={"ATS_PROMPT_DIR": str(prompt_dir)},
    )
    assert tool_lane.returncode == 0, tool_lane.stdout
    packet = (prompt_dir / "fixture-one.prompt").read_text()
    assert "Tool lane: local source" in packet
    assert "tilth" in packet


@pytest.mark.parametrize("corruption", ["missing", "null", "oversized", "stale"])
def test_invalid_cache_entries_are_never_accepted(
    tmp_path: Path,
    probe: Path,
    corruption: str,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    first = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
    )
    assert first.returncode == 0, first.stdout
    cache_files = list((tmp_path / ".agent-token-saver" / "cache" / "llmadapter").glob("v2-*.json"))
    assert len(cache_files) == 1
    cache = cache_files[0]
    value = json.loads(cache.read_text())
    if corruption == "missing":
        value.pop("answer")
    elif corruption == "null":
        value["answer"] = None
    elif corruption == "oversized":
        value["answer"] = "x" * (256 * 1024 + 1)
    else:
        value["ts"] = 0
    cache.write_text(json.dumps(value))

    second = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        extra={"ATS_PROBE_FAIL": "1"},
    )
    assert second.returncode == 1
    report = json.loads(second.stdout)
    assert report["results"][0].get("cached") is not True
    assert report["results"][0]["terminal"] == "failed"
    assert report["results"][0]["call_started"] is True
    assert report["accounting"]["cache_hits"] == 0


def test_valid_cache_hit_is_not_counted_as_a_started_call(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    first = run_v2(tmp_path, "--stdin", "--swarm", "--lanes", "fixture-one")
    assert first.returncode == 0, first.stdout

    second = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        extra={"ATS_PROBE_FAIL": "1"},
    )
    assert second.returncode == 0, second.stdout
    report = json.loads(second.stdout)
    lane = report["results"][0]
    assert lane["terminal"] == "cached"
    assert lane["cached"] is True
    assert lane["call_started"] is False
    assert report["accounting"]["calls_started"] == 0
    assert report["accounting"]["calls_completed"] == 0
    assert report["accounting"]["cache_hits"] == 1


def test_unsafe_local_lane_configuration_is_ignored(
    tmp_path: Path,
    probe: Path,
) -> None:
    install_lanes(tmp_path, probe, [("fixture-one", "local", "ok")])
    config = tmp_path / ".agent-token-saver" / "local-lanes.json"
    config.chmod(0o644)
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "fixture-one",
        "--no-cache",
    )
    assert result.returncode == 64
    assert json.loads(result.stdout)["error"] == "no_lanes_matched"


def test_openrouter_receives_server_generation_cap(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            requests.append(json.loads(self.rfile.read(length)))
            body = json.dumps(
                {
                    "choices": [{"message": {"content": "fixture remote answer"}}],
                    "usage": {"prompt_tokens": 6, "completion_tokens": 7},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_v2(
            tmp_path,
            "--stdin",
            "--swarm",
            "--lanes",
            "gpt-oss-20b",
            "--max-tokens",
            "234",
            "--allow-remote",
            "--no-cache",
            extra={
                "LLMADAPTER_OPENROUTER_URL": (
                    f"http://127.0.0.1:{server.server_address[1]}/chat/completions"
                ),
                "OPENROUTER_API_KEY": "fixture-key",
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result.returncode == 0, result.stdout
    assert requests[0]["max_tokens"] == 234
    report = json.loads(result.stdout)
    assert report["results"][0]["cap_mode"] == "provider_server"


def test_http_response_body_is_bounded_before_json_parse(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(1024 * 1024 + 1))
            self.end_headers()
            try:
                self.wfile.write(b"x" * (1024 * 1024 + 1))
            except BrokenPipeError:
                pass

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_v2(
            tmp_path,
            "--stdin",
            "--swarm",
            "--lanes",
            "gpt-oss-20b",
            "--allow-remote",
            "--no-cache",
            extra={
                "LLMADAPTER_OPENROUTER_URL": (
                    f"http://127.0.0.1:{server.server_address[1]}/chat/completions"
                ),
                "OPENROUTER_API_KEY": "fixture-key",
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["results"][0]["terminal"] == "output_limit"
    assert report["results"][0]["error"] == "http_body_limit"


def write_ledger(home: Path, rows: list[tuple[str, int, int]]) -> None:
    """Seed (lane, ok_calls, failed_calls) into this month's llmadapter ledger."""
    ledger = home / ".agent-token-saver" / "ledger"
    ledger.mkdir(parents=True, exist_ok=True)
    now = time.gmtime()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", now)
    month = time.strftime("%Y%m", now)
    lines = []
    for lane, ok_calls, failed_calls in rows:
        for ok in [True] * ok_calls + [False] * failed_calls:
            lines.append(json.dumps({"ts": stamp, "lane": lane, "ok": ok, "ms": 10}))
    (ledger / f"llmadapter-{month}.jsonl").write_text("\n".join(lines) + "\n")


def test_cheap_selector_stays_inside_the_wire_class_contract() -> None:
    """AgentMaster validates class against free|paid|local|cli, so `cheap` is
    a selector keyword, never a fifth class value."""
    listing = subprocess.run(
        ["bun", str(ADAPTER), "lanes"],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ},
    )
    assert listing.returncode == 0, listing.stderr
    cheap = [line for line in listing.stdout.splitlines() if line.startswith("cheap ")]
    assert cheap, listing.stdout
    for line in cheap:
        assert "/Mout" in line, line


def test_cheap_lanes_are_gated_like_any_other_paid_lane(tmp_path: Path) -> None:
    result = run_v2(tmp_path, "--stdin", "--swarm", "--lanes", "cheap", "--allow-remote")
    assert result.returncode == 64
    assert json.loads(result.stdout)["error"] == "paid_requires_allow_remote_and_allow_paid"


# `local` also selects the built-in ollama lane. Point it at a closed localhost
# port so it fails immediately instead of waiting: still local, so the remote
# gate stays out of the way, and the ledger decides where it lands.
DEAD_OLLAMA = {"LLMADAPTER_OLLAMA_URL": "http://127.0.0.1:1/api/generate"}


def test_class_selector_prefers_lanes_that_answered_recently(
    tmp_path: Path,
    probe: Path,
) -> None:
    """The 3-lane cap decides who runs; array order would always pick 1-3."""
    names = [f"fixture-{number}" for number in range(1, 5)]
    install_lanes(tmp_path, probe, [(name, "local", "ok") for name in names])
    write_ledger(
        tmp_path,
        [
            ("ollama-gemma4", 0, 9),
            ("fixture-1", 0, 9),
            ("fixture-2", 0, 9),
            ("fixture-3", 6, 1),
            ("fixture-4", 8, 0),
        ],
    )
    result = run_v2(
        tmp_path, "--stdin", "--swarm", "--lanes", "local", "--no-cache", extra=DEAD_OLLAMA
    )

    assert result.returncode == 0, result.stdout
    report = json.loads(result.stdout)
    assert [item["lane"] for item in report["results"]] == [
        "fixture-4",
        "fixture-3",
        # Equal scores keep array order, so the first dead lane wins the slot.
        "ollama-gemma4",
    ]


def test_named_lanes_keep_the_callers_order(tmp_path: Path, probe: Path) -> None:
    """`--lanes a,b,c` is the caller stating an order, not asking for the best."""
    names = [f"fixture-{number}" for number in range(1, 4)]
    install_lanes(tmp_path, probe, [(name, "local", "ok") for name in names])
    write_ledger(tmp_path, [("fixture-1", 0, 9), ("fixture-3", 9, 0)])
    result = run_v2(tmp_path, "--stdin", "--swarm", "--lanes", ",".join(names), "--no-cache")

    assert result.returncode == 0, result.stdout
    report = json.loads(result.stdout)
    assert [item["lane"] for item in report["results"]] == names


def test_lane_health_ordering_can_be_switched_off(tmp_path: Path, probe: Path) -> None:
    names = [f"fixture-{number}" for number in range(1, 5)]
    install_lanes(tmp_path, probe, [(name, "local", "ok") for name in names])
    write_ledger(tmp_path, [("fixture-1", 0, 9), ("fixture-4", 9, 0)])
    result = run_v2(
        tmp_path,
        "--stdin",
        "--swarm",
        "--lanes",
        "local",
        "--no-cache",
        extra={**DEAD_OLLAMA, "LLMADAPTER_LANE_HEALTH": "0"},
    )

    assert result.returncode == 0, result.stdout
    report = json.loads(result.stdout)
    assert [item["lane"] for item in report["results"]] == [
        "ollama-gemma4",
        "fixture-1",
        "fixture-2",
    ]


def _answering_handler(
    requests: list[dict[str, object]],
    *,
    finish_reason: str = "stop",
    drop_first: bool = False,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            requests.append(json.loads(self.rfile.read(length)))
            if drop_first and len(requests) == 1:
                self.close_connection = True
                return
            body = json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": "fixture remote answer"},
                            "finish_reason": finish_reason,
                        }
                    ],
                    "usage": {"prompt_tokens": 6, "completion_tokens": 7},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def _serve(handler: type[BaseHTTPRequestHandler], tmp_path: Path, *args: str):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return run_v2(
            tmp_path,
            "--stdin",
            "--swarm",
            *args,
            "--allow-remote",
            "--no-cache",
            extra={
                "LLMADAPTER_OPENROUTER_URL": (
                    f"http://127.0.0.1:{server.server_address[1]}/chat/completions"
                ),
                "OPENROUTER_API_KEY": "fixture-key",
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_free_reasoning_lane_asks_the_provider_to_skip_visible_reasoning(
    tmp_path: Path,
) -> None:
    """Visible chain-of-thought spends the whole result budget on free lanes."""
    requests: list[dict[str, object]] = []
    result = _serve(
        _answering_handler(requests),
        tmp_path,
        "--lanes",
        "nemotron-3-super-120b-a12b",
    )
    assert result.returncode == 0, result.stdout
    assert requests[0]["reasoning"] == {"enabled": False}


@pytest.mark.parametrize(
    ("lane", "expected"),
    [
        # Measured 2026-08-01: gpt-oss-20b answers with an empty completion when
        # it receives `enabled:false`, so it gets no reasoning field at all.
        ("gpt-oss-20b", None),
        # nemotron-nano-9b-v2 reasons either way; `exclude` keeps the reasoning
        # out of the returned budget instead of truncating the answer.
        ("nemotron-nano-9b-v2", {"exclude": True}),
    ],
)
def test_measured_reasoning_exceptions_are_honoured(
    tmp_path: Path, lane: str, expected: dict[str, bool] | None
) -> None:
    requests: list[dict[str, object]] = []
    result = _serve(_answering_handler(requests), tmp_path, "--lanes", lane)
    assert result.returncode == 0, result.stdout
    assert requests[0].get("reasoning") == expected


def test_reasoning_override_env_restores_the_plain_request(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _answering_handler(requests))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_v2(
            tmp_path,
            "--stdin",
            "--swarm",
            "--lanes",
            "nemotron-3-super-120b-a12b",
            "--allow-remote",
            "--no-cache",
            extra={
                "LLMADAPTER_OPENROUTER_URL": (
                    f"http://127.0.0.1:{server.server_address[1]}/chat/completions"
                ),
                "OPENROUTER_API_KEY": "fixture-key",
                "LLMADAPTER_REASONING": "on",
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result.returncode == 0, result.stdout
    assert "reasoning" not in requests[0]


def test_dropped_socket_is_retried_instead_of_failing_the_lane(tmp_path: Path) -> None:
    """A closed connection used to escape the retry and kill the lane outright."""
    requests: list[dict[str, object]] = []
    result = _serve(
        _answering_handler(requests, drop_first=True),
        tmp_path,
        "--lanes",
        "gpt-oss-20b",
        "--deadline-secs",
        "9",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(requests) == 2
    report = json.loads(result.stdout)
    assert report["results"][0]["terminal"] == "succeeded"


def test_provider_stop_at_token_ceiling_is_reported_as_output_limit(
    tmp_path: Path,
) -> None:
    """`succeeded` would make a truncated deliberation look like a result."""
    requests: list[dict[str, object]] = []
    result = _serve(
        _answering_handler(requests, finish_reason="length"),
        tmp_path,
        "--lanes",
        "gpt-oss-20b",
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["results"][0]["terminal"] == "output_limit"
    assert report["results"][0]["error"] == "provider_finish_length"
