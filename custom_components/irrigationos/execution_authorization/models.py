"""Contracts for fail-closed execution authorization evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

EXECUTION_AUTHORIZATION_SCHEMA_VERSION = 1


class ExecutionAuthorizationStatus(StrEnum):
    """Operator-facing authorization state; never a live command permission."""

    BLOCKED = "blocked"
    MANUAL_REVIEW_ELIGIBLE = "manual_review_eligible"


@dataclass(frozen=True, slots=True)
class ExecutionAuthorizationSummary:
    """Deterministic fail-closed safety-gate assessment."""

    status: ExecutionAuthorizationStatus
    evaluated_at: datetime
    gates: dict[str, bool]
    blocker_codes: tuple[str, ...]
    criteria_met_count: int
    criteria_total_count: int
    observation_age_seconds: int | None
    controller_count: int
    online_controller_count: int
    active_watering_session_count: int
    candidate_runtime_seconds: int | None
    maximum_single_command_runtime_seconds: int
    ownership_state: str
    manual_review_state: str
    restart_policy: str
    live_control_feature_enabled: bool = False
    live_control_authorized: bool = False
    positive_authorization_persisted: bool = False
    schema_version: int = EXECUTION_AUTHORIZATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible authorization evidence."""

        payload = asdict(self)
        payload["status"] = self.status.value
        payload["evaluated_at"] = self.evaluated_at.isoformat()
        return payload
