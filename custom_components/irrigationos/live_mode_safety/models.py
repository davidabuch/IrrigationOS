"""Contracts for pre-Live safety architecture evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

LIVE_MODE_SAFETY_SCHEMA_VERSION = 1


class LiveModeSafetyStatus(StrEnum):
    """Safety architecture state; never live-control permission."""

    PREREQUISITES_INCOMPLETE = "prerequisites_incomplete"
    ARCHITECTURE_INCOMPLETE = "architecture_incomplete"
    ARCHITECTURE_REVIEW_ELIGIBLE = "architecture_review_eligible"


@dataclass(frozen=True, slots=True)
class LiveModeSafetySummary:
    """Deterministic evidence for the pre-Live safety boundary."""

    status: LiveModeSafetyStatus
    prerequisite_gates: dict[str, bool]
    safeguard_gates: dict[str, bool]
    blocker_codes: tuple[str, ...]
    prerequisites_met_count: int
    prerequisites_total_count: int
    safeguards_met_count: int
    safeguards_total_count: int
    architecture_revision: int
    commissioning_policy: str
    live_mode_commissionable: bool = False
    live_control_feature_enabled: bool = False
    live_control_authorized: bool = False
    schema_version: int = LIVE_MODE_SAFETY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
