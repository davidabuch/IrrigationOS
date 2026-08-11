"""Deterministic fail-closed safety preemption evaluation without dispatch."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import SafetyPreemptionEvent, SafetyPreemptionReason


def evaluate_preemption_reasons(
    *,
    health_state: str,
    observation_age_seconds: float | None,
    observation_stale_after_seconds: float,
    controller_available: bool,
    ownership_confirmed: bool,
    active_watering_conflict: bool,
    execution_authorization_status: str,
) -> tuple[str, ...]:
    """Return sorted canonical reasons requiring immediate fail-closed preemption."""

    reasons: list[str] = []
    if health_state != "healthy":
        reasons.append(SafetyPreemptionReason.SYSTEM_UNHEALTHY.value)
    if (
        observation_age_seconds is None
        or observation_age_seconds > observation_stale_after_seconds
    ):
        reasons.append(SafetyPreemptionReason.OBSERVATION_STALE.value)
    if not controller_available:
        reasons.append(SafetyPreemptionReason.CONTROLLER_UNAVAILABLE.value)
    if not ownership_confirmed:
        reasons.append(SafetyPreemptionReason.OWNERSHIP_NOT_CONFIRMED.value)
    if active_watering_conflict:
        reasons.append(SafetyPreemptionReason.ACTIVE_WATERING_CONFLICT.value)
    if execution_authorization_status != "manual_review_eligible":
        reasons.append(SafetyPreemptionReason.EXECUTION_NOT_REVIEW_ELIGIBLE.value)
    return tuple(sorted(reasons))


def build_preemption_event(
    *, command_id: str, evaluated_at: datetime, reason_codes: tuple[str, ...]
) -> SafetyPreemptionEvent:
    """Build immutable evidence for a required synthetic lifecycle preemption."""

    command_id = command_id.strip()
    if not command_id:
        raise ValueError("command_id_required")
    if not reason_codes:
        raise ValueError("preemption_reason_required")
    recorded_at = evaluated_at.astimezone(UTC)
    canonical_reasons = tuple(sorted(set(reason_codes)))
    seed = f"{command_id}|{recorded_at.isoformat()}|{'|'.join(canonical_reasons)}"
    event_id = hashlib.sha256(seed.encode()).hexdigest()
    return SafetyPreemptionEvent(
        event_id=event_id,
        command_id=command_id,
        evaluated_at_utc=recorded_at,
        reason_codes=canonical_reasons,
        detail_code="synthetic_command_lifecycle_preempted",
    )
