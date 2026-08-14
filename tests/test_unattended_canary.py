"""Behavioral tests for explicit approval and one-shot canary execution."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers.models")
health = load_integration_module("health")
readiness = load_integration_module("production_readiness")
canary_models = load_integration_module("unattended_canary.models")
canary_manager = load_integration_module("unattended_canary.manager")
canary_audit = load_integration_module("unattended_canary.audit")
canary_monitor = load_integration_module("unattended_canary.monitor")
operator = load_integration_module("unattended_canary.operator")

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
TARGET = readiness.ProductionTarget(1, 2)


class _ValidatedTargets:
    def __init__(self, targets: set[tuple[int, int]] | None = None) -> None:
        self.targets = {(1, 2)} if targets is None else targets
        self.last_persistence_error: str | None = None

    def contains(self, controller_slot: int, area_slot: int) -> bool:
        return (controller_slot, area_slot) in self.targets


class _Recorder:
    def __init__(self, *, success: bool = True) -> None:
        self.records: list[Any] = []
        self.success = success

    async def async_record(self, record: Any) -> bool:
        self.records.append(record)
        return self.success


class _Hass:
    def __init__(self, root: Path) -> None:
        self.config = SimpleNamespace(path=lambda *parts: str(root.joinpath(*parts)))
        self.tasks: list[Any] = []


class _Entry:
    def __init__(self, hass: _Hass) -> None:
        self.data = {"api_key": "secret"}
        self._hass = hass

    def async_create_background_task(
        self, hass: _Hass, coroutine: Any, name: str
    ) -> None:
        assert hass is self._hass
        assert name
        hass.tasks.append(coroutine)


class _Coordinator(SimpleNamespace):
    async def async_request_refresh(self) -> None:
        self.refresh_count += 1
        if self.refresh_error is not None:
            raise self.refresh_error

    def async_update_listeners(self) -> None:
        self.listener_updates += 1

    def update_production_readiness(self, now: datetime | None = None) -> None:
        evaluated_at = now or datetime.now(UTC)
        approved = self.unattended_canary.valid_approval_for(
            now=evaluated_at,
            production_targets=self.production_targets,
            validated_targets=tuple(
                readiness.ProductionTarget(*target)
                for target in sorted(self.validated_targets.targets)
            ),
        )
        state = (
            readiness.ProductionReadinessState.READY_FOR_UNATTENDED_CANARY
            if approved and not self.unattended_canary.in_progress
            else readiness.ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
        )
        self.production_readiness.summary = SimpleNamespace(
            state=state,
            production_targets=self.production_targets,
        )


def _snapshot(
    *,
    state: Any = None,
    controller_online: bool = True,
    observation_fresh: bool = True,
) -> Any:
    area_state = state or controllers.IrrigationAreaState.IDLE
    now = datetime.now(UTC)
    area = controllers.IrrigationArea(
        area_id="canonical-area-2",
        controller_id="canonical-controller-1",
        slot_number=2,
        name="Zone 2",
        enabled=True,
        configured=True,
        state=area_state,
        binding=controllers.VendorBinding("rachio", "native-zone-secret"),
    )
    controller = controllers.IrrigationController(
        controller_id="canonical-controller-1",
        binding=controllers.VendorBinding("rachio", "native-controller-secret"),
        name="Controller",
        availability=(
            controllers.ControllerAvailability.ONLINE
            if controller_online
            else controllers.ControllerAvailability.OFFLINE
        ),
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
            fresh_until=now + timedelta(minutes=5 if observation_fresh else -1),
            source="polling",
            quality=controllers.ObservationQuality.CONFIRMED,
        ),
    )


def _coordinator(tmp_path: Path) -> Any:
    manager = canary_manager.UnattendedCanaryManager()
    hass = _Hass(tmp_path)
    coordinator = _Coordinator(
        unattended_canary=manager,
        unattended_canary_acceptance=SimpleNamespace(
            last_persistence_error=None,
            async_record=_Recorder().async_record,
        ),
        supervised_operation=SimpleNamespace(
            in_progress=False,
            dispatch_lock=asyncio.Lock(),
        ),
        validated_targets=_ValidatedTargets(),
        production_targets=(TARGET,),
        production_readiness=SimpleNamespace(
            summary=SimpleNamespace(
                state=readiness.ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION,
                production_targets=(TARGET,),
            )
        ),
        data=_snapshot(),
        health_assessment=SimpleNamespace(
            state=health.IrrigationOSHealthState.HEALTHY,
            persistence_healthy=True,
            operational_log_healthy=True,
        ),
        ownership_commissioning=SimpleNamespace(
            summary=SimpleNamespace(
                ownership_confirmed=True,
                boundary_review_acknowledged=True,
                topology_matches=True,
            )
        ),
        live_commissioning=SimpleNamespace(
            summary=SimpleNamespace(supervised_safety_prerequisites_met=True)
        ),
        observation_history=SimpleNamespace(active_sessions=()),
        first_live_acceptance=SimpleNamespace(last_persistence_error=None),
        supervised_operation_acceptance=SimpleNamespace(last_persistence_error=None),
        last_update_success=True,
        refresh_error=None,
        refresh_count=0,
        listener_updates=0,
        hass=hass,
        entry=_Entry(hass),
    )
    return coordinator


def _approval(
    manager: Any,
    *,
    controller_slot: int = 1,
    area_slot: int = 2,
    runtime_seconds: int = 30,
    approved_at: datetime | None = None,
) -> Any:
    started = approved_at or datetime.now(UTC)
    approval = canary_models.UnattendedCanaryApproval(
        approval_id="unattended_canary_approval_test",
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        approved_at=started,
        expires_at=started + timedelta(minutes=10),
    )
    manager.install_approval(approval)
    return approval


def test_operator_import_does_not_require_home_assistant() -> None:
    script = """
