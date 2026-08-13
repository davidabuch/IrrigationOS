"""Tests for deterministic replay and control-readiness evidence."""

from __future__ import annotations

from typing import Any

from tests.helpers import load_integration_module

commissioning_report = load_integration_module("commissioning_report")
replay_readiness = load_integration_module("replay_readiness")

CommissioningEvidenceStatus = commissioning_report.CommissioningEvidenceStatus
CommissioningSummary = commissioning_report.CommissioningSummary
ControlReadinessStatus = replay_readiness.ControlReadinessStatus
ReplayEvidenceStatus = replay_readiness.ReplayEvidenceStatus
build_replay_readiness_summary = replay_readiness.build_replay_readiness_summary
replay_reconciliation_record = replay_readiness.replay_reconciliation_record
run_golden_scenarios = replay_readiness.run_golden_scenarios


def _commissioning(*, evidence_day_count: int = 10) -> Any:
    base = CommissioningSummary(
        status=CommissioningEvidenceStatus.EVIDENCE_AVAILABLE,
        shadow_evaluation_count=20,
        nightly_shadow_count=14,
        reconciliation_count=20,
        comparable_count=20,
        insufficient_evidence_count=0,
        agreement_count=18,
        partial_count=2,
        disagreement_count=0,
        skipped_planned_count=0,
        unexpected_observed_count=0,
        high_confidence_count=15,
        medium_confidence_count=5,
        low_confidence_count=0,
        no_confidence_count=0,
        substantive_disagreement_count=0,
        evidence_day_count=evidence_day_count,
        target_count=2,
        agreement_rate_percent=90.0,
        mean_absolute_start_delta_seconds=60.0,
        mean_absolute_runtime_delta_seconds=30.0,
        max_absolute_start_delta_seconds=120,
        max_absolute_runtime_delta_seconds=60,
    )
    return base


def _planned(identifier: str) -> dict[str, object]:
    return {
        "comparison_id": identifier,
        "kind": "planned_vs_observed",
        "outcome": "agreement",
        "confidence": "high",
        "reason_codes": ["planned_zone_observed"],
        "planned_start_utc": "2026-08-01T05:00:00+00:00",
        "planned_runtime_seconds": 600,
        "observed_start_utc": "2026-08-01T05:00:00+00:00",
        "observed_runtime_seconds": 600,
        "start_delta_seconds": 0,
        "runtime_delta_seconds": 0,
        "observation_quality": "confirmed",
        "timestamp_precision": "event_bounded",
        "observation_incomplete": False,
    }


def test_planned_comparison_replays_exactly() -> None:
    result = replay_reconciliation_record(_planned("one"))

    assert result.replayable is True
    assert result.matched is True
    assert result.reason == "replay_match"


def test_replay_detects_algorithm_or_evidence_mismatch() -> None:
    record = _planned("one")
    record["outcome"] = "partial"

    result = replay_reconciliation_record(record)

    assert result.replayable is True
    assert result.matched is False


def test_legacy_skipped_record_without_quality_is_not_falsely_replayed() -> None:
    result = replay_reconciliation_record(
        {
            "comparison_id": "skip",
            "kind": "skipped_planned_watering",
            "outcome": "disagreement",
            "confidence": "medium",
            "reason_codes": ["planned_watering_not_observed_after_grace_window"],
            "observation_quality": None,
        }
    )

    assert result.replayable is False
    assert result.matched is None
    assert result.reason == "insufficient_preserved_inputs"


def test_golden_scenarios_all_pass() -> None:
    results = run_golden_scenarios()

    assert len(results) >= 5
    assert all(results.values())


def test_insufficient_evidence_never_authorizes_live_control() -> None:
    summary = build_replay_readiness_summary(_commissioning(evidence_day_count=2), ())

    assert summary.readiness_status is ControlReadinessStatus.INSUFFICIENT_EVIDENCE
    assert summary.replay_status is ReplayEvidenceStatus.NO_EVIDENCE
    assert summary.live_control_authorized is False
    assert summary.promotion_assessment == "not_ready"


def test_ten_days_meets_evidence_day_threshold_but_nine_does_not() -> None:
    records = tuple(_planned(f"record-{index}") for index in range(20))
    ten_days = build_replay_readiness_summary(_commissioning(evidence_day_count=10), records)
    nine_days = build_replay_readiness_summary(_commissioning(evidence_day_count=9), records)

    assert ten_days.criteria["minimum_evidence_days"] is True
    assert ten_days.thresholds["minimum_evidence_days"] == 10
    assert nine_days.criteria["minimum_evidence_days"] is False


def test_explicit_criteria_can_be_met_but_still_require_manual_review() -> None:
    records = tuple(_planned(f"record-{index}") for index in range(20))
    summary = build_replay_readiness_summary(_commissioning(), records)

    assert summary.replay_status is ReplayEvidenceStatus.VALIDATED
    assert summary.replay_coverage_percent == 100.0
    assert summary.replay_match_rate_percent == 100.0
    assert summary.criteria_met_count == summary.criteria_total_count
    assert summary.readiness_status is ControlReadinessStatus.CRITERIA_MET
    assert summary.promotion_assessment == "criteria_met_pending_manual_review"
    assert summary.live_control_authorized is False


def test_replay_mismatch_forces_review_required() -> None:
    records = [_planned(f"record-{index}") for index in range(20)]
    records[0]["confidence"] = "medium"

    summary = build_replay_readiness_summary(_commissioning(), records)

    assert summary.replay_mismatch_count == 1
    assert summary.replay_status is ReplayEvidenceStatus.MISMATCH
    assert summary.readiness_status is ControlReadinessStatus.REVIEW_REQUIRED
    assert summary.live_control_authorized is False
