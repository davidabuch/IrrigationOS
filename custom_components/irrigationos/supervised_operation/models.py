"""Models for the bounded supervised operational watering path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SupervisedOperationStatus(StrEnum):
    """Outcome of one supervised operational dispatch attempt."""

    BLOCKED = "blocked"
    AUDIT_FAILED = "audit_failed"
    TRANSPORT_FAILED = "transport_failed"
    START_DISPATCHED = "start_dispatched"


@dataclass(frozen=True, slots=True)
class SupervisedOperationResult:
    """Privacy-safe result returned by the manual supervised command boundary."""

    status: SupervisedOperationStatus
    blocker_codes: tuple[str, ...]
    operation_id: str | None
    controller_slot: int
    area_slot: int
    runtime_seconds: int
