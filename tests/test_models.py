"""Tests for controller-agnostic IrrigationOS domain models."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "irrigationos"
    / "controllers"
    / "models.py"
)
SPEC = importlib.util.spec_from_file_location("irrigationos_controller_models", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

ControllerAvailability = MODULE.ControllerAvailability
ControllerCapabilities = MODULE.ControllerCapabilities
ControllerRegistrySnapshot = MODULE.ControllerRegistrySnapshot
IrrigationArea = MODULE.IrrigationArea
IrrigationAreaState = MODULE.IrrigationAreaState
IrrigationController = MODULE.IrrigationController


def test_registry_snapshot_flattens_irrigation_areas() -> None:
    area = IrrigationArea(
        area_id="rachio:zone-1",
        controller_id="rachio:controller-1",
        native_id="zone-1",
        name="Avocado Tree",
        enabled=True,
        state=IrrigationAreaState.IDLE,
    )
    controller = IrrigationController(
        controller_id="rachio:controller-1",
        native_id="controller-1",
        provider="rachio",
        name="Home",
        availability=ControllerAvailability.ONLINE,
        enabled=True,
        model="GENERATION3_8ZONE",
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capabilities=ControllerCapabilities(observe_last_watered=True),
        areas=(area,),
    )
    snapshot = ControllerRegistrySnapshot(
        provider="rachio",
        account_id="person-1",
        account_name="Test User",
        controllers=(controller,),
    )
    assert snapshot.areas == (area,)
    assert snapshot.controllers[0].capabilities.supports_start_area is False


def test_controller_state_vocabularies_are_stable() -> None:
    assert ControllerAvailability.ONLINE.value == "online"
    assert IrrigationAreaState.WATERING.value == "watering"
    assert IrrigationAreaState.DISABLED.value == "disabled"
