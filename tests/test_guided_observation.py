"""Regression tests for bounded operator-directed zone observation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from custom_components.irrigationos.controllers import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerProviderError,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
    ObservationMetadata,
    ObservationQuality,
    VendorBinding,
)
from custom_components.irrigationos.guided_observation import (
    GUIDED_OBSERVATION_DURATION_SECONDS,
    ZONE_IDENTIFICATION_DURATION_SECONDS,
    GuidedObservationManager,
    GuidedObservationState,
    async_start_guided_observation,
    async_stop_guided_observation,
)
from custom_components.irrigationos.health import IrrigationOSHealthState

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def _snapshot(state: IrrigationAreaState) -> ControllerRegistrySnapshot:
    observed_at = datetime.now(UTC)
    area = IrrigationArea(
        "area.1.1", "controller.1", 1, "Zone 1", True, True, state,
        VendorBinding("rachio", "private-zone"),
    )
    controller = IrrigationController(
        "controller.1", VendorBinding("rachio", "private-controller"), "Controller",
        ControllerAvailability.ONLINE, True, None, None, None, None, None, 16,
        ObservationQuality.CONFIRMED,
        ControllerCapabilities(supports_start_area=True, supports_stop_all=True),
        (area,),
    )
    return ControllerRegistrySnapshot(
        "rachio", "private-account", None, (controller,),
        ObservationMetadata(
            observed_at,
            observed_at + timedelta(hours=1),
            "test",
            ObservationQuality.CONFIRMED,
        ),
    )


class _Adapter:
    provider = "rachio"

    def __init__(self) -> None:
        self.starts: list[tuple[str, int]] = []
        self.stops: list[str] = []
        self.fail_start = False
        self.fail_stop = False

    async def async_start_guided_observation(
        self, *, area_binding: VendorBinding, duration_seconds: int
    ) -> None:
        self.starts.append((area_binding.native_id, duration_seconds))
        if self.fail_start:
            raise ControllerProviderError("synthetic start failure")

    async def async_stop_guided_observation(
        self, *, controller_binding: VendorBinding
    ) -> None:
        self.stops.append(controller_binding.native_id)
        if self.fail_stop:
            raise ControllerProviderError("synthetic stop failure")


def _coordinator(states: list[IrrigationAreaState]) -> SimpleNamespace:
    adapter = _Adapter()
    coordinator = SimpleNamespace(
        data=_snapshot(states[0]),
        adapter=adapter,
        health_assessment=SimpleNamespace(state=IrrigationOSHealthState.HEALTHY),
        supervised_operation=SimpleNamespace(
            dispatch_lock=asyncio.Lock(), in_progress=False
        ),
        unattended_canary=SimpleNamespace(in_progress=False),
        guided_observation=GuidedObservationManager(),
    )

    async def refresh() -> None:
        if len(states) > 1:
            states.pop(0)
        coordinator.data = _snapshot(states[0])
        coordinator.guided_observation.reconcile(coordinator.data)

    coordinator.async_request_refresh = refresh
    return coordinator


@pytest.mark.asyncio
async def test_guided_observation_is_explicit_bounded_repeatable_and_stoppable() -> None:
    states = [
        IrrigationAreaState.IDLE,
        IrrigationAreaState.IDLE,
        IrrigationAreaState.WATERING,
    ]
    coordinator = _coordinator(states)
    result = await async_start_guided_observation(
        coordinator, controller_slot=1, area_slot=1
    )
    assert result.status.value == "accepted"
    assert coordinator.adapter.starts == [
        ("private-zone", GUIDED_OBSERVATION_DURATION_SECONDS)
    ]
    assert coordinator.guided_observation.snapshot.state is GuidedObservationState.RUNNING
    assert (
        coordinator.guided_observation.snapshot.requested_duration_seconds
        == GUIDED_OBSERVATION_DURATION_SECONDS
    )
    assert coordinator.guided_observation.snapshot.expected_stop_at is not None
    assert coordinator.guided_observation.snapshot.requested_at is not None
    assert (
        coordinator.guided_observation.snapshot.expected_stop_at
        - coordinator.guided_observation.snapshot.requested_at
    ) == timedelta(seconds=GUIDED_OBSERVATION_DURATION_SECONDS)
    assert not coordinator.guided_observation.snapshot.execution_authorized
    assert not coordinator.guided_observation.snapshot.live_control_authorized

    states[0] = IrrigationAreaState.IDLE
    coordinator.data = _snapshot(IrrigationAreaState.IDLE)
    result = await async_stop_guided_observation(
        coordinator, controller_slot=1, area_slot=1
    )
    assert result.status.value == "accepted"
    assert coordinator.adapter.stops == ["private-controller"]


@pytest.mark.asyncio
async def test_zone_identification_dispatches_and_records_exactly_30_seconds() -> None:
    coordinator = _coordinator(
        [IrrigationAreaState.IDLE, IrrigationAreaState.IDLE, IrrigationAreaState.WATERING]
    )
    result = await async_start_guided_observation(
        coordinator,
        controller_slot=1,
        area_slot=1,
        duration_seconds=ZONE_IDENTIFICATION_DURATION_SECONDS,
    )

    assert result.status.value == "accepted"
    assert coordinator.adapter.starts == [
        ("private-zone", ZONE_IDENTIFICATION_DURATION_SECONDS)
    ]
    snapshot = coordinator.guided_observation.snapshot
    assert snapshot.requested_duration_seconds == ZONE_IDENTIFICATION_DURATION_SECONDS
    assert snapshot.requested_at is not None
    assert snapshot.expected_stop_at is not None
    assert snapshot.expected_stop_at - snapshot.requested_at == timedelta(seconds=30)
    assert coordinator.guided_observation.diagnostics()[
        "requested_duration_seconds"
    ] == ZONE_IDENTIFICATION_DURATION_SECONDS


@pytest.mark.asyncio
async def test_invalid_guided_observation_duration_blocks_before_dispatch() -> None:
    coordinator = _coordinator([IrrigationAreaState.IDLE])

    blocked = await async_start_guided_observation(
        coordinator,
        controller_slot=1,
        area_slot=1,
        duration_seconds=GUIDED_OBSERVATION_DURATION_SECONDS + 1,
    )

    assert blocked.status.value == "blocked"
    assert blocked.blocker_codes == ("guided_observation_duration_invalid",)
    assert coordinator.adapter.starts == []
    assert coordinator.guided_observation.snapshot.state is GuidedObservationState.IDLE


@pytest.mark.asyncio
async def test_guided_observation_wrong_zone_and_active_watering_fail_closed() -> None:
    coordinator = _coordinator([IrrigationAreaState.WATERING])
    blocked = await async_start_guided_observation(
        coordinator, controller_slot=1, area_slot=1
    )
    assert "active_watering_conflict" in blocked.blocker_codes
    assert coordinator.adapter.starts == []
    coordinator.guided_observation.mark_starting(1, 1)
    wrong_stop = await async_stop_guided_observation(
        coordinator, controller_slot=1, area_slot=2
    )
    assert wrong_stop.blocker_codes == ("guided_observation_target_mismatch",)


def test_guided_observation_restart_restores_no_authority_or_task() -> None:
    manager = GuidedObservationManager()
    manager.mark_starting(1, 1)
    restarted = GuidedObservationManager()
    assert restarted.snapshot.state is GuidedObservationState.IDLE
    assert not restarted.in_progress


@pytest.mark.asyncio
async def test_transport_failures_are_uncertain_and_never_retried() -> None:
    coordinator = _coordinator([IrrigationAreaState.IDLE, IrrigationAreaState.IDLE])
    coordinator.adapter.fail_start = True
    failed_start = await async_start_guided_observation(
        coordinator, controller_slot=1, area_slot=1
    )
    assert failed_start.status.value == "uncertain"
    assert len(coordinator.adapter.starts) == 1
    assert coordinator.guided_observation.snapshot.state is GuidedObservationState.UNCERTAIN

    coordinator.adapter.fail_start = False
    coordinator.adapter.fail_stop = True
    failed_stop = await async_stop_guided_observation(
        coordinator, controller_slot=1, area_slot=1
    )
    assert failed_stop.status.value == "uncertain"
    assert len(coordinator.adapter.stops) == 1
