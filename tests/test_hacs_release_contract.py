from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_metadata_and_hacs_floor_are_synchronized() -> None:
    manifest = json.loads(
        (ROOT / "custom_components/irrigationos/manifest.json").read_text(encoding="utf-8")
    )
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    const_text = (ROOT / "custom_components/irrigationos/const.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^VERSION: Final = "([^"]+)"$', const_text, re.MULTILINE)

    assert match is not None
    assert manifest["version"] == pyproject["project"]["version"] == match.group(1)
    assert hacs["name"] == "IrrigationOS"
    assert hacs["homeassistant"] == "2026.8.0"


def test_hassfest_and_hacs_validation_workflows_are_present() -> None:
    hassfest = (ROOT / ".github/workflows/hassfest.yml").read_text(encoding="utf-8")
    hacs = (ROOT / ".github/workflows/hacs.yml").read_text(encoding="utf-8")

    assert "home-assistant/actions/hassfest@master" in hassfest
    assert "pull_request:" in hassfest
    assert "push:" in hassfest
    assert "workflow_dispatch:" in hassfest

    assert "hacs/action@main" in hacs
    assert "category: integration" in hacs
    assert "github.event.repository.private == false" in hacs
    assert "pull_request:" in hacs
    assert "workflow_dispatch:" in hacs
