"""In-memory derived commissioning report manager."""

from __future__ import annotations

from typing import Any

from .engine import build_commissioning_summary


class CommissioningReportManager:
    """Maintain a derived operator summary from immutable evidence."""

    def __init__(self) -> None:
        self._shadow_records: dict[str, dict[str, Any]] = {}
        self._reconciliation_records: dict[str, dict[str, Any]] = {}
        self.summary = build_commissioning_summary((), ())

    def initialize(
        self,
        shadow_records: tuple[dict[str, Any], ...],
        reconciliation_records: tuple[dict[str, Any], ...],
    ) -> None:
        """Rebuild derived state from retained immutable evidence."""

        self._shadow_records = {
            str(record.get("evaluation_id")): dict(record)
            for record in shadow_records
            if record.get("evaluation_id")
        }
        self._reconciliation_records = {
            str(record.get("comparison_id")): dict(record)
            for record in reconciliation_records
            if record.get("comparison_id")
        }
        self._rebuild()

    def consider(
        self,
        *,
        shadow_record: object | None,
        reconciliation_records: tuple[object, ...],
    ) -> None:
        """Include newly persisted evidence and refresh the derived summary."""

        shadow = _record_dict(shadow_record, "evaluation_id")
        if shadow is not None:
            self._shadow_records[str(shadow["evaluation_id"])] = shadow
        for item in reconciliation_records:
            record = _record_dict(item, "comparison_id")
            if record is not None:
                self._reconciliation_records[str(record["comparison_id"])] = record
        self._rebuild()

    def diagnostics(self) -> dict[str, Any]:
        """Return privacy-safe aggregate reporting diagnostics."""

        return self.summary.to_dict()

    def _rebuild(self) -> None:
        self.summary = build_commissioning_summary(
            self._shadow_records.values(),
            self._reconciliation_records.values(),
        )


def _record_dict(record: object | None, identifier: str) -> dict[str, Any] | None:
    if record is None:
        return None
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
    if not value.get(identifier):
        return None
    return value
