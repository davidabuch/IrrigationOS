"""Append-only privacy-safe audit evidence for first-live trial attempts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class FirstLiveTrialAuditEvent:
    """One canonical audit event; native provider identifiers are intentionally absent."""

    event_id: str
    attempt_id: str
    event_type: str
    recorded_at: datetime
    controller_id: str
    controller_slot: int
    area_slot: int
    runtime_seconds: int
    detail_code: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["recorded_at"] = self.recorded_at.isoformat()
        return payload


class FirstLiveTrialAuditSink(Protocol):
    """Required durable audit boundary for a physical trial attempt."""

    async def async_record(self, event: FirstLiveTrialAuditEvent) -> bool:
        """Persist one event and return whether durability was confirmed."""
        ...


class JsonlFirstLiveTrialAuditSink:
    """Append first-live audit events to one local JSONL file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def async_record(self, event: FirstLiveTrialAuditEvent) -> bool:
        """Persist without blocking the Home Assistant event loop."""

        return await asyncio.to_thread(self._write, event)

    def _write(self, event: FirstLiveTrialAuditEvent) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")))
                handle.write("\n")
            return True
        except (OSError, TypeError, ValueError):
            return False


def build_audit_event(
    *,
    attempt_id: str,
    event_type: str,
    recorded_at: datetime,
    controller_id: str,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    detail_code: str,
) -> FirstLiveTrialAuditEvent:
    """Build one immutable canonical audit event."""

    return FirstLiveTrialAuditEvent(
        event_id=f"first_live_event_{uuid4().hex}",
        attempt_id=attempt_id,
        event_type=event_type,
        recorded_at=recorded_at,
        controller_id=controller_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        detail_code=detail_code,
    )


def new_attempt_id() -> str:
    """Allocate a non-provider attempt identifier."""

    return f"first_live_attempt_{uuid4().hex}"
