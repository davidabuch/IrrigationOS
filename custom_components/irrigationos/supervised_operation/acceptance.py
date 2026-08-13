"""Structured JSONL acceptance evidence for supervised operational watering."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ..first_live_delivery.acceptance import FirstLiveAcceptanceRecord


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
