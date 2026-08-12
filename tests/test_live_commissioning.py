"""Tests for the bounded non-actuating first-live commissioning protocol."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

commissioning = load_integration_module("live_commissioning")
NOW = datetime(2026, 8, 12, 4, 30, tzinfo=UTC)


def _approval(**overrides: object) -> Any:
    values = {
        "controller_slot": 1,
        "area_slot": 2,
        "requested_runtime_seconds": 120,
        "approved_at": NOW,
        "expires_at": NOW + timedelta(minutes=10),
        "supervised_daytime": True,
    }
    values.update(overrides)
    return commissioning.FirstLiveTrialApproval(**values)


def _summary(**overrides: object) -> Any:
    values = {
        "integrated_review_status": "validated_review_eligible",
        "approval": _approval(),
        "evaluated_at": NOW + timedelta(minutes=1),
        "health_state": "healthy",
        "observation_age_seconds": 10.0,
        "active_external_watering_count": 0,
        "commissioning_window_open": True,
    }
    values.update(overrides)
    return commissioning.build_live_commissioning_summary(**values)


def test_valid_protocol_can_only_become_first_live_trial_eligible() -> None:
    summary = _summary()
    assert summary.status is commissioning.LiveCommissioningStatus.FIRST_LIVE_TRIAL_ELIGIBLE
    assert summary.max_runtime_seconds == 120
    assert summary.first_live_trial_dispatch_enabled is False
    assert summary.live_mode_commissionable is False
    assert summary.live_control_feature_enabled is False
    assert summary.live_control_authorized is False


def test_operator_approval_is_mandatory() -> None:
    summary = _summary(approval=None)
    assert summary.status is commissioning.LiveCommissioningStatus.OPERATOR_APPROVAL_REQUIRED
    assert "explicit_operator_approval_required" in summary.blocker_codes


def test_runtime_above_two_minutes_is_rejected() -> None:
    summary = _summary(approval=_approval(requested_runtime_seconds=121))
    assert "requested_runtime_outside_first_live_limit" in summary.blocker_codes


def test_only_one_positive_controller_and_area_slot_are_accepted() -> None:
    summary = _summary(approval=_approval(controller_slot=0, area_slot=0))
    assert "target_controller_slot_invalid" in summary.blocker_codes
    assert "target_area_slot_invalid" in summary.blocker_codes


def test_supervised_daytime_is_required() -> None:
    summary = _summary(approval=_approval(supervised_daytime=False))
    assert "supervised_daytime_required" in summary.blocker_codes


def test_external_watering_blocks_trial_eligibility() -> None:
    summary = _summary(active_external_watering_count=1)
    assert "external_watering_active" in summary.blocker_codes


def test_health_and_freshness_degradation_fail_closed() -> None:
    summary = _summary(health_state="degraded", observation_age_seconds=121.0)
    assert "system_not_healthy" in summary.blocker_codes
    assert "observation_not_fresh_enough_for_commissioning" in summary.blocker_codes


def test_integrated_review_must_remain_eligible() -> None:
    summary = _summary(integrated_review_status="blocked")
    assert "integrated_safety_review_not_eligible" in summary.blocker_codes


def test_approval_expires_and_consumed_approval_cannot_be_reused() -> None:
    expired = _summary(evaluated_at=NOW + timedelta(minutes=11))
    assert "operator_approval_expired" in expired.blocker_codes
    consumed = _summary(approval=_approval(consumed=True))
    assert "operator_approval_already_consumed" in consumed.blocker_codes


def test_manager_approval_is_single_use_and_restart_unsafe() -> None:
    manager = commissioning.LiveCommissioningManager()
    manager.approve_trial(
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=60,
        approved_at=NOW,
        supervised_daytime=True,
    )
    manager.set_supervised_commissioning_window(open_window=True)
    manager.consider(
        integrated_review_status="validated_review_eligible",
        evaluated_at=NOW + timedelta(seconds=5),
        health_state="healthy",
        observation_age_seconds=5.0,
        active_external_watering_count=0,
    )
    assert manager.summary.status is commissioning.LiveCommissioningStatus.FIRST_LIVE_TRIAL_ELIGIBLE
    manager.consume_approval()
    manager.consider(
        integrated_review_status="validated_review_eligible",
        evaluated_at=NOW + timedelta(seconds=6),
        health_state="healthy",
        observation_age_seconds=6.0,
        active_external_watering_count=0,
    )
    assert "operator_approval_already_consumed" in manager.summary.blocker_codes
    restarted = commissioning.LiveCommissioningManager()
    assert restarted.diagnostics()["first_live_trial_dispatch_enabled"] is False


def test_acceptance_evidence_is_explicit_before_any_future_actuation() -> None:
    summary = _summary()
    assert summary.required_acceptance_evidence == (
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
    assert summary.approval_persists_across_restart is False
