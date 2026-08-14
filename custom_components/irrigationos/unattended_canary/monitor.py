"""Terminal observation for one bounded unattended canary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from ..controllers.models import (
    ControllerRegistrySnapshot,
    IrrigationAreaState,
    ObservationQuality,
)
from .acceptance import (
    UnattendedCanaryAcceptanceManager,
    UnattendedCanaryAcceptanceSink,
    async_record_terminal_acceptance,
    build_canary_acceptance_record,
)
from .audit import UnattendedCanaryAuditSink, build_audit_event
from .manager import UnattendedCanaryManager

UNATTENDED_CANARY_OBSERVATION_INTERVAL_SECONDS = 5
UNATTENDED_CANARY_START_GRACE_SECONDS = 30
UNATTENDED_CANARY_COMPLETION_GRACE_SECONDS = 45


class UnattendedCanarySnapshotRefresher(Protocol):
    """Minimal coordinator boundary required for terminal observation."""

    data: ControllerRegistrySnapshot
    health_assessment: Any
    live_commissioning: Any
    ownership_commissioning: Any
    execution_authorization: Any
    live_mode_safety: Any
    integrated_safety_review: Any

    async def async_request_refresh(self) -> None:
        """Request one fresh canonical observation."""
        ...

    def update_production_readiness(self, evaluated_at: datetime | None = None) -> None:
        """Recompute non-persistent advisory readiness."""
        ...

    def async_update_listeners(self) -> None:
        """Publish transient and acceptance state."""
        ...


async def async_monitor_unattended_canary(
    *,
    coordinator: UnattendedCanarySnapshotRefresher,
    manager: UnattendedCanaryManager,
    audit_sink: UnattendedCanaryAuditSink,
    acceptance_sink: UnattendedCanaryAcceptanceSink,
    acceptance: UnattendedCanaryAcceptanceManager,
    canary_id: str,
    approval_id: str,
    controller_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    dispatched_at: datetime,
    audit_chain_complete: bool,
) -> None:
    """Observe WATERING then IDLE without retrying a failed refresh."""

    observed_watering_at: datetime | None = None
    refresh_error_count = 0
    concurrent_watering_observed = False
    safety_preemption_observed = False
    start_deadline = dispatched_at + timedelta(
        seconds=UNATTENDED_CANARY_START_GRACE_SECONDS
    )
    completion_deadline = dispatched_at + timedelta(
        seconds=runtime_seconds + UNATTENDED_CANARY_COMPLETION_GRACE_SECONDS
    )
    try:
        while datetime.now(UTC) <= completion_deadline:
            try:
                await coordinator.async_request_refresh()
            except Exception:
                refresh_error_count += 1
                await _record_terminal(
                    coordinator=coordinator,
                    manager=manager,
                    audit_sink=audit_sink,
                    acceptance_sink=acceptance_sink,
                    acceptance=acceptance,
                    canary_id=canary_id,
                    approval_id=approval_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    observed_watering_at=observed_watering_at,
                    observed_idle_at=None,
                    refresh_error_count=refresh_error_count,
                    concurrent_watering_observed=concurrent_watering_observed,
                    safety_preemption_observed=safety_preemption_observed,
                    detail_code="monitor_refresh_failed_no_retry",
                    audit_chain_complete=audit_chain_complete,
                )
                return

            snapshot = coordinator.data
            state = _target_state(snapshot, controller_id, area_slot)
            concurrent_watering_observed |= _other_watering_active(
                snapshot, controller_id, area_slot
            )
            now = datetime.now(UTC)
            observation_confirmed = (
                snapshot.observation.quality is ObservationQuality.CONFIRMED
                and snapshot.observation.is_fresh(now)
            )
            safety_preemption_observed |= _safety_preemption_required(
                coordinator,
                observation_confirmed=observation_confirmed,
                target_state=state,
                concurrent_watering_observed=concurrent_watering_observed,
            )
            if safety_preemption_observed:
                await _record_terminal(
                    coordinator=coordinator,
                    manager=manager,
                    audit_sink=audit_sink,
                    acceptance_sink=acceptance_sink,
                    acceptance=acceptance,
                    canary_id=canary_id,
                    approval_id=approval_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    observed_watering_at=observed_watering_at,
                    observed_idle_at=None,
                    refresh_error_count=refresh_error_count,
                    concurrent_watering_observed=concurrent_watering_observed,
                    safety_preemption_observed=True,
                    detail_code="safety_preemption_observed",
                    audit_chain_complete=audit_chain_complete,
                )
                return

            if (
                state is IrrigationAreaState.WATERING
                and observed_watering_at is None
                and observation_confirmed
            ):
                observed_watering_at = now
                success = await audit_sink.async_record(
                    build_audit_event(
                        canary_id=canary_id,
                        approval_id=approval_id,
                        controller_slot=controller_slot,
                        area_slot=area_slot,
                        runtime_seconds=runtime_seconds,
                        event_type="target_watering_observed",
                        detail_code="target_watering_observed",
                        recorded_at=now,
                    )
                )
                audit_chain_complete = audit_chain_complete and success
            elif (
                observed_watering_at is not None
                and state is IrrigationAreaState.IDLE
                and observation_confirmed
            ):
                await _record_terminal(
                    coordinator=coordinator,
                    manager=manager,
                    audit_sink=audit_sink,
                    acceptance_sink=acceptance_sink,
                    acceptance=acceptance,
                    canary_id=canary_id,
                    approval_id=approval_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    observed_watering_at=observed_watering_at,
                    observed_idle_at=now,
                    refresh_error_count=refresh_error_count,
                    concurrent_watering_observed=concurrent_watering_observed,
                    safety_preemption_observed=False,
                    detail_code=(
                        "canary_rejected_concurrent_watering"
                        if concurrent_watering_observed
                        else "canary_accepted"
                    ),
                    audit_chain_complete=audit_chain_complete,
                )
                return

            if observed_watering_at is None and now > start_deadline:
                await _record_terminal(
                    coordinator=coordinator,
                    manager=manager,
                    audit_sink=audit_sink,
                    acceptance_sink=acceptance_sink,
                    acceptance=acceptance,
                    canary_id=canary_id,
                    approval_id=approval_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    observed_watering_at=None,
                    observed_idle_at=None,
                    refresh_error_count=refresh_error_count,
                    concurrent_watering_observed=concurrent_watering_observed,
                    safety_preemption_observed=False,
                    detail_code="watering_not_observed_within_grace",
                    audit_chain_complete=audit_chain_complete,
                )
                return
            await asyncio.sleep(UNATTENDED_CANARY_OBSERVATION_INTERVAL_SECONDS)

        await _record_terminal(
            coordinator=coordinator,
            manager=manager,
            audit_sink=audit_sink,
            acceptance_sink=acceptance_sink,
            acceptance=acceptance,
            canary_id=canary_id,
            approval_id=approval_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            observed_watering_at=observed_watering_at,
            observed_idle_at=None,
            refresh_error_count=refresh_error_count,
            concurrent_watering_observed=concurrent_watering_observed,
            safety_preemption_observed=safety_preemption_observed,
            detail_code="completion_not_observed_within_grace",
            audit_chain_complete=audit_chain_complete,
        )
    finally:
        manager.mark_complete(canary_id)
        coordinator.update_production_readiness()
        coordinator.async_update_listeners()


async def _record_terminal(
    *,
    coordinator: UnattendedCanarySnapshotRefresher,
    manager: UnattendedCanaryManager,
    audit_sink: UnattendedCanaryAuditSink,
    acceptance_sink: UnattendedCanaryAcceptanceSink,
    acceptance: UnattendedCanaryAcceptanceManager,
    canary_id: str,
    approval_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    observed_watering_at: datetime | None,
    observed_idle_at: datetime | None,
    refresh_error_count: int,
    concurrent_watering_observed: bool,
    safety_preemption_observed: bool,
    detail_code: str,
    audit_chain_complete: bool,
) -> None:
    now = datetime.now(UTC)
    terminal_audit_recorded = await audit_sink.async_record(
        build_audit_event(
            canary_id=canary_id,
            approval_id=approval_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            event_type="acceptance_terminal",
            detail_code=detail_code,
            recorded_at=now,
        )
    )
    audit_chain_complete = audit_chain_complete and terminal_audit_recorded
    manager.record_audit_result(audit_chain_complete)
    record = build_canary_acceptance_record(
        canary_id=canary_id,
        approval_id=approval_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        requested_runtime_seconds=runtime_seconds,
        observed_watering_at=observed_watering_at,
        observed_idle_at=observed_idle_at,
        refresh_error_count=refresh_error_count,
        concurrent_watering_observed=concurrent_watering_observed,
        safety_preemption_observed=safety_preemption_observed,
        terminal_detail_code=detail_code,
        terminal_acceptance_audit_recorded=terminal_audit_recorded,
        audit_chain_complete=audit_chain_complete,
        recorded_at=now,
    )
    await async_record_terminal_acceptance(
        record,
        history=acceptance_sink,
        latest=acceptance,
    )
    coordinator.update_production_readiness(now)


def _target_state(
    snapshot: ControllerRegistrySnapshot, controller_id: str, area_slot: int
) -> IrrigationAreaState | None:
    controller = next(
        (item for item in snapshot.controllers if item.controller_id == controller_id), None
    )
    if controller is None:
        return None
    area = next((item for item in controller.areas if item.slot_number == area_slot), None)
    return None if area is None else area.state


def _other_watering_active(
    snapshot: ControllerRegistrySnapshot, controller_id: str, area_slot: int
) -> bool:
    return any(
        area.state is IrrigationAreaState.WATERING
        and not (
            controller.controller_id == controller_id and area.slot_number == area_slot
        )
        for controller in snapshot.controllers
        for area in controller.areas
    )


def _safety_preemption_required(
    coordinator: UnattendedCanarySnapshotRefresher,
    *,
    observation_confirmed: bool,
    target_state: IrrigationAreaState | None,
    concurrent_watering_observed: bool,
) -> bool:
    ownership = coordinator.ownership_commissioning.summary
    safety_prerequisites_met = (
        coordinator.live_commissioning.summary.supervised_safety_prerequisites_met
    )
    if (
        not safety_prerequisites_met
        and target_state is IrrigationAreaState.WATERING
        and not concurrent_watering_observed
    ):
        execution_gates = coordinator.execution_authorization.summary.gates
        execution_without_expected_watering = {
            gate: passed
            for gate, passed in execution_gates.items()
            if gate not in {"control_readiness_criteria_met", "no_active_watering_conflict"}
        }
        safety_prerequisites_met = all(
            (
                execution_gates.get("no_active_watering_conflict") is False,
                bool(execution_without_expected_watering)
                and all(execution_without_expected_watering.values()),
                bool(coordinator.live_mode_safety.summary.safeguard_gates)
                and all(coordinator.live_mode_safety.summary.safeguard_gates.values()),
                bool(coordinator.integrated_safety_review.summary.validation_scenarios)
                and all(
                    coordinator.integrated_safety_review.summary.validation_scenarios.values()
                ),
            )
        )
    return (
        getattr(coordinator.health_assessment.state, "value", "") != "HEALTHY"
        or not observation_confirmed
        or not ownership.ownership_confirmed
        or not ownership.boundary_review_acknowledged
        or not ownership.topology_matches
        or not safety_prerequisites_met
    )
