"""Persistent explicit controller ownership commissioning manager."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .engine import build_ownership_commissioning_summary

OWNERSHIP_STORE_VERSION = 1


class OwnershipCommissioningManager:
    """Persist only explicit operator commissioning decisions; never command equipment."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass, OWNERSHIP_STORE_VERSION, f"irrigationos.{entry_id}.ownership_commissioning"
        )
        self._stored: dict[str, Any] = {}
        self._controller_ids: tuple[str, ...] = ()
        self.summary = build_ownership_commissioning_summary(controller_ids=(), stored=None)
        self.last_error: str | None = None

    async def async_initialize(self) -> None:
        try:
            stored = await self._store.async_load()
        except Exception:
            stored = None
            self.last_error = "ownership_store_load_failed"
        self._stored = dict(stored) if isinstance(stored, dict) else {}
        self._rebuild()

    def consider_topology(self, controller_ids: tuple[str, ...]) -> None:
        self._controller_ids = tuple(sorted(set(controller_ids)))
        self._rebuild()

    async def async_confirm_ownership(self) -> bool:
        if not self._controller_ids:
            return False
        now = datetime.now(UTC)
        revision = _next_revision(self._stored.get("commissioning_revision"))
        self._stored = {
            "state": "confirmed",
            "controller_ids": list(self._controller_ids),
            "confirmed_at": now.isoformat(),
            "boundary_reviewed_at": None,
            "revoked_at": None,
            "commissioning_revision": revision,
        }
        return await self._save_and_rebuild()

    async def async_acknowledge_boundary_review(self) -> bool:
        if not self.summary.ownership_confirmed:
            return False
        self._stored["boundary_reviewed_at"] = datetime.now(UTC).isoformat()
        self._stored["commissioning_revision"] = _next_revision(
            self._stored.get("commissioning_revision")
        )
        return await self._save_and_rebuild()

    async def async_revoke(self) -> bool:
        self._stored = {
            "state": "revoked",
            "controller_ids": list(self._controller_ids),
            "confirmed_at": None,
            "boundary_reviewed_at": None,
            "revoked_at": datetime.now(UTC).isoformat(),
            "commissioning_revision": _next_revision(
                self._stored.get("commissioning_revision")
            ),
        }
        return await self._save_and_rebuild()

    async def _save_and_rebuild(self) -> bool:
        try:
            await self._store.async_save(self._stored)
        except Exception:
            self.last_error = "ownership_store_save_failed"
            return False
        self.last_error = None
        self._rebuild()
        return True

    def _rebuild(self) -> None:
        self.summary = build_ownership_commissioning_summary(
            controller_ids=self._controller_ids, stored=self._stored
        )

    def diagnostics(self) -> dict[str, object]:
        payload = self.summary.to_dict()
        payload["last_error"] = self.last_error
        return payload


def _next_revision(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value + 1
    return 1
