"""Tests for the bounded supervised operational watering boundary."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

from tests.helpers import load_integration_module

controller_models = load_integration_module("controllers.models")
acceptance = load_integration_module("first_live_delivery.acceptance")
health = load_integration_module("health")
audit = load_integration_module("supervised_operation.audit")
supervised_manager = load_integration_module("supervised_operation.manager")
operator = load_integration_module("supervised_operation.operator")

ControllerAvailability = controller_models.ControllerAvailability
ControllerCapabilities = controller_models.ControllerCapabilities
ControllerRegistrySnapshot = controller_models.ControllerRegistrySnapshot
IrrigationArea = controller_models.IrrigationArea
IrrigationAreaState = controller_models.IrrigationAreaState
IrrigationController = controller_models.IrrigationController
ObservationMetadata = controller_models.ObservationMetadata
ObservationQuality = controller_models.ObservationQuality
VendorBinding = controller_models.VendorBinding
FirstLiveAcceptanceStatus = acceptance.FirstLiveAcceptanceStatus
IrrigationOSHealthState = health.IrrigationOSHealthState
SupervisedOperationManager = supervised_manager.SupervisedOperationManager
JsonlSupervisedOperationAuditSink = audit.JsonlSupervisedOperationAuditSink
build_audit_event = audit.build_audit_event
new_operation_id = audit.new_operation_id
SUPERVISED_OPERATION_CONFIRMATION = operator.SUPERVISED_OPERATION_CONFIRMATION
evaluate_supervised_operation_blockers = operator.evaluate_supervised_operation_blockers
SupervisedOperationStatus = operator.SupervisedOperationStatus


class _ManualAdapter:
    def __init__(self) -> None:
        self.start_calls: list[tuple[object, int]] = []
        self.stop_calls: list[object] = []

    async def async_start_manual_watering(
        self, *, area_binding: object, duration_seconds: int
    ) -> None:
        self.start_calls.append((area_binding, duration_seconds))

    async def async_stop_manual_watering(self, *, controller_binding: object) -> None:
        self.stop_calls.append(controller_binding)


class _LatestAcceptance:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def async_record(self, record: Any) -> bool:
        self.records.append(record)
        return True


class _ValidatedTargets:
    def __init__(self, targets: set[tuple[int, int]] | None = None) -> None:
        self.targets = {(1, 2)} if targets is None else targets

    def contains(self, controller_slot: int, area_slot: int) -> bool:
        return (controller_slot, area_slot) in self.targets

    def revoke(self, controller_slot: int, area_slot: int) -> None:
        self.targets.discard((controller_slot, area_slot))


class _Hass:
    def __init__(self, root: Path) -> None:
        self.config = SimpleNamespace(path=lambda *parts: str(root.joinpath(*parts)))
        self.created_tasks: list[Any] = []


class _Entry:
    def __init__(self, hass: _Hass) -> None:
        self.data = {"api_key": "secret"}
        self._hass = hass

    def async_create_background_task(
        self, hass: _Hass, coroutine: Any, name: str
    ) -> None:
        assert hass is self._hass
        assert name
        hass.created_tasks.append(coroutine)


class _DispatchCoordinator(SimpleNamespace):
    async def async_request_refresh(self) -> None:
        return None

    def async_update_listeners(self) -> None:
        self.listener_updates += 1

    def update_production_readiness(self, _evaluated_at: datetime | None = None) -> None:
        return None


def _dispatch_coordinator(tmp_path: Path, monkeypatch: Any) -> Any:
    base = _coordinator()
    coordinator = _DispatchCoordinator(**base.__dict__)
    coordinator.hass = _Hass(tmp_path)
    coordinator.entry = _Entry(coordinator.hass)
    coordinator.last_update_success = True
    coordinator.listener_updates = 0
    coordinator.supervised_operation_acceptance = _LatestAcceptance()

    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.__dict__["async_get_clientsession"] = lambda _hass: object()
    monkeypatch.setitem(sys.modules, "homeassistant", ModuleType("homeassistant"))
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", ModuleType("homeassistant.helpers"))
    monkeypatch.setitem(
        sys.modules, "homeassistant.helpers.aiohttp_client", aiohttp_client
    )
    return coordinator


def _with_area_state(
    snapshot: Any,
    *,
    area_slot: int,
    state: Any,
) -> Any:
    controller = snapshot.controllers[0]
    areas = tuple(
        replace(area, state=state) if area.slot_number == area_slot else area
        for area in controller.areas
    )
    now = datetime.now(UTC)
    return replace(
        snapshot,
        controllers=(replace(controller, areas=areas),),
        observation=replace(
            snapshot.observation,
            observed_at=now,
            fresh_until=now + timedelta(minutes=5),
            quality=ObservationQuality.CONFIRMED,
        ),
    )


async def _no_sleep(_seconds: float) -> None:
    return None


def test_operator_module_import_does_not_require_home_assistant() -> None:
    """Keep pure safety-gate tests runnable without Home Assistant installed."""

    script = """