import builtins
original_import = builtins.__import__
def without_ha(name, *args, **kwargs):
    if name == 'homeassistant' or name.startswith('homeassistant.'):
        raise ModuleNotFoundError('Home Assistant intentionally unavailable')
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_ha
from tests.helpers import load_integration_module
load_integration_module('unattended_canary.operator')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_monitor_cancellation_clears_transient_in_progress_state(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    manager = coordinator.unattended_canary
    manager.mark_dispatched(
        "unattended_canary_test",
        "unattended_canary_approval_test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    task = asyncio.create_task(
        canary_monitor.async_monitor_unattended_canary(
            coordinator=coordinator,
            manager=manager,
            audit_sink=_Recorder(),
            acceptance_sink=_Recorder(),
            acceptance=coordinator.unattended_canary_acceptance,
            canary_id="unattended_canary_test",
            approval_id="unattended_canary_approval_test",
            controller_id="canonical-controller-1",
            controller_slot=1,
            area_slot=2,
            runtime_seconds=30,
            dispatched_at=datetime.now(UTC),
            audit_chain_complete=True,
        )
    )
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert manager.in_progress is False


def test_approval_is_exact_bounded_single_use_and_restart_ephemeral(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    assert operator.evaluate_canary_authorization_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        confirmation=operator.UNATTENDED_CANARY_CONFIRMATION,
        now=NOW,
    ) == ()
    wrong = operator.evaluate_canary_authorization_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=14,
        confirmation=f" {operator.UNATTENDED_CANARY_CONFIRMATION}",
        now=NOW,
    )
    assert wrong == ("operator_confirmation_mismatch", "runtime_out_of_range")

    approval = _approval(coordinator.unattended_canary, approved_at=NOW)
    assert coordinator.unattended_canary.approval_state(NOW).value == "approved"
    assert coordinator.unattended_canary.approval_state(
        NOW + timedelta(minutes=10)
    ).value == "expired"
    assert coordinator.unattended_canary.consume_approval(
        approval.approval_id, NOW + timedelta(minutes=1)
    )
    assert coordinator.unattended_canary.approval_state(
        NOW + timedelta(minutes=1)
    ).value == "consumed"
    assert not coordinator.unattended_canary.consume_approval(
        approval.approval_id, NOW + timedelta(minutes=2)
    )
    restarted = canary_manager.UnattendedCanaryManager()
    assert restarted.approval_state().value == "none"
    assert restarted.in_progress is False


