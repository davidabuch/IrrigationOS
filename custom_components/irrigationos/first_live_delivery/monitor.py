"""Asynchronous acceptance monitor for a supervised first-live watering trial."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ..controllers.models import ControllerRegistrySnapshot, IrrigationAreaState
from .audit import FirstLiveTrialAuditSink, build_audit_event

FIRST_LIVE_ACCEPTANCE_MONITOR_REVISION = 1
FIRST_LIVE_OBSERVATION_INTERVAL_SECONDS = 5
FIRST_LIVE_START_OBSERVATION_GRACE_SECONDS = 30
FIRST_LIVE_COMPLETION_GRACE_SECONDS = 45


class FirstLiveSnapshotRefresher(Protocol):
    """Minimal coordinator boundary required by the acceptance monitor."""

    data: ControllerRegistrySnapshot

    async def async_request_refresh(self) -> None:
        """Request one canonical controller refresh."""
        ...


async def async_monitor_first_live_acceptance(
    *,
    coordinator: FirstLiveSnapshotRefresher,
    audit_sink: FirstLiveTrialAuditSink,
    attempt_id: str,
    controller_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    dispatched_at: datetime,
) -> None:
    """Observe WATERING then IDLE and persist terminal acceptance evidence."""

    saw_watering = False
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
            await asyncio.sleep(FIRST_LIVE_OBSERVATION_INTERVAL_SECONDS)
            continue

        state = _target_state(coordinator.data, controller_id, area_slot)
        now = datetime.now(UTC)
        if state is IrrigationAreaState.WATERING and not saw_watering:
            saw_watering = True
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
        elif saw_watering and state is IrrigationAreaState.IDLE:
            await audit_sink.async_record(
                build_audit_event(
                    attempt_id=attempt_id,
                    event_type="acceptance_terminal",
                    recorded_at=now,
                    controller_id=controller_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    detail_code="first_live_trial_accepted",
                )
            )
            return

        if not saw_watering and now > start_deadline:
            await audit_sink.async_record(
                build_audit_event(
                    attempt_id=attempt_id,
                    event_type="acceptance_terminal",
                    recorded_at=now,
                    controller_id=controller_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    detail_code="watering_not_observed_within_grace",
                )
            )
            return
        await asyncio.sleep(FIRST_LIVE_OBSERVATION_INTERVAL_SECONDS)

    await audit_sink.async_record(
        build_audit_event(
            attempt_id=attempt_id,
            event_type="acceptance_terminal",
            recorded_at=datetime.now(UTC),
            controller_id=controller_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            detail_code=(
                "completion_not_observed_within_grace"
                if saw_watering
                else "watering_not_observed_within_grace"
            ),
        )
    )


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
