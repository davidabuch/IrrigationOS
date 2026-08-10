"""Deterministic fail-closed execution authorization safety gates."""

from __future__ import annotations

from datetime import datetime

from ..health import STALE_OBSERVATION_THRESHOLD
from .models import ExecutionAuthorizationStatus, ExecutionAuthorizationSummary

MAX_OBSERVATION_AGE_SECONDS = int(STALE_OBSERVATION_THRESHOLD.total_seconds())
MAX_SINGLE_COMMAND_RUNTIME_SECONDS = 60 * 60


def build_execution_authorization_summary(
    *,
    evaluated_at: datetime,
    health_state: str,
    observation_age_seconds: int | None,
    controller_count: int,
    online_controller_count: int,
    pipeline_available: bool,
    readiness_status: str,
    ownership_confirmed: bool,
    boundary_review_acknowledged: bool,
    active_watering_session_count: int,
    candidate_runtime_seconds: int | None = None,
) -> ExecutionAuthorizationSummary:
    """Evaluate safety prerequisites without ever enabling live control."""

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    if controller_count < 0 or online_controller_count < 0:
        raise ValueError("controller counts cannot be negative")
    if online_controller_count > controller_count:
        raise ValueError("online controller count cannot exceed controller count")
    if active_watering_session_count < 0:
        raise ValueError("active watering session count cannot be negative")
    if candidate_runtime_seconds is not None and candidate_runtime_seconds <= 0:
        raise ValueError("candidate_runtime_seconds must be positive when provided")

    gates = {
        "control_readiness_criteria_met": readiness_status == "criteria_met",
        "system_health_healthy": health_state == "HEALTHY",
        "observation_fresh": (
            observation_age_seconds is not None
            and 0 <= observation_age_seconds <= MAX_OBSERVATION_AGE_SECONDS
        ),
        "controllers_fully_available": (
            controller_count > 0 and online_controller_count == controller_count
        ),
        "pipeline_available": bool(pipeline_available),
        "controller_ownership_confirmed": bool(ownership_confirmed),
        "execution_boundary_review_acknowledged": bool(boundary_review_acknowledged),
        "no_active_watering_conflict": active_watering_session_count == 0,
        "candidate_runtime_within_limit": (
            candidate_runtime_seconds is None
            or candidate_runtime_seconds <= MAX_SINGLE_COMMAND_RUNTIME_SECONDS
        ),
    }
    blockers = tuple(sorted(name for name, passed in gates.items() if not passed))
    status = (
        ExecutionAuthorizationStatus.MANUAL_REVIEW_ELIGIBLE
        if not blockers
        else ExecutionAuthorizationStatus.BLOCKED
    )
    return ExecutionAuthorizationSummary(
        status=status,
        evaluated_at=evaluated_at,
        gates=gates,
        blocker_codes=blockers,
        criteria_met_count=sum(gates.values()),
        criteria_total_count=len(gates),
        observation_age_seconds=observation_age_seconds,
        controller_count=controller_count,
        online_controller_count=online_controller_count,
        active_watering_session_count=active_watering_session_count,
        candidate_runtime_seconds=candidate_runtime_seconds,
        maximum_single_command_runtime_seconds=MAX_SINGLE_COMMAND_RUNTIME_SECONDS,
        ownership_state="confirmed" if ownership_confirmed else "uncommissioned",
        manual_review_state=(
            "acknowledged" if boundary_review_acknowledged else "required"
        ),
        restart_policy="fail_closed_recompute_required",
        live_control_feature_enabled=False,
        live_control_authorized=False,
        positive_authorization_persisted=False,
    )
