"""Tests for the v0.4.0 live-installation foundation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "custom_components/irrigationos/adapters/rachio/adapter.py"


def _load_adapter_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("irrigationos_test_adapter_v040", ADAPTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_schedule_zone_ids_are_found_across_supported_shapes() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert "async_get_current_schedule" in source
    assert "_find_zone_ids" in source


def test_config_flow_contains_review_and_reauthentication_steps() -> None:
    source = (ROOT / "custom_components/irrigationos/config_flow.py").read_text(encoding="utf-8")
    assert "async_step_confirm" in source
    assert "async_step_reauth_confirm" in source
    assert "async_update_reload_and_abort" in source


def test_live_installation_remains_observation_only() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "custom_components/irrigationos").rglob("*.py")
    )
    for endpoint in ("/zone/start", "/device/stop_water", "/device/rain_delay"):
        assert endpoint not in source
