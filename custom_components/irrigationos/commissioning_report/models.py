"""Contracts for observation-only commissioning summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

COMMISSIONING_REPORT_SCHEMA_VERSION = 1


class CommissioningEvidenceStatus(StrEnum):
    """Operator-facing evidence state without implying live-control approval."""

    NO_EVIDENCE = "no_evidence"
    COLLECTING_EVIDENCE = "collecting_evidence"
    EVIDENCE_AVAILABLE = "evidence_available"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class CommissioningSummary:
    """Deterministic aggregate of preserved shadow and reconciliation evidence."""

    status: CommissioningEvidenceStatus
    shadow_evaluation_count: int
    nightly_shadow_count: int
    reconciliation_count: int
    comparable_count: int
    insufficient_evidence_count: int
    agreement_count: int
    partial_count: int
    disagreement_count: int
    skipped_planned_count: int
    unexpected_observed_count: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    no_confidence_count: int
    substantive_disagreement_count: int
    evidence_day_count: int
    target_count: int
    agreement_rate_percent: float | None
    mean_absolute_start_delta_seconds: float | None
    mean_absolute_runtime_delta_seconds: float | None
    max_absolute_start_delta_seconds: int | None
    max_absolute_runtime_delta_seconds: int | None
    promotion_assessment: str = "not_assessed"
    schema_version: int = COMMISSIONING_REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible summary data."""

        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
