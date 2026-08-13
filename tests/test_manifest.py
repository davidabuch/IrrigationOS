"""Repository-level tests that do not require Home Assistant."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "irrigationos"
CURRENT_VERSION = "1.0.38"


def test_manifest_is_valid() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "irrigationos"
    assert manifest["config_flow"] is True
    assert manifest["version"] == CURRENT_VERSION


def test_python_project_version_matches_manifest() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == CURRENT_VERSION
    assert pyproject["project"]["version"] == manifest["version"]


def test_readme_current_release_matches_manifest() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**v{manifest['version']} —" in readme
    assert "Observation remains the default commissioned operating mode" in readme
    assert "No irrigation command service or button is registered" in readme
    assert "live_control_authorized` hard-coded `false`" in readme


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
        "button.py",
        "health.py",
        "operational_log.py",
        "observation_history",
        "diagnostics.py",
        "strings.json",
    }
    assert required <= {path.name for path in INTEGRATION.iterdir()}
