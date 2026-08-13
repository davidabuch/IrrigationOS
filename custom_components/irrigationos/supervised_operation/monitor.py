"""Asynchronous completion monitor for supervised operational watering."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ..controllers.models import (
    ControllerRegistrySnapshot,
    IrrigationAreaState,
    ObservationQuality,
)
from ..first_live_delivery.acceptance import build_acceptance_record
from .acceptance import JsonlSupervisedOperationAcceptanceSink
from .audit import SupervisedOperationAuditSink, build_audit_event
from .manager import SupervisedOperationManager

SUPERVISED_OPERATION_MONITOR_REVISION = 1
SUPERVISED_OPERATION_OBSERVATION_INTERVAL_SECONDS = 5
SUPERVISED_OPERATION_START_GRACE_SECONDS = 30
SUPERVISED_OPERATION_COMPLETION_GRACE_SECONDS = 45


class SupervisedOperationSnapshotRefresher(Protocol):
    """Minimal coordinator boundary required by the operation monitor."""

    data: ControllerRegistrySnapshot

    async def async_request_refresh(self) -> None:
        """Request one canonical controller refresh."""
        ...


async def async_monitor_supervised_operation(
    *,
    coordinator: SupervisedOperationSnapshotRefresher,
    manager: SupervisedOperationManager,
    audit_sink: SupervisedOperationAuditSink,
    acceptance_sink: JsonlSupervisedOperationAcceptanceSink,
    operation_id: str,
    controller_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    dispatched_at: datetime,
) -> None:
    """Observe the selected target enter WATERING and return to IDLE."""

    observed_watering_at: datetime | None = None
    refresh_error_count = 0
    concurrent_watering_observed = False
    start_deadline = dispatched_at + timedelta(
        seconds=SUPERVISED_OPERATION_START_GRACE_SECONDS
    )
    completion_deadline = dispatched_at + timedelta(
        seconds=runtime_seconds + SUPERVISED_OPERATION_COMPLETION_GRACE_SECONDS
    )

    try:
        while datetime.now(UTC) <= completion_deadline:
            try:
                await coordinator.async_request_refresh()
            except Exception:
                refresh_error_count += 1
                await asyncio.sleep(SUPERVISED_OPERATION_OBSERVATION_INTERVAL_SECONDS)
                continue

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

            if (
                state is IrrigationAreaState.WATERING
                and observed_watering_at is None
                and observation_confirmed
            ):
                observed_watering_at = now
                await audit_sink.async_record(
                    build_audit_event(
                        operation_id=operation_id,
                        event_type="acceptance_observation",
                        recorded_at=now,
                        controller_slot=controller_slot,
                        area_slot=area_slot,
                        runtime_seconds=runtime_seconds,
                        detail_code="target_watering_observed",
                    )
                )
            elif (
                observed_watering_at is not None
                and state is IrrigationAreaState.IDLE
                and observation_confirmed
            ):
                await _record_terminal(
                    audit_sink=audit_sink,
                    acceptance_sink=acceptance_sink,
                    operation_id=operation_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    observed_watering_at=observed_watering_at,
                    observed_idle_at=now,
                    refresh_error_count=refresh_error_count,
                    concurrent_watering_observed=concurrent_watering_observed,
                    detail_code=(
                        "supervised_operation_rejected_concurrent_watering"
                        if concurrent_watering_observed
                        else "supervised_operation_accepted"
                    ),
                )
                return

            if observed_watering_at is None and now > start_deadline:
                await _record_terminal(
                    audit_sink=audit_sink,
                    acceptance_sink=acceptance_sink,
                    operation_id=operation_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    observed_watering_at=None,
                    observed_idle_at=None,
                    refresh_error_count=refresh_error_count,
                    concurrent_watering_observed=concurrent_watering_observed,
                    detail_code="watering_not_observed_within_grace",
                )
                return

            await asyncio.sleep(SUPERVISED_OPERATION_OBSERVATION_INTERVAL_SECONDS)

        await _record_terminal(
            audit_sink=audit_sink,
            acceptance_sink=acceptance_sink,
            operation_id=operation_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            observed_watering_at=observed_watering_at,
            observed_idle_at=None,
            refresh_error_count=refresh_error_count,
            concurrent_watering_observed=concurrent_watering_observed,
            detail_code=(
                "completion_not_observed_within_grace"
                if observed_watering_at is not None
                else "watering_not_observed_within_grace"
            ),
        )
    finally:
        manager.mark_complete(operation_id)


async def _record_terminal(
    *,
    audit_sink: SupervisedOperationAuditSink,
    acceptance_sink: JsonlSupervisedOperationAcceptanceSink,
    operation_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    observed_watering_at: datetime | None,
    observed_idle_at: datetime | None,
    refresh_error_count: int,
    concurrent_watering_observed: bool,
    detail_code: str,
) -> None:
    now = datetime.now(UTC)
    terminal_audit_recorded = await audit_sink.async_record(
        build_audit_event(
            operation_id=operation_id,
            event_type="acceptance_terminal",
            recorded_at=now,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            detail_code=detail_code,
        )
    )
    record = build_acceptance_record(
        attempt_id=operation_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        requested_runtime_seconds=runtime_seconds,
        observed_watering_at=observed_watering_at,
        observed_idle_at=observed_idle_at,
        refresh_error_count=refresh_error_count,
        concurrent_watering_observed=concurrent_watering_observed,
        terminal_detail_code=detail_code,
        terminal_audit_recorded=terminal_audit_recorded,
    )
    await acceptance_sink.async_record(record)


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
