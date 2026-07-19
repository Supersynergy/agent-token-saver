"""Deterministic log fixture for engine-lane and team benchmarks.

Regenerates the 2026-07-16 fixture shape: 4,000 lines, exactly 100 lines
containing ``ERROR`` and one ``CRITICAL-MARKER`` line at line 3777. The
oracle for every lane is: report ``{"total_errors":100,"marker_line":3777}``.

Usage: uv run python scripts/make_log_fixture.py <output-path>
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

TOTAL_LINES = 4_000
ERROR_LINES = 100
MARKER_LINE = 3_777
SEED = 42

COMPONENTS = ("auth", "billing", "ingest", "scheduler", "cache", "api")
INFO_TEMPLATES = (
    "INFO {c} request handled in {ms}ms",
    "DEBUG {c} heartbeat ok seq={ms}",
    "WARN {c} retry queue depth {ms}",
    "INFO {c} flushed {ms} rows",
)


def build() -> str:
    rng = random.Random(SEED)
    candidates = [n for n in range(1, TOTAL_LINES + 1) if n != MARKER_LINE]
    error_lines = set(rng.sample(candidates, ERROR_LINES))
    rows = []
    for n in range(1, TOTAL_LINES + 1):
        c = COMPONENTS[n % len(COMPONENTS)]
        ts = f"2026-07-16T{(n // 3600) % 24:02d}:{(n // 60) % 60:02d}:{n % 60:02d}Z"
        if n == MARKER_LINE:
            rows.append(f"{ts} NOTICE core CRITICAL-MARKER checkpoint reached")
        elif n in error_lines:
            rows.append(f"{ts} ERROR {c} upstream timeout code={rng.randint(500, 599)}")
        else:
            t = INFO_TEMPLATES[n % len(INFO_TEMPLATES)]
            rows.append(f"{ts} {t.format(c=c, ms=rng.randint(1, 900))}")
    return "\n".join(rows) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fixture.log")
    text = build()
    out.write_text(text)
    n_err = sum("ERROR" in line for line in text.splitlines())
    marker = [i for i, line in enumerate(text.splitlines(), 1) if "CRITICAL-MARKER" in line]
    assert n_err == ERROR_LINES, n_err
    assert marker == [MARKER_LINE], marker
    print(f"wrote {out} lines={TOTAL_LINES} errors={n_err} marker={marker[0]}")


if __name__ == "__main__":
    main()
