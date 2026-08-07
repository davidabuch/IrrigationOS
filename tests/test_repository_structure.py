"""Tests for the IrrigationOS repository foundation."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_github_actions_workflow_exists() -> None:
    """The repository must include its CI workflow."""
    assert (ROOT / ".github/workflows/ci.yml").is_file()


def test_ci_includes_home_assistant_validation() -> None:
    """Release CI must exercise Home Assistant compatibility."""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "requirements-ha-test.txt" in workflow
    assert "tests_ha" in workflow


def test_local_brand_icon_exists() -> None:
    """HACS and Home Assistant must have a local integration icon."""
    assert (ROOT / "custom_components/irrigationos/brand/icon.png").is_file()


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
    assert manifest["version"] == "1.0.3"
    assert manifest["domain"] == "irrigationos"


def test_governance_documents_exist() -> None:
    """Canonical governance documents and ADRs must remain present."""
    required = (
        "docs/VISION.md",
        "docs/ROADMAP.md",
        "docs/ARCHITECTURE.md",
        "docs/OPERATING_MODES.md",
        "docs/ENGINEERING_GUIDELINES.md",
        "docs/RELEASE_STRATEGY.md",
        "docs/adr/ADR-002-controller-adapter-boundary.md",
        "docs/adr/ADR-001-observation-first-safety-boundary.md",
        "docs/adr/ADR-003-weather-provider-architecture.md",
        "docs/adr/ADR-004-soil-model-architecture.md",
        "docs/adr/ADR-005-decision-transparency.md",
        "docs/adr/ADR-006-controller-domain-model.md",
        "docs/adr/ADR-007-landscape-digital-twin-foundation.md",
        "docs/adr/ADR-008-first-live-installation-boundary.md",
        "docs/adr/ADR-009-stable-controller-slot-identity.md",
        "docs/adr/ADR-010-canonical-controller-model.md",
        "PRODUCT_PRINCIPLES.md",
    )
    for relative_path in required:
        assert (ROOT / relative_path).is_file(), relative_path


def test_governance_preserves_observation_first_boundary() -> None:
    """Governance must retain the staged commissioning safety rule."""
    operating_modes = (ROOT / "docs/OPERATING_MODES.md").read_text(encoding="utf-8")
    assert "Observation -> Simulation -> Shadow -> Live" in operating_modes
    assert "must never automatically promote" in operating_modes


def test_controller_foundation_files_exist() -> None:
    """The controller-agnostic boundary must remain part of the repository."""
    required = (
        "custom_components/irrigationos/controllers/base.py",
        "custom_components/irrigationos/controllers/models.py",
        "custom_components/irrigationos/controllers/registry.py",
        "custom_components/irrigationos/adapters/rachio/adapter.py",
        "docs/adr/ADR-006-controller-domain-model.md",
        "docs/adr/ADR-007-landscape-digital-twin-foundation.md",
        "docs/adr/ADR-008-first-live-installation-boundary.md",
    )
    for relative_path in required:
        assert (ROOT / relative_path).is_file(), relative_path
