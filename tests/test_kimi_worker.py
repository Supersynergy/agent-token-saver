"""Executable contract for integration/cli/kimi-worker.

Runs the wrapper against a stub ``kimi-cli`` on PATH so no provider call
happens: retry-on-75 semantics, permanent-failure passthrough, share-dir
seeding, evidence-suffix injection, lean --skills-dir argument and the
ledger-compatible usage export.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / "integration" / "cli" / "kimi-worker"


def run_worker(tmp_path: Path, stub_body: str, env_extra: dict[str, str], *args: str):
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "kimi-cli"
    stub.write_text("#!/bin/bash\n" + stub_body)
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["KIMI_WORKER_STATE"] = str(tmp_path / "state")
    env.pop("KIMI_WORKER_SHARE_DIR", None)
    env.pop("KIMI_WORKER_USAGE_OUT", None)
    env.pop("KIMI_WORKER_EVIDENCE", None)
    env.pop("KIMI_WORKER_NO_THINKING", None)
    env.update(env_extra)
    return subprocess.run(
        [str(WORKER), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


CAPTURE_ARGS = 'printf "%s\\n" "$@" > "$KIMI_WORKER_STATE-args"\n'


def test_success_passthrough_and_lean_args(tmp_path):
    result = run_worker(
        tmp_path,
        CAPTURE_ARGS + 'echo "{\\"ok\\":1}"\nexit 0\n',
        {},
        "count errors",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == '{"ok":1}'
    argv = (tmp_path / "state-args").read_text().splitlines()
    assert "--quiet" in argv
    assert "-y" in argv
    skills_dir = Path(argv[argv.index("--skills-dir") + 1])
    assert not any(skills_dir.iterdir() if skills_dir.exists() else [])
    assert argv[argv.index("-p") + 1] == "count errors"


def test_retries_only_exit_75(tmp_path):
    counter = tmp_path / "state-count"
    body = (
        f'n=$(cat "{counter}" 2>/dev/null || echo 0)\n'
        f'echo $((n + 1)) > "{counter}"\n'
        'if [ "$n" -lt 2 ]; then exit 75; fi\n'
        "echo recovered\nexit 0\n"
    )
    result = run_worker(tmp_path, body, {"KIMI_WORKER_RETRIES": "3"}, "task")
    assert result.returncode == 0
    assert result.stdout.strip() == "recovered"
    assert counter.read_text().strip() == "3"


def test_retry_cap_returns_75(tmp_path):
    result = run_worker(tmp_path, "exit 75\n", {"KIMI_WORKER_RETRIES": "1"}, "task")
    assert result.returncode == 75


def test_permanent_failure_not_retried(tmp_path):
    counter = tmp_path / "state-count"
    body = f'n=$(cat "{counter}" 2>/dev/null || echo 0)\necho $((n + 1)) > "{counter}"\nexit 1\n'
    result = run_worker(tmp_path, body, {"KIMI_WORKER_RETRIES": "3"}, "task")
    assert result.returncode == 1
    assert counter.read_text().strip() == "1"


def test_share_dir_seeded_from_default_root(tmp_path):
    seed = tmp_path / "seed-root"
    (seed / "credentials").mkdir(parents=True)
    (seed / "credentials" / "token").write_text("t")
    (seed / "config.toml").write_text('default_model = "x"\n')
    share = tmp_path / "share"
    result = run_worker(
        tmp_path,
        "exit 0\n",
        {
            "KIMI_WORKER_SHARE_DIR": str(share),
            "KIMI_WORKER_SEED_FROM": str(seed),
        },
        "task",
    )
    assert result.returncode == 0
    assert (share / "config.toml").read_text() == 'default_model = "x"\n'
    assert (share / "credentials" / "token").read_text() == "t"


def test_evidence_suffix_appended(tmp_path):
    result = run_worker(
        tmp_path,
        CAPTURE_ARGS + "exit 0\n",
        {"KIMI_WORKER_EVIDENCE": "/tmp/ev.md"},
        "base task",
    )
    assert result.returncode == 0
    args_text = (tmp_path / "state-args").read_text()
    argv = args_text.splitlines()
    assert argv[argv.index("-p") + 1] == "base task"
    assert "/tmp/ev.md" in args_text


def test_no_thinking_flag_passthrough(tmp_path):
    result = run_worker(
        tmp_path,
        CAPTURE_ARGS + "exit 0\n",
        {"KIMI_WORKER_NO_THINKING": "1"},
        "task",
    )
    assert result.returncode == 0
    argv = (tmp_path / "state-args").read_text().splitlines()
    assert "--no-thinking" in argv
    assert "--config" not in argv


def test_usage_export_normalizes_wire_log(tmp_path):
    share = tmp_path / "share"
    seed = tmp_path / "seed-root"
    seed.mkdir()
    wire_dir = share / "sessions" / "proj" / "sess"
    body = (
        f'mkdir -p "{wire_dir}"\n'
        'cat > "' + str(wire_dir / "wire.jsonl") + "\" <<'EOF'\n"
        '{"message": {"payload": {"token_usage": {"input_other": 100, '
        '"output": 7, "input_cache_read": 900, "input_cache_creation": 0}}}}\n'
        '{"message": {"payload": {"token_usage": {"input_other": 40, '
        '"output": 5, "input_cache_read": 1000, "input_cache_creation": 0}}}}\n'
        "EOF\n"
        "exit 0\n"
    )
    usage_out = tmp_path / "usage.jsonl"
    result = run_worker(
        tmp_path,
        body,
        {
            "KIMI_WORKER_SHARE_DIR": str(share),
            "KIMI_WORKER_SEED_FROM": str(seed),
            "KIMI_WORKER_USAGE_OUT": str(usage_out),
        },
        "task",
    )
    assert result.returncode == 0
    records = [json.loads(line) for line in usage_out.read_text().splitlines()]
    assert records == [
        {
            "usage": {
                "input_tokens": 140,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 1900,
                "output_tokens": 12,
            }
        }
    ]