import builtins

original_import = builtins.__import__

def import_without_home_assistant(name, *args, **kwargs):
    if name == "homeassistant" or name.startswith("homeassistant."):
        raise ModuleNotFoundError("Home Assistant intentionally unavailable")
    return original_import(name, *args, **kwargs)

builtins.__import__ = import_without_home_assistant
from tests.helpers import load_integration_module
load_integration_module("supervised_operation.operator")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _coordinator(*, accepted_slot: int = 2, active_sessions: tuple[object, ...] = ()) -> Any:
    now = datetime.now(UTC)
    areas = tuple(
        IrrigationArea(
            area_id=f"canonical-area-{slot}",
            controller_id="canonical-controller-1",
            slot_number=slot,
            name=f"Area {slot}",
            enabled=True,
            configured=True,
            state=IrrigationAreaState.IDLE,
            binding=VendorBinding(
                provider="rachio",
                native_id=("native-zone-secret" if slot == 2 else "native-zone-one"),
            ),
            vendor_name=f"Zone {slot}",
        )
        for slot in (1, 2)
    )
    controller = IrrigationController(
        controller_id="canonical-controller-1",
        binding=VendorBinding(provider="rachio", native_id="native-controller-secret"),
        name="Controller",
        availability=ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=16,
        watering_observation_quality=ObservationQuality.CONFIRMED,
        capabilities=ControllerCapabilities(observe_current_watering=True),
        areas=areas,
    )
    snapshot = ControllerRegistrySnapshot(
        provider="rachio",
        account_id="account",
        account_name=None,
        controllers=(controller,),
        observation=ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=5),
            source="polling",
            quality=ObservationQuality.CONFIRMED,
        ),
    )
    return SimpleNamespace(
        data=snapshot,
        health_assessment=SimpleNamespace(state=IrrigationOSHealthState.HEALTHY),
        ownership_commissioning=SimpleNamespace(
            summary=SimpleNamespace(
                ownership_confirmed=True,
                boundary_review_acknowledged=True,
            )
        ),
        observation_history=SimpleNamespace(active_sessions=active_sessions),
        live_commissioning=SimpleNamespace(
            summary=SimpleNamespace(supervised_safety_prerequisites_met=True)
        ),
        first_live_acceptance=SimpleNamespace(
            status=FirstLiveAcceptanceStatus.PASS,
            latest=SimpleNamespace(controller_slot=1, area_slot=accepted_slot),
            last_persistence_error=None,
        ),
        supervised_operation=SupervisedOperationManager(),
        adapter=_ManualAdapter(),
        validated_targets=_ValidatedTargets(),
    )


def _blockers(coordinator: Any, **overrides: object) -> tuple[str, ...]:
    values: dict[str, object] = {
        "controller_slot": 1,
        "area_slot": 2,
        "runtime_seconds": 30,
        "confirmation": SUPERVISED_OPERATION_CONFIRMATION,
    }
    values.update(overrides)
    return evaluate_supervised_operation_blockers(coordinator, **values)


def test_supervised_operation_happy_path_has_no_blockers() -> None:
    assert _blockers(_coordinator()) == ()


def test_supervised_operation_requires_exact_confirmation() -> None:
    blockers = _blockers(_coordinator(), confirmation="RUN SOMETHING ELSE")
    assert "operator_confirmation_mismatch" in blockers


def test_supervised_operation_requires_validated_target_evidence() -> None:
    coordinator = _coordinator()
    coordinator.validated_targets = _ValidatedTargets(set())
    blockers = _blockers(coordinator)
    assert "target_not_validated" in blockers


