"""Oracle: stdout error signatures flip success to False; real answers do not."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "integration" / "cli" / "ats-swarm-bench.py"
spec = importlib.util.spec_from_file_location("ats_swarm_bench", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod  # dataclass introspection needs the module registered
spec.loader.exec_module(mod)


def test_http_errors_are_failures():
    assert mod._looks_like_error("HTTP 401: The API Key appears to be invalid")
    assert mod._looks_like_error("Billing or credits exhausted: HTTP 402: ...")
    assert mod._looks_like_error("Rate limit reached, retry later")


def test_real_answers_pass():
    assert not mod._looks_like_error('{"name": "Acme Widget Pro", "price": "$42.99"}')
    assert not mod._looks_like_error("The product costs 402 dollars")  # number != marker


def test_error_marker_only_scans_head():
    long_tail = "x" * 500 + "http 401"
    assert not mod._looks_like_error(long_tail)
