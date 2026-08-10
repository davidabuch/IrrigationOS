"""Contracts for explicit controller ownership commissioning evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

OWNERSHIP_COMMISSIONING_SCHEMA_VERSION = 1


class OwnershipCommissioningStatus(StrEnum):
    """Operator-facing commissioning state."""

    UNCOMMISSIONED = "uncommissioned"
    OWNERSHIP_CONFIRMED = "ownership_confirmed"
    BOUNDARY_REVIEW_ACKNOWLEDGED = "boundary_review_acknowledged"
    STALE_TOPOLOGY = "stale_topology"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class OwnershipCommissioningSummary:
    """Derived ownership and execution-boundary review evidence."""

    status: OwnershipCommissioningStatus
    controller_count: int
    commissioned_controller_count: int
    topology_matches: bool
    ownership_confirmed: bool
    boundary_review_acknowledged: bool
    confirmed_at: datetime | None
    boundary_reviewed_at: datetime | None
    revoked_at: datetime | None
    commissioning_revision: int
    persistence_policy: str = "explicit_operator_decision_only"
    live_control_feature_enabled: bool = False
    live_control_authorized: bool = False
    schema_version: int = OWNERSHIP_COMMISSIONING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        for field in ("confirmed_at", "boundary_reviewed_at", "revoked_at"):
            value = getattr(self, field)
            payload[field] = None if value is None else value.isoformat()
        return payload
