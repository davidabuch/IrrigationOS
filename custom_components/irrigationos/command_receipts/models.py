"""Non-actuating command intent and receipt evidence contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

COMMAND_RECEIPT_SCHEMA_VERSION = 1


class CommandIntentAction(StrEnum):
    """Canonical future irrigation command actions."""

    START_ZONE = "start_zone"
    STOP_ZONE = "stop_zone"
    STOP_ALL = "stop_all"


class CommandAttribution(StrEnum):
    """Origin of a recorded command intent."""

    IRRIGATIONOS = "irrigationos"
    OPERATOR = "operator"
    SAFETY_MANAGER = "safety_manager"


class CommandReceiptOutcome(StrEnum):
    """Current non-actuating receipt outcomes."""

    NOT_DISPATCHED = "not_dispatched"


@dataclass(frozen=True, slots=True)
class CommandIntent:
    """Canonical command intent recorded before any future dispatch boundary."""

    command_id: str
    created_at_utc: datetime
    attribution: CommandAttribution
    action: CommandIntentAction
    controller_id: str
    zone_id: str | None
    requested_runtime_seconds: int | None
    reason_code: str
    schema_version: int = COMMAND_RECEIPT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["created_at_utc"] = self.created_at_utc.isoformat()
        payload["attribution"] = self.attribution.value
        payload["action"] = self.action.value
        return payload


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    """Immutable evidence that an intent was recorded but not dispatched."""

    receipt_id: str
    command_id: str
    recorded_at_utc: datetime
    outcome: CommandReceiptOutcome
    detail_code: str
    schema_version: int = COMMAND_RECEIPT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recorded_at_utc"] = self.recorded_at_utc.isoformat()
        payload["outcome"] = self.outcome.value
        return payload
