"""Tests for fail-closed execution authorization safety gates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tests.helpers import load_integration_module

execution_authorization = load_integration_module("execution_authorization")
authorization_manager = load_integration_module("execution_authorization.manager")
ExecutionAuthorizationStatus = execution_authorization.ExecutionAuthorizationStatus
ExecutionAuthorizationManager = authorization_manager.ExecutionAuthorizationManager
build_execution_authorization_summary = (
    execution_authorization.build_execution_authorization_summary
)

NOW = datetime(2026, 8, 10, 5, 0, tzinfo=UTC)


def _summary(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "evaluated_at": NOW,
        "health_state": "HEALTHY",
        "observation_age_seconds": 30,
        "controller_count": 1,
        "online_controller_count": 1,
        "pipeline_available": True,
        "readiness_status": "criteria_met",
        "ownership_confirmed": True,
        "boundary_review_acknowledged": True,
        "active_watering_session_count": 0,
        "candidate_runtime_seconds": 600,
    }
    values.update(overrides)
    return build_execution_authorization_summary(**values)


def test_all_prerequisites_only_make_manual_review_eligible() -> None:
    summary = _summary()

    assert summary.status is ExecutionAuthorizationStatus.MANUAL_REVIEW_ELIGIBLE
    assert summary.blocker_codes == ()
    assert summary.live_control_feature_enabled is False
    assert summary.live_control_authorized is False
    assert summary.positive_authorization_persisted is False
    assert summary.restart_policy == "fail_closed_recompute_required"


def test_stale_observation_blocks_authorization() -> None:
    summary = _summary(observation_age_seconds=721)

    assert summary.status is ExecutionAuthorizationStatus.BLOCKED
    assert "observation_fresh" in summary.blocker_codes


def test_unconfirmed_ownership_blocks_authorization() -> None:
    summary = _summary(ownership_confirmed=False)

    assert summary.status is ExecutionAuthorizationStatus.BLOCKED
    assert summary.ownership_state == "uncommissioned"
    assert "controller_ownership_confirmed" in summary.blocker_codes


def test_degraded_health_and_partial_controller_availability_block() -> None:
    summary = _summary(
        health_state="DEGRADED",
        controller_count=2,
        online_controller_count=1,
    )

    assert "system_health_healthy" in summary.blocker_codes
    assert "controllers_fully_available" in summary.blocker_codes


def test_active_watering_conflict_blocks_authorization() -> None:
    summary = _summary(active_watering_session_count=1)

    assert "no_active_watering_conflict" in summary.blocker_codes


def test_candidate_runtime_limit_is_explicit_and_fail_closed() -> None:
    summary = _summary(candidate_runtime_seconds=3601)

    assert summary.maximum_single_command_runtime_seconds == 3600
    assert "candidate_runtime_within_limit" in summary.blocker_codes


def test_missing_candidate_runtime_is_not_itself_a_blocker() -> None:
    summary = _summary(candidate_runtime_seconds=None)

    assert summary.gates["candidate_runtime_within_limit"] is True
    assert summary.live_control_authorized is False


def test_readiness_evidence_and_pipeline_are_required() -> None:
    summary = _summary(readiness_status="review_required", pipeline_available=False)

    assert "control_readiness_criteria_met" in summary.blocker_codes
    assert "pipeline_available" in summary.blocker_codes

def test_runtime_manager_starts_and_recomputes_fail_closed() -> None:
    manager = ExecutionAuthorizationManager()

    assert manager.summary.status is ExecutionAuthorizationStatus.BLOCKED
    assert manager.summary.live_control_authorized is False
    assert manager.summary.positive_authorization_persisted is False

    manager.consider(
        evaluated_at=NOW,
        health_state="HEALTHY",
        observation_age_seconds=30,
        controller_count=1,
        online_controller_count=1,
        pipeline_available=True,
        readiness_status="criteria_met",
        ownership_confirmed=False,
        boundary_review_acknowledged=False,
        active_watering_session_count=0,
    )

    assert manager.summary.status is ExecutionAuthorizationStatus.BLOCKED
    assert "controller_ownership_confirmed" in manager.summary.blocker_codes
    assert manager.summary.restart_policy == "fail_closed_recompute_required"



def test_boundary_review_acknowledgement_is_required() -> None:
    summary = _summary(boundary_review_acknowledged=False)

    assert summary.status is ExecutionAuthorizationStatus.BLOCKED
    assert summary.manual_review_state == "required"
    assert "execution_boundary_review_acknowledged" in summary.blocker_codes
