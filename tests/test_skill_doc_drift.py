"""Guards against documentation drift in the portable skill.

The lane count was documented as 23, then 28, while the built-in table held 27
and the host showed 43 (built-ins plus host-local lanes). A portable skill that
hardcodes host-specific or sweep-volatile counts is wrong on someone else's
machine by construction, so the rule is: name the selector, not the number.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "agent-token-saver" / "SKILL.md"
REPO_SKILL_COPY = ROOT / ".agents" / "skills" / "agent-token-saver" / "SKILL.md"

# Countables whose real value depends on a catalog sweep or the host's
# local-lanes.json, i.e. anything the skill must not pin to a literal.
VOLATILE_NOUNS = ("lanes", "lane", "models", "providers")


def test_skill_does_not_hardcode_volatile_lane_counts() -> None:
    text = SKILL.read_text(encoding="utf-8")
    offenders = [
        match.group(0)
        for match in re.finditer(r"\b(\d+)\s+(" + "|".join(VOLATILE_NOUNS) + r")\b", text)
    ]
    assert not offenders, (
        "SKILL.md pins a volatile count: "
        f"{offenders}. Point at `llmadapter lanes` instead — the number is "
        "host-specific and drifts with every catalog sweep."
    )


def test_skill_names_the_stable_selectors() -> None:
    """Selectors are the stable contract, so they must stay documented."""
    text = SKILL.read_text(encoding="utf-8")
    for selector in ("cheap", "free", "paid", "local", "cli"):
        assert f"`{selector}`" in text, f"selector {selector} missing from SKILL.md"


@pytest.mark.skipif(not REPO_SKILL_COPY.is_file(), reason="repo skill copy not installed")
def test_repo_skill_copy_matches_canonical_source() -> None:
    """The installer mirrors the canonical skill into .agents/; a stale copy
    means agents reading the repo see different instructions than installed
    hosts do."""
    assert REPO_SKILL_COPY.read_text(encoding="utf-8") == SKILL.read_text(encoding="utf-8")
