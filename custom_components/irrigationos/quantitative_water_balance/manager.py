"""Fail-closed persistence for immutable forecast-deferral ledger events."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import WaterBalanceLedgerEvent, WaterBalanceLedgerEventKind, WaterBalanceTargetState

WATER_BALANCE_LEDGER_STORE_VERSION = 1
WATER_BALANCE_LEDGER_PAYLOAD_SCHEMA_VERSION = 2
MAX_LEDGER_EVENTS = 4096
MAX_RESOLVED_FORECAST_EVENTS = 256


class WaterBalanceLedgerManager:
    """Persist only decision/reconciliation facts, never current authority."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            WATER_BALANCE_LEDGER_STORE_VERSION,
            f"irrigationos.{entry_id}.water_balance_ledger",
        )
        self._events: tuple[WaterBalanceLedgerEvent, ...] = ()
        self._target_states: tuple[WaterBalanceTargetState, ...] = ()
        self.healthy = True
        self.last_error: str | None = None

    @property
    def events(self) -> tuple[WaterBalanceLedgerEvent, ...]:
        """Return validated immutable ledger evidence."""

        return self._events

    @property
    def target_states(self) -> tuple[WaterBalanceTargetState, ...]:
        """Return bounded current scientific state, one record per target."""

        return self._target_states

    async def async_initialize(self) -> None:
        """Restore validated events; corruption fails closed to no usable evidence."""

        try:
            stored = await self._store.async_load()
            if stored is not None and not isinstance(stored, dict):
                raise ValueError("ledger payload must be a mapping")
            payload_schema = 1 if stored is None else int(stored.get("schema_version", 1))
            if payload_schema not in {1, WATER_BALANCE_LEDGER_PAYLOAD_SCHEMA_VERSION}:
                raise ValueError("unsupported ledger payload schema")
            raw = [] if stored is None else stored.get("forecast_events", stored.get("events", []))
            if not isinstance(raw, list):
                raise ValueError("ledger events must be a list")
            events = tuple(WaterBalanceLedgerEvent.from_dict(item) for item in raw)
            keys = tuple((item.recorded_at, item.event_id) for item in events)
            if keys != tuple(sorted(set(keys))):
                raise ValueError("ledger events are not deterministic and unique")
            self._events = events
            raw_states = [] if stored is None else stored.get("target_states", [])
            if not isinstance(raw_states, list):
                raise ValueError("water-balance target states must be a list")
            states = tuple(WaterBalanceTargetState.from_dict(item) for item in raw_states)
            _validate_target_states(states)
            self._target_states = states
            self.healthy = True
            self.last_error = None
        except (KeyError, TypeError, ValueError, OSError):
            self._events = ()
            self._target_states = ()
            self.healthy = False
            self.last_error = "water_balance_ledger_invalid"

    async def async_append(self, event: WaterBalanceLedgerEvent) -> bool:
        """Durably append one idempotent event before exposing it to consumers."""

        return await self.async_append_many((event,))

    async def async_append_many(self, events: tuple[WaterBalanceLedgerEvent, ...]) -> bool:
        """Backward-compatible forecast-event append boundary."""

        return await self.async_commit(forecast_events=events)

    async def async_commit(
        self,
        *,
        target_states: tuple[WaterBalanceTargetState, ...] = (),
        forecast_events: tuple[WaterBalanceLedgerEvent, ...] = (),
    ) -> bool:
        """Atomically persist changed current state and forecast facts once."""

        if not self.healthy:
            return False
        by_id = {item.event_id: item for item in self._events}
        additions: list[WaterBalanceLedgerEvent] = []
        for event in forecast_events:
            existing = by_id.get(event.event_id)
            if existing is not None:
                if existing != event:
                    self.healthy = False
                    self.last_error = "water_balance_ledger_event_conflict"
                    return False
                continue
            by_id[event.event_id] = event
            additions.append(event)
        candidate_events = tuple(
            sorted(
                (*self._events, *additions),
                key=lambda item: (item.recorded_at, item.event_id),
            )
        )
        candidate_events = _compact_resolved_forecasts(candidate_events)
        if len(candidate_events) > MAX_LEDGER_EVENTS:
            self.healthy = False
            self.last_error = "water_balance_ledger_capacity_reached"
            return False
        state_by_target = {item.target: item for item in self._target_states}
        try:
            for state in target_states:
                _validate_state_transition(state_by_target.get(state.target), state)
                state_by_target[state.target] = state
            candidate_states = tuple(state_by_target[key] for key in sorted(state_by_target))
            _validate_target_states(candidate_states)
        except ValueError:
            self.healthy = False
            self.last_error = "water_balance_target_state_invalid"
            return False
        if candidate_events == self._events and candidate_states == self._target_states:
            return True
        try:
            await self._store.async_save(
                {
                    "schema_version": WATER_BALANCE_LEDGER_PAYLOAD_SCHEMA_VERSION,
                    "target_states": [item.to_dict() for item in candidate_states],
                    "forecast_events": [item.to_dict() for item in candidate_events],
                }
            )
        except Exception:
            self.last_error = "water_balance_ledger_save_failed"
            self.healthy = False
            return False
        self._events = candidate_events
        self._target_states = candidate_states
        self.last_error = None
        return True

    def diagnostics(self) -> dict[str, object]:
        """Return a privacy-safe persistence summary."""

        return {
            "healthy": self.healthy,
            "event_count": len(self._events),
            "target_state_count": len(self._target_states),
            "last_error": self.last_error,
            "store_version": WATER_BALANCE_LEDGER_STORE_VERSION,
            "schema_version": WATER_BALANCE_LEDGER_PAYLOAD_SCHEMA_VERSION,
            "execution_authorized": False,
        }


def _validate_target_states(states: tuple[WaterBalanceTargetState, ...]) -> None:
    targets = tuple(item.target for item in states)
    if targets != tuple(sorted(set(targets))):
        raise ValueError("target states must be deterministic and unique")


def _validate_state_transition(
    previous: WaterBalanceTargetState | None, candidate: WaterBalanceTargetState
) -> None:
    if previous is None:
        return
    if candidate.accounted_through < previous.accounted_through:
        raise ValueError("target-state replay")
    if candidate.accounted_through == previous.accounted_through:
        if candidate != previous:
            raise ValueError("target-state boundary conflict")
        return
    if candidate.window_start != previous.accounted_through:
        raise ValueError("target-state gap or overlap")


def _compact_resolved_forecasts(
    events: tuple[WaterBalanceLedgerEvent, ...],
) -> tuple[WaterBalanceLedgerEvent, ...]:
    """Retain every unresolved deferral and a bounded resolved audit tail."""

    reconciled = {
        event.forecast_id
        for event in events
        if event.kind is WaterBalanceLedgerEventKind.FORECAST_RECONCILIATION
    }
    unresolved = tuple(
        event
        for event in events
        if event.kind is WaterBalanceLedgerEventKind.FORECAST_DEFERRAL
        and event.forecast_id not in reconciled
    )
    resolved = tuple(event for event in events if event not in unresolved)
    return tuple(
        sorted(
            (*resolved[-MAX_RESOLVED_FORECAST_EVENTS:], *unresolved),
            key=lambda item: (item.recorded_at, item.event_id),
        )
    )
