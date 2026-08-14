"""Tests for non-retrying unattended-canary terminal observation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers.models")
health = load_integration_module("health")
manager_module = load_integration_module("unattended_canary.manager")
monitor = load_integration_module("unattended_canary.monitor")


def _snapshot(state: Any) -> Any:
    now = datetime.now(UTC)
    area = controllers.IrrigationArea(
        area_id="canonical-area-2",
        controller_id="canonical-controller",
        slot_number=2,
        name="Zone 2",
        enabled=True,
        configured=True,
        state=state,
        binding=controllers.VendorBinding("rachio", "native-zone-secret"),
    )
    controller = controllers.IrrigationController(
        controller_id="canonical-controller",
        binding=controllers.VendorBinding("rachio", "native-controller-secret"),
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
        areas=(area,),
    )
    return controllers.ControllerRegistrySnapshot(
        provider="rachio",
        account_id="account",
        account_name=None,
        controllers=(controller,),
        observation=controllers.ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=1),
            source="polling",
            quality=controllers.ObservationQuality.CONFIRMED,
        ),
    )


class _Coordinator:
    def __init__(self, states: list[Any], *, fail_refresh: bool = False) -> None:
        self.states = states
        self.fail_refresh = fail_refresh
        self.refresh_count = 0
        self.data = _snapshot(controllers.IrrigationAreaState.IDLE)
        self.health_assessment = SimpleNamespace(
            state=health.IrrigationOSHealthState.HEALTHY
        )
        self.ownership_commissioning = SimpleNamespace(
            summary=SimpleNamespace(
                ownership_confirmed=True,
                boundary_review_acknowledged=True,
                topology_matches=True,
            )
        )
        self.live_commissioning = SimpleNamespace(
            summary=SimpleNamespace(supervised_safety_prerequisites_met=True)
        )
        self.execution_authorization = SimpleNamespace(
            summary=SimpleNamespace(
                gates={
                    "control_readiness_criteria_met": False,
                    "system_health_healthy": True,
                    "observation_fresh": True,
                    "controllers_fully_available": True,
                    "pipeline_available": True,
                    "controller_ownership_confirmed": True,
                    "execution_boundary_review_acknowledged": True,
                    "no_active_watering_conflict": False,
                    "candidate_runtime_within_limit": True,
                }
            )
        )
        self.live_mode_safety = SimpleNamespace(
            summary=SimpleNamespace(safeguard_gates={"all_safeguards": True})
        )
        self.integrated_safety_review = SimpleNamespace(
            summary=SimpleNamespace(validation_scenarios={"integrated": True})
        )
        self.listener_updates = 0

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1
        if self.fail_refresh:
            raise OSError("refresh failed")
        self.data = _snapshot(self.states.pop(0))

    def update_production_readiness(self, _now: datetime | None = None) -> None:
        return None

    def async_update_listeners(self) -> None:
        self.listener_updates += 1


class _Recorder:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def async_record(self, record: Any) -> bool:
        self.records.append(record)
        return True


async def _run_monitor(
    coordinator: _Coordinator,
    monkeypatch: Any,
    *,
    dispatched_at: datetime | None = None,
) -> tuple[Any, _Recorder, _Recorder, _Recorder]:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(monitor.asyncio, "sleep", _no_sleep)
    manager = manager_module.UnattendedCanaryManager()
    manager.mark_dispatched(
        "unattended_canary_test",
        "unattended_canary_approval_test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    audit = _Recorder()
    history = _Recorder()
    latest = _Recorder()
    await monitor.async_monitor_unattended_canary(
        coordinator=coordinator,
        manager=manager,
        audit_sink=audit,
        acceptance_sink=history,
        acceptance=latest,
        canary_id="unattended_canary_test",
        approval_id="unattended_canary_approval_test",
        controller_id="canonical-controller",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        dispatched_at=dispatched_at or datetime.now(UTC),
        audit_chain_complete=True,
    )
    return manager, audit, history, latest


async def test_pass_observes_watering_idle_and_clears_in_progress(
    monkeypatch: Any,
) -> None:
    coordinator = _Coordinator(
        [controllers.IrrigationAreaState.WATERING, controllers.IrrigationAreaState.IDLE]
    )
    manager, audit, history, latest = await _run_monitor(coordinator, monkeypatch)
    assert history.records[0].status.value == "pass"
    assert latest.records == history.records
    assert [event.event_type for event in audit.records] == [
        "target_watering_observed",
        "acceptance_terminal",
    ]
    assert manager.in_progress is False
    assert coordinator.listener_updates == 1


async def test_expected_canary_watering_does_not_self_trigger_preemption(
    monkeypatch: Any,
) -> None:
    coordinator = _Coordinator(
        [controllers.IrrigationAreaState.WATERING, controllers.IrrigationAreaState.IDLE]
    )
    coordinator.live_commissioning.summary.supervised_safety_prerequisites_met = False
    original_refresh = coordinator.async_request_refresh

    async def _refresh() -> None:
        await original_refresh()
        if coordinator.data.controllers[0].areas[0].state is controllers.IrrigationAreaState.IDLE:
            coordinator.live_commissioning.summary.supervised_safety_prerequisites_met = True

    coordinator.async_request_refresh = _refresh  # type: ignore[method-assign]
    manager, _audit, history, _latest = await _run_monitor(coordinator, monkeypatch)
    assert history.records[0].status.value == "pass"
    assert manager.in_progress is False


async def test_timeout_records_fail_and_clears(monkeypatch: Any) -> None:
    coordinator = _Coordinator([])
    manager, _audit, history, _latest = await _run_monitor(
        coordinator,
        monkeypatch,
        dispatched_at=datetime.now(UTC) - timedelta(minutes=2),
    )
    assert history.records[0].status.value == "fail"
    assert manager.in_progress is False


async def test_refresh_failure_is_terminal_without_retry(monkeypatch: Any) -> None:
    coordinator = _Coordinator([], fail_refresh=True)
    manager, _audit, history, _latest = await _run_monitor(coordinator, monkeypatch)
    assert coordinator.refresh_count == 1
    assert history.records[0].terminal_detail_code == "monitor_refresh_failed_no_retry"
    assert manager.in_progress is False


async def test_safety_preemption_records_fail_and_clears(monkeypatch: Any) -> None:
    coordinator = _Coordinator([controllers.IrrigationAreaState.WATERING])
    coordinator.health_assessment.state = health.IrrigationOSHealthState.UNHEALTHY
    manager, _audit, history, _latest = await _run_monitor(coordinator, monkeypatch)
    assert history.records[0].status.value == "fail"
    assert history.records[0].terminal_detail_code == "safety_preemption_observed"
    assert manager.in_progress is False
