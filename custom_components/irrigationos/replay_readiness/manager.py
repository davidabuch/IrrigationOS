"""In-memory deterministic replay and readiness manager."""

from __future__ import annotations

from typing import Any

from ..commissioning_report.models import CommissioningSummary
from .engine import build_replay_readiness_summary


class ReplayReadinessManager:
    """Maintain derived replay/readiness evidence without any control capability."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self.summary = build_replay_readiness_summary(_empty_commissioning(), ())

    def initialize(
        self,
        reconciliation_records: tuple[dict[str, Any], ...],
        commissioning_summary: CommissioningSummary,
    ) -> None:
        """Rebuild replay/readiness evidence from retained immutable records."""

        self._records = {
            str(record.get("comparison_id")): dict(record)
            for record in reconciliation_records
            if record.get("comparison_id")
        }
        self._rebuild(commissioning_summary)

    def consider(
        self,
        *,
        reconciliation_records: tuple[object, ...],
        commissioning_summary: CommissioningSummary,
    ) -> None:
        """Incorporate newly persisted reconciliation records and rebuild."""

        for item in reconciliation_records:
            record = _record_dict(item)
            if record is not None:
                self._records[str(record["comparison_id"])] = record
        self._rebuild(commissioning_summary)

    def diagnostics(self) -> dict[str, Any]:
        """Return privacy-safe aggregate replay/readiness evidence."""

        return self.summary.to_dict()

    def _rebuild(self, commissioning_summary: CommissioningSummary) -> None:
        self.summary = build_replay_readiness_summary(
            commissioning_summary,
            self._records.values(),
        )


def _record_dict(record: object) -> dict[str, Any] | None:
    if isinstance(record, dict):
        value = dict(record)
    else:
        to_dict = getattr(record, "to_dict", None)
        if not callable(to_dict):
            return None
        result = to_dict()
        if not isinstance(result, dict):
            return None
        value = result
    if not value.get("comparison_id"):
        return None
    return value


def _empty_commissioning() -> CommissioningSummary:
    from ..commissioning_report.engine import build_commissioning_summary

    return build_commissioning_summary((), ())