@pytest.mark.asyncio
async def test_authorization_records_audit_and_advances_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = _coordinator(tmp_path)
    audit = _Recorder()
    monkeypatch.setattr(operator, "_audit_sink", lambda _coordinator: audit)
    result = await operator.async_authorize_unattended_canary(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        confirmation=operator.UNATTENDED_CANARY_CONFIRMATION,
    )
    assert result.status is canary_models.UnattendedCanaryAuthorizationStatus.APPROVED
    assert len(audit.records) == 1
    assert audit.records[0].event_type == "approval_recorded"
    assert coordinator.production_readiness.summary.state is (
        readiness.ProductionReadinessState.READY_FOR_UNATTENDED_CANARY
    )
    assert "native" not in repr(audit.records[0].to_dict()).lower()


@pytest.mark.asyncio
async def test_jsonl_audit_contains_only_canonical_privacy_safe_data(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unattended_canary_audit.jsonl"
    sink = canary_audit.JsonlUnattendedCanaryAuditSink(path)
    event = canary_audit.build_audit_event(
        canary_id="unattended_canary_test",
        approval_id="unattended_canary_approval_test",
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        event_type="dispatch_intent",
        detail_code="bounded_unattended_canary_start",
        recorded_at=NOW,
    )
    assert await sink.async_record(event)
    content = path.read_text(encoding="utf-8")
    assert '"controller_slot":1' in content
    assert '"area_slot":2' in content
    assert "native-zone" not in content
    assert "native-controller" not in content


def test_authorization_rejects_nonproduction_and_unvalidated_targets(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    blockers = operator.evaluate_canary_authorization_blockers(
        coordinator,
        controller_slot=1,
        area_slot=3,
        runtime_seconds=30,
        confirmation=operator.UNATTENDED_CANARY_CONFIRMATION,
    )
    assert blockers == ("target_not_production_target", "target_not_validated")


def _consume_current_approval(coordinator: Any) -> None:
    approval = coordinator.unattended_canary.approval
    assert approval is not None
    coordinator.unattended_canary.consume_approval(
        approval.approval_id, datetime.now(UTC)
    )


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        (_consume_current_approval, "approval_consumed"),
        (
            lambda c: setattr(c.supervised_operation, "in_progress", True),
            "supervised_operation_in_progress",
        ),
        (
            lambda c: setattr(c.unattended_canary, "active_canary_id", "active"),
            "unattended_canary_in_progress",
        ),
        (
            lambda c: setattr(
                c.health_assessment,
                "state",
                health.IrrigationOSHealthState.UNHEALTHY,
            ),
            "system_not_healthy",
        ),
        (lambda c: setattr(c, "data", _snapshot(observation_fresh=False)), "observation_stale"),
        (
            lambda c: setattr(
                c,
                "data",
                _snapshot(state=controllers.IrrigationAreaState.WATERING),
            ),
            "active_watering_conflict",
        ),
        (
            lambda c: setattr(c, "data", _snapshot(controller_online=False)),
            "controller_not_online",
        ),
        (
            lambda c: setattr(
                c.validated_targets, "last_persistence_error", "failed"
            ),
            "persistence_unhealthy",
        ),
    ],
)
def test_execution_blockers_are_fail_closed(
    tmp_path: Path, mutation: Any, blocker: str
) -> None:
    coordinator = _coordinator(tmp_path)
    _approval(coordinator.unattended_canary)
    coordinator.update_production_readiness()
    mutation(coordinator)
    blockers = operator.evaluate_unattended_canary_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    )
    assert blocker in blockers
    assert blockers == tuple(sorted(blockers))


def test_execution_requires_exact_target_runtime_and_canary_readiness(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    _approval(coordinator.unattended_canary)
    coordinator.update_production_readiness()
    assert operator.evaluate_unattended_canary_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
    ) == ()
    assert "approval_target_mismatch" in operator.evaluate_unattended_canary_blockers(
        coordinator,
        controller_slot=1,
        area_slot=1,
        runtime_seconds=30,
    )
    assert "approval_runtime_mismatch" in operator.evaluate_unattended_canary_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=31,
    )
    coordinator.production_readiness.summary.state = (
        readiness.ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
    )
    assert "production_readiness_not_ready" in (
        operator.evaluate_unattended_canary_blockers(
            coordinator,
            controller_slot=1,
            area_slot=2,
            runtime_seconds=30,
        )
    )


