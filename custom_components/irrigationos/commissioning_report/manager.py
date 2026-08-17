"""In-memory derived commissioning report manager."""

from __future__ import annotations

from typing import Any

from .engine import build_commissioning_summary, build_commissioning_summary_from_counts


class CommissioningReportManager:
    """Maintain a derived operator summary from immutable evidence."""

    def __init__(self) -> None:
        self._shadow_evaluation_count = 0
        self._nightly_shadow_count = 0
        self._reconciliation_records: dict[str, dict[str, Any]] = {}
        self.summary = build_commissioning_summary((), ())

    def initialize(
        self,
        shadow_records: tuple[dict[str, Any], ...],
        reconciliation_records: tuple[dict[str, Any], ...],
    ) -> None:
        """Rebuild derived state from retained immutable evidence."""

        seen_shadow_ids: set[str] = set()
        self._shadow_evaluation_count = 0
        self._nightly_shadow_count = 0
        for record in shadow_records:
            identifier = str(record.get("evaluation_id", ""))
            if not identifier or identifier in seen_shadow_ids:
                continue
            seen_shadow_ids.add(identifier)
            self._shadow_evaluation_count += 1
            self._nightly_shadow_count += record.get("reason") == "nightly"
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

        shadow_reason = _shadow_reason(shadow_record)
        if shadow_reason is not None:
            self._shadow_evaluation_count += 1
            if shadow_reason == "nightly":
                self._nightly_shadow_count += 1
        for item in reconciliation_records:
            record = _record_dict(item, "comparison_id")
            if record is not None:
                self._reconciliation_records[str(record["comparison_id"])] = record
        self._rebuild()

    def diagnostics(self) -> dict[str, Any]:
        """Return privacy-safe aggregate reporting diagnostics."""

        return {
            **self.summary.to_dict(),
            "retained_commissioning_record_count": len(
                self._reconciliation_records
            ),
        }

    @property
    def retained_record_count(self) -> int:
        """Return bounded records retained for repeat reconciliation summaries."""

        return len(self._reconciliation_records)

    def _rebuild(self) -> None:
        self.summary = build_commissioning_summary_from_counts(
            shadow_count=self._shadow_evaluation_count,
            nightly_shadow_count=self._nightly_shadow_count,
            reconciliation_records=self._reconciliation_records.values(),
        )


def _shadow_reason(record: object | None) -> str | None:
    if record is None:
        return None
    if isinstance(record, dict):
        return str(record.get("reason", "")) or None
    reason = getattr(record, "reason", None)
    value = getattr(reason, "value", reason)
    return value if isinstance(value, str) and value else None


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
