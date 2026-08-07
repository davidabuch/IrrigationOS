"""Repository-level tests that do not require Home Assistant."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "irrigationos"


def test_manifest_is_valid() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "irrigationos"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "1.0.13"


def test_hacs_metadata_is_valid() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["name"] == "IrrigationOS"
    assert hacs["content_in_root"] is False


def test_required_files_exist() -> None:
    required = {
        "__init__.py",
        "manifest.json",
        "const.py",
        "config_flow.py",
        "coordinator.py",
        "sensor.py",
        "binary_sensor.py",
        "diagnostics.py",
        "strings.json",
    }
    assert required <= {path.name for path in INTEGRATION.iterdir()}
