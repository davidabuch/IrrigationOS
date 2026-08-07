"""Compatibility contracts for the frozen v1.0 public APIs."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

from tests.helpers import load_integration_module

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "docs/V1_0_PUBLIC_API_CONTRACT.json").read_text())
MODULES = {
    name: load_integration_module(name)
    for name in (
        "plant_water_requirement",
        "plant_stress",
        "plant_health",
        "recommendations",
        "planning",
        "scheduling",
        "execution",
        "runtime_monitoring",
        "pipeline",
    )
}


def test_v1_public_api_contract_manifest_is_current() -> None:
    assert CONTRACT["contract_version"] == "1.0"
    assert CONTRACT["frozen_release"] == "1.0.13"
    assert set(CONTRACT["modules"]) == set(MODULES)


def test_v1_public_exports_are_exactly_frozen() -> None:
    for name, module in MODULES.items():
        expected = tuple(CONTRACT["modules"][name]["exports"])
        assert module.__all__ == expected
        assert all(hasattr(module, symbol) for symbol in expected)


def test_v1_schema_and_algorithm_versions_are_frozen() -> None:
    for name, module in MODULES.items():
        expected = CONTRACT["modules"][name]["versions"]
        actual = {symbol: getattr(module, symbol) for symbol in expected}
        assert actual == expected


def test_v1_enum_names_and_values_are_frozen() -> None:
    for name, module in MODULES.items():
        for symbol, expected in CONTRACT["modules"][name]["enums"].items():
            enum_type = getattr(module, symbol)
            assert isinstance(enum_type, type) and issubclass(enum_type, Enum)
            actual = [{"name": item.name, "value": item.value} for item in enum_type]
            assert actual == expected


def test_v1_dataclass_field_order_is_frozen() -> None:
    for name, module in MODULES.items():
        for symbol, expected in CONTRACT["modules"][name]["dataclasses"].items():
            model_type = getattr(module, symbol)
            assert isinstance(model_type, type) and is_dataclass(model_type)
            assert [field.name for field in fields(model_type)] == expected
