"""Transient lifecycle owner for guided observation state."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from ..controllers import ControllerRegistrySnapshot, IrrigationAreaState
from .models import (
    GUIDED_OBSERVATION_DURATION_SECONDS,
    GuidedObservationSnapshot,
    GuidedObservationState,
)


class GuidedObservationManager:
    """Own one non-restored, non-retrying operator observation."""

    def __init__(self) -> None:
        self.snapshot = GuidedObservationSnapshot()

    @property
    def in_progress(self) -> bool:
        """Return whether local state is awaiting a terminal observation."""
        return self.snapshot.state in {
            GuidedObservationState.STARTING,
            GuidedObservationState.RUNNING,
            GuidedObservationState.STOPPING,
            GuidedObservationState.UNCERTAIN,
        }

    def mark_starting(
        self,
        controller_slot: int,
        area_slot: int,
        duration_seconds: int = GUIDED_OBSERVATION_DURATION_SECONDS,
    ) -> None:
        now = datetime.now(UTC)
        self.snapshot = GuidedObservationSnapshot(
            state=GuidedObservationState.STARTING,
            controller_slot=controller_slot,
            area_slot=area_slot,
            requested_duration_seconds=duration_seconds,
            requested_at=now,
            expected_stop_at=now + timedelta(seconds=duration_seconds),
        )

    def mark_stopping(self) -> None:
        self.snapshot = replace(self.snapshot, state=GuidedObservationState.STOPPING)

    def mark_failed(self, reason: str) -> None:
        self.snapshot = replace(
            self.snapshot, state=GuidedObservationState.FAILED, failure_reason=reason
        )

    def mark_uncertain(self, reason: str) -> None:
        """Record that transport or observation cannot prove physical state."""
        self.snapshot = replace(
            self.snapshot, state=GuidedObservationState.UNCERTAIN, failure_reason=reason
        )

    def reconcile(self, registry: ControllerRegistrySnapshot) -> None:
        """Reconcile accepted transport with current observed state only."""
        current = self.snapshot
        if current.controller_slot is None or current.area_slot is None:
            return
        controller = (
            registry.controllers[current.controller_slot - 1]
            if 1 <= current.controller_slot <= len(registry.controllers)
            else None
        )
        area = None if controller is None else next(
            (item for item in controller.areas if item.slot_number == current.area_slot), None
        )
        if area is None or area.state is IrrigationAreaState.UNKNOWN:
            self.snapshot = replace(current, state=GuidedObservationState.UNCERTAIN)
        elif area.state is IrrigationAreaState.WATERING:
            self.snapshot = replace(
                current,
                state=GuidedObservationState.RUNNING,
                started_at=current.started_at or registry.observation.observed_at,
            )
        elif current.state in {
            GuidedObservationState.RUNNING,
            GuidedObservationState.STOPPING,
        }:
            self.snapshot = replace(
                current,
                state=GuidedObservationState.COMPLETED,
                stopped_at=registry.observation.observed_at,
            )

    def diagnostics(self) -> dict[str, object]:
        return {
            "state": self.snapshot.state.value,
            "controller_slot": self.snapshot.controller_slot,
            "area_slot": self.snapshot.area_slot,
            "requested_duration_seconds": self.snapshot.requested_duration_seconds,
            "failure_reason": self.snapshot.failure_reason,
            "operator_initiated": True,
            "persists_across_restart": False,
            "execution_authorized": False,
            "live_control_authorized": False,
        }
