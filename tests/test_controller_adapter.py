"""Contract tests for the controller abstraction and Rachio adapter."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS = ROOT / "custom_components" / "irrigationos" / "controllers"
RACHIO_ADAPTER = ROOT / "custom_components" / "irrigationos" / "adapters" / "rachio" / "adapter.py"


def test_controller_contract_files_parse() -> None:
    for path in (*CONTROLLERS.glob("*.py"), RACHIO_ADAPTER):
        ast.parse(path.read_text(encoding="utf-8"))


def test_controller_protocol_exposes_read_only_snapshot() -> None:
    source = (CONTROLLERS / "base.py").read_text(encoding="utf-8")
    assert "async_get_snapshot" in source
    assert "async_start" not in source
    assert "async_stop" not in source


def test_rachio_adapter_uses_irrigation_area_domain_language() -> None:
    source = RACHIO_ADAPTER.read_text(encoding="utf-8")
    assert "IrrigationArea" in source
    assert 'area_id=f"{PROVIDER}:{native_id}"' in source
    assert "supports_start_area=False" not in source
    assert "supports_start_area" not in source
