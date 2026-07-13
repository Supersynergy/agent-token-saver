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


def test_catalog_contains_no_dead_profile_entries():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "stack" / "catalog.json").read_text())
    referenced = {name for profile in catalog["profiles"].values() for name in profile}

    assert set(catalog["tools"]) == referenced
    assert catalog["profiles"]["minimal"] == ["native-projection"]


def test_missing_optional_tool_is_core_ready(monkeypatch):
    monkeypatch.setattr("scripts.stack_doctor.shutil.which", lambda _command: None)
    catalog = {
        "profiles": {"lean": ["native", "optional-cli"]},
        "tools": {
            "native": {"kind": "builtin", "required": True},
            "optional-cli": {
                "kind": "command",
                "command": "optional-cli",
                "required": False,
            },
        },
    }
    report = build_report(catalog, "lean")
    assert report["healthy"] is True
    assert report["profile_complete"] is False
    assert report["status"] == "core-ready"
    assert report["missing_optional"] == ["optional-cli"]
