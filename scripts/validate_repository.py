#!/usr/bin/env python3
"""Validate required IrrigationOS repository metadata without third-party packages."""

from __future__ import annotations

import json
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
    "custom_components/irrigationos/brand/icon.png",
    "custom_components/irrigationos/manifest.json",
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
    if manifest.get("version") != "1.0.13":
        raise SystemExit("manifest.json version must be 1.0.13")

    hacs = load_json("hacs.json")
    if not isinstance(hacs, dict) or hacs.get("name") != "IrrigationOS":
        raise SystemExit("hacs.json must identify IrrigationOS")

    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