def test_operational_eligibility_does_not_follow_latest_first_live_target() -> None:
    coordinator = _coordinator(accepted_slot=1)
    coordinator.validated_targets = _ValidatedTargets({(1, 1), (1, 2)})
    assert _blockers(coordinator) == ()


def test_multiple_validated_targets_remain_independently_eligible() -> None:
    coordinator = _coordinator()
    coordinator.validated_targets = _ValidatedTargets({(1, 1), (1, 2)})
    assert _blockers(coordinator, area_slot=1) == ()
    assert _blockers(coordinator, area_slot=2) == ()
    assert "target_not_validated" in _blockers(coordinator, area_slot=3)


def test_revocation_removes_only_revoked_target_eligibility() -> None:
    coordinator = _coordinator()
    registry = _ValidatedTargets({(1, 1), (1, 2)})
    coordinator.validated_targets = registry
    registry.revoke(1, 1)
    assert "target_not_validated" in _blockers(coordinator, area_slot=1)
    assert _blockers(coordinator, area_slot=2) == ()


def test_supervised_operation_requires_current_integrated_safety() -> None:
    coordinator = _coordinator()
    coordinator.live_commissioning.summary.supervised_safety_prerequisites_met = False
    blockers = _blockers(coordinator)
    assert "supervised_safety_prerequisites_not_met" in blockers


def test_supervised_operation_blocks_existing_watering() -> None:
    blockers = _blockers(_coordinator(active_sessions=(object(),)))
    assert "active_watering_conflict" in blockers


def test_supervised_operation_blocks_an_in_progress_unattended_canary() -> None:
    coordinator = _coordinator()
    coordinator.unattended_canary = SimpleNamespace(in_progress=True)
    assert "unattended_canary_in_progress" in _blockers(coordinator)


def test_supervised_operation_manager_exposes_and_clears_safe_state() -> None:
    manager = SupervisedOperationManager()
    manager.mark_dispatched(
        "supervised_operation_test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    assert manager.diagnostics() == {
        "in_progress": True,
        "active_operation_id": "supervised_operation_test",
        "controller_slot": 1,
        "area_slot": 2,
        "requested_runtime_seconds": 30,
    }
    manager.mark_complete("supervised_operation_test")
    assert manager.in_progress is False
    assert manager.active_operation_id is None
    assert manager.active_controller_slot is None
    assert manager.active_area_slot is None
    assert manager.active_runtime_seconds is None


