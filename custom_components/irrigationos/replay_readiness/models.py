"""Contracts for deterministic replay and control-readiness evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

REPLAY_READINESS_SCHEMA_VERSION = 1


class ReplayEvidenceStatus(StrEnum):
    """Status of deterministic historical replay evidence."""

    NO_EVIDENCE = "no_evidence"
    PARTIAL_COVERAGE = "partial_coverage"
    VALIDATED = "validated"
    MISMATCH = "mismatch"


class ControlReadinessStatus(StrEnum):
    """Evidence-based readiness state that never authorizes live control."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REVIEW_REQUIRED = "review_required"
    CRITERIA_MET = "criteria_met"


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Replay result for one immutable reconciliation record."""

    comparison_id: str
    replayable: bool
    matched: bool | None
    reason: str


@dataclass(frozen=True, slots=True)
class ReplayReadinessSummary:
    """Aggregate replay and explicit control-readiness evidence."""

    replay_status: ReplayEvidenceStatus
    readiness_status: ControlReadinessStatus
    reconciliation_count: int
    replayable_count: int
    replay_match_count: int
    replay_mismatch_count: int
    replay_unavailable_count: int
    replay_coverage_percent: float | None
    replay_match_rate_percent: float | None
    golden_scenario_count: int
    golden_scenario_pass_count: int
    golden_scenario_fail_count: int
    criteria_met_count: int
    criteria_total_count: int
    criteria: dict[str, bool]
    thresholds: dict[str, float | int]
    promotion_assessment: str
    live_control_authorized: bool = False
    schema_version: int = REPLAY_READINESS_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible replay/readiness evidence."""

        payload = asdict(self)
        payload["replay_status"] = self.replay_status.value
        payload["readiness_status"] = self.readiness_status.value
        return payload
