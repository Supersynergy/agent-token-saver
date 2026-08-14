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

# One release means editing six files. Each is a place the version can be
# forgotten, and a stale one ships a wrong contract string to every worker or
# a wrong skill version into every host manifest.
VERSION_SITES = (
    (ROOT / "pyproject.toml", re.compile(r'^version = "([^"]+)"', re.MULTILINE)),
    (ROOT / "uv.lock", re.compile(r'name = "agent-token-saver"\nversion = "([^"]+)"')),
    (SKILL, re.compile(r"^version:\s*(\S+)", re.MULTILINE)),
    (REPO_SKILL_COPY, re.compile(r"^version:\s*(\S+)", re.MULTILINE)),
    (
        ROOT / "integration" / "hooks" / "agent-worker-capsule.py",
        re.compile(r"worker contract \(v([^)]+)\)"),
    ),
)

# Countables whose real value depends on a catalog sweep or the host's
# local-lanes.json, i.e. anything the skill must not pin to a literal.
VOLATILE_NOUNS = ("lanes", "lane", "models", "providers")


def test_all_version_declarations_agree() -> None:
    versions: dict[str, str] = {}
    for path, pattern in VERSION_SITES:
        assert path.is_file(), f"missing version site: {path}"
        match = pattern.search(path.read_text(encoding="utf-8"))
        assert match, f"no version found in {path.relative_to(ROOT)}"
        versions[str(path.relative_to(ROOT))] = match.group(1)

    assert len(set(versions.values())) == 1, f"version drift across release sites: {versions}"


def test_changelog_documents_the_current_version() -> None:
    """A release that ships without its changelog entry is undocumented."""
    pyproject_pattern = VERSION_SITES[0][1]
    match = pyproject_pattern.search((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert match
    version = match.group(1)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## {re.escape(version)} ", changelog, re.MULTILINE), (
        f"CHANGELOG.md has no released section for {version}"
    )


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