def test_new_supervised_operation_manager_never_restores_in_progress() -> None:
    previous = SupervisedOperationManager()
    previous.mark_dispatched(
        "supervised_operation_before_restart",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    restarted = SupervisedOperationManager()
    assert previous.in_progress is True
    assert restarted.in_progress is False


async def test_confirmed_manual_stop_cancels_owned_monitor_task() -> None:
    manager = SupervisedOperationManager()
    manager.mark_dispatched(
        "manual-stop-task",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=900,
    )

    async def _monitor() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(_monitor())
    manager.attach_monitor("manual-stop-task", task)
    await manager.async_cancel_monitor("manual-stop-task")
    assert task.done()
    assert manager.in_progress is False


async def test_supervised_operation_audit_is_privacy_safe(tmp_path: Path) -> None:
    path = tmp_path / "supervised_operation_audit.jsonl"
    operation_id = new_operation_id()
    sink = JsonlSupervisedOperationAuditSink(path)
    event = build_audit_event(
        operation_id=operation_id,
        event_type="dispatch_intent",
        recorded_at=datetime.now(UTC),
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        detail_code="supervised_operational_start",
    )
    assert await sink.async_record(event) is True
    content = path.read_text(encoding="utf-8")
    assert operation_id in content
    assert "native-zone-secret" not in content
    assert "native-controller-secret" not in content


async def test_successful_dispatch_sets_coordinator_owned_in_progress_state(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)

    result = await operator.async_run_supervised_operation(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        confirmation=SUPERVISED_OPERATION_CONFIRMATION,
    )

    assert result.status is SupervisedOperationStatus.START_DISPATCHED
    assert coordinator.supervised_operation.in_progress is True
    assert coordinator.supervised_operation.active_controller_slot == 1
    assert coordinator.supervised_operation.active_area_slot == 2
    assert coordinator.supervised_operation.active_runtime_seconds == 30
    assert coordinator.listener_updates == 1
    assert coordinator.adapter.start_calls[0][1] == 30
    assert len(coordinator.hass.created_tasks) == 1
    coordinator.hass.created_tasks[0].close()


async def test_transport_failure_records_fail_and_clears_in_progress(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)

    async def _fail_start(*, area_binding: object, duration_seconds: int) -> None:
        raise operator.ControllerProviderError("ambiguous transport failure")

    coordinator.adapter.async_start_manual_watering = _fail_start
    result = await operator.async_run_supervised_operation(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        confirmation=SUPERVISED_OPERATION_CONFIRMATION,
    )

    assert result.status is SupervisedOperationStatus.TRANSPORT_FAILED
    assert coordinator.supervised_operation.in_progress is False
    assert coordinator.listener_updates == 1
    assert len(coordinator.supervised_operation_acceptance.records) == 1
    assert (
        coordinator.supervised_operation_acceptance.records[0].status
        is FirstLiveAcceptanceStatus.FAIL
    )
    assert coordinator.hass.created_tasks == []


def test_manual_runtime_ceiling_accepts_three_hours_and_rejects_more() -> None:
    coordinator = _coordinator()
    assert _blockers(coordinator, runtime_seconds=10_800) == ()
    assert "runtime_out_of_range" in _blockers(
        coordinator, runtime_seconds=10_801
    )


async def test_valve_operator_intent_does_not_require_text_confirmation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    result = await operator.async_run_manual_operation(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=900,
    )
    assert result.status is SupervisedOperationStatus.START_DISPATCHED
    assert coordinator.adapter.start_calls[0][1] == 900
    coordinator.hass.created_tasks[0].close()


async def test_manual_runtime_above_three_hours_never_dispatches(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    result = await operator.async_run_manual_operation(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=10_801,
    )
    assert result.status is SupervisedOperationStatus.BLOCKED
    assert result.blocker_codes == ("runtime_out_of_range",)
    assert coordinator.adapter.start_calls == []


async def test_manual_stop_uses_controller_wide_adapter_and_clears_transient_state(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    coordinator.supervised_operation.mark_dispatched(
        "manual-stop-test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=900,
    )
    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=2
    )
    assert result.status is SupervisedOperationStatus.STOP_DISPATCHED
    assert len(coordinator.adapter.stop_calls) == 1
    assert coordinator.supervised_operation.in_progress is False


async def test_manual_stop_waits_for_delayed_confirmed_idle_without_transport_retry(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    coordinator.data = _with_area_state(
        coordinator.data,
        area_slot=2,
        state=IrrigationAreaState.WATERING,
    )
    coordinator.supervised_operation.mark_dispatched(
        "manual-stop-delayed",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=180,
    )
    refresh_count = 0

    async def _refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1
        state = (
            IrrigationAreaState.WATERING
            if refresh_count < 3
            else IrrigationAreaState.IDLE
        )
        coordinator.data = _with_area_state(
            coordinator.data,
            area_slot=2,
            state=state,
        )

    coordinator.async_request_refresh = _refresh
    monkeypatch.setattr(operator.asyncio, "sleep", _no_sleep)

    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=2
    )

    assert result.status is SupervisedOperationStatus.STOP_DISPATCHED
    assert refresh_count == 3
    assert len(coordinator.adapter.stop_calls) == 1
    assert coordinator.supervised_operation.in_progress is False
    audit_path = tmp_path / "irrigationos_logs" / "supervised_operation_audit.jsonl"
    audit_content = audit_path.read_text(encoding="utf-8")
    assert audit_content.count('"event_type":"stop_intent"') == 1
    assert audit_content.count('"event_type":"stop_transport_outcome"') == 1


async def test_manual_stop_timeout_preserves_active_monitor_without_transport_retry(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    coordinator.data = _with_area_state(
        coordinator.data,
        area_slot=2,
        state=IrrigationAreaState.WATERING,
    )
    coordinator.supervised_operation.mark_dispatched(
        "manual-stop-unconfirmed",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=180,
    )

    async def _monitor() -> None:
        await asyncio.Event().wait()

    monitor_task = asyncio.create_task(_monitor())
    coordinator.supervised_operation.attach_monitor(
        "manual-stop-unconfirmed", monitor_task
    )
    refresh_count = 0

    async def _refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1
        coordinator.data = _with_area_state(
            coordinator.data,
            area_slot=2,
            state=IrrigationAreaState.WATERING,
        )

    coordinator.async_request_refresh = _refresh
    monkeypatch.setattr(operator.asyncio, "sleep", _no_sleep)

    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=2
    )

    assert result.status is SupervisedOperationStatus.STOP_UNCONFIRMED
    assert result.blocker_codes == ("stop_outcome_not_observed",)
    assert refresh_count == 11
    assert len(coordinator.adapter.stop_calls) == 1
    assert coordinator.supervised_operation.in_progress is True
    assert monitor_task.done() is False
    await coordinator.supervised_operation.async_cancel_monitor(
        "manual-stop-unconfirmed"
    )


async def test_manual_stop_tolerates_refresh_failure_before_confirmed_idle(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    coordinator.data = _with_area_state(
        coordinator.data,
        area_slot=2,
        state=IrrigationAreaState.WATERING,
    )
    coordinator.supervised_operation.mark_dispatched(
        "manual-stop-refresh-failure",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=180,
    )
    refresh_count = 0

    async def _refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1
        if refresh_count == 1:
            raise RuntimeError("temporary refresh failure")
        coordinator.data = _with_area_state(
            coordinator.data,
            area_slot=2,
            state=IrrigationAreaState.IDLE,
        )

    coordinator.async_request_refresh = _refresh
    monkeypatch.setattr(operator.asyncio, "sleep", _no_sleep)

    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=2
    )

    assert result.status is SupervisedOperationStatus.STOP_DISPATCHED
    assert refresh_count == 2
    assert len(coordinator.adapter.stop_calls) == 1


async def test_manual_stop_already_inactive_never_dispatches_transport(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)

    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=2
    )

    assert result.status is SupervisedOperationStatus.BLOCKED
    assert result.blocker_codes == ("manual_watering_not_active",)
    assert coordinator.adapter.stop_calls == []


async def test_manual_stop_wrong_zone_fails_closed_without_transport(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    coordinator.supervised_operation.mark_dispatched(
        "manual-stop-test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=900,
    )
    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=1
    )
    assert result.status is SupervisedOperationStatus.BLOCKED
    assert "manual_stop_target_mismatch" in result.blocker_codes
    assert coordinator.adapter.stop_calls == []


async def test_manual_stop_transport_uncertainty_has_no_retry(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)
    coordinator.supervised_operation.mark_dispatched(
        "manual-stop-test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=900,
    )
    calls = 0

    async def _fail_stop(*, controller_binding: object) -> None:
        nonlocal calls
        del controller_binding
        calls += 1
        raise operator.ControllerProviderError("ambiguous stop failure")

    coordinator.adapter.async_stop_manual_watering = _fail_stop
    result = await operator.async_stop_manual_operation(
        coordinator, controller_slot=1, area_slot=2
    )
    assert result.status is SupervisedOperationStatus.TRANSPORT_FAILED
    assert result.blocker_codes == ("stop_transport_failed_no_retry",)
    assert calls == 1
    assert coordinator.supervised_operation.in_progress is True


async def test_audit_failure_persists_fail_without_setting_in_progress(
    tmp_path: Path, monkeypatch: Any
) -> None:
    coordinator = _dispatch_coordinator(tmp_path, monkeypatch)

    class _FailingAudit:
        def __init__(self, _path: Path) -> None:
            return None

        async def async_record(self, _event: Any) -> bool:
            return False

    monkeypatch.setattr(operator, "JsonlSupervisedOperationAuditSink", _FailingAudit)
    result = await operator.async_run_supervised_operation(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        confirmation=SUPERVISED_OPERATION_CONFIRMATION,
    )

    assert result.status is SupervisedOperationStatus.AUDIT_FAILED
    assert coordinator.supervised_operation.in_progress is False
    assert coordinator.listener_updates == 1
    assert len(coordinator.supervised_operation_acceptance.records) == 1
    assert (
        coordinator.supervised_operation_acceptance.records[0].status
        is FirstLiveAcceptanceStatus.FAIL
    )
    assert coordinator.hass.created_tasks == []
