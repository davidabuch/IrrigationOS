"""Fail-closed persistence for immutable forecast-deferral ledger events."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import WaterBalanceLedgerEvent

WATER_BALANCE_LEDGER_STORE_VERSION = 1
MAX_LEDGER_EVENTS = 4096


class WaterBalanceLedgerManager:
    """Persist only decision/reconciliation facts, never current authority."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            WATER_BALANCE_LEDGER_STORE_VERSION,
            f"irrigationos.{entry_id}.water_balance_ledger",
        )
        self._events: tuple[WaterBalanceLedgerEvent, ...] = ()
        self.healthy = True
        self.last_error: str | None = None

    @property
    def events(self) -> tuple[WaterBalanceLedgerEvent, ...]:
        """Return validated immutable ledger evidence."""

        return self._events

    async def async_initialize(self) -> None:
        """Restore validated events; corruption fails closed to no usable evidence."""

        try:
            stored = await self._store.async_load()
            if stored is not None and not isinstance(stored, dict):
                raise ValueError("ledger payload must be a mapping")
            raw = [] if stored is None else stored.get("events", [])
            if not isinstance(raw, list):
                raise ValueError("ledger events must be a list")
            events = tuple(WaterBalanceLedgerEvent.from_dict(item) for item in raw)
            keys = tuple((item.recorded_at, item.event_id) for item in events)
            if keys != tuple(sorted(set(keys))):
                raise ValueError("ledger events are not deterministic and unique")
            self._events = events
            self.healthy = True
            self.last_error = None
        except (KeyError, TypeError, ValueError, OSError):
            self._events = ()
            self.healthy = False
            self.last_error = "water_balance_ledger_invalid"

    async def async_append(self, event: WaterBalanceLedgerEvent) -> bool:
        """Durably append one idempotent event before exposing it to consumers."""

        if not self.healthy:
            return False
        by_id = {item.event_id: item for item in self._events}
        existing = by_id.get(event.event_id)
        if existing is not None:
            return existing == event
        if len(self._events) >= MAX_LEDGER_EVENTS:
            self.healthy = False
            self.last_error = "water_balance_ledger_capacity_reached"
            return False
        candidate = tuple(
            sorted(
                (*self._events, event),
                key=lambda item: (item.recorded_at, item.event_id),
            )
        )
        try:
            await self._store.async_save(
                {"events": [item.to_dict() for item in candidate]}
            )
        except Exception:
            self.last_error = "water_balance_ledger_save_failed"
            self.healthy = False
            return False
        self._events = candidate
        self.last_error = None
        return True

    def diagnostics(self) -> dict[str, object]:
        """Return a privacy-safe persistence summary."""

        return {
            "healthy": self.healthy,
            "event_count": len(self._events),
            "last_error": self.last_error,
            "schema_version": WATER_BALANCE_LEDGER_STORE_VERSION,
            "execution_authorized": False,
        }
