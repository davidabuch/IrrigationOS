"""Deterministic sunrise boundary evaluation without controller dispatch."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import SunriseHardStopEvent


def _require_aware(value: datetime, *, code: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(code)


def sunrise_boundary_reached(*, now: datetime, sunrise_at: datetime) -> bool:
    """Return whether the configured sunrise hard-stop boundary has been reached."""

    _require_aware(now, code="now_timezone_required")
    _require_aware(sunrise_at, code="sunrise_timezone_required")
    return now.astimezone(UTC) >= sunrise_at.astimezone(UTC)


def build_sunrise_hard_stop_event(
    *, command_id: str, evaluated_at: datetime, sunrise_at: datetime
) -> SunriseHardStopEvent:
    """Build immutable evidence for a synthetic lifecycle stopped at sunrise."""

    command_id = command_id.strip()
    if not command_id:
        raise ValueError("command_id_required")
    _require_aware(evaluated_at, code="evaluated_at_timezone_required")
    _require_aware(sunrise_at, code="sunrise_timezone_required")
    evaluated_at_utc = evaluated_at.astimezone(UTC)
    sunrise_at_utc = sunrise_at.astimezone(UTC)
    if evaluated_at_utc < sunrise_at_utc:
        raise ValueError("sunrise_boundary_not_reached")
    seed = f"{command_id}|{evaluated_at_utc.isoformat()}|{sunrise_at_utc.isoformat()}"
    return SunriseHardStopEvent(
        event_id=hashlib.sha256(seed.encode()).hexdigest(),
        command_id=command_id,
        evaluated_at_utc=evaluated_at_utc,
        sunrise_at_utc=sunrise_at_utc,
        detail_code="sunrise_hard_stop_reached",
    )
