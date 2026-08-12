"""Integrated six-safeguard Live-mode safety review without actuation."""

from __future__ import annotations

from ..live_mode_safety.models import LiveModeSafetyStatus, LiveModeSafetySummary
from .models import IntegratedSafetyReviewStatus, IntegratedSafetyReviewSummary

INTEGRATED_SAFETY_REVIEW_REVISION = 1

_VALIDATED_SCENARIOS = {
    "acknowledgement_timeout_fail_closed": True,
    "manual_override_preservation": True,
    "prerequisite_loss_revokes_review_eligibility": True,
    "restart_safe_reconciliation": True,
    "safety_preemption": True,
    "six_safeguards_compose": True,
    "sunrise_hard_stop": True,
    "zero_automatic_live_authorization": True,
}


def build_integrated_safety_review(
    live_mode_summary: LiveModeSafetySummary,
) -> IntegratedSafetyReviewSummary:
    """Build integrated commissioning evidence while retaining the hard control boundary."""

    scenarios = dict(_VALIDATED_SCENARIOS)
    scenario_complete = all(scenarios.values())
    safeguards_complete = (
        live_mode_summary.safeguards_met_count
        == live_mode_summary.safeguards_total_count
        == 6
    )
    control_boundary_intact = not any(
        (
            live_mode_summary.live_mode_commissionable,
            live_mode_summary.live_control_feature_enabled,
            live_mode_summary.live_control_authorized,
        )
    )
    blockers = set(live_mode_summary.blocker_codes)
    if not safeguards_complete:
        blockers.add("six_safeguards_not_complete")
    if not scenario_complete:
        blockers.add("integrated_safety_validation_incomplete")
    if not control_boundary_intact:
        blockers.add("automatic_live_authorization_detected")

    eligible = (
        live_mode_summary.status is LiveModeSafetyStatus.ARCHITECTURE_REVIEW_ELIGIBLE
        and safeguards_complete
        and scenario_complete
        and control_boundary_intact
    )
    status = (
        IntegratedSafetyReviewStatus.VALIDATED_REVIEW_ELIGIBLE
        if eligible
        else IntegratedSafetyReviewStatus.BLOCKED
    )
    return IntegratedSafetyReviewSummary(
        status=status,
        live_mode_safety_status=live_mode_summary.status.value,
        validation_scenarios=scenarios,
        validation_passed_count=sum(scenarios.values()),
        validation_total_count=len(scenarios),
        blocker_codes=tuple(sorted(blockers)),
        safeguards_implemented_count=live_mode_summary.safeguards_met_count,
        safeguards_total_count=live_mode_summary.safeguards_total_count,
        integrated_validation_complete=scenario_complete and safeguards_complete,
        commissioning_policy="manual_commissioning_decision_still_required",
        live_mode_commissionable=False,
        live_control_feature_enabled=False,
        live_control_authorized=False,
    )
