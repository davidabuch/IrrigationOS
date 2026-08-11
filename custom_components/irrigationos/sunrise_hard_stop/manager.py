"""Persist sunrise hard-stop evidence and terminate synthetic waits."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant

from ..command_acknowledgements.manager import CommandAcknowledgementManager
from .engine import build_sunrise_hard_stop_event, sunrise_boundary_reached
from .models import SunriseHardStopEvent

SUNRISE_HARD_STOP_RETENTION_DAYS = 30


class SunriseHardStopManager:
    """Enforce a fail-closed sunrise boundary without controller dispatch."""

    def __init__(
        self,
        hass: HomeAssistant,
        root: Path,
        acknowledgements: CommandAcknowledgementManager,
    ) -> None:
        self._hass = hass
        self._root = root
        self._acknowledgements = acknowledgements
        self.event_count = 0
        self.last_event: SunriseHardStopEvent | None = None
        self.last_error: str | None = None
        self._last_cleanup_date: date | None = None

    async def async_consider_synthetic_command(
        self,
        *,
        command_id: str,
        evaluated_at: datetime,
        sunrise_at: datetime,
    ) -> SunriseHardStopEvent | None:
        """Terminate a pending synthetic lifecycle once sunrise is reached."""

        if not self._acknowledgements.is_pending(command_id):
            raise ValueError("pending_acknowledgement_not_found")
        if not sunrise_boundary_reached(now=evaluated_at, sunrise_at=sunrise_at):
            return None
        event = build_sunrise_hard_stop_event(
            command_id=command_id,
            evaluated_at=evaluated_at,
            sunrise_at=sunrise_at,
        )
        success = await self._hass.async_add_executor_job(self._write_event, event)
        if success:
            self.event_count += 1
            self.last_event = event
        await self._acknowledgements.async_preempt_synthetic(
            command_id=command_id,
            observed_at=evaluated_at,
            detail_code="sunrise_hard_stop_reached",
        )
        return event

    def _write_event(self, event: SunriseHardStopEvent) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            local_date = event.evaluated_at_utc.date()
            self._cleanup(local_date)
            path = self._root / (
                f"irrigationos_sunrise_hard_stop_{local_date.isoformat()}.jsonl"
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "sunrise_hard_stop_log_write_failed"
            return False

    def _cleanup(self, today: date) -> None:
        if self._last_cleanup_date == today:
            return
        self._last_cleanup_date = today
        oldest = today - timedelta(days=SUNRISE_HARD_STOP_RETENTION_DAYS - 1)
        for path in self._root.glob("irrigationos_sunrise_hard_stop_????-??-??.jsonl"):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_sunrise_hard_stop_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe hard-stop evidence without identifiers."""

        return {
            "event_count": self.event_count,
            "last_detail_code": (
                None if self.last_event is None else self.last_event.detail_code
            ),
            "synthetic_only": True,
            "dispatch_capability": False,
            "last_error": self.last_error,
        }
