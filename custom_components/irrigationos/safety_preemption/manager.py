"""Persist non-actuating safety preemption evidence and terminate synthetic waits."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant

from ..command_acknowledgements.manager import CommandAcknowledgementManager
from .engine import build_preemption_event, evaluate_preemption_reasons
from .models import SafetyPreemptionEvent

SAFETY_PREEMPTION_RETENTION_DAYS = 30


class SafetyPreemptionManager:
    """Exercise fail-closed preemption semantics without controller dispatch."""

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
        self.last_event: SafetyPreemptionEvent | None = None
        self.last_error: str | None = None
        self._last_cleanup_date: date | None = None

    async def async_consider_synthetic_command(
        self,
        *,
        command_id: str,
        evaluated_at: datetime,
        health_state: str,
        observation_age_seconds: float | None,
        observation_stale_after_seconds: float,
        controller_available: bool,
        ownership_confirmed: bool,
        active_watering_conflict: bool,
        execution_authorization_status: str,
    ) -> SafetyPreemptionEvent | None:
        """Preempt a synthetic command lifecycle when any hard safety gate fails."""

        if not self._acknowledgements.is_pending(command_id):
            raise ValueError("pending_acknowledgement_not_found")
        reasons = evaluate_preemption_reasons(
            health_state=health_state,
            observation_age_seconds=observation_age_seconds,
            observation_stale_after_seconds=observation_stale_after_seconds,
            controller_available=controller_available,
            ownership_confirmed=ownership_confirmed,
            active_watering_conflict=active_watering_conflict,
            execution_authorization_status=execution_authorization_status,
        )
        if not reasons:
            return None
        event = build_preemption_event(
            command_id=command_id,
            evaluated_at=evaluated_at,
            reason_codes=reasons,
        )
        success = await self._hass.async_add_executor_job(self._write_event, event)
        if not success:
            return event
        self.event_count += 1
        self.last_event = event
        await self._acknowledgements.async_preempt_synthetic(
            command_id=command_id,
            observed_at=evaluated_at,
            detail_code="safety_preemption_required",
        )
        return event

    def _write_event(self, event: SafetyPreemptionEvent) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            local_date = event.evaluated_at_utc.date()
            self._cleanup(local_date)
            path = self._root / (
                f"irrigationos_safety_preemption_{local_date.isoformat()}.jsonl"
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "safety_preemption_log_write_failed"
            return False

    def _cleanup(self, today: date) -> None:
        if self._last_cleanup_date == today:
            return
        self._last_cleanup_date = today
        oldest = today - timedelta(days=SAFETY_PREEMPTION_RETENTION_DAYS - 1)
        for path in self._root.glob("irrigationos_safety_preemption_????-??-??.jsonl"):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_safety_preemption_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe preemption evidence without exposing identifiers."""

        return {
            "event_count": self.event_count,
            "last_reason_codes": (
                () if self.last_event is None else self.last_event.reason_codes
            ),
            "synthetic_only": True,
            "dispatch_capability": False,
            "last_error": self.last_error,
        }
