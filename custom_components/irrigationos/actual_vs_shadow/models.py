"""Canonical contracts for actual-vs-shadow reconciliation evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

RECONCILIATION_SCHEMA_VERSION = 1


class ReconciliationOutcome(StrEnum):
    """High-level relationship between shadow intent and observed watering."""

    AGREEMENT = "agreement"
    PARTIAL = "partial"
    DISAGREEMENT = "disagreement"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ReconciliationConfidence(StrEnum):
    """Confidence supported by the available observation evidence."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ReconciliationKind(StrEnum):
    """Stable kind of comparison record."""

    PLANNED_VS_OBSERVED = "planned_vs_observed"
    SKIPPED_PLANNED_WATERING = "skipped_planned_watering"
    UNEXPECTED_OBSERVED_WATERING = "unexpected_observed_watering"
    UNMATCHED_WITHOUT_SHADOW = "unmatched_without_shadow"


@dataclass(frozen=True, slots=True)
class ActualVsShadowRecord:
    """Immutable comparison between preserved intent and later observation."""

    comparison_id: str
    kind: ReconciliationKind
    outcome: ReconciliationOutcome
    confidence: ReconciliationConfidence
    reason_codes: tuple[str, ...]
    reconciled_at_utc: datetime
    reconciled_at_local: datetime
    evaluation_id: str | None = None
    scheduled_action_id: str | None = None
    session_id: str | None = None
    target_id: str | None = None
    planned_start_utc: datetime | None = None
    planned_end_utc: datetime | None = None
    planned_runtime_seconds: int | None = None
    observed_start_utc: datetime | None = None
    observed_end_utc: datetime | None = None
    observed_runtime_seconds: int | None = None
    start_delta_seconds: int | None = None
    runtime_delta_seconds: int | None = None
    observation_source: str | None = None
    observation_quality: str | None = None
    timestamp_precision: str | None = None
    observation_incomplete: bool | None = None
    schema_version: int = RECONCILIATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible evidence."""

        payload = asdict(self)
        for key, value in tuple(payload.items()):
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
            elif isinstance(value, StrEnum):
                payload[key] = value.value
            elif isinstance(value, tuple):
                payload[key] = list(value)
        return payload
