"""Integrated validation of all six non-actuating Live-mode safeguards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

acknowledgements = load_integration_module("command_acknowledgements")
integrated_review = load_integration_module("integrated_safety_review")
live_mode_safety = load_integration_module("live_mode_safety")
manual_override = load_integration_module("manual_override_preservation")
observation_models = load_integration_module("observation_history.models")
safety_preemption = load_integration_module("safety_preemption")
sunrise_hard_stop = load_integration_module("sunrise_hard_stop")

WateringAttribution = observation_models.WateringAttribution
NOW = datetime(2026, 8, 11, 23, 0, tzinfo=UTC)


def _live_summary(**overrides: object) -> Any:
    values: dict[str, Any] = {
        "readiness_status": "criteria_met",
        "execution_authorization_status": "manual_review_eligible",
        "ownership_confirmed": True,
        "boundary_review_acknowledged": True,
    }
    values.update(overrides)
    return live_mode_safety.build_live_mode_safety_summary(**values)


def test_six_safeguards_are_integrated_but_never_auto_authorize() -> None:
    live = _live_summary()
    review = integrated_review.build_integrated_safety_review(live)
    assert live.safeguards_met_count == live.safeguards_total_count == 6
    assert review.status is integrated_review.IntegratedSafetyReviewStatus.VALIDATED_REVIEW_ELIGIBLE
    assert review.validation_passed_count == review.validation_total_count == 8
    assert review.integrated_validation_complete is True
    assert review.live_mode_commissionable is False
    assert review.live_control_feature_enabled is False
    assert review.live_control_authorized is False


def test_readiness_loss_immediately_blocks_integrated_review() -> None:
    review = integrated_review.build_integrated_safety_review(
        _live_summary(readiness_status="insufficient_evidence")
    )
    assert review.status is integrated_review.IntegratedSafetyReviewStatus.BLOCKED
    assert "control_readiness_criteria_met" in review.blocker_codes
    assert review.live_control_authorized is False


def test_ownership_loss_immediately_blocks_integrated_review() -> None:
    review = integrated_review.build_integrated_safety_review(
        _live_summary(ownership_confirmed=False)
    )
    assert review.status is integrated_review.IntegratedSafetyReviewStatus.BLOCKED
    assert "controller_ownership_confirmed" in review.blocker_codes


def test_acknowledgement_timeout_remains_terminal_and_fail_closed() -> None:
    pending = acknowledgements.begin_acknowledgement_wait(
        command_id="integrated-command", dispatched_at=NOW
    )
    timed_out = acknowledgements.evaluate_acknowledgement_timeout(
        pending, now=NOW + timedelta(seconds=31)
    )
    assert timed_out.state is acknowledgements.CommandAcknowledgementState.TIMED_OUT
    assert timed_out.terminal is True


def test_restart_reconciliation_restores_only_still_valid_waits() -> None:
    valid = acknowledgements.begin_acknowledgement_wait(
        command_id="valid-command", dispatched_at=NOW
    )
    expired = acknowledgements.begin_acknowledgement_wait(
        command_id="expired-command", dispatched_at=NOW - timedelta(minutes=2)
    )
    pending, transitions = acknowledgements.reconcile_acknowledgement_history(
        (valid, expired), now=NOW + timedelta(seconds=5)
    )
    assert set(pending) == {"valid-command"}
    assert len(transitions) == 1
    assert transitions[0].state is acknowledgements.CommandAcknowledgementState.TIMED_OUT


def test_health_degradation_requires_safety_preemption() -> None:
    reasons = safety_preemption.evaluate_preemption_reasons(
        health_state="degraded",
        observation_age_seconds=30.0,
        observation_stale_after_seconds=720.0,
        controller_available=True,
        ownership_confirmed=True,
        active_watering_conflict=False,
        execution_authorization_status="manual_review_eligible",
    )
    assert reasons == ("system_unhealthy",)
    event = safety_preemption.build_preemption_event(
        command_id="integrated-command", evaluated_at=NOW, reason_codes=reasons
    )
    assert event.dispatch_capability is False


def test_sunrise_boundary_preempts_without_dispatch_capability() -> None:
    sunrise = NOW + timedelta(minutes=5)
    assert sunrise_hard_stop.sunrise_boundary_reached(now=NOW, sunrise_at=sunrise) is False
    assert (
        sunrise_hard_stop.sunrise_boundary_reached(
            now=sunrise + timedelta(seconds=1), sunrise_at=sunrise
        )
        is True
    )
    event = sunrise_hard_stop.build_sunrise_hard_stop_event(
        command_id="integrated-command",
        evaluated_at=sunrise + timedelta(seconds=1),
        sunrise_at=sunrise,
    )
    assert event.dispatch_capability is False


def test_manual_and_ambiguous_watering_are_preserved() -> None:
    reasons = manual_override.evaluate_preservation_reasons(
        (WateringAttribution.MANUAL, WateringAttribution.EXTERNAL_UNKNOWN)
    )
    assert reasons == (
        "ambiguous_external_watering_preserved",
        "manual_watering_preserved",
    )
    event = manual_override.build_manual_override_preservation_event(
        command_id="integrated-command",
        evaluated_at=NOW,
        active_attributions=(
            WateringAttribution.MANUAL,
            WateringAttribution.EXTERNAL_UNKNOWN,
        ),
    )
    assert event.dispatch_capability is False
    assert event.protected_session_count == 2


def test_only_explicit_irrigationos_attribution_is_non_blocking() -> None:
    assert manual_override.preservation_required((WateringAttribution.IRRIGATIONOS,)) is False
    assert manual_override.preservation_required(("future_unknown_source",)) is True


def test_multiple_simultaneous_faults_all_fail_closed_independently() -> None:
    preemption = safety_preemption.evaluate_preemption_reasons(
        health_state="unhealthy",
        observation_age_seconds=None,
        observation_stale_after_seconds=720.0,
        controller_available=False,
        ownership_confirmed=False,
        active_watering_conflict=True,
        execution_authorization_status="blocked",
    )
    preservation = manual_override.evaluate_preservation_reasons(
        (WateringAttribution.MANUAL,)
    )
    assert len(preemption) == 6
    assert preservation == ("manual_watering_preserved",)
    assert integrated_review.build_integrated_safety_review(
        _live_summary(
            readiness_status="insufficient_evidence",
            execution_authorization_status="blocked",
            ownership_confirmed=False,
        )
    ).status is integrated_review.IntegratedSafetyReviewStatus.BLOCKED
