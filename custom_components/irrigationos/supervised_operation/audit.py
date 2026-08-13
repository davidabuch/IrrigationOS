"""Append-only audit evidence for bounded supervised operational watering."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SupervisedOperationAuditEvent:
    """One privacy-safe operational audit event without provider-native identifiers."""

    event_id: str
    operation_id: str
    event_type: str
    recorded_at: datetime
    controller_slot: int
    area_slot: int
    runtime_seconds: int
    detail_code: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["recorded_at"] = self.recorded_at.isoformat()
        return payload


class SupervisedOperationAuditSink(Protocol):
    """Durable append-only audit boundary for supervised operations."""

    async def async_record(self, event: SupervisedOperationAuditEvent) -> bool:
        """Persist one event and report whether durability was confirmed."""
        ...


class JsonlSupervisedOperationAuditSink:
    """Persist supervised operation events without blocking the HA event loop."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def async_record(self, event: SupervisedOperationAuditEvent) -> bool:
        return await asyncio.to_thread(self._write, event)

    def _write(self, event: SupervisedOperationAuditEvent) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        event.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                handle.write("\n")
            return True
        except (OSError, TypeError, ValueError):
            return False


def new_operation_id() -> str:
    """Return a provider-independent correlation identifier."""

    return f"supervised_operation_{uuid4().hex}"


def build_audit_event(
    *,
    operation_id: str,
    event_type: str,
    recorded_at: datetime,
    controller_slot: int,
    area_slot: int,
    runtime_seconds: int,
    detail_code: str,
) -> SupervisedOperationAuditEvent:
    """Build one immutable operational audit event."""

    return SupervisedOperationAuditEvent(
        event_id=f"supervised_operation_event_{uuid4().hex}",
        operation_id=operation_id,
        event_type=event_type,
        recorded_at=recorded_at,
        controller_slot=controller_slot,
        area_slot=area_slot,
        runtime_seconds=runtime_seconds,
        detail_code=detail_code,
    )
