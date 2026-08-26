"""Strict manual boundary for a three-minute commissioning observation."""

from __future__ import annotations

from datetime import UTC, datetime
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
    GuidedObservationStatus,
)


async def async_start_guided_observation(
    coordinator: Any, *, controller_slot: int, area_slot: int
) -> GuidedObservationResult:
    """Start one selected area after a fresh fail-closed preflight."""
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
        coordinator.guided_observation.mark_starting(controller_slot, area_slot)
        try:
            await adapter.async_start_guided_observation(
                area_binding=area.binding,
                duration_seconds=GUIDED_OBSERVATION_DURATION_SECONDS,
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
        try:
            await coordinator.async_request_refresh()
        except Exception:
            return _result(GuidedObservationStatus.UNCERTAIN, controller_slot, area_slot,
                           ("post_start_observation_failed",))
        if coordinator.guided_observation.snapshot.state.value != "running":
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
        try:
            await coordinator.async_request_refresh()
        except Exception:
            return _result(GuidedObservationStatus.UNCERTAIN, controller_slot, area_slot,
                           ("post_stop_observation_failed",))
        if coordinator.guided_observation.snapshot.state.value != "completed":
            coordinator.guided_observation.mark_uncertain("stop_not_observed")
            return _result(
                GuidedObservationStatus.UNCERTAIN,
                controller_slot,
                area_slot,
                ("stop_not_observed",),
            )
        return _result(GuidedObservationStatus.ACCEPTED, controller_slot, area_slot)


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
