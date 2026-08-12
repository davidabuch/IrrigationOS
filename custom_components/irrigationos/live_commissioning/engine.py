"""Fail-closed manual commissioning protocol without controller actuation."""

from __future__ import annotations

from datetime import datetime

from .models import (
    APPROVAL_TTL_SECONDS,
    MAX_FIRST_LIVE_RUNTIME_SECONDS,
    REQUIRED_FIRST_LIVE_ACCEPTANCE_EVIDENCE,
    FirstLiveTrialApproval,
    LiveCommissioningStatus,
    LiveCommissioningSummary,
)

LIVE_COMMISSIONING_PROTOCOL_REVISION = 1
MAX_COMMISSIONING_OBSERVATION_AGE_SECONDS = 120.0


def build_live_commissioning_summary(
    *,
    integrated_review_status: str,
    approval: FirstLiveTrialApproval | None,
    evaluated_at: datetime,
    health_state: str,
    observation_age_seconds: float | None,
    active_external_watering_count: int,
    commissioning_window_open: bool,
) -> LiveCommissioningSummary:
    """Evaluate one bounded supervised trial while preserving zero dispatch capability."""

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    blockers: set[str] = set()
    if integrated_review_status != "validated_review_eligible":
        blockers.add("integrated_safety_review_not_eligible")
    if health_state != "healthy":
        blockers.add("system_not_healthy")
    if observation_age_seconds is None:
        blockers.add("observation_freshness_unknown")
    elif observation_age_seconds > MAX_COMMISSIONING_OBSERVATION_AGE_SECONDS:
        blockers.add("observation_not_fresh_enough_for_commissioning")
    if active_external_watering_count > 0:
        blockers.add("external_watering_active")
    if not commissioning_window_open:
        blockers.add("supervised_commissioning_window_not_open")

    if approval is None:
        blockers.add("explicit_operator_approval_required")
    else:
        if approval.consumed:
            blockers.add("operator_approval_already_consumed")
        if evaluated_at > approval.expires_at:
            blockers.add("operator_approval_expired")
        if approval.controller_slot <= 0:
            blockers.add("target_controller_slot_invalid")
        if approval.area_slot <= 0:
            blockers.add("target_area_slot_invalid")
        if not 1 <= approval.requested_runtime_seconds <= MAX_FIRST_LIVE_RUNTIME_SECONDS:
            blockers.add("requested_runtime_outside_first_live_limit")
        if not approval.supervised_daytime:
            blockers.add("supervised_daytime_required")

    if not blockers and approval is not None:
        status = LiveCommissioningStatus.FIRST_LIVE_TRIAL_ELIGIBLE
    elif approval is None and blockers == {"explicit_operator_approval_required"}:
        status = LiveCommissioningStatus.OPERATOR_APPROVAL_REQUIRED
    else:
        status = LiveCommissioningStatus.BLOCKED

    return LiveCommissioningSummary(
        status=status,
        integrated_review_status=integrated_review_status,
        blocker_codes=tuple(sorted(blockers)),
        operator_approval_present=approval is not None,
        approval_expires_at=None if approval is None else approval.expires_at,
        approval_consumed=False if approval is None else approval.consumed,
        target_controller_slot=None if approval is None else approval.controller_slot,
        target_area_slot=None if approval is None else approval.area_slot,
        requested_runtime_seconds=(
            None if approval is None else approval.requested_runtime_seconds
        ),
        max_runtime_seconds=MAX_FIRST_LIVE_RUNTIME_SECONDS,
        supervised_daytime=False if approval is None else approval.supervised_daytime,
        commissioning_window_open=commissioning_window_open,
        health_state=health_state,
        observation_age_seconds=observation_age_seconds,
        active_external_watering_count=max(0, active_external_watering_count),
        approval_ttl_seconds=APPROVAL_TTL_SECONDS,
        single_use_approval=True,
        approval_persists_across_restart=False,
        required_acceptance_evidence=REQUIRED_FIRST_LIVE_ACCEPTANCE_EVIDENCE,
        first_live_trial_dispatch_enabled=False,
        live_mode_commissionable=False,
        live_control_feature_enabled=False,
        live_control_authorized=False,
    )