def test_missing_expired_and_invalidated_approval_fall_back_fail_closed(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    missing = operator.evaluate_unattended_canary_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        now=NOW,
    )
    assert "no_valid_canary_approval" in missing
    assert "production_readiness_not_ready" in missing

    _approval(
        coordinator.unattended_canary,
        approved_at=NOW - timedelta(minutes=11),
    )
    coordinator.update_production_readiness(NOW)
    assert coordinator.production_readiness.summary.state is (
        readiness.ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
    )
    expired = operator.evaluate_unattended_canary_blockers(
        coordinator,
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        now=NOW,
    )
    assert "approval_expired" in expired

    coordinator.unattended_canary = canary_manager.UnattendedCanaryManager()
    _approval(coordinator.unattended_canary, approved_at=NOW)
    coordinator.validated_targets.targets.clear()
    coordinator.update_production_readiness(NOW)
    assert coordinator.production_readiness.summary.state is (
        readiness.ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
    )
    assert not coordinator.unattended_canary.valid_approval_for(
        now=NOW,
        production_targets=(TARGET,),
        validated_targets=(),
    )


@pytest.mark.asyncio
async def test_happy_path_dispatches_once_consumes_once_and_never_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = _coordinator(tmp_path)
    _approval(coordinator.unattended_canary)
    coordinator.update_production_readiness()
    audit = _Recorder()
    history = _Recorder()
    transport_calls: list[tuple[str, int]] = []

    class _Transport:
        def __init__(self, *_args: object) -> None:
            pass

        async def async_start_zone(self, *, zone_id: str, runtime_seconds: int) -> None:
            transport_calls.append((zone_id, runtime_seconds))

    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.__dict__["async_get_clientsession"] = lambda _hass: object()
    monkeypatch.setitem(sys.modules, "homeassistant", ModuleType("homeassistant"))
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", ModuleType("homeassistant.helpers"))
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.aiohttp_client", aiohttp_client)
    monkeypatch.setattr(operator, "RachioFirstLiveTransport", _Transport)
    monkeypatch.setattr(operator, "_audit_sink", lambda _coordinator: audit)
    monkeypatch.setattr(operator, "_acceptance_sink", lambda _coordinator: history)

    result = await operator.async_run_unattended_canary(
        coordinator, controller_slot=1, area_slot=2, runtime_seconds=30
    )
    assert result.status is canary_models.UnattendedCanaryRunStatus.START_DISPATCHED
    assert transport_calls == [("native-zone-secret", 30)]
    assert coordinator.unattended_canary.approval_state().value == "consumed"
    assert coordinator.unattended_canary.in_progress is True
    assert coordinator.production_readiness.summary.state is (
        readiness.ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
    )
    assert [event.event_type for event in audit.records] == [
        "dispatch_intent",
        "approval_consumed",
        "transport_accepted",
    ]
    assert len(coordinator.hass.tasks) == 1
    coordinator.hass.tasks[0].close()

    blocked = await operator.async_run_unattended_canary(
        coordinator, controller_slot=1, area_slot=2, runtime_seconds=30
    )
    assert blocked.status is canary_models.UnattendedCanaryRunStatus.BLOCKED
    assert transport_calls == [("native-zone-secret", 30)]


@pytest.mark.asyncio
async def test_transport_failure_consumes_approval_and_does_not_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = _coordinator(tmp_path)
    _approval(coordinator.unattended_canary)
    coordinator.update_production_readiness()
    calls = 0

    class _FailingTransport:
        def __init__(self, *_args: object) -> None:
            pass

        async def async_start_zone(self, **_kwargs: object) -> None:
            nonlocal calls
            calls += 1
            raise operator.FirstLiveTransportError("failed")

    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.__dict__["async_get_clientsession"] = lambda _hass: object()
    monkeypatch.setitem(sys.modules, "homeassistant", ModuleType("homeassistant"))
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", ModuleType("homeassistant.helpers"))
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.aiohttp_client", aiohttp_client)
    monkeypatch.setattr(operator, "RachioFirstLiveTransport", _FailingTransport)
    monkeypatch.setattr(operator, "_audit_sink", lambda _coordinator: _Recorder())
    monkeypatch.setattr(operator, "_acceptance_sink", lambda _coordinator: _Recorder())

    result = await operator.async_run_unattended_canary(
        coordinator, controller_slot=1, area_slot=2, runtime_seconds=30
    )
    assert result.status is canary_models.UnattendedCanaryRunStatus.TRANSPORT_FAILED
    assert calls == 1
    assert coordinator.unattended_canary.approval_state().value == "consumed"
    assert coordinator.unattended_canary.in_progress is False
