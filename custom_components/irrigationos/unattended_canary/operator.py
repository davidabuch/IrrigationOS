"""Explicit approval and one-shot unattended-canary command boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..const import CONF_API_KEY
from ..controllers import (
    ControllerAvailability,
    IrrigationAreaState,
    ObservationQuality,
)
from ..first_live_delivery.rachio import FirstLiveTransportError, RachioFirstLiveTransport
from ..health import IrrigationOSHealthState
from ..production_readiness import ProductionReadinessState, ProductionTarget
from .acceptance import (
    JsonlUnattendedCanaryAcceptanceSink,
    UnattendedCanaryAcceptanceManager,
    async_record_terminal_acceptance,
    build_canary_acceptance_record,
)
from .audit import (
    JsonlUnattendedCanaryAuditSink,
    build_audit_event,
    new_approval_id,
    new_canary_id,
)
from .models import (
    UnattendedCanaryApproval,
    UnattendedCanaryApprovalState,
    UnattendedCanaryAuthorizationResult,
    UnattendedCanaryAuthorizationStatus,
    UnattendedCanaryRunResult,
    UnattendedCanaryRunStatus,
)
from .monitor import async_monitor_unattended_canary

UNATTENDED_CANARY_CONFIRMATION = "AUTHORIZE ONE UNATTENDED CANARY"
UNATTENDED_CANARY_APPROVAL_TTL = timedelta(minutes=10)
UNATTENDED_CANARY_MIN_RUNTIME_SECONDS = 15
UNATTENDED_CANARY_DEFAULT_RUNTIME_SECONDS = 30
UNATTENDED_CANARY_MAX_RUNTIME_SECONDS = 60
SERVICE_AUTHORIZE_UNATTENDED_CANARY = "authorize_unattended_canary"
SERVICE_RUN_UNATTENDED_CANARY = "run_unattended_canary"


async def async_authorize_unattended_canary(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    confirmation: str,
) -> UnattendedCanaryAuthorizationResult:
    """Record one audited, restart-ephemeral, non-actuating approval."""

    manager = coordinator.unattended_canary
    async with coordinator.supervised_operation.dispatch_lock, manager.dispatch_lock:
        now = datetime.now(UTC)
        coordinator.update_production_readiness(now)
        blockers = evaluate_canary_authorization_blockers(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            confirmation=confirmation,
            now=now,
        )
        if blockers:
            return UnattendedCanaryAuthorizationResult(
                status=UnattendedCanaryAuthorizationStatus.BLOCKED,
                blocker_codes=blockers,
                approval_id=None,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )

        approval = UnattendedCanaryApproval(
            approval_id=new_approval_id(),
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            approved_at=now,
            expires_at=now + UNATTENDED_CANARY_APPROVAL_TTL,
        )
        audit_sink = _audit_sink(coordinator)
        recorded = await audit_sink.async_record(
            build_audit_event(
                canary_id=None,
                approval_id=approval.approval_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                event_type="approval_recorded",
                detail_code="single_use_canary_approval_recorded",
                recorded_at=now,
            )
        )
        manager.record_audit_result(recorded)
        if not recorded:
            coordinator.update_production_readiness(now)
            coordinator.async_update_listeners()
            return UnattendedCanaryAuthorizationResult(
                status=UnattendedCanaryAuthorizationStatus.BLOCKED,
                blocker_codes=("approval_audit_not_durable",),
                approval_id=None,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
            )
        manager.install_approval(approval)
        coordinator.update_production_readiness(now)
        coordinator.async_update_listeners()
        return UnattendedCanaryAuthorizationResult(
            status=UnattendedCanaryAuthorizationStatus.APPROVED,
            blocker_codes=(),
            approval_id=approval.approval_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
        )


def evaluate_canary_authorization_blockers(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    confirmation: str,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Validate approval scope without granting or executing authority."""

    blockers: set[str] = set()
    if confirmation != UNATTENDED_CANARY_CONFIRMATION:
        blockers.add("operator_confirmation_mismatch")
    if not UNATTENDED_CANARY_MIN_RUNTIME_SECONDS <= runtime_seconds <= (
        UNATTENDED_CANARY_MAX_RUNTIME_SECONDS
    ):
        blockers.add("runtime_out_of_range")
    state = coordinator.unattended_canary.approval_state(now or datetime.now(UTC))
    if state is UnattendedCanaryApprovalState.APPROVED:
        blockers.add("canary_approval_already_pending")
    if coordinator.unattended_canary.in_progress:
        blockers.add("unattended_canary_in_progress")
    target = ProductionTarget(controller_slot, area_slot)
    if target not in coordinator.production_readiness.summary.production_targets:
        blockers.add("target_not_production_target")
    if not coordinator.validated_targets.contains(controller_slot, area_slot):
        blockers.add("target_not_validated")
    return tuple(sorted(blockers))


