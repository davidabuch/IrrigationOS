"""Deterministic fail-closed Live-mode safety architecture assessment."""

from __future__ import annotations

from .models import LiveModeSafetyStatus, LiveModeSafetySummary

LIVE_MODE_SAFETY_ARCHITECTURE_REVISION = 3

# These safeguards deliberately remain false until separately implemented and validated.
_REQUIRED_SAFEGUARDS = {
    "command_attribution_and_receipts": True,
    "acknowledgement_and_timeout_handling": True,
    "restart_safe_command_reconciliation": False,
    "safety_preemption_path": False,
    "sunrise_hard_stop": False,
    "manual_override_preservation": False,
}


def build_live_mode_safety_summary(
    *,
    readiness_status: str,
    execution_authorization_status: str,
    ownership_confirmed: bool,
    boundary_review_acknowledged: bool,
) -> LiveModeSafetySummary:
    """Assess whether the separate Live-mode safety architecture is complete."""

    prerequisites = {
        "control_readiness_criteria_met": readiness_status == "criteria_met",
        "execution_authorization_review_eligible": (
            execution_authorization_status == "manual_review_eligible"
        ),
        "controller_ownership_confirmed": bool(ownership_confirmed),
        "execution_boundary_review_acknowledged": bool(boundary_review_acknowledged),
    }
    safeguards = dict(_REQUIRED_SAFEGUARDS)
    blockers = tuple(
        sorted(
            [name for name, passed in prerequisites.items() if not passed]
            + [name for name, passed in safeguards.items() if not passed]
        )
    )

    if not all(prerequisites.values()):
        status = LiveModeSafetyStatus.PREREQUISITES_INCOMPLETE
    elif not all(safeguards.values()):
        status = LiveModeSafetyStatus.ARCHITECTURE_INCOMPLETE
    else:
        status = LiveModeSafetyStatus.ARCHITECTURE_REVIEW_ELIGIBLE

    return LiveModeSafetySummary(
        status=status,
        prerequisite_gates=prerequisites,
        safeguard_gates=safeguards,
        blocker_codes=blockers,
        prerequisites_met_count=sum(prerequisites.values()),
        prerequisites_total_count=len(prerequisites),
        safeguards_met_count=sum(safeguards.values()),
        safeguards_total_count=len(safeguards),
        architecture_revision=LIVE_MODE_SAFETY_ARCHITECTURE_REVISION,
        commissioning_policy="separate_manual_safety_review_required",
        live_mode_commissionable=False,
        live_control_feature_enabled=False,
        live_control_authorized=False,
    )
