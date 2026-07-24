"""Oracle: put→get roundtrip, TTL expiry → miss, empty body never cached."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "integration" / "cli" / "ats-url-cache"


def run(env_db, args, stdin=b""):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        env={"ATS_URL_CACHE_DB": str(env_db), "PATH": "/usr/bin:/bin"},
    )


def test_put_get_roundtrip(tmp_path):
    db = tmp_path / "c.db"
    assert run(db, ["put", "https://x.test/a"], b"# hello\n").returncode == 0
    got = run(db, ["get", "https://x.test/a"])
    assert got.returncode == 0
    assert got.stdout == b"# hello\n"


def test_ttl_expiry_is_miss(tmp_path):
    db = tmp_path / "c.db"
    run(db, ["put", "https://x.test/a"], b"body")
    assert run(db, ["get", "https://x.test/a", "--ttl", "0"]).returncode == 1


def test_empty_body_never_cached(tmp_path):
    db = tmp_path / "c.db"
    assert run(db, ["put", "https://x.test/empty"], b"  \n").returncode == 1
    assert run(db, ["get", "https://x.test/empty"]).returncode == 1


def test_unknown_url_is_miss(tmp_path):
    assert run(tmp_path / "c.db", ["get", "https://x.test/nope"]).returncode == 1


def test_stats_and_vacuum(tmp_path):
    db = tmp_path / "c.db"
    run(db, ["put", "https://x.test/a"], b"body")
    stats = run(db, ["stats"])
    assert stats.returncode == 0 and b"rows=1" in stats.stdout
    vac = run(db, ["vacuum", "--ttl", "0"])
    assert vac.returncode == 0 and b"expired=1" in vac.stdout
    assert run(db, ["get", "https://x.test/a"]).returncode == 1