async def async_run_unattended_canary(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
) -> UnattendedCanaryRunResult:
    """Attempt exactly one dispatch after fresh fail-closed preflight."""

    manager = coordinator.unattended_canary
    async with coordinator.supervised_operation.dispatch_lock, manager.dispatch_lock:
        try:
            await coordinator.async_request_refresh()
        except Exception:
            return _run_result(
                UnattendedCanaryRunStatus.BLOCKED,
                ("preflight_refresh_failed",),
                None,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )
        if not coordinator.last_update_success:
            return _run_result(
                UnattendedCanaryRunStatus.BLOCKED,
                ("preflight_refresh_failed",),
                None,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )

        now = datetime.now(UTC)
        coordinator.update_production_readiness(now)
        blockers = evaluate_unattended_canary_blockers(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            now=now,
        )
        if blockers:
            return _run_result(
                UnattendedCanaryRunStatus.BLOCKED,
                blockers,
                None,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )

        approval = manager.approval
        assert approval is not None
        controller = coordinator.data.controllers[controller_slot - 1]
        area = next(item for item in controller.areas if item.slot_number == area_slot)
        assert area.binding is not None
        canary_id = new_canary_id()
        audit_sink = _audit_sink(coordinator)
        acceptance_sink = _acceptance_sink(coordinator)

        intent_recorded = await audit_sink.async_record(
            build_audit_event(
                canary_id=canary_id,
                approval_id=approval.approval_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                event_type="dispatch_intent",
                detail_code="bounded_unattended_canary_start",
                recorded_at=now,
            )
        )
        manager.record_audit_result(intent_recorded)
        if not intent_recorded:
            consumed_on_failure = manager.consume_approval(
                approval.approval_id, datetime.now(UTC)
            )
            await _record_pre_dispatch_failure(
                coordinator=coordinator,
                audit_sink=audit_sink,
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.unattended_canary_acceptance,
                canary_id=canary_id,
                approval=approval,
                detail_code="dispatch_intent_not_durable",
                command_intent_recorded=False,
                approval_consumed=consumed_on_failure,
                start_acknowledged=False,
                audit_chain_complete=False,
            )
            return _run_result(
                UnattendedCanaryRunStatus.AUDIT_FAILED,
                ("dispatch_intent_not_durable",),
                canary_id,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )

        consumed = manager.consume_approval(approval.approval_id, datetime.now(UTC))
        if not consumed:
            await _record_pre_dispatch_failure(
                coordinator=coordinator,
                audit_sink=audit_sink,
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.unattended_canary_acceptance,
                canary_id=canary_id,
                approval=approval,
                detail_code="approval_consumption_failed",
                command_intent_recorded=True,
                approval_consumed=False,
                start_acknowledged=False,
                audit_chain_complete=True,
            )
            return _run_result(
                UnattendedCanaryRunStatus.BLOCKED,
                ("approval_consumption_failed",),
                canary_id,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )
        coordinator.update_production_readiness()
        coordinator.async_update_listeners()
        consumption_recorded = await audit_sink.async_record(
            build_audit_event(
                canary_id=canary_id,
                approval_id=approval.approval_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                event_type="approval_consumed",
                detail_code="single_use_approval_consumed_before_transport",
                recorded_at=datetime.now(UTC),
            )
        )
        manager.record_audit_result(consumption_recorded)
        if not consumption_recorded:
            await _record_pre_dispatch_failure(
                coordinator=coordinator,
                audit_sink=audit_sink,
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.unattended_canary_acceptance,
                canary_id=canary_id,
                approval=approval,
                detail_code="approval_consumption_audit_not_durable",
                command_intent_recorded=True,
                approval_consumed=True,
                start_acknowledged=False,
                audit_chain_complete=False,
            )
            return _run_result(
                UnattendedCanaryRunStatus.AUDIT_FAILED,
                ("approval_consumption_audit_not_durable",),
                canary_id,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )

        try:
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
            transport_audited = await audit_sink.async_record(
                build_audit_event(
                    canary_id=canary_id,
                    approval_id=approval.approval_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    event_type="transport_failed",
                    detail_code="transport_failed_no_retry",
                    recorded_at=datetime.now(UTC),
                )
            )
            manager.record_audit_result(transport_audited)
            await _record_pre_dispatch_failure(
                coordinator=coordinator,
                audit_sink=audit_sink,
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.unattended_canary_acceptance,
                canary_id=canary_id,
                approval=approval,
                detail_code="unattended_canary_transport_failed",
                command_intent_recorded=True,
                approval_consumed=True,
                start_acknowledged=False,
                audit_chain_complete=transport_audited,
            )
            return _run_result(
                UnattendedCanaryRunStatus.TRANSPORT_FAILED,
                ("transport_failed_no_retry",),
                canary_id,
                manager,
                controller_slot,
                area_slot,
                runtime_seconds,
            )

        transport_audited = await audit_sink.async_record(
            build_audit_event(
                canary_id=canary_id,
                approval_id=approval.approval_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                event_type="transport_accepted",
                detail_code="start_http_accepted",
                recorded_at=datetime.now(UTC),
            )
        )
        manager.record_audit_result(transport_audited)
        manager.mark_dispatched(
            canary_id,
            approval.approval_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
        )
        coordinator.update_production_readiness()
        coordinator.async_update_listeners()
        coordinator.hass.async_create_task(
            async_monitor_unattended_canary(
                coordinator=coordinator,
                manager=manager,
                audit_sink=audit_sink,
                acceptance_sink=acceptance_sink,
                acceptance=coordinator.unattended_canary_acceptance,
                canary_id=canary_id,
                approval_id=approval.approval_id,
                controller_id=controller.controller_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                dispatched_at=now,
                audit_chain_complete=transport_audited,
            ),
            "IrrigationOS bounded unattended canary monitor",
        )
        return _run_result(
            UnattendedCanaryRunStatus.START_DISPATCHED,
            (),
            canary_id,
            manager,
            controller_slot,
            area_slot,
            runtime_seconds,
        )


