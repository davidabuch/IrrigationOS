"""Tests for supervised first-live completion and acceptance evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers.models")
monitor = load_integration_module("first_live_delivery.monitor")


def _snapshot(state: Any) -> Any:
    area = controllers.IrrigationArea(
        area_id="controller-canonical:slot:2",
        controller_id="controller-canonical",
        slot_number=2,
        name="Zone 2",
        enabled=True,
        configured=True,
        state=state,
        binding=controllers.VendorBinding("rachio", "native-zone-secret"),
    )
    controller = controllers.IrrigationController(
        controller_id="controller-canonical",
        binding=controllers.VendorBinding("rachio", "native-device-secret"),
        name="Controller",
        availability=controllers.ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=2,
        watering_observation_quality=controllers.ObservationQuality.CONFIRMED,
        capabilities=controllers.ControllerCapabilities(),
        areas=(area,),
    )
    now = datetime.now(UTC)
    return controllers.ControllerRegistrySnapshot(
        provider="rachio",
        account_id="account",
        account_name=None,
        controllers=(controller,),
        observation=controllers.ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=1),
            source="rachio",
            quality=controllers.ObservationQuality.CONFIRMED,
        ),
    )


class _Coordinator:
    def __init__(self, states: list[Any]) -> None:
        self._states = states
        self.data = _snapshot(controllers.IrrigationAreaState.IDLE)

    async def async_request_refresh(self) -> None:
        self.data = _snapshot(self._states.pop(0))


class _Audit:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def async_record(self, event: Any) -> bool:
        self.events.append(event)
        return True


async def test_monitor_records_watering_then_terminal_acceptance(monkeypatch: Any) -> None:
    coordinator = _Coordinator(
        [controllers.IrrigationAreaState.WATERING, controllers.IrrigationAreaState.IDLE]
    )
    audit = _Audit()

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(monitor.asyncio, "sleep", _no_sleep)
    await monitor.async_monitor_first_live_acceptance(
        coordinator=coordinator,
        audit_sink=audit,
        attempt_id="first_live_attempt_test",
        controller_id="controller-canonical",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=60,
        dispatched_at=datetime.now(UTC),
    )
    assert [event.detail_code for event in audit.events] == [
        "target_watering_observed",
        "first_live_trial_accepted",
    ]
    assert {event.attempt_id for event in audit.events} == {"first_live_attempt_test"}
    serialized = repr([event.to_dict() for event in audit.events])
    assert "native-zone-secret" not in serialized
    assert "native-device-secret" not in serialized
