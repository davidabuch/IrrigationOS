"""Tests for aggregate shadow commissioning reporting."""

from __future__ import annotations

from tests.helpers import load_integration_module

commissioning_report = load_integration_module("commissioning_report")
CommissioningEvidenceStatus = commissioning_report.CommissioningEvidenceStatus
build_commissioning_summary = commissioning_report.build_commissioning_summary


def _shadow(identifier: str, *, reason: str = "nightly") -> dict[str, object]:
    return {
        "evaluation_id": identifier,
        "reason": reason,
        "timestamp_utc": "2026-08-09T03:00:00+00:00",
    }


def _reconciliation(
    identifier: str,
    *,
    outcome: str,
    confidence: str,
    kind: str = "planned_vs_observed",
    start_delta: int | None = 60,
    runtime_delta: int | None = -30,
) -> dict[str, object]:
    return {
        "comparison_id": identifier,
        "kind": kind,
        "outcome": outcome,
        "confidence": confidence,
        "reconciled_at_local": "2026-08-09T20:10:00-07:00",
        "target_id": "area-1",
        "start_delta_seconds": start_delta,
        "runtime_delta_seconds": runtime_delta,
    }


def test_no_evidence_is_explicit_and_never_promotes_live_control() -> None:
    summary = build_commissioning_summary((), ())

    assert summary.status is CommissioningEvidenceStatus.NO_EVIDENCE
    assert summary.agreement_rate_percent is None
    assert summary.promotion_assessment == "not_assessed"


def test_shadow_without_comparison_reports_collecting_evidence() -> None:
    summary = build_commissioning_summary((_shadow("shadow-1"),), ())

    assert summary.status is CommissioningEvidenceStatus.COLLECTING_EVIDENCE
    assert summary.shadow_evaluation_count == 1
    assert summary.nightly_shadow_count == 1
    assert summary.comparable_count == 0


def test_agreement_summary_reports_rates_and_absolute_deltas() -> None:
    records = (
        _reconciliation(
            "a", outcome="agreement", confidence="high", start_delta=-60, runtime_delta=30
        ),
        _reconciliation(
            "b", outcome="partial", confidence="medium", start_delta=180, runtime_delta=-90
        ),
    )
    summary = build_commissioning_summary((_shadow("shadow-1"),), records)

    assert summary.status is CommissioningEvidenceStatus.EVIDENCE_AVAILABLE
    assert summary.comparable_count == 2
    assert summary.agreement_count == 1
    assert summary.partial_count == 1
    assert summary.agreement_rate_percent == 50.0
    assert summary.mean_absolute_start_delta_seconds == 120.0
    assert summary.mean_absolute_runtime_delta_seconds == 60.0
    assert summary.max_absolute_start_delta_seconds == 180
    assert summary.max_absolute_runtime_delta_seconds == 90
    assert summary.evidence_day_count == 1
    assert summary.target_count == 1


def test_medium_confidence_disagreement_requires_review() -> None:
    records = (
        _reconciliation(
            "a",
            outcome="disagreement",
            confidence="medium",
            kind="skipped_planned_watering",
            start_delta=None,
            runtime_delta=None,
        ),
        _reconciliation(
            "b",
            outcome="insufficient_evidence",
            confidence="low",
            kind="unexpected_observed_watering",
            start_delta=None,
            runtime_delta=None,
        ),
    )
    summary = build_commissioning_summary((_shadow("shadow-1"),), records)

    assert summary.status is CommissioningEvidenceStatus.REVIEW_REQUIRED
    assert summary.disagreement_count == 1
    assert summary.insufficient_evidence_count == 1
    assert summary.substantive_disagreement_count == 1
    assert summary.skipped_planned_count == 1
    assert summary.unexpected_observed_count == 1
