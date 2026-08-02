"""Load integration submodules without requiring a Home Assistant installation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_integration_module(relative_name: str) -> ModuleType:
    """Import a pure integration module without executing its HA entry point."""
    packages = {
        "custom_components": ROOT / "custom_components",
        "custom_components.irrigationos": ROOT / "custom_components" / "irrigationos",
        "custom_components.irrigationos.adapters": (
            ROOT / "custom_components" / "irrigationos" / "adapters"
        ),
    }
    for name, path in packages.items():
        if name in sys.modules:
            continue
        package = ModuleType(name)
        package.__path__ = [str(path)]
        package.__package__ = name
        sys.modules[name] = package
    return importlib.import_module(f"custom_components.irrigationos.{relative_name}")
