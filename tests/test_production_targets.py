"""Tests for the shared authoritative production-target selector."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers")
targets = load_integration_module("production_targets")


def _snapshot() -> Any:
    now = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
    areas = tuple(
        controllers.IrrigationArea(
            area_id=f"controller:slot:{slot}",
            controller_id="controller",
            slot_number=slot,
            name=f"Zone {slot}",
            enabled=slot in {1, 2, 4, 5},
            configured=slot in {1, 2, 4, 5},
            state=(
                controllers.IrrigationAreaState.IDLE
                if slot in {1, 2, 4, 5}
                else controllers.IrrigationAreaState.UNUSED
            ),
            binding=(
                controllers.VendorBinding("rachio", f"private-{slot}")
                if slot in {1, 2, 4, 5}
                else None
            ),
        )
        for slot in range(1, 17)
    )
    controller = controllers.IrrigationController(
        controller_id="controller",
        binding=controllers.VendorBinding("rachio", "private-controller"),
        name="Controller",
        availability=controllers.ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=16,
        watering_observation_quality=controllers.ObservationQuality.CONFIRMED,
        capabilities=controllers.ControllerCapabilities(),
        areas=areas,
    )
    return controllers.ControllerRegistrySnapshot(
        provider="rachio",
        account_id="private-account",
        account_name=None,
        controllers=(controller,),
        observation=controllers.ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=5),
            source="polling",
            quality=controllers.ObservationQuality.CONFIRMED,
        ),
    )


def test_selector_is_authoritative_deterministic_and_excludes_unused_slots() -> None:
    snapshot = _snapshot()
    selected = targets.select_production_targets(snapshot)
    assert [target.to_dict() for target in selected] == [
        {"controller_slot": 1, "area_slot": slot} for slot in (1, 2, 4, 5)
    ]
    assert "private" not in repr(selected)

    controller = snapshot.controllers[0]
    disabled = replace(controller.areas[0], enabled=False)
    changed = replace(
        snapshot,
        controllers=(replace(controller, areas=(disabled, *controller.areas[1:])),),
    )
    assert [target.area_slot for target in targets.select_production_targets(changed)] == [
        2,
        4,
        5,
    ]
