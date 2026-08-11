"""Contracts for the non-actuating sunrise hard-stop safeguard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

SUNRISE_HARD_STOP_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SunriseHardStopEvent:
    """Immutable evidence that a synthetic lifecycle crossed sunrise."""

    event_id: str
    command_id: str
    evaluated_at_utc: datetime
    sunrise_at_utc: datetime
    detail_code: str
    synthetic_only: bool = True
    dispatch_capability: bool = False
    schema_version: int = SUNRISE_HARD_STOP_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe hard-stop evidence."""

        payload = asdict(self)
        payload["evaluated_at_utc"] = self.evaluated_at_utc.isoformat()
        payload["sunrise_at_utc"] = self.sunrise_at_utc.isoformat()
        return payload
