"""Tests for the IrrigationOS repository foundation."""

from __future__ import annotations

import json
import tomllib
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


def test_release_versions_are_consistent() -> None:
    """Stable release metadata must remain synchronized."""
    manifest = json.loads(
        (ROOT / "custom_components/irrigationos/manifest.json").read_text(encoding="utf-8")
    )
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    const_text = (ROOT / "custom_components/irrigationos/const.py").read_text(encoding="utf-8")
    assert manifest["version"] == "1.0.15"
    assert pyproject["project"]["version"] == manifest["version"]
    assert 'VERSION: Final = "1.0.15"' in const_text
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
        "V1_0_15_RELEASE_NOTES.md",
        "docs/V1_0_15_STABLE_RELEASE_CANDIDATE.md",
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


def test_v1_release_documentation_matches_current_boundary() -> None:
    """Canonical docs must distinguish implemented simulation from future live control."""
    audit = (ROOT / "docs/V1_0_ARCHITECTURE_AUDIT.md").read_text(encoding="utf-8")
    operating_modes = (ROOT / "docs/OPERATING_MODES.md").read_text(encoding="utf-8")
    assert "Home Assistant coordinator invokes the synchronized pipeline" in audit
    assert "Observation and simulation only" in audit
    assert "Live mode is **not enabled in the current release candidate**" in operating_modes


def test_v1_release_strategy_uses_github_as_authoritative_state() -> None:
    """Release governance must preserve the verified GitHub-first workflow."""
    strategy = (ROOT / "docs/RELEASE_STRATEGY.md").read_text(encoding="utf-8")
    assert "GitHub `main` is authoritative" in strategy
    assert "local/uncommitted state" in strategy


def test_v1_0_15_is_monotonic_stable_release_candidate() -> None:
    """Release docs must preserve the resolved monotonic SemVer decision."""
    strategy = (ROOT / "docs/RELEASE_STRATEGY.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    notes = (ROOT / "V1_0_15_RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert "first stable public release is **v1.0.15**" in strategy
    assert "Installable Home Assistant release:** v1.0.15" in roadmap
    assert "first stable public release candidate" in notes
    assert "live execution remains disabled" in notes.lower()
