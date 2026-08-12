"""Contracts for bounded first-live commissioning eligibility."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

LIVE_COMMISSIONING_SCHEMA_VERSION = 1
MAX_FIRST_LIVE_RUNTIME_SECONDS = 120
APPROVAL_TTL_SECONDS = 600

REQUIRED_FIRST_LIVE_ACCEPTANCE_EVIDENCE = (
    "command_intent_recorded",
    "operator_approval_recorded",
    "preflight_target_observed",
    "start_acknowledged",
    "target_watering_observed",
    "runtime_within_ceiling",
    "stop_acknowledged",
    "no_safety_preemption",
    "no_external_watering_displaced",
    "post_run_reconciliation_passed",
)


class LiveCommissioningStatus(StrEnum):
    """Manual first-live commissioning state; never controller authorization."""

    BLOCKED = "blocked"
    OPERATOR_APPROVAL_REQUIRED = "operator_approval_required"
    FIRST_LIVE_TRIAL_ELIGIBLE = "first_live_trial_eligible"


@dataclass(frozen=True, slots=True)
class FirstLiveTrialApproval:
    """Ephemeral single-use operator approval for one bounded trial target."""

    controller_id: str
    controller_slot: int
    area_slot: int
    requested_runtime_seconds: int
    approved_at: datetime
    expires_at: datetime
    supervised_daytime: bool
    consumed: bool = False


@dataclass(frozen=True, slots=True)
class LiveCommissioningSummary:
    """Fail-closed evidence for a future supervised first-live trial."""

    status: LiveCommissioningStatus
    integrated_review_status: str
    evaluated_at: datetime
    blocker_codes: tuple[str, ...]
    operator_approval_present: bool
    approval_expires_at: datetime | None
    approval_consumed: bool
    target_controller_id: str | None
    target_controller_slot: int | None
    target_area_slot: int | None
    requested_runtime_seconds: int | None
    max_runtime_seconds: int
    supervised_daytime: bool
    commissioning_window_open: bool
    health_state: str
    observation_age_seconds: float | None
    active_external_watering_count: int
    approval_ttl_seconds: int
    single_use_approval: bool
    approval_persists_across_restart: bool
    required_acceptance_evidence: tuple[str, ...]
    first_live_trial_dispatch_enabled: bool = False
    live_mode_commissionable: bool = False
    live_control_feature_enabled: bool = False
    live_control_authorized: bool = False
    schema_version: int = LIVE_COMMISSIONING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic operator-safe commissioning evidence."""

        payload = asdict(self)
        payload["status"] = self.status.value
        payload["evaluated_at"] = self.evaluated_at.isoformat()
        payload["approval_expires_at"] = (
            None if self.approval_expires_at is None else self.approval_expires_at.isoformat()
        )
        return payload
