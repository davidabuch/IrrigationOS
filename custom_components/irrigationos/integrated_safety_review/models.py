"""Contracts for integrated six-safeguard commissioning validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

INTEGRATED_SAFETY_REVIEW_SCHEMA_VERSION = 1


class IntegratedSafetyReviewStatus(StrEnum):
    """Integrated safety-review state; never live-control permission."""

    BLOCKED = "blocked"
    VALIDATED_REVIEW_ELIGIBLE = "validated_review_eligible"


@dataclass(frozen=True, slots=True)
class IntegratedSafetyReviewSummary:
    """Deterministic evidence that the six-safeguard architecture was reviewed together."""

    status: IntegratedSafetyReviewStatus
    live_mode_safety_status: str
    validation_scenarios: dict[str, bool]
    validation_passed_count: int
    validation_total_count: int
    blocker_codes: tuple[str, ...]
    safeguards_implemented_count: int
    safeguards_total_count: int
    integrated_validation_complete: bool
    commissioning_policy: str
    live_mode_commissionable: bool = False
    live_control_feature_enabled: bool = False
    live_control_authorized: bool = False
    schema_version: int = INTEGRATED_SAFETY_REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic operator-safe review evidence."""

        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
