"""Immutable contracts for one bounded unattended irrigation canary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

UNATTENDED_CANARY_SCHEMA_VERSION = 1


class UnattendedCanaryApprovalState(StrEnum):
    """Ephemeral single-use approval state."""

    NONE = "none"
    APPROVED = "approved"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class UnattendedCanaryAuthorizationStatus(StrEnum):
    """Outcome of an explicit approval request."""

    APPROVED = "approved"
    BLOCKED = "blocked"


class UnattendedCanaryRunStatus(StrEnum):
    """Outcome of one canary dispatch attempt."""

    BLOCKED = "blocked"
    AUDIT_FAILED = "audit_failed"
    TRANSPORT_FAILED = "transport_failed"
    START_DISPATCHED = "start_dispatched"


@dataclass(frozen=True, slots=True)
class UnattendedCanaryApproval:
    """One restart-ephemeral approval bound to an exact target and runtime."""

    approval_id: str
    controller_slot: int
    area_slot: int
    runtime_seconds: int
    approved_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    schema_version: int = UNATTENDED_CANARY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.approval_id.strip():
            raise ValueError("approval_id must not be blank")
        if self.controller_slot < 1 or self.area_slot < 1:
            raise ValueError("canonical target slots must be positive")
        if not 15 <= self.runtime_seconds <= 60:
            raise ValueError("canary runtime must be between 15 and 60 seconds")
        for value in (self.approved_at, self.expires_at, self.consumed_at):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("approval timestamps must be timezone-aware")
        if self.expires_at <= self.approved_at:
            raise ValueError("approval expiry must follow approval creation")
        if self.consumed_at is not None and self.consumed_at < self.approved_at:
            raise ValueError("approval cannot be consumed before creation")

    def state_at(self, now: datetime) -> UnattendedCanaryApprovalState:
        """Return the deterministic state at one aware timestamp."""

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if self.consumed_at is not None:
            return UnattendedCanaryApprovalState.CONSUMED
        if now >= self.expires_at:
            return UnattendedCanaryApprovalState.EXPIRED
        return UnattendedCanaryApprovalState.APPROVED

    def to_dict(self, now: datetime) -> dict[str, Any]:
        """Return privacy-safe entity and diagnostics data."""

        return {
            "approval_id": self.approval_id,
            "state": self.state_at(now).value,
            "controller_slot": self.controller_slot,
            "area_slot": self.area_slot,
            "runtime_seconds": self.runtime_seconds,
            "approved_at": self.approved_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "consumed_at": (
                None if self.consumed_at is None else self.consumed_at.isoformat()
            ),
            "single_use": True,
            "persists_across_restart": False,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class UnattendedCanaryAuthorizationResult:
    """Privacy-safe result of an approval request."""

    status: UnattendedCanaryAuthorizationStatus
    blocker_codes: tuple[str, ...]
    approval_id: str | None
    controller_slot: int
    area_slot: int
    runtime_seconds: int


@dataclass(frozen=True, slots=True)
class UnattendedCanaryRunResult:
    """Privacy-safe result of one execution request."""

    status: UnattendedCanaryRunStatus
    blocker_codes: tuple[str, ...]
    canary_id: str | None
    approval_id: str | None
    controller_slot: int
    area_slot: int
    runtime_seconds: int
