"""Contracts for non-actuating manual override preservation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

MANUAL_OVERRIDE_PRESERVATION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ManualOverridePreservationEvent:
    """Immutable evidence that externally owned watering was preserved."""

    event_id: str
    command_id: str
    evaluated_at_utc: datetime
    reason_codes: tuple[str, ...]
    active_session_count: int
    protected_session_count: int
    ambiguous_attribution_present: bool
    detail_code: str = "manual_override_preservation_required"
    synthetic_only: bool = True
    dispatch_capability: bool = False
    schema_version: int = MANUAL_OVERRIDE_PRESERVATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe preservation evidence."""

        payload = asdict(self)
        payload["evaluated_at_utc"] = self.evaluated_at_utc.isoformat()
        payload["reason_codes"] = list(self.reason_codes)
        return payload
