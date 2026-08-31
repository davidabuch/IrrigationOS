"""Strict manual boundary for a three-minute commissioning observation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from ..controllers import (
    ControllerAvailability,
    ControllerProviderError,
    GuidedObservationAdapter,
    IrrigationAreaState,
    ObservationQuality,
)
from ..health import IrrigationOSHealthState
from .models import (
    GUIDED_OBSERVATION_DURATION_SECONDS,
    GuidedObservationResult,
    GuidedObservationState,
    GuidedObservationStatus,
)

GUIDED_OBSERVATION_CONFIRMATION_TIMEOUT_SECONDS = 10
GUIDED_OBSERVATION_CONFIRMATION_INTERVAL_SECONDS = 1


async def async_start_guided_observation(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    duration_seconds: int = GUIDED_OBSERVATION_DURATION_SECONDS,
) -> GuidedObservationResult:
    """Start one selected area after a fresh fail-closed preflight."""
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, int)
        or not 1 <= duration_seconds <= GUIDED_OBSERVATION_DURATION_SECONDS
    ):
        return _result(
            GuidedObservationStatus.BLOCKED,
            controller_slot,
            area_slot,
            ("guided_observation_duration_invalid",),
        )
    async with coordinator.supervised_operation.dispatch_lock:
        try:
            await coordinator.async_request_refresh()
        except Exception:
            return _result(GuidedObservationStatus.BLOCKED, controller_slot, area_slot,
                           ("preflight_refresh_failed",))
        blockers = _start_blockers(coordinator, controller_slot, area_slot)
        if blockers:
            return _result(GuidedObservationStatus.BLOCKED, controller_slot, area_slot, blockers)
        _controller, area = _target(coordinator, controller_slot, area_slot)
        adapter = coordinator.adapter
        if not isinstance(adapter, GuidedObservationAdapter):
            return _result(GuidedObservationStatus.BLOCKED, controller_slot, area_slot,
                           ("guided_observation_not_supported",))
        coordinator.guided_observation.mark_starting(
            controller_slot, area_slot, duration_seconds
        )
        requested_at = coordinator.guided_observation.snapshot.requested_at
        assert requested_at is not None
        try:
            await adapter.async_start_guided_observation(
                area_binding=area.binding,
                duration_seconds=duration_seconds,
            )
        except (ControllerProviderError, TimeoutError, ValueError):
            coordinator.guided_observation.mark_uncertain(
                "start_transport_outcome_unknown_no_retry"
            )
            return _result(
                GuidedObservationStatus.UNCERTAIN,
                controller_slot,
                area_slot,
                ("start_transport_outcome_unknown_no_retry",),
            )
        if not await _async_confirm_guided_observation(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            expected_state=GuidedObservationState.RUNNING,
            observation_not_before=requested_at,
        ):
            coordinator.guided_observation.mark_uncertain("start_not_observed")
            return _result(
                GuidedObservationStatus.UNCERTAIN,
                controller_slot,
                area_slot,
                ("start_not_observed",),
            )
        return _result(GuidedObservationStatus.ACCEPTED, controller_slot, area_slot)


async def async_stop_guided_observation(
    coordinator: Any, *, controller_slot: int, area_slot: int
) -> GuidedObservationResult:
    """Stop the exact locally active observation; never retry automatically."""
    async with coordinator.supervised_operation.dispatch_lock:
        active = coordinator.guided_observation.snapshot
        if not coordinator.guided_observation.in_progress:
            return _result(
                GuidedObservationStatus.BLOCKED,
                controller_slot,
                area_slot,
                ("no_guided_observation_in_progress",),
            )
        if (active.controller_slot, active.area_slot) != (controller_slot, area_slot):
            return _result(GuidedObservationStatus.BLOCKED, controller_slot, area_slot,
                           ("guided_observation_target_mismatch",))
        controller, _area = _target(coordinator, controller_slot, area_slot)
        adapter = coordinator.adapter
        if not isinstance(adapter, GuidedObservationAdapter):
            return _result(GuidedObservationStatus.BLOCKED, controller_slot, area_slot,
                           ("guided_observation_not_supported",))
        stop_requested_at = datetime.now(UTC)
        coordinator.guided_observation.mark_stopping()
        try:
            await adapter.async_stop_guided_observation(
                controller_binding=controller.binding
            )
        except (ControllerProviderError, TimeoutError, ValueError):
            coordinator.guided_observation.mark_uncertain(
                "stop_transport_outcome_unknown_no_retry"
            )
            return _result(
                GuidedObservationStatus.UNCERTAIN,
                controller_slot,
                area_slot,
                ("stop_transport_outcome_unknown_no_retry",),
            )
        if not await _async_confirm_guided_observation(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            expected_state=GuidedObservationState.COMPLETED,
            observation_not_before=stop_requested_at,
        ):
            coordinator.guided_observation.mark_uncertain("stop_not_observed")
            return _result(
                GuidedObservationStatus.UNCERTAIN,
                controller_slot,
                area_slot,
                ("stop_not_observed",),
            )
        return _result(GuidedObservationStatus.ACCEPTED, controller_slot, area_slot)


async def _async_confirm_guided_observation(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    expected_state: GuidedObservationState,
    observation_not_before: datetime,
) -> bool:
    """Boundedly re-observe one dispatched command without retrying transport."""

    deadline = monotonic() + GUIDED_OBSERVATION_CONFIRMATION_TIMEOUT_SECONDS
    while True:
        if _guided_observation_confirmed(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            expected_state=expected_state,
            observation_not_before=observation_not_before,
        ):
            return True

        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        try:
            async with asyncio.timeout(remaining):
                await coordinator.async_request_refresh()
        except Exception:
            pass

        if _guided_observation_confirmed(
            coordinator,
            controller_slot=controller_slot,
            area_slot=area_slot,
            expected_state=expected_state,
            observation_not_before=observation_not_before,
        ):
            return True

        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        await asyncio.sleep(
            min(GUIDED_OBSERVATION_CONFIRMATION_INTERVAL_SECONDS, remaining)
        )


def _guided_observation_confirmed(
    coordinator: Any,
    *,
    controller_slot: int,
    area_slot: int,
    expected_state: GuidedObservationState,
    observation_not_before: datetime,
) -> bool:
    """Return whether fresh authoritative evidence proves the exact operation state."""

    current = coordinator.guided_observation.snapshot
    if (
        current.state is not expected_state
        or current.controller_slot != controller_slot
        or current.area_slot != area_slot
    ):
        return False
    registry = coordinator.data
    if (
        registry.observation.quality is not ObservationQuality.CONFIRMED
        or not registry.observation.is_fresh(datetime.now(UTC))
        or registry.observation.observed_at < observation_not_before
    ):
        return False
    try:
        controller, area = _target(coordinator, controller_slot, area_slot)
    except (IndexError, StopIteration):
        return False
    if controller.watering_observation_quality is not ObservationQuality.CONFIRMED:
        return False
    if expected_state is GuidedObservationState.RUNNING:
        return area.state is IrrigationAreaState.WATERING
    return area.state not in {
        IrrigationAreaState.WATERING,
        IrrigationAreaState.UNKNOWN,
    }


def _start_blockers(coordinator: Any, controller_slot: int, area_slot: int) -> tuple[str, ...]:
    blockers: set[str] = set()
    if coordinator.health_assessment.state is not IrrigationOSHealthState.HEALTHY:
        blockers.add("system_not_healthy")
    snapshot = coordinator.data
    if snapshot.observation.quality is not ObservationQuality.CONFIRMED:
        blockers.add("observation_not_confirmed")
    if not snapshot.observation.is_fresh(datetime.now(UTC)):
        blockers.add("observation_not_fresh")
    if coordinator.supervised_operation.in_progress:
        blockers.add("supervised_operation_in_progress")
    if coordinator.unattended_canary.in_progress:
        blockers.add("unattended_canary_in_progress")
    if coordinator.guided_observation.in_progress:
        blockers.add("guided_observation_in_progress")
    ownership = getattr(coordinator, "ownership_commissioning", None)
    if ownership is not None:
        if not ownership.summary.ownership_confirmed:
            blockers.add("controller_ownership_not_confirmed")
        if not ownership.summary.boundary_review_acknowledged:
            blockers.add("execution_boundary_review_not_acknowledged")
    if any(
        area.state is IrrigationAreaState.WATERING
        for controller in snapshot.controllers for area in controller.areas
    ):
        blockers.add("active_watering_conflict")
    try:
        controller, area = _target(coordinator, controller_slot, area_slot)
    except (IndexError, StopIteration):
        blockers.add("target_not_observed")
    else:
        if not controller.enabled or controller.availability is not ControllerAvailability.ONLINE:
            blockers.add("controller_not_available")
        if not area.configured or not area.enabled or area.binding is None:
            blockers.add("target_not_configured")
        elif area.state is not IrrigationAreaState.IDLE:
            blockers.add("target_not_idle")
    return tuple(sorted(blockers))


def _target(coordinator: Any, controller_slot: int, area_slot: int) -> tuple[Any, Any]:
    controller = coordinator.data.controllers[controller_slot - 1]
    area = next(item for item in controller.areas if item.slot_number == area_slot)
    return controller, area


def _result(status: GuidedObservationStatus, controller_slot: int, area_slot: int,
            blockers: tuple[str, ...] = ()) -> GuidedObservationResult:
    return GuidedObservationResult(status, controller_slot, area_slot, blockers)
