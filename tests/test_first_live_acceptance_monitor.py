"""Tests for supervised first-live completion and acceptance evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers.models")
monitor = load_integration_module("first_live_delivery.monitor")
acceptance = load_integration_module("first_live_delivery.acceptance")


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

    def async_update_listeners(self) -> None:
        return None


class _Audit:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def async_record(self, event: Any) -> bool:
        self.events.append(event)
        return True


class _Acceptance:
    def __init__(self, *, succeeds: bool = True) -> None:
        self.records: list[Any] = []
        self.succeeds = succeeds

    async def async_record(self, record: Any) -> bool:
        self.records.append(record)
        return self.succeeds


class _ValidatedTargets:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def async_register(self, record: Any) -> bool:
        self.records.append(record)
        return True


async def test_monitor_records_watering_then_terminal_acceptance(monkeypatch: Any) -> None:
    coordinator = _Coordinator(
        [controllers.IrrigationAreaState.WATERING, controllers.IrrigationAreaState.IDLE]
    )
    audit = _Audit()
    acceptance_sink = _Acceptance()
    validated_targets = _ValidatedTargets()

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(monitor.asyncio, "sleep", _no_sleep)
    await monitor.async_monitor_first_live_acceptance(
        coordinator=coordinator,
        audit_sink=audit,
        acceptance=acceptance_sink,
        validated_targets=validated_targets,
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
    assert len(acceptance_sink.records) == 1
    record = acceptance_sink.records[0]
    assert record.status is acceptance.FirstLiveAcceptanceStatus.PASS
    assert record.observed_runtime_seconds is not None
    assert all(criterion.status.value == "pass" for criterion in record.criteria)
    assert validated_targets.records == [record]
    serialized = repr([event.to_dict() for event in audit.events])
    assert "native-zone-secret" not in serialized
    assert "native-device-secret" not in serialized


async def test_pass_not_registered_when_acceptance_persistence_fails() -> None:
    coordinator = _Coordinator([])
    acceptance_sink = _Acceptance(succeeds=False)
    validated_targets = _ValidatedTargets()
    now = datetime.now(UTC)
    await monitor._record_terminal(
        coordinator=coordinator,
        acceptance=acceptance_sink,
        validated_targets=validated_targets,
        audit_sink=_Audit(),
        attempt_id="first_live_pass_not_durable",
        controller_id="controller-canonical",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        observed_watering_at=now,
        observed_idle_at=now + timedelta(seconds=30),
        refresh_error_count=0,
        concurrent_watering_observed=False,
        detail_code="first_live_trial_accepted",
    )
    assert acceptance_sink.records[0].status.value == "pass"
    assert validated_targets.records == []


async def test_fail_and_indeterminate_never_register_targets() -> None:
    for observed_watering_at, observed_idle_at, concurrent in (
        (None, None, False),
        (datetime.now(UTC), None, False),
    ):
        validated_targets = _ValidatedTargets()
        acceptance_sink = _Acceptance()
        await monitor._record_terminal(
            coordinator=_Coordinator([]),
            acceptance=acceptance_sink,
            validated_targets=validated_targets,
            audit_sink=_Audit(),
            attempt_id="first_live_nonpass",
            controller_id="controller-canonical",
            controller_slot=1,
            area_slot=2,
            runtime_seconds=30,
            observed_watering_at=observed_watering_at,
            observed_idle_at=observed_idle_at,
            refresh_error_count=0,
            concurrent_watering_observed=concurrent,
            detail_code="first_live_not_accepted",
        )
        assert acceptance_sink.records[0].status.value != "pass"
        assert validated_targets.records == []
