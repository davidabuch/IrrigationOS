"""Non-actuating command acknowledgement and timeout evidence contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

COMMAND_ACKNOWLEDGEMENT_SCHEMA_VERSION = 1


class CommandAcknowledgementState(StrEnum):
    """Deterministic acknowledgement lifecycle states."""

    WAITING = "waiting"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class CommandAcknowledgementRecord:
    """Immutable acknowledgement lifecycle evidence for a hypothetical dispatch."""

    event_id: str
    command_id: str
    state: CommandAcknowledgementState
    recorded_at_utc: datetime
    deadline_at_utc: datetime
    detail_code: str
    synthetic_only: bool = True
    schema_version: int = COMMAND_ACKNOWLEDGEMENT_SCHEMA_VERSION

    @property
    def terminal(self) -> bool:
        """Return whether no further acknowledgement transition is permitted."""

        return self.state is not CommandAcknowledgementState.WAITING

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe immutable evidence."""

        payload = asdict(self)
        payload["state"] = self.state.value
        payload["recorded_at_utc"] = self.recorded_at_utc.isoformat()
        payload["deadline_at_utc"] = self.deadline_at_utc.isoformat()
        return payload
