"""Structured JSONL acceptance evidence for supervised operational watering."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..first_live_delivery.acceptance import (
    FIRST_LIVE_ACCEPTANCE_RECORD_SCHEMA_VERSION,
    FirstLiveAcceptanceRecord,
    FirstLiveAcceptanceStatus,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SUPERVISED_OPERATION_ACCEPTANCE_STORE_VERSION = 1
SUPERVISED_OPERATION_ACCEPTANCE_RECORD_SCHEMA_VERSION = (
    FIRST_LIVE_ACCEPTANCE_RECORD_SCHEMA_VERSION
)


class JsonlSupervisedOperationAcceptanceSink:
    """Append terminal structured operation results to a local JSONL stream."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def async_record(self, record: FirstLiveAcceptanceRecord) -> bool:
        """Persist one terminal result without blocking the HA event loop."""

        return await asyncio.to_thread(self._write, record)

    def _write(self, record: FirstLiveAcceptanceRecord) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        record.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                handle.write("\n")
            return True
        except (OSError, TypeError, ValueError):
            return False


class SupervisedOperationAcceptanceManager:
    """Persist and expose the latest supervised operational result."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store[dict[str, Any]](
            hass,
            SUPERVISED_OPERATION_ACCEPTANCE_STORE_VERSION,
            f"irrigationos.{entry_id}.supervised_operation_acceptance",
        )
        self.latest: FirstLiveAcceptanceRecord | None = None
        self.last_persistence_error: str | None = None

    async def async_initialize(self) -> None:
        """Restore only the latest completed result; never restore an operation."""

        try:
            stored = await self._store.async_load()
        except Exception:
            self.last_persistence_error = "supervised_acceptance_load_failed"
            return
        if stored is None:
            return
        try:
            self.latest = FirstLiveAcceptanceRecord.from_dict(stored)
            self.last_persistence_error = None
        except (KeyError, TypeError, ValueError):
            self.latest = None
            self.last_persistence_error = "supervised_acceptance_restore_failed"

    async def async_record(self, record: FirstLiveAcceptanceRecord) -> bool:
        """Persist a terminal result before exposing it as latest state."""

        try:
            await self._store.async_save(record.to_dict())
        except Exception:
            self.latest = None
            self.last_persistence_error = "supervised_acceptance_save_failed"
            return False
        self.latest = record
        self.last_persistence_error = None
        return True

    @property
    def status(self) -> FirstLiveAcceptanceStatus:
        """Return the latest structured acceptance status."""

        if self.latest is None:
            return FirstLiveAcceptanceStatus.NOT_AVAILABLE
        return self.latest.status

    def diagnostics(self) -> dict[str, Any]:
        """Return only privacy-safe structured acceptance evidence."""

        return {
            "status": self.status.value,
            "latest": None if self.latest is None else self.latest.to_dict(),
            "last_persistence_error": self.last_persistence_error,
            "schema_version": FIRST_LIVE_ACCEPTANCE_RECORD_SCHEMA_VERSION,
        }


async def async_record_terminal_acceptance(
    record: FirstLiveAcceptanceRecord,
    *,
    history: JsonlSupervisedOperationAcceptanceSink,
    latest: SupervisedOperationAcceptanceManager,
) -> None:
    """Write independent append-only history and latest-result persistence."""

    await history.async_record(record)
    await latest.async_record(record)
