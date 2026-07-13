import json
from pathlib import Path

from scripts.stack_doctor import build_report


def test_minimal_profile_reports_builtin(tmp_path: Path):
    catalog = {
        "profiles": {"minimal": ["native"]},
        "tools": {
            "native": {
                "kind": "builtin",
                "required": True,
                "activation": "default",
            }
        },
    }
    report = build_report(catalog, "minimal")
    assert report["healthy"] is True
    assert report["tools"][0]["version"] == "builtin"


def test_catalog_profiles_reference_known_tools():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "stack" / "catalog.json").read_text())
    known = set(catalog["tools"])
    for tools in catalog["profiles"].values():
        assert set(tools) <= known
