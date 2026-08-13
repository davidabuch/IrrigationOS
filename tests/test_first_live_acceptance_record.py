"""Tests for persistent structured supervised first-live acceptance records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.helpers import load_integration_module

acceptance = load_integration_module("first_live_delivery.acceptance")
NOW = datetime(2026, 8, 13, 17, 25, tzinfo=UTC)


def test_successful_observation_builds_explicit_pass_record() -> None:
    record = acceptance.build_acceptance_record(
        attempt_id="first_live_attempt_test",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=NOW,
        observed_idle_at=NOW + timedelta(seconds=31),
        refresh_error_count=0,
        concurrent_watering_observed=False,
        terminal_detail_code="first_live_trial_accepted",
    )

    assert record.status is acceptance.FirstLiveAcceptanceStatus.PASS
    assert record.observed_runtime_seconds == 31
    payload = record.to_dict()
    assert payload["criteria_passed_count"] == payload["criteria_total_count"] == 10
    assert payload["observation_precision"] == "polling_bounded"
    assert "native" not in repr(payload).lower()


def test_missing_completion_is_indeterminate_not_success() -> None:
    record = acceptance.build_acceptance_record(
        attempt_id="first_live_attempt_test",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=NOW,
        observed_idle_at=None,
        refresh_error_count=2,
        concurrent_watering_observed=False,
        terminal_detail_code="completion_not_observed_within_grace",
    )

    assert record.status is acceptance.FirstLiveAcceptanceStatus.INDETERMINATE
    criteria = {item.code: item.status.value for item in record.criteria}
    assert criteria["target_watering_observed"] == "pass"
    assert criteria["target_returned_idle"] == "fail"
    assert criteria["post_run_reconciliation_passed"] == "fail"


def test_concurrent_watering_fails_acceptance() -> None:
    record = acceptance.build_acceptance_record(
        attempt_id="first_live_attempt_test",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=NOW,
        observed_idle_at=NOW + timedelta(seconds=30),
        refresh_error_count=0,
        concurrent_watering_observed=True,
        terminal_detail_code="first_live_trial_accepted",
    )

    assert record.status is acceptance.FirstLiveAcceptanceStatus.FAIL
    criteria = {item.code: item.status.value for item in record.criteria}
    assert criteria["no_concurrent_watering_observed"] == "fail"


def test_record_round_trip_preserves_structured_evidence() -> None:
    original = acceptance.build_acceptance_record(
        attempt_id="first_live_attempt_round_trip",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=NOW,
        observed_idle_at=NOW + timedelta(seconds=30),
        refresh_error_count=1,
        concurrent_watering_observed=False,
        terminal_detail_code="first_live_trial_accepted",
    )

    restored = acceptance.FirstLiveAcceptanceRecord.from_dict(original.to_dict())
    assert restored == original
