#!/usr/bin/env python3
"""Validate required IrrigationOS repository metadata without third-party packages."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    ".github/workflows/ci.yml",
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "PRODUCT_PRINCIPLES.md",
    "V0_4_1_RELEASE_NOTES.md",
    "V0_4_2_RELEASE_NOTES.md",
    "V1_0_15_RELEASE_NOTES.md",
    "custom_components/irrigationos/brand/icon.png",
    "custom_components/irrigationos/manifest.json",
    "custom_components/irrigationos/button.py",
    "custom_components/irrigationos/health.py",
    "custom_components/irrigationos/operational_log.py",
    "custom_components/irrigationos/observation_history/models.py",
    "custom_components/irrigationos/observation_history/reconciliation.py",
    "custom_components/irrigationos/observation_history/manager.py",
    "custom_components/irrigationos/observation_history/session_log.py",
    "custom_components/irrigationos/strings.json",
    "custom_components/irrigationos/translations/en.json",
    "docs/IRRIGATIONOS_ARCHITECTURE_V1.md",
    "docs/VISION.md",
    "docs/V0_4_2_ARCHITECTURE.md",
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
    "docs/adr/ADR-011-realtime-rachio-observation.md",
    "custom_components/irrigationos/landscape/models.py",
    "custom_components/irrigationos/landscape/builder.py",
    "custom_components/irrigationos/scientific_inputs/engine.py",
    "custom_components/irrigationos/scientific_inputs/models.py",
    "docs/V1_0_3_WATER_REQUIREMENT_PIPELINE.md",
    "docs/V1_0_4_PLANT_STRESS_PIPELINE.md",
    "docs/V1_0_5_PLANT_HEALTH_PIPELINE.md",
    "docs/V1_0_6_RECOMMENDATION_PIPELINE.md",
    "docs/V1_0_7_PLANNING_PIPELINE.md",
    "docs/V1_0_8_SCHEDULING_PIPELINE.md",
    "docs/V1_0_9_EXECUTION_SIMULATION_PIPELINE.md",
    "docs/V1_0_10_RUNTIME_MONITORING_PIPELINE.md",
    "docs/V1_0_11_PIPELINE_ENTITIES_DIAGNOSTICS.md",
    "docs/V1_0_12_HA_LIFECYCLE_VALIDATION.md",
    "docs/V1_0_13_PUBLIC_API_COMPATIBILITY_FREEZE.md",
    "docs/V1_0_14_ARCHITECTURE_RELEASE_DOCUMENTATION.md",
    "docs/V1_0_15_STABLE_RELEASE_CANDIDATE.md",
    "docs/V1_0_16_HEALTH_MONITORING.md",
    "docs/V1_0_17_OBSERVATION_HISTORY.md",
    "docs/V1_0_18_SHADOW_EVALUATION_FOUNDATION.md",
    "docs/V1_0_19_ACTUAL_VS_SHADOW_RECONCILIATION.md",
    "docs/V1_0_20_SHADOW_REPORTING_COMMISSIONING_SUMMARY.md",
    "docs/V1_0_21_REPLAY_CONTROL_READINESS_EVIDENCE.md",
    "custom_components/irrigationos/replay_readiness/engine.py",
    "custom_components/irrigationos/replay_readiness/models.py",
    "docs/V1_0_22_SAFETY_MANAGER_EXECUTION_AUTHORIZATION.md",
    "custom_components/irrigationos/execution_authorization/engine.py",
    "custom_components/irrigationos/execution_authorization/models.py",
    "custom_components/irrigationos/ownership_commissioning/engine.py",
    "custom_components/irrigationos/ownership_commissioning/models.py",
    "docs/V1_0_23_CONTROLLER_OWNERSHIP_COMMISSIONING.md",
    "docs/V1_0_24_LIVE_MODE_SAFETY_ARCHITECTURE.md",
    "docs/V1_0_25_COMMAND_ATTRIBUTION_RECEIPTS.md",
    "docs/V1_0_26_COMMAND_ACKNOWLEDGEMENT_TIMEOUTS.md",
    "custom_components/irrigationos/command_acknowledgements/engine.py",
    "custom_components/irrigationos/command_acknowledgements/models.py",
    "custom_components/irrigationos/command_receipts/engine.py",
    "custom_components/irrigationos/command_receipts/models.py",
    "custom_components/irrigationos/live_mode_safety/engine.py",
    "custom_components/irrigationos/live_mode_safety/models.py",
    "custom_components/irrigationos/commissioning_report/engine.py",
    "custom_components/irrigationos/commissioning_report/models.py",
    "docs/V1_0_PUBLIC_API_CONTRACT.json",
    "hacs.json",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements-ha-test.txt",
    "tests_ha/conftest.py",
    "tests_ha/test_smoke.py",
)


def load_json(relative_path: str) -> object:
    """Load a JSON file from the repository root."""
    with (ROOT / relative_path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_pyproject() -> dict[str, object]:
    """Load pyproject metadata with the standard-library TOML parser."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def main() -> int:
    """Validate the repository structure and metadata."""
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")

    manifest = load_json("custom_components/irrigationos/manifest.json")
    if not isinstance(manifest, dict):
        raise SystemExit("manifest.json must contain a JSON object")
    if manifest.get("domain") != "irrigationos":
        raise SystemExit("manifest.json domain must be irrigationos")
    if manifest.get("config_flow") is not True:
        raise SystemExit("manifest.json must enable config_flow")
    if manifest.get("version") != "1.0.26":
        raise SystemExit("manifest.json version must be 1.0.26")

    pyproject = load_pyproject()
    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise SystemExit("pyproject.toml must contain a [project] table")
    if project.get("version") != manifest.get("version"):
        raise SystemExit("pyproject.toml and manifest.json versions must match")

    hacs = load_json("hacs.json")
    if not isinstance(hacs, dict) or hacs.get("name") != "IrrigationOS":
        raise SystemExit("hacs.json must identify IrrigationOS")

    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