def evaluate_unattended_canary_blockers(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Return deterministic blockers from fresh current state."""

    evaluated_at = now or datetime.now(UTC)
    blockers: set[str] = set()
    manager = coordinator.unattended_canary
    approval = manager.approval
    state = manager.approval_state(evaluated_at)
    if state is UnattendedCanaryApprovalState.NONE:
        blockers.add("no_valid_canary_approval")
    elif state is UnattendedCanaryApprovalState.EXPIRED:
        blockers.add("approval_expired")
    elif state is UnattendedCanaryApprovalState.CONSUMED:
        blockers.add("approval_consumed")
    if approval is not None:
        if (
            approval.controller_slot != controller_slot
            or approval.area_slot != area_slot
        ):
            blockers.add("approval_target_mismatch")
        if approval.runtime_seconds != runtime_seconds:
            blockers.add("approval_runtime_mismatch")
    if not UNATTENDED_CANARY_MIN_RUNTIME_SECONDS <= runtime_seconds <= (
        UNATTENDED_CANARY_MAX_RUNTIME_SECONDS
    ):
        blockers.add("runtime_out_of_range")
    if manager.in_progress:
        blockers.add("unattended_canary_in_progress")
    if coordinator.supervised_operation.in_progress:
        blockers.add("supervised_operation_in_progress")
    if (
        coordinator.production_readiness.summary.state
        is not ProductionReadinessState.READY_FOR_UNATTENDED_CANARY
    ):
        blockers.add("production_readiness_not_ready")
    target = ProductionTarget(controller_slot, area_slot)
    if target not in coordinator.production_readiness.summary.production_targets:
        blockers.add("target_not_production_target")
    if not coordinator.validated_targets.contains(controller_slot, area_slot):
        blockers.add("target_not_validated")
    if coordinator.health_assessment.state is not IrrigationOSHealthState.HEALTHY:
        blockers.add("system_not_healthy")

    snapshot = coordinator.data
    if snapshot.observation.quality is not ObservationQuality.CONFIRMED:
        blockers.add("observation_not_confirmed")
    if not snapshot.observation.is_fresh(evaluated_at):
        blockers.add("observation_stale")
    ownership = coordinator.ownership_commissioning.summary
    if not ownership.ownership_confirmed:
        blockers.add("controller_ownership_not_confirmed")
    if not ownership.boundary_review_acknowledged:
        blockers.add("execution_boundary_review_not_acknowledged")
    if not ownership.topology_matches:
        blockers.add("controller_topology_mismatch")
    if not coordinator.live_commissioning.summary.supervised_safety_prerequisites_met:
        blockers.add("safety_prerequisites_not_met")
    if coordinator.observation_history.active_sessions or any(
        area.state is IrrigationAreaState.WATERING
        for controller in snapshot.controllers
        for area in controller.areas
    ):
        blockers.add("active_watering_conflict")
    if _persistence_unhealthy(coordinator):
        blockers.add("persistence_unhealthy")

    controller = (
        snapshot.controllers[controller_slot - 1]
        if 1 <= controller_slot <= len(snapshot.controllers)
        else None
    )
    if controller is None:
        blockers.add("controller_slot_not_observed")
    else:
        if (
            not controller.enabled
            or controller.availability is not ControllerAvailability.ONLINE
        ):
            blockers.add("controller_not_online")
        if controller.binding.provider != "rachio":
            blockers.add("unsupported_transport_provider")
        area = next(
            (item for item in controller.areas if item.slot_number == area_slot), None
        )
        if area is None:
            blockers.add("area_slot_not_observed")
        elif (
            not area.configured
            or not area.enabled
            or area.binding is None
            or area.state is not IrrigationAreaState.IDLE
        ):
            blockers.add("target_not_idle")
    return tuple(sorted(blockers))


async def _record_pre_dispatch_failure(
    *,
    coordinator: Any,
    audit_sink: JsonlUnattendedCanaryAuditSink,
    acceptance_sink: JsonlUnattendedCanaryAcceptanceSink,
    acceptance: UnattendedCanaryAcceptanceManager,
    canary_id: str,
    approval: UnattendedCanaryApproval,
    detail_code: str,
    command_intent_recorded: bool,
    approval_consumed: bool,
    start_acknowledged: bool,
    audit_chain_complete: bool,
) -> None:
    terminal_audit_recorded = await audit_sink.async_record(
        build_audit_event(
            canary_id=canary_id,
            approval_id=approval.approval_id,
            controller_slot=approval.controller_slot,
            area_slot=approval.area_slot,
            runtime_seconds=approval.runtime_seconds,
            event_type="acceptance_terminal",
            detail_code=detail_code,
            recorded_at=datetime.now(UTC),
        )
    )
    audit_chain_complete = audit_chain_complete and terminal_audit_recorded
    coordinator.unattended_canary.record_audit_result(audit_chain_complete)
    record = build_canary_acceptance_record(
        canary_id=canary_id,
        approval_id=approval.approval_id,
        controller_slot=approval.controller_slot,
        area_slot=approval.area_slot,
        requested_runtime_seconds=approval.runtime_seconds,
        observed_watering_at=None,
        observed_idle_at=None,
        refresh_error_count=0,
        concurrent_watering_observed=False,
        safety_preemption_observed=False,
        terminal_detail_code=detail_code,
        command_intent_recorded=command_intent_recorded,
        approval_consumed=approval_consumed,
        start_acknowledged=start_acknowledged,
        terminal_acceptance_audit_recorded=terminal_audit_recorded,
        audit_chain_complete=audit_chain_complete,
    )
    await async_record_terminal_acceptance(
        record,
        history=acceptance_sink,
        latest=acceptance,
    )
    coordinator.update_production_readiness()
    coordinator.async_update_listeners()


def _persistence_unhealthy(coordinator: Any) -> bool:
    return any(
        (
            coordinator.validated_targets.last_persistence_error is not None,
            coordinator.first_live_acceptance.last_persistence_error is not None,
            coordinator.supervised_operation_acceptance.last_persistence_error is not None,
            coordinator.unattended_canary_acceptance.last_persistence_error is not None,
            coordinator.unattended_canary.last_audit_error is not None,
            not coordinator.health_assessment.persistence_healthy,
            not coordinator.health_assessment.operational_log_healthy,
        )
    )


def _audit_sink(coordinator: Any) -> JsonlUnattendedCanaryAuditSink:
    return JsonlUnattendedCanaryAuditSink(
        Path(
            coordinator.hass.config.path(
                "irrigationos_logs", "unattended_canary_audit.jsonl"
            )
        )
    )


def _acceptance_sink(coordinator: Any) -> JsonlUnattendedCanaryAcceptanceSink:
    return JsonlUnattendedCanaryAcceptanceSink(
        Path(
            coordinator.hass.config.path(
                "irrigationos_logs", "unattended_canary_acceptance.jsonl"
            )
        )
    )


def _run_result(
    status: UnattendedCanaryRunStatus,
    blockers: tuple[str, ...],
    canary_id: str | None,
    manager: Any,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
) -> UnattendedCanaryRunResult:
    approval_id = (
        None if manager.approval is None else manager.approval.approval_id
    )
    return UnattendedCanaryRunResult(
        status=status,
        blocker_codes=blockers,
        canary_id=canary_id,
        approval_id=approval_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
    )
