"""Manual fail-closed operator boundary for bounded operational watering."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..const import (
    MANUAL_WATERING_MAX_RUNTIME_SECONDS as SUPERVISED_OPERATION_MAX_RUNTIME_SECONDS,
)
from ..controllers import (
    ControllerAvailability,
    ControllerProviderError,
    IrrigationAreaState,
    ManualWateringAdapter,
    ObservationQuality,
)
from ..first_live_delivery.acceptance import build_acceptance_record
from ..health import IrrigationOSHealthState
from .acceptance import (
    JsonlSupervisedOperationAcceptanceSink,
    SupervisedOperationAcceptanceManager,
    async_record_terminal_acceptance,
)
from .audit import JsonlSupervisedOperationAuditSink, build_audit_event, new_operation_id
from .models import SupervisedOperationResult, SupervisedOperationStatus
from .monitor import async_monitor_supervised_operation

SUPERVISED_OPERATION_CONFIRMATION = "RUN SUPERVISED OPERATIONAL WATERING"
SUPERVISED_OPERATION_REVISION = 1


async def async_run_supervised_operation(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    confirmation: str,
) -> SupervisedOperationResult:
    """Dispatch one manually confirmed operation after strict live-state preflight."""

    return await _async_run_operator_approved_operation(
        coordinator,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        operator_approved=confirmation.strip() == SUPERVISED_OPERATION_CONFIRMATION,
    )


async def async_run_manual_operation(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
) -> SupervisedOperationResult:
    """Dispatch one valve-requested operation through the shared safety engine."""

    return await _async_run_operator_approved_operation(
        coordinator,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        operator_approved=True,
    )


async def _async_run_operator_approved_operation(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    operator_approved: bool,
) -> SupervisedOperationResult:
    """Run the common audited preflight and dispatch for explicit operator intent."""

    manager = coordinator.supervised_operation
    async with manager.dispatch_lock:
        try:
            await coordinator.async_request_refresh()
        except Exception:
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.BLOCKED,
                blocker_codes=("preflight_refresh_failed",),
                operation_id=None,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )
        if not coordinator.last_update_success:
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.BLOCKED,
                blocker_codes=("preflight_refresh_failed",),
                operation_id=None,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        blockers = _evaluate_supervised_operation_blockers(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            operator_approved=operator_approved,
        )
        if blockers:
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.BLOCKED,
                blocker_codes=blockers,
                operation_id=None,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        controller = coordinator.data.controllers[controller_slot - 1]
        area = next(item for item in controller.areas if item.slot_number == area_slot)
        assert area.binding is not None

        operation_id = new_operation_id()
        audit_sink = JsonlSupervisedOperationAuditSink(
            Path(
                coordinator.hass.config.path(
                    "irrigationos_logs", "supervised_operation_audit.jsonl"
                )
            )
        )
        acceptance_sink = JsonlSupervisedOperationAcceptanceSink(
            Path(
                coordinator.hass.config.path(
                    "irrigationos_logs", "supervised_operation_acceptance.jsonl"
                )
            )
        )
        recorded_at = datetime.now(UTC)
        intent_recorded = await audit_sink.async_record(
            build_audit_event(
                operation_id=operation_id,
                event_type="dispatch_intent",
                recorded_at=recorded_at,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                detail_code="supervised_operational_start",
            )
        )
        if not intent_recorded:
            await _record_pre_dispatch_failure(
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.supervised_operation_acceptance,
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                detail_code="dispatch_intent_not_durable",
                dispatch_intent_recorded=False,
                start_acknowledged=False,
                terminal_audit_recorded=False,
            )
            coordinator.update_production_readiness()
            coordinator.async_update_listeners()
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.AUDIT_FAILED,
                blocker_codes=("dispatch_intent_not_durable",),
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        adapter = coordinator.adapter
        assert isinstance(adapter, ManualWateringAdapter)
        try:
            await adapter.async_start_manual_watering(
                area_binding=area.binding,
                duration_seconds=runtime_seconds,
            )
        except (ControllerProviderError, ValueError):
            manager.mark_complete(operation_id)
            terminal_recorded = await audit_sink.async_record(
                build_audit_event(
                    operation_id=operation_id,
                    event_type="transport_outcome",
                    recorded_at=datetime.now(UTC),
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    detail_code="transport_failed_no_retry",
                )
            )
            await _record_pre_dispatch_failure(
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.supervised_operation_acceptance,
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                detail_code="supervised_operation_transport_failed",
                dispatch_intent_recorded=True,
                start_acknowledged=False,
                terminal_audit_recorded=terminal_recorded,
            )
            coordinator.update_production_readiness()
            coordinator.async_update_listeners()
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.TRANSPORT_FAILED,
                blocker_codes=("transport_failed_no_retry",),
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        manager.mark_dispatched(
            operation_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
        )
        coordinator.update_production_readiness()
        coordinator.async_update_listeners()
        await audit_sink.async_record(
            build_audit_event(
                operation_id=operation_id,
                event_type="transport_outcome",
                recorded_at=datetime.now(UTC),
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                detail_code="start_http_accepted",
            )
        )
        monitor_task = coordinator.entry.async_create_background_task(
            coordinator.hass,
            async_monitor_supervised_operation(
                coordinator=coordinator,
                manager=manager,
                audit_sink=audit_sink,
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.supervised_operation_acceptance,
                operation_id=operation_id,
                controller_id=controller.controller_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                dispatched_at=recorded_at,
            ),
            "IrrigationOS supervised operational watering monitor",
        )
        manager.attach_monitor(operation_id, monitor_task)
        return SupervisedOperationResult(
            status=SupervisedOperationStatus.START_DISPATCHED,
            blocker_codes=(),
            operation_id=operation_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
        )


async def async_stop_manual_operation(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
) -> SupervisedOperationResult:
    """Stop explicit manual watering through the provider's supported boundary."""

    manager = coordinator.supervised_operation
    async with manager.dispatch_lock:
        snapshot = coordinator.data
        controller = (
            snapshot.controllers[controller_slot - 1]
            if 1 <= controller_slot <= len(snapshot.controllers)
            else None
        )
        area = (
            None
            if controller is None
            else next(
                (item for item in controller.areas if item.slot_number == area_slot),
                None,
            )
        )
        runtime_seconds = manager.active_runtime_seconds or 0
        blockers: set[str] = set()
        if controller is None:
            blockers.add("controller_slot_not_observed")
        if area is None:
            blockers.add("area_slot_not_observed")
        if manager.in_progress and (
            manager.active_controller_slot != controller_slot
            or manager.active_area_slot != area_slot
        ):
            blockers.add("manual_stop_target_mismatch")
        if (
            area is not None
            and area.state is not IrrigationAreaState.WATERING
            and not (
                manager.in_progress
                and manager.active_controller_slot == controller_slot
                and manager.active_area_slot == area_slot
            )
        ):
            blockers.add("manual_watering_not_active")
        adapter = getattr(coordinator, "adapter", None)
        if not isinstance(adapter, ManualWateringAdapter):
            blockers.add("manual_watering_transport_unavailable")
        if blockers:
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.BLOCKED,
                blocker_codes=tuple(sorted(blockers)),
                operation_id=manager.active_operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        assert controller is not None
        assert area is not None
        assert isinstance(adapter, ManualWateringAdapter)
        operation_id = manager.active_operation_id or new_operation_id()
        audit_sink = JsonlSupervisedOperationAuditSink(
            Path(
                coordinator.hass.config.path(
                    "irrigationos_logs", "supervised_operation_audit.jsonl"
                )
            )
        )
        stop_intent = build_audit_event(
            operation_id=operation_id,
            event_type="stop_intent",
            recorded_at=datetime.now(UTC),
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            detail_code="manual_controller_wide_stop",
        )
        try:
            await adapter.async_stop_manual_watering(
                controller_binding=controller.binding
            )
        except (ControllerProviderError, ValueError):
            await audit_sink.async_record(stop_intent)
            await audit_sink.async_record(
                build_audit_event(
                    operation_id=operation_id,
                    event_type="stop_transport_outcome",
                    recorded_at=datetime.now(UTC),
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    detail_code="stop_transport_failed_no_retry",
                )
            )
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.TRANSPORT_FAILED,
                blocker_codes=("stop_transport_failed_no_retry",),
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        await audit_sink.async_record(stop_intent)
        await audit_sink.async_record(
            build_audit_event(
                operation_id=operation_id,
                event_type="stop_transport_outcome",
                recorded_at=datetime.now(UTC),
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                detail_code="controller_wide_stop_http_accepted",
            )
        )
        try:
            await coordinator.async_request_refresh()
        except Exception:
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.STOP_UNCONFIRMED,
                blocker_codes=("stop_outcome_not_observed",),
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        now = datetime.now(UTC)
        refreshed_controller = (
            coordinator.data.controllers[controller_slot - 1]
            if 1 <= controller_slot <= len(coordinator.data.controllers)
            else None
        )
        stop_confirmed = (
            refreshed_controller is not None
            and coordinator.data.observation.quality is ObservationQuality.CONFIRMED
            and coordinator.data.observation.is_fresh(now)
            and not any(
                item.state is IrrigationAreaState.WATERING
                for item in refreshed_controller.areas
            )
        )
        if not stop_confirmed:
            return SupervisedOperationResult(
                status=SupervisedOperationStatus.STOP_UNCONFIRMED,
                blocker_codes=("stop_outcome_not_observed",),
                operation_id=operation_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )
        if manager.active_operation_id == operation_id:
            await manager.async_cancel_monitor(operation_id)
        coordinator.update_production_readiness()
        coordinator.async_update_listeners()
        return SupervisedOperationResult(
            status=SupervisedOperationStatus.STOP_DISPATCHED,
            blocker_codes=(),
            operation_id=operation_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
        )


