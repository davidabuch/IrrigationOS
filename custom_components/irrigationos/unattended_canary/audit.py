"""Append-only privacy-safe audit evidence for unattended canaries."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class UnattendedCanaryAuditEvent:
    """One canonical audit event without provider-native identifiers."""

    event_id: str
    canary_id: str | None
    approval_id: str
    controller_slot: int
    area_slot: int
    runtime_seconds: int
    event_type: str
    detail_code: str
    recorded_at: datetime

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["recorded_at"] = self.recorded_at.isoformat()
        return payload


class UnattendedCanaryAuditSink(Protocol):
    async def async_record(self, event: UnattendedCanaryAuditEvent) -> bool:
        """Persist one event and report confirmed durability."""
        ...


class JsonlUnattendedCanaryAuditSink:
    """Append deterministic JSON lines without blocking Home Assistant."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def async_record(self, event: UnattendedCanaryAuditEvent) -> bool:
        return await asyncio.to_thread(self._write, event)

    def _write(self, event: UnattendedCanaryAuditEvent) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            return True
        except (OSError, TypeError, ValueError):
            return False


def new_approval_id() -> str:
    return f"unattended_canary_approval_{uuid4().hex}"


def new_canary_id() -> str:
    return f"unattended_canary_{uuid4().hex}"


def build_audit_event(
    *,
    canary_id: str | None,
    approval_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    event_type: str,
    detail_code: str,
    recorded_at: datetime,
) -> UnattendedCanaryAuditEvent:
    return UnattendedCanaryAuditEvent(
        event_id=f"unattended_canary_event_{uuid4().hex}",
        canary_id=canary_id,
        approval_id=approval_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        event_type=event_type,
        detail_code=detail_code,
        recorded_at=recorded_at,
    )
