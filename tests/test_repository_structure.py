"""Tests for the IrrigationOS repository foundation."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_github_actions_workflow_exists() -> None:
    """The repository must include its CI workflow."""
    assert (ROOT / ".github/workflows/ci.yml").is_file()


def test_generated_cache_files_are_ignored() -> None:
    """Python and Finder cache files must be ignored by Git."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("__pycache__/", "*.py[cod]", ".pytest_cache/", ".DS_Store"):
        assert pattern in gitignore


def test_manifest_and_hacs_versions_are_consistent() -> None:
    """The manifest must expose a valid pre-release version."""
    manifest = json.loads(
        (ROOT / "custom_components/irrigationos/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == "0.1.0"
    assert manifest["domain"] == "irrigationos"
