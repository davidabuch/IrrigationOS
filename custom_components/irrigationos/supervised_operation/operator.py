"""Manual fail-closed operator boundary for bounded operational watering."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..const import CONF_API_KEY
from ..controllers import (
    ControllerAvailability,
    IrrigationAreaState,
    ObservationQuality,
)
from ..first_live_delivery.acceptance import build_acceptance_record
from ..first_live_delivery.rachio import FirstLiveTransportError, RachioFirstLiveTransport
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
SUPERVISED_OPERATION_MAX_RUNTIME_SECONDS = 120
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

        blockers = evaluate_supervised_operation_blockers(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            confirmation=confirmation,
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

        try:
            # Home Assistant is required only when this live path executes.
            # The local import preserves the HA-independent unit-test boundary.
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            transport = RachioFirstLiveTransport(
                async_get_clientsession(coordinator.hass),
                str(coordinator.entry.data[CONF_API_KEY]),
            )
            await transport.async_start_zone(
                zone_id=area.binding.native_id,
                runtime_seconds=runtime_seconds,
            )
        except (FirstLiveTransportError, ValueError):
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
        coordinator.entry.async_create_background_task(
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
        return SupervisedOperationResult(
            status=SupervisedOperationStatus.START_DISPATCHED,
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

    blockers: set[str] = set()
    if confirmation.strip() != SUPERVISED_OPERATION_CONFIRMATION:
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
        if controller.binding.provider != "rachio":
            blockers.add("unsupported_transport_provider")
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
    )
    await async_record_terminal_acceptance(
        record,
        history=acceptance_sink,
        latest=acceptance,
    )
