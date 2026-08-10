"""Home Assistant persistence and presentation boundary for session history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..controllers import ControllerRegistrySnapshot
from .models import (
    WateringSession,
    WateringSessionEvent,
    safe_session_summary,
)
from .reconciliation import SessionObservationContext, WateringSessionReconciler
from .session_log import DailyWateringSessionLog

SESSION_HISTORY_STORE_VERSION = 1
MAX_COMPLETED_SESSIONS = 100

_LOGGER = logging.getLogger(__name__)


class WateringSessionHistoryManager:
    """Own restart-safe watering sessions, persistence, and safe evidence logs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        root: Path,
        timezone: ZoneInfo,
    ) -> None:
        self._hass = hass
        self._timezone = timezone
        self._store = Store[dict[str, Any]](
            hass,
            SESSION_HISTORY_STORE_VERSION,
            f"irrigationos.{entry_id}.watering_sessions",
        )
        self._reconciler = WateringSessionReconciler()
        self.session_log = DailyWateringSessionLog(root, timezone)
        self.persistence_healthy = True
        self.log_healthy = True
        self.restored_active_count = 0

    @property
    def active_sessions(self) -> tuple[WateringSession, ...]:
        """Return active canonical sessions."""

        return self._reconciler.active_sessions

    @property
    def completed_sessions(self) -> tuple[WateringSession, ...]:
        """Return recent completed sessions newest first."""

        return self._reconciler.completed_sessions

    @property
    def last_completed_session(self) -> WateringSession | None:
        """Return the most recently completed session."""

        completed = self.completed_sessions
        return completed[0] if completed else None

    async def async_initialize(self) -> None:
        """Restore active and recent completed session evidence."""

        try:
            stored = await self._store.async_load()
            active, completed = _restore_sessions(stored)
        except (KeyError, TypeError, ValueError):
            active, completed = (), ()
            self.persistence_healthy = False
            _LOGGER.warning("Unable to restore IrrigationOS watering-session history")
        except Exception:
            active, completed = (), ()
            self.persistence_healthy = False
            _LOGGER.exception("Unable to load IrrigationOS watering-session history")
        restored = tuple(session.reconstructed() for session in active if session.active)
        self.restored_active_count = len(restored)
        self._reconciler = WateringSessionReconciler(
            active_sessions=restored,
            completed_sessions=completed[:MAX_COMPLETED_SESSIONS],
        )

    async def async_reconcile(
        self,
        snapshot: ControllerRegistrySnapshot,
        context: SessionObservationContext,
    ) -> tuple[WateringSessionEvent, ...]:
        """Reconcile, persist, and export one successful canonical snapshot."""

        events = self._reconciler.reconcile(snapshot, context)
        if not events:
            return ()
        batch_log_healthy = True
        for event in events:
            payload = _safe_log_payload(event)
            success = await self._hass.async_add_executor_job(
                self.session_log.record,
                event.recorded_at,
                payload,
            )
            batch_log_healthy = batch_log_healthy and success
        self.log_healthy = batch_log_healthy
        await self._async_persist()
        return events

    async def async_shutdown(self) -> None:
        """Persist the latest state before config-entry unload."""

        await self._async_persist()

    def sessions_today(self, now: datetime | None = None) -> int:
        """Count sessions first observed on the current local day."""

        current = (now or datetime.now(UTC)).astimezone(self._timezone).date()
        sessions = (*self.active_sessions, *self.completed_sessions)
        return sum(
            session.first_observed_at.astimezone(self._timezone).date() == current
            for session in sessions
        )

    def diagnostics(self) -> dict[str, object]:
        """Return vendor-ID-free session and persistence diagnostics."""

        return {
            "active_session_count": len(self.active_sessions),
            "completed_session_count": len(self.completed_sessions),
            "sessions_today": self.sessions_today(),
            "restored_active_count": self.restored_active_count,
            "persistence_healthy": self.persistence_healthy,
            "log_healthy": self.log_healthy,
            "active_sessions": [
                safe_session_summary(session) for session in self.active_sessions
            ],
            "last_completed_session": (
                None
                if self.last_completed_session is None
                else safe_session_summary(self.last_completed_session)
            ),
            "session_log": self.session_log.diagnostics(),
        }

    async def _async_persist(self) -> None:
        completed = self.completed_sessions[:MAX_COMPLETED_SESSIONS]
        payload = {
            "active_sessions": [session.to_dict() for session in self.active_sessions],
            "completed_sessions": [session.to_dict() for session in completed],
        }
        try:
            await self._store.async_save(payload)
            self.persistence_healthy = True
        except Exception:
            self.persistence_healthy = False
            _LOGGER.exception("Unable to persist IrrigationOS watering-session history")


def _restore_sessions(
    stored: object,
) -> tuple[tuple[WateringSession, ...], tuple[WateringSession, ...]]:
    if stored is None:
        return (), ()
    if not isinstance(stored, dict):
        raise ValueError("watering-session storage must be a mapping")
    active_values = stored.get("active_sessions", [])
    completed_values = stored.get("completed_sessions", [])
    if not isinstance(active_values, list) or not isinstance(completed_values, list):
        raise ValueError("watering-session storage collections must be lists")
    return (
        tuple(WateringSession.from_dict(item) for item in active_values),
        tuple(WateringSession.from_dict(item) for item in completed_values),
    )


def _safe_log_payload(event: WateringSessionEvent) -> dict[str, object]:
    session = event.session
    return {
        "event_type": event.event_type.value,
        "session_id": session.session_id,
        "slot_number": session.slot_number,
        "area_name": session.area_name,
        "started_at": session.started_at.isoformat(),
        "ended_at": None if session.ended_at is None else session.ended_at.isoformat(),
        "duration_seconds": session.duration_seconds,
        "attribution": session.attribution.value,
        "attribution_confidence": session.attribution_confidence,
        "attribution_evidence": list(session.attribution_evidence),
        "observation_source": session.observation_source.value,
        "observation_quality": session.observation_quality.value,
        "timestamp_precision": session.timestamp_precision.value,
        "reconstructed_after_restart": session.reconstructed_after_restart,
        "incomplete": session.incomplete,
    }
