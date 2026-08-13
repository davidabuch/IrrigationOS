"""Asynchronous acceptance monitor for a supervised first-live watering trial."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ..controllers.models import (
    ControllerRegistrySnapshot,
    IrrigationAreaState,
    ObservationQuality,
)
from .acceptance import (
    FirstLiveAcceptanceManager,
    FirstLiveAcceptanceStatus,
    build_acceptance_record,
)
from .audit import FirstLiveTrialAuditSink, build_audit_event
from .validated_targets import ValidatedTargetRegistry

FIRST_LIVE_ACCEPTANCE_MONITOR_REVISION = 2
FIRST_LIVE_OBSERVATION_INTERVAL_SECONDS = 5
FIRST_LIVE_START_OBSERVATION_GRACE_SECONDS = 30
FIRST_LIVE_COMPLETION_GRACE_SECONDS = 45


class FirstLiveSnapshotRefresher(Protocol):
    """Minimal coordinator boundary required by the acceptance monitor."""

    data: ControllerRegistrySnapshot

    async def async_request_refresh(self) -> None:
        """Request one canonical controller refresh."""
        ...

    def async_update_listeners(self) -> None:
        """Publish updated acceptance evidence to Home Assistant entities."""
        ...

    def update_production_readiness(self, evaluated_at: datetime | None = None) -> None:
        """Recompute advisory readiness after terminal commissioning evidence."""
        ...


async def async_monitor_first_live_acceptance(
    *,
    coordinator: FirstLiveSnapshotRefresher,
    audit_sink: FirstLiveTrialAuditSink,
    acceptance: FirstLiveAcceptanceManager,
    validated_targets: ValidatedTargetRegistry,
    attempt_id: str,
    controller_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    dispatched_at: datetime,
) -> None:
    """Observe WATERING then IDLE and persist structured terminal evidence."""

    observed_watering_at: datetime | None = None
    refresh_error_count = 0
    concurrent_watering_observed = False
    start_deadline = dispatched_at + timedelta(
        seconds=FIRST_LIVE_START_OBSERVATION_GRACE_SECONDS
    )
    completion_deadline = dispatched_at + timedelta(
        seconds=runtime_seconds + FIRST_LIVE_COMPLETION_GRACE_SECONDS
    )

    while datetime.now(UTC) <= completion_deadline:
        try:
            await coordinator.async_request_refresh()
        except Exception:  # A later refresh may recover; terminal evidence remains fail-closed.
            refresh_error_count += 1
            await asyncio.sleep(FIRST_LIVE_OBSERVATION_INTERVAL_SECONDS)
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
                    attempt_id=attempt_id,
                    event_type="acceptance_observation",
                    recorded_at=now,
                    controller_id=controller_id,
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
                coordinator=coordinator,
                acceptance=acceptance,
                validated_targets=validated_targets,
                audit_sink=audit_sink,
                attempt_id=attempt_id,
                controller_id=controller_id,
                controller_slot=controller_slot,
                area_slot=area_slot,
                runtime_seconds=runtime_seconds,
                observed_watering_at=observed_watering_at,
                observed_idle_at=now,
                refresh_error_count=refresh_error_count,
                concurrent_watering_observed=concurrent_watering_observed,
                detail_code=(
                    "first_live_trial_rejected_concurrent_watering"
                    if concurrent_watering_observed
                    else "first_live_trial_accepted"
                ),
            )
            return

        if observed_watering_at is None and now > start_deadline:
            await _record_terminal(
                coordinator=coordinator,
                acceptance=acceptance,
                validated_targets=validated_targets,
                audit_sink=audit_sink,
                attempt_id=attempt_id,
                controller_id=controller_id,
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
        await asyncio.sleep(FIRST_LIVE_OBSERVATION_INTERVAL_SECONDS)

    await _record_terminal(
        coordinator=coordinator,
        acceptance=acceptance,
        validated_targets=validated_targets,
        audit_sink=audit_sink,
        attempt_id=attempt_id,
        controller_id=controller_id,
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


async def _record_terminal(
    *,
    coordinator: FirstLiveSnapshotRefresher,
    acceptance: FirstLiveAcceptanceManager,
    validated_targets: ValidatedTargetRegistry,
    audit_sink: FirstLiveTrialAuditSink,
    attempt_id: str,
    controller_id: str,
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
            attempt_id=attempt_id,
            event_type="acceptance_terminal",
            recorded_at=now,
            controller_id=controller_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            detail_code=detail_code,
        )
    )
    record = build_acceptance_record(
        attempt_id=attempt_id,
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
    acceptance_recorded = await acceptance.async_record(record)
    if acceptance_recorded and record.status is FirstLiveAcceptanceStatus.PASS:
        await validated_targets.async_register(record)
    coordinator.update_production_readiness(now)
    coordinator.async_update_listeners()


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
