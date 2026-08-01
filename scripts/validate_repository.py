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
    "custom_components/irrigationos/manifest.json",
    "custom_components/irrigationos/strings.json",
    "custom_components/irrigationos/translations/en.json",
    "docs/IRRIGATIONOS_ARCHITECTURE_V1.md",
    "hacs.json",
    "pyproject.toml",
    "requirements-dev.txt",
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
    if not manifest.get("version"):
        raise SystemExit("manifest.json must include a version")

    hacs = load_json("hacs.json")
    if not isinstance(hacs, dict) or hacs.get("name") != "IrrigationOS":
        raise SystemExit("hacs.json must identify IrrigationOS")

    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
