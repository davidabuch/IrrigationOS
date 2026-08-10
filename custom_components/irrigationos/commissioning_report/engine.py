"""Build deterministic commissioning summaries from immutable evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from .models import CommissioningEvidenceStatus, CommissioningSummary

_SUBSTANTIVE_CONFIDENCE = {"high", "medium"}
_COMPARABLE_OUTCOMES = {"agreement", "partial", "disagreement"}


def build_commissioning_summary(
    shadow_records: Iterable[Mapping[str, Any]],
    reconciliation_records: Iterable[Mapping[str, Any]],
) -> CommissioningSummary:
    """Aggregate preserved evidence without making a live-control promotion decision."""

    shadows = tuple(shadow_records)
    reconciliations = tuple(reconciliation_records)

    outcome_counts = {name: 0 for name in (*_COMPARABLE_OUTCOMES, "insufficient_evidence")}
    confidence_counts = {name: 0 for name in ("high", "medium", "low", "none")}
    kind_counts = {
        "skipped_planned_watering": 0,
        "unexpected_observed_watering": 0,
    }
    substantive_disagreement_count = 0
    start_deltas: list[int] = []
    runtime_deltas: list[int] = []
    evidence_days: set[str] = set()
    targets: set[str] = set()

    for record in reconciliations:
        outcome = str(record.get("outcome", ""))
        confidence = str(record.get("confidence", ""))
        kind = str(record.get("kind", ""))
        if outcome in outcome_counts:
            outcome_counts[outcome] += 1
        if confidence in confidence_counts:
            confidence_counts[confidence] += 1
        if kind in kind_counts:
            kind_counts[kind] += 1
        if outcome == "disagreement" and confidence in _SUBSTANTIVE_CONFIDENCE:
            substantive_disagreement_count += 1

        start_delta = _integer(record.get("start_delta_seconds"))
        if start_delta is not None:
            start_deltas.append(abs(start_delta))
        runtime_delta = _integer(record.get("runtime_delta_seconds"))
        if runtime_delta is not None:
            runtime_deltas.append(abs(runtime_delta))

        local_timestamp = record.get("reconciled_at_local")
        day = _date_part(local_timestamp)
        if day is not None:
            evidence_days.add(day)
        target = record.get("target_id")
        if isinstance(target, str) and target:
            targets.add(target)

    comparable_count = sum(outcome_counts[name] for name in _COMPARABLE_OUTCOMES)
    agreement_rate = (
        round(100.0 * outcome_counts["agreement"] / comparable_count, 1)
        if comparable_count
        else None
    )
    status = _status(
        shadow_count=len(shadows),
        reconciliation_count=len(reconciliations),
        comparable_count=comparable_count,
        substantive_disagreement_count=substantive_disagreement_count,
    )

    return CommissioningSummary(
        status=status,
        shadow_evaluation_count=len(shadows),
        nightly_shadow_count=sum(1 for item in shadows if item.get("reason") == "nightly"),
        reconciliation_count=len(reconciliations),
        comparable_count=comparable_count,
        insufficient_evidence_count=outcome_counts["insufficient_evidence"],
        agreement_count=outcome_counts["agreement"],
        partial_count=outcome_counts["partial"],
        disagreement_count=outcome_counts["disagreement"],
        skipped_planned_count=kind_counts["skipped_planned_watering"],
        unexpected_observed_count=kind_counts["unexpected_observed_watering"],
        high_confidence_count=confidence_counts["high"],
        medium_confidence_count=confidence_counts["medium"],
        low_confidence_count=confidence_counts["low"],
        no_confidence_count=confidence_counts["none"],
        substantive_disagreement_count=substantive_disagreement_count,
        evidence_day_count=len(evidence_days),
        target_count=len(targets),
        agreement_rate_percent=agreement_rate,
        mean_absolute_start_delta_seconds=_mean(start_deltas),
        mean_absolute_runtime_delta_seconds=_mean(runtime_deltas),
        max_absolute_start_delta_seconds=max(start_deltas, default=None),
        max_absolute_runtime_delta_seconds=max(runtime_deltas, default=None),
    )


def _status(
    *,
    shadow_count: int,
    reconciliation_count: int,
    comparable_count: int,
    substantive_disagreement_count: int,
) -> CommissioningEvidenceStatus:
    if shadow_count == 0 and reconciliation_count == 0:
        return CommissioningEvidenceStatus.NO_EVIDENCE
    if substantive_disagreement_count:
        return CommissioningEvidenceStatus.REVIEW_REQUIRED
    if comparable_count == 0:
        return CommissioningEvidenceStatus.COLLECTING_EVIDENCE
    return CommissioningEvidenceStatus.EVIDENCE_AVAILABLE


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _date_part(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def _mean(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None