def evaluate_supervised_operation_blockers(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    confirmation: str,
) -> tuple[str, ...]:
    """Return deterministic fail-closed blockers without performing actuation."""

    return _evaluate_supervised_operation_blockers(
        coordinator,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        operator_approved=confirmation.strip() == SUPERVISED_OPERATION_CONFIRMATION,
    )


def _evaluate_supervised_operation_blockers(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    operator_approved: bool,
) -> tuple[str, ...]:
    """Evaluate every shared start gate after explicit intent normalization."""

    blockers: set[str] = set()
    if not operator_approved:
        blockers.add("operator_confirmation_mismatch")
    if not 1 <= runtime_seconds <= SUPERVISED_OPERATION_MAX_RUNTIME_SECONDS:
        blockers.add("runtime_out_of_range")
    if coordinator.supervised_operation.in_progress:
        blockers.add("supervised_operation_in_progress")
    unattended_canary = getattr(coordinator, "unattended_canary", None)
    if unattended_canary is not None and unattended_canary.in_progress:
        blockers.add("unattended_canary_in_progress")

    if not coordinator.validated_targets.contains(controller_slot, area_slot):
        blockers.add("target_not_validated")

    if coordinator.health_assessment.state is not IrrigationOSHealthState.HEALTHY:
        blockers.add("system_not_healthy")

    snapshot = coordinator.data
    now = datetime.now(UTC)
    if snapshot.observation.quality is not ObservationQuality.CONFIRMED:
        blockers.add("observation_not_confirmed")
    if not snapshot.observation.is_fresh(now):
        blockers.add("observation_not_fresh")

    if not coordinator.live_commissioning.summary.supervised_safety_prerequisites_met:
        blockers.add("supervised_safety_prerequisites_not_met")

    ownership = coordinator.ownership_commissioning.summary
    if not ownership.ownership_confirmed:
        blockers.add("controller_ownership_not_confirmed")
    if not ownership.boundary_review_acknowledged:
        blockers.add("execution_boundary_review_not_acknowledged")
    if coordinator.observation_history.active_sessions or any(
        area.state is IrrigationAreaState.WATERING
        for controller in snapshot.controllers
        for area in controller.areas
    ):
        blockers.add("active_watering_conflict")

    controller = (
        snapshot.controllers[controller_slot - 1]
        if 1 <= controller_slot <= len(snapshot.controllers)
        else None
    )
    area = None
    if controller is None:
        blockers.add("controller_slot_not_observed")
    else:
        if not controller.enabled or controller.availability is not ControllerAvailability.ONLINE:
            blockers.add("controller_not_available")
        if not isinstance(getattr(coordinator, "adapter", None), ManualWateringAdapter):
            blockers.add("manual_watering_transport_unavailable")
        area = next(
            (item for item in controller.areas if item.slot_number == area_slot),
            None,
        )
        if area is None:
            blockers.add("area_slot_not_observed")
        elif (
            not area.configured
            or not area.enabled
            or area.binding is None
            or area.state is not IrrigationAreaState.IDLE
        ):
            blockers.add("area_not_idle_and_eligible")

    return tuple(sorted(blockers))


async def _record_pre_dispatch_failure(
    *,
    acceptance_sink: JsonlSupervisedOperationAcceptanceSink,
    acceptance: SupervisedOperationAcceptanceManager,
    operation_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    detail_code: str,
    dispatch_intent_recorded: bool,
    start_acknowledged: bool,
    terminal_audit_recorded: bool = True,
) -> None:
    record = build_acceptance_record(
        attempt_id=operation_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        requested_runtime_seconds=runtime_seconds,
        observed_watering_at=None,
        observed_idle_at=None,
        refresh_error_count=0,
        concurrent_watering_observed=False,
        terminal_detail_code=detail_code,
        dispatch_intent_recorded=dispatch_intent_recorded,
        operator_approval_recorded=True,
        preflight_target_observed=True,
        start_acknowledged=start_acknowledged,
        terminal_audit_recorded=terminal_audit_recorded,
        maximum_runtime_seconds=SUPERVISED_OPERATION_MAX_RUNTIME_SECONDS,
    )
    await async_record_terminal_acceptance(
        record,
        history=acceptance_sink,
        latest=acceptance,
    )
