"""Deterministic historical replay and explicit readiness criteria."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from ..actual_vs_shadow.matching import classify_match, parse_time
from ..commissioning_report.models import CommissioningSummary
from .models import (
    ControlReadinessStatus,
    ReplayEvidenceStatus,
    ReplayReadinessSummary,
    ReplayResult,
)

MIN_EVIDENCE_DAYS = 10
MIN_COMPARABLE_RECONCILIATIONS = 20
MIN_AGREEMENT_RATE_PERCENT = 80.0
MAX_INSUFFICIENT_EVIDENCE_PERCENT = 20.0
MIN_REPLAY_COVERAGE_PERCENT = 90.0
REQUIRED_REPLAY_MATCH_RATE_PERCENT = 100.0


def replay_reconciliation_record(record: Mapping[str, Any]) -> ReplayResult:
    """Recompute one reconciliation classification from preserved evidence."""

    comparison_id = str(record.get("comparison_id", ""))
    kind = str(record.get("kind", ""))
    if not comparison_id:
        return ReplayResult("", False, None, "missing_comparison_id")

    expected: dict[str, Any] | None
    try:
        if kind == "planned_vs_observed":
            expected = _replay_planned_vs_observed(record)
        elif kind == "unexpected_observed_watering":
            expected = _replay_unexpected(record)
        elif kind == "unmatched_without_shadow":
            expected = {
                "outcome": "insufficient_evidence",
                "confidence": "none",
                "reason_codes": ("no_preceding_shadow_evaluation",),
            }
        elif kind == "skipped_planned_watering":
            expected = _replay_skipped(record)
        else:
            return ReplayResult(comparison_id, False, None, "unsupported_kind")
    except (KeyError, TypeError, ValueError):
        return ReplayResult(comparison_id, False, None, "insufficient_preserved_inputs")

    if expected is None:
        return ReplayResult(comparison_id, False, None, "insufficient_preserved_inputs")

    matched = _matches_expected(record, expected)
    return ReplayResult(
        comparison_id=comparison_id,
        replayable=True,
        matched=matched,
        reason="replay_match" if matched else "replay_mismatch",
    )


def build_replay_readiness_summary(
    commissioning: CommissioningSummary,
    reconciliation_records: Iterable[Mapping[str, Any]],
) -> ReplayReadinessSummary:
    """Build deterministic replay metrics and conservative readiness criteria."""

    records = tuple(reconciliation_records)
    replay_results = tuple(replay_reconciliation_record(record) for record in records)
    replayable = tuple(result for result in replay_results if result.replayable)
    match_count = sum(result.matched is True for result in replayable)
    mismatch_count = sum(result.matched is False for result in replayable)
    unavailable_count = len(records) - len(replayable)
    coverage = _percent(len(replayable), len(records))
    match_rate = _percent(match_count, len(replayable))

    golden = run_golden_scenarios()
    golden_pass_count = sum(golden.values())
    golden_fail_count = len(golden) - golden_pass_count

    insufficient_percent = _percent(
        commissioning.insufficient_evidence_count,
        commissioning.reconciliation_count,
    )
    criteria = {
        "minimum_evidence_days": commissioning.evidence_day_count >= MIN_EVIDENCE_DAYS,
        "minimum_comparable_reconciliations": (
            commissioning.comparable_count >= MIN_COMPARABLE_RECONCILIATIONS
        ),
        "minimum_agreement_rate": (
            commissioning.agreement_rate_percent is not None
            and commissioning.agreement_rate_percent >= MIN_AGREEMENT_RATE_PERCENT
        ),
        "no_substantive_disagreements": commissioning.substantive_disagreement_count == 0,
        "insufficient_evidence_within_limit": (
            insufficient_percent is not None
            and insufficient_percent <= MAX_INSUFFICIENT_EVIDENCE_PERCENT
        ),
        "minimum_replay_coverage": (
            coverage is not None and coverage >= MIN_REPLAY_COVERAGE_PERCENT
        ),
        "replay_is_deterministic": (
            match_rate is not None
            and match_rate >= REQUIRED_REPLAY_MATCH_RATE_PERCENT
            and mismatch_count == 0
        ),
        "golden_scenarios_pass": golden_fail_count == 0,
    }
    criteria_met = sum(criteria.values())
    readiness = _readiness_status(commissioning, criteria, mismatch_count, golden_fail_count)
    replay_status = _replay_status(records, coverage, mismatch_count)
    promotion_assessment = (
        "criteria_met_pending_manual_review"
        if readiness is ControlReadinessStatus.CRITERIA_MET
        else "not_ready"
    )

    return ReplayReadinessSummary(
        replay_status=replay_status,
        readiness_status=readiness,
        reconciliation_count=len(records),
        replayable_count=len(replayable),
        replay_match_count=match_count,
        replay_mismatch_count=mismatch_count,
        replay_unavailable_count=unavailable_count,
        replay_coverage_percent=coverage,
        replay_match_rate_percent=match_rate,
        golden_scenario_count=len(golden),
        golden_scenario_pass_count=golden_pass_count,
        golden_scenario_fail_count=golden_fail_count,
        criteria_met_count=criteria_met,
        criteria_total_count=len(criteria),
        criteria=criteria,
        thresholds={
            "minimum_evidence_days": MIN_EVIDENCE_DAYS,
            "minimum_comparable_reconciliations": MIN_COMPARABLE_RECONCILIATIONS,
            "minimum_agreement_rate_percent": MIN_AGREEMENT_RATE_PERCENT,
            "maximum_insufficient_evidence_percent": MAX_INSUFFICIENT_EVIDENCE_PERCENT,
            "minimum_replay_coverage_percent": MIN_REPLAY_COVERAGE_PERCENT,
            "required_replay_match_rate_percent": REQUIRED_REPLAY_MATCH_RATE_PERCENT,
        },
        promotion_assessment=promotion_assessment,
    )


def run_golden_scenarios() -> dict[str, bool]:
    """Exercise stable canonical comparison scenarios against current logic."""

    planned = datetime.fromisoformat("2026-08-01T05:00:00+00:00")
    scenarios = {
        "exact_event_bounded": _synthetic_planned_record(
            "golden-exact", planned, planned, 600, 600, False, "confirmed", "event_bounded"
        ),
        "timing_partial": _synthetic_planned_record(
            "golden-timing",
            planned,
            datetime.fromisoformat("2026-08-01T05:20:00+00:00"),
            600,
            600,
            False,
            "confirmed",
            "event_bounded",
        ),
        "runtime_partial": _synthetic_planned_record(
            "golden-runtime", planned, planned, 600, 780, False, "confirmed", "poll_bounded"
        ),
        "partial_observation": _synthetic_planned_record(
            "golden-partial", planned, planned, 600, 600, True, "partial", "poll_bounded"
        ),
        "unexpected_partial": {
            "comparison_id": "golden-unexpected",
            "kind": "unexpected_observed_watering",
            "outcome": "disagreement",
            "confidence": "low",
            "reason_codes": ["observed_watering_without_matching_shadow_action"],
            "observation_quality": "partial",
            "observation_incomplete": False,
        },
    }
    return {
        name: replay_reconciliation_record(record).matched is True
        for name, record in scenarios.items()
    }


def _replay_planned_vs_observed(record: Mapping[str, Any]) -> dict[str, Any]:
    planned_start = parse_time(record["planned_start_utc"])
    observed_start = parse_time(record["observed_start_utc"])
    planned_runtime = _required_int(record.get("planned_runtime_seconds"))
    observed_runtime = _optional_int(record.get("observed_runtime_seconds"))
    observation_quality = _required_text(record.get("observation_quality"))
    timestamp_precision = _required_text(record.get("timestamp_precision"))
    incomplete = _required_bool(record.get("observation_incomplete"))
    return classify_match(
        planned_start=planned_start,
        planned_runtime_seconds=planned_runtime,
        observed_start=observed_start,
        observed_runtime_seconds=observed_runtime,
        incomplete=incomplete,
        observation_quality=observation_quality,
        timestamp_precision=timestamp_precision,
    )


def _replay_unexpected(record: Mapping[str, Any]) -> dict[str, Any] | None:
    quality = record.get("observation_quality")
    incomplete = record.get("observation_incomplete")
    if not isinstance(quality, str) or not isinstance(incomplete, bool):
        return None
    confidence = "low" if incomplete or quality == "partial" else "medium"
    return {
        "outcome": "disagreement",
        "confidence": confidence,
        "reason_codes": ("observed_watering_without_matching_shadow_action",),
    }


def _replay_skipped(record: Mapping[str, Any]) -> dict[str, Any] | None:
    quality = record.get("observation_quality")
    if not isinstance(quality, str) or not quality:
        return None
    if quality == "confirmed":
        return {
            "outcome": "disagreement",
            "confidence": "medium",
            "reason_codes": ("planned_watering_not_observed_after_grace_window",),
        }
    return {
        "outcome": "insufficient_evidence",
        "confidence": "low",
        "reason_codes": (
            "observation_quality_not_confirmed",
            "planned_watering_not_observed",
        ),
    }


def _matches_expected(record: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    if str(record.get("outcome", "")) != str(expected.get("outcome", "")):
        return False
    if str(record.get("confidence", "")) != str(expected.get("confidence", "")):
        return False
    actual_reasons = tuple(sorted(str(value) for value in record.get("reason_codes", ())))
    expected_reasons = tuple(sorted(str(value) for value in expected.get("reason_codes", ())))
    if actual_reasons != expected_reasons:
        return False
    for key in ("start_delta_seconds", "runtime_delta_seconds"):
        if key in expected and record.get(key) != expected.get(key):
            return False
    return True


def _readiness_status(
    commissioning: CommissioningSummary,
    criteria: Mapping[str, bool],
    replay_mismatches: int,
    golden_failures: int,
) -> ControlReadinessStatus:
    if replay_mismatches or golden_failures or commissioning.substantive_disagreement_count:
        return ControlReadinessStatus.REVIEW_REQUIRED
    if all(criteria.values()):
        return ControlReadinessStatus.CRITERIA_MET
    return ControlReadinessStatus.INSUFFICIENT_EVIDENCE


def _replay_status(
    records: tuple[Mapping[str, Any], ...],
    coverage: float | None,
    mismatches: int,
) -> ReplayEvidenceStatus:
    if not records:
        return ReplayEvidenceStatus.NO_EVIDENCE
    if mismatches:
        return ReplayEvidenceStatus.MISMATCH
    if coverage is not None and coverage == 100.0:
        return ReplayEvidenceStatus.VALIDATED
    return ReplayEvidenceStatus.PARTIAL_COVERAGE


def _synthetic_planned_record(
    identifier: str,
    planned_start: datetime,
    observed_start: datetime,
    planned_runtime: int,
    observed_runtime: int,
    incomplete: bool,
    quality: str,
    precision: str,
) -> dict[str, Any]:
    classified = classify_match(
        planned_start=planned_start,
        planned_runtime_seconds=planned_runtime,
        observed_start=observed_start,
        observed_runtime_seconds=observed_runtime,
        incomplete=incomplete,
        observation_quality=quality,
        timestamp_precision=precision,
    )
    return {
        "comparison_id": identifier,
        "kind": "planned_vs_observed",
        "planned_start_utc": planned_start.isoformat(),
        "planned_runtime_seconds": planned_runtime,
        "observed_start_utc": observed_start.isoformat(),
        "observed_runtime_seconds": observed_runtime,
        "observation_quality": quality,
        "timestamp_precision": precision,
        "observation_incomplete": incomplete,
        **classified,
    }


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100.0 * numerator / denominator, 1) if denominator else None


def _required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected integer")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _required_int(value)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected text")
    return value


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("expected bool")
    return value
