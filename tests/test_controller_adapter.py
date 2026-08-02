"""Behavioral tests for canonical identity and Rachio normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from tests.helpers import load_integration_module

CONTROLLERS = load_integration_module("controllers")
ADAPTER = load_integration_module("adapters.rachio.adapter")
API = load_integration_module("adapters.rachio.api")

ControllerIdentityRegistry = CONTROLLERS.ControllerIdentityRegistry
IrrigationAreaState = CONTROLLERS.IrrigationAreaState
ObservationQuality = CONTROLLERS.ObservationQuality
RachioControllerAdapter = ADAPTER.RachioControllerAdapter
RachioApiError = API.RachioApiError


def _payload(*, controller_name: str = "Back Yard", zone_name: str = "Avocado") -> dict[str, Any]:
    return {
        "id": "person-1",
        "fullName": "Test User",
        "devices": [
            {
                "id": "device-1",
                "name": controller_name,
                "status": "ONLINE",
                "on": True,
                "model": "GENERATION3_8ZONE",
                "zones": [
                    {
                        "id": "zone-native-1",
                        "zoneNumber": 1,
                        "name": zone_name,
                        "enabled": True,
                    }
                ],
            }
        ],
    }


def test_identity_is_stable_across_controller_and_landscape_name_changes() -> None:
    identities = ControllerIdentityRegistry()
    first = RachioControllerAdapter.from_person_payload(_payload(), identities)
    renamed = RachioControllerAdapter.from_person_payload(
        _payload(controller_name="Renamed", zone_name="Citrus Trees"), identities
    )

    assert first.controllers[0].controller_id == renamed.controllers[0].controller_id
    assert first.areas[0].area_id == renamed.areas[0].area_id
    assert first.areas[0].name == renamed.areas[0].name == "Zone 1"
    assert renamed.areas[0].vendor_name == "Citrus Trees"
    assert "device-1" not in first.controllers[0].controller_id
    assert "zone-native-1" not in first.areas[0].area_id


def test_capacity_creates_permanent_unused_slot_placeholders() -> None:
    snapshot = RachioControllerAdapter.from_person_payload(
        _payload(), ControllerIdentityRegistry()
    )
    controller = snapshot.controllers[0]

    assert controller.capacity == 8
    assert len(controller.areas) == 8
    assert controller.areas[0].configured is True
    assert controller.areas[0].name == "Zone 1"
    assert controller.areas[1].configured is False
    assert controller.areas[1].state is IrrigationAreaState.UNUSED
    assert controller.areas[1].name == "Zone 2"
    assert controller.areas[1].binding is None


class FakeClient:
    """Return one account payload and endpoint-specific watering outcomes."""

    def __init__(self, payload: dict[str, Any], current_schedule: object) -> None:
        self.payload = payload
        self.current_schedule = current_schedule

    async def async_get_person(self, account_id: str) -> dict[str, Any]:
        assert account_id == "person-1"
        return self.payload

    async def async_get_current_schedule(self, device_id: str) -> dict[str, Any]:
        assert device_id == "device-1"
        if isinstance(self.current_schedule, Exception):
            raise self.current_schedule
        assert isinstance(self.current_schedule, dict)
        return self.current_schedule


@pytest.mark.asyncio
async def test_confirmed_idle_is_distinct_from_unavailable_watering_status() -> None:
    identities = ControllerIdentityRegistry()
    idle = await RachioControllerAdapter(
        FakeClient(_payload(), {}), identities
    ).async_get_snapshot("person-1")
    unavailable = await RachioControllerAdapter(
        FakeClient(_payload(), RachioApiError("secondary endpoint unavailable")), identities
    ).async_get_snapshot("person-1")

    assert idle.areas[0].state is IrrigationAreaState.IDLE
    assert idle.observation.quality is ObservationQuality.CONFIRMED
    assert idle.observation.errors == ()
    assert unavailable.areas[0].state is IrrigationAreaState.UNKNOWN
    assert unavailable.controllers[0].watering_observation_quality is (
        ObservationQuality.UNAVAILABLE
    )
    assert unavailable.observation.quality is ObservationQuality.PARTIAL
    assert unavailable.observation.errors[0].endpoint == "current_schedule"
    assert unavailable.observation.observed_at.tzinfo is UTC
    assert unavailable.observation.fresh_until > datetime.now(UTC)
