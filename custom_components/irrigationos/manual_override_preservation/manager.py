"""Persist non-actuating manual override preservation evidence."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant

from ..command_acknowledgements.manager import CommandAcknowledgementManager
from ..observation_history.models import WateringAttribution
from .engine import build_manual_override_preservation_event, evaluate_preservation_reasons
from .models import ManualOverridePreservationEvent

MANUAL_OVERRIDE_PRESERVATION_RETENTION_DAYS = 30


class ManualOverridePreservationManager:
    """Preserve externally owned watering without controller dispatch."""

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
        self.last_event: ManualOverridePreservationEvent | None = None
        self.last_error: str | None = None
        self._last_cleanup_date: date | None = None

    async def async_consider_synthetic_command(
        self,
        *,
        command_id: str,
        evaluated_at: datetime,
        active_attributions: Iterable[WateringAttribution | str],
    ) -> ManualOverridePreservationEvent | None:
        """Preempt a synthetic lifecycle rather than displace externally owned watering."""

        if not self._acknowledgements.is_pending(command_id):
            raise ValueError("pending_acknowledgement_not_found")
        attribution_values = tuple(active_attributions)
        if not evaluate_preservation_reasons(attribution_values):
            return None
        event = build_manual_override_preservation_event(
            command_id=command_id,
            evaluated_at=evaluated_at,
            active_attributions=attribution_values,
        )
        success = await self._hass.async_add_executor_job(self._write_event, event)
        if success:
            self.event_count += 1
            self.last_event = event
        await self._acknowledgements.async_preempt_synthetic(
            command_id=command_id,
            observed_at=evaluated_at,
            detail_code="manual_override_preservation_required",
        )
        return event

    def _write_event(self, event: ManualOverridePreservationEvent) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            local_date = event.evaluated_at_utc.date()
            self._cleanup(local_date)
            path = self._root / (
                f"irrigationos_manual_override_preservation_{local_date.isoformat()}.jsonl"
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "manual_override_preservation_log_write_failed"
            return False

    def _cleanup(self, today: date) -> None:
        if self._last_cleanup_date == today:
            return
        self._last_cleanup_date = today
        oldest = today - timedelta(days=MANUAL_OVERRIDE_PRESERVATION_RETENTION_DAYS - 1)
        for path in self._root.glob(
            "irrigationos_manual_override_preservation_????-??-??.jsonl"
        ):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_manual_override_preservation_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe preservation evidence without identifiers."""

        return {
            "event_count": self.event_count,
            "last_reason_codes": (
                () if self.last_event is None else self.last_event.reason_codes
            ),
            "ambiguous_attribution_present": (
                False
                if self.last_event is None
                else self.last_event.ambiguous_attribution_present
            ),
            "synthetic_only": True,
            "dispatch_capability": False,
            "last_error": self.last_error,
        }
