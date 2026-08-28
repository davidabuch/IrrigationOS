"""Immutable models for one transient guided observation run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

GUIDED_OBSERVATION_DURATION_SECONDS = 180
ZONE_IDENTIFICATION_DURATION_SECONDS = 30


class GuidedObservationState(StrEnum):
    """Locally known state; uncertain never implies stopped or running."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class GuidedObservationStatus(StrEnum):
    """Outcome of one explicit operator request."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class GuidedObservationResult:
    """Privacy-safe acknowledgement for an operator action."""

    status: GuidedObservationStatus
    controller_slot: int
    area_slot: int
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GuidedObservationSnapshot:
    """Transient coordinator-owned state; never persisted or restored."""

    state: GuidedObservationState = GuidedObservationState.IDLE
    controller_slot: int | None = None
    area_slot: int | None = None
    requested_duration_seconds: int = GUIDED_OBSERVATION_DURATION_SECONDS
    requested_at: datetime | None = None
    started_at: datetime | None = None
    expected_stop_at: datetime | None = None
    stopped_at: datetime | None = None
    failure_reason: str | None = None
    operator_initiated: bool = True
    execution_authorized: bool = False
    live_control_authorized: bool = False
