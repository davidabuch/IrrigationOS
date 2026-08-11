"""Contracts for non-actuating safety preemption evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

SAFETY_PREEMPTION_SCHEMA_VERSION = 1


class SafetyPreemptionReason(StrEnum):
    """Canonical fail-closed reasons that can preempt a future command lifecycle."""

    SYSTEM_UNHEALTHY = "system_unhealthy"
    OBSERVATION_STALE = "observation_stale"
    CONTROLLER_UNAVAILABLE = "controller_unavailable"
    OWNERSHIP_NOT_CONFIRMED = "ownership_not_confirmed"
    ACTIVE_WATERING_CONFLICT = "active_watering_conflict"
    EXECUTION_NOT_REVIEW_ELIGIBLE = "execution_not_review_eligible"


@dataclass(frozen=True, slots=True)
class SafetyPreemptionEvent:
    """Immutable evidence that a synthetic command lifecycle was preempted."""

    event_id: str
    command_id: str
    evaluated_at_utc: datetime
    reason_codes: tuple[str, ...]
    detail_code: str
    synthetic_only: bool = True
    dispatch_capability: bool = False
    schema_version: int = SAFETY_PREEMPTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe preemption evidence."""

        payload = asdict(self)
        payload["evaluated_at_utc"] = self.evaluated_at_utc.isoformat()
        return payload
