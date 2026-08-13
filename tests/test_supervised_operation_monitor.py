"""Tests for supervised operational terminal persistence and state clearing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers.models")
acceptance = load_integration_module("first_live_delivery.acceptance")
manager_module = load_integration_module("supervised_operation.manager")
monitor = load_integration_module("supervised_operation.monitor")

SupervisedOperationManager = manager_module.SupervisedOperationManager


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
        self.listener_updates = 0

    async def async_request_refresh(self) -> None:
        self.data = _snapshot(self._states.pop(0))

    def async_update_listeners(self) -> None:
        self.listener_updates += 1

    def update_production_readiness(self, _evaluated_at: datetime | None = None) -> None:
        return None


class _Recorder:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def async_record(self, record: Any) -> bool:
        self.records.append(record)
        return True


async def test_terminal_pass_updates_both_records_and_clears_in_progress(
    monkeypatch: Any,
) -> None:
    coordinator = _Coordinator(
        [controllers.IrrigationAreaState.WATERING, controllers.IrrigationAreaState.IDLE]
    )
    manager = SupervisedOperationManager()
    manager.mark_dispatched(
        "supervised_operation_test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    audit = _Recorder()
    history = _Recorder()
    latest = _Recorder()

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(monitor.asyncio, "sleep", _no_sleep)
    await monitor.async_monitor_supervised_operation(
        coordinator=coordinator,
        manager=manager,
        audit_sink=audit,
        acceptance_sink=history,
        acceptance=latest,
        operation_id="supervised_operation_test",
        controller_id="controller-canonical",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        dispatched_at=datetime.now(UTC),
    )

    assert len(history.records) == 1
    assert latest.records == history.records
    assert history.records[0].status is acceptance.FirstLiveAcceptanceStatus.PASS
    assert manager.in_progress is False
    assert coordinator.listener_updates == 1


async def test_start_timeout_records_fail_and_clears_in_progress() -> None:
    coordinator = _Coordinator([])
    manager = SupervisedOperationManager()
    manager.mark_dispatched(
        "supervised_operation_timeout",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    history = _Recorder()
    latest = _Recorder()

    await monitor.async_monitor_supervised_operation(
        coordinator=coordinator,
        manager=manager,
        audit_sink=_Recorder(),
        acceptance_sink=history,
        acceptance=latest,
        operation_id="supervised_operation_timeout",
        controller_id="controller-canonical",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        dispatched_at=datetime.now(UTC) - timedelta(minutes=2),
    )

    assert history.records[0].status is acceptance.FirstLiveAcceptanceStatus.FAIL
    assert latest.records == history.records
    assert manager.in_progress is False
    assert coordinator.listener_updates == 1


async def test_completion_timeout_records_indeterminate_and_clears_in_progress(
    monkeypatch: Any,
) -> None:
    dispatched_at = datetime.now(UTC)
    deadline = dispatched_at + timedelta(seconds=75)
    times = iter((dispatched_at, dispatched_at, deadline + timedelta(seconds=1)))

    class _Clock:
        @classmethod
        def now(cls, _timezone: object) -> datetime:
            return next(times, deadline + timedelta(seconds=1))

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(monitor, "datetime", _Clock)
    monkeypatch.setattr(monitor.asyncio, "sleep", _no_sleep)
    coordinator = _Coordinator([controllers.IrrigationAreaState.WATERING])
    manager = SupervisedOperationManager()
    manager.mark_dispatched(
        "supervised_operation_completion_timeout",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    history = _Recorder()
    latest = _Recorder()

    await monitor.async_monitor_supervised_operation(
        coordinator=coordinator,
        manager=manager,
        audit_sink=_Recorder(),
        acceptance_sink=history,
        acceptance=latest,
        operation_id="supervised_operation_completion_timeout",
        controller_id="controller-canonical",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        dispatched_at=dispatched_at,
    )

    assert history.records[0].status is acceptance.FirstLiveAcceptanceStatus.INDETERMINATE
    assert latest.records == history.records
    assert manager.in_progress is False
    assert coordinator.listener_updates == 1
