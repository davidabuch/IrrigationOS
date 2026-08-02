"""Tests for controller-agnostic IrrigationOS domain models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.helpers import load_integration_module

MODULE = load_integration_module("controllers.models")

ControllerAvailability = MODULE.ControllerAvailability
ControllerCapabilities = MODULE.ControllerCapabilities
ControllerRegistrySnapshot = MODULE.ControllerRegistrySnapshot
IrrigationArea = MODULE.IrrigationArea
IrrigationAreaState = MODULE.IrrigationAreaState
IrrigationController = MODULE.IrrigationController
ObservationMetadata = MODULE.ObservationMetadata
ObservationQuality = MODULE.ObservationQuality
VendorBinding = MODULE.VendorBinding


def test_registry_snapshot_flattens_irrigation_areas() -> None:
    area = IrrigationArea(
        area_id="controller_1:slot:1",
        controller_id="controller_1",
        slot_number=1,
        name="Zone 1",
        enabled=True,
        configured=True,
        state=IrrigationAreaState.IDLE,
        binding=VendorBinding("rachio", "zone-1"),
    )
    controller = IrrigationController(
        controller_id="controller_1",
        binding=VendorBinding("rachio", "controller-1"),
        name="Home",
        availability=ControllerAvailability.ONLINE,
        enabled=True,
        model="GENERATION3_8ZONE",
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=1,
        watering_observation_quality=ObservationQuality.CONFIRMED,
        capabilities=ControllerCapabilities(observe_last_watered=True),
        areas=(area,),
    )
    now = datetime.now(UTC)
    snapshot = ControllerRegistrySnapshot(
        provider="rachio",
        account_id="person-1",
        account_name="Test User",
        controllers=(controller,),
        observation=ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=10),
            source="rachio",
            quality=ObservationQuality.CONFIRMED,
        ),
    )
    assert snapshot.areas == (area,)
    assert snapshot.controllers[0].capabilities.supports_start_area is False


def test_controller_state_vocabularies_are_stable() -> None:
    assert ControllerAvailability.ONLINE.value == "online"
    assert IrrigationAreaState.WATERING.value == "watering"
    assert IrrigationAreaState.DISABLED.value == "disabled"
