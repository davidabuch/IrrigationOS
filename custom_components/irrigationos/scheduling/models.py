"""Immutable contracts for deterministic irrigation scheduling."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from ..planning import IrrigationPlan, PlanAction

SCHEDULING_SCHEMA_VERSION = 1
SCHEDULING_ALGORITHM_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ScheduleStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    NOT_SCHEDULABLE = "not_schedulable"


class ScheduledActionDisposition(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL_ONLY = "manual_only"
    BLOCKED = "blocked"


def _id(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _time(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _sorted_text(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    normalized = tuple(value.strip().casefold() for value in values)
    if any(not value for value in normalized) or normalized != tuple(sorted(set(normalized))):
        raise ValueError(f"{name} must use deterministic unique ordering")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(value[key]) for key in sorted(value, key=str)}
    return value


class SerializableSchedulingModel:
    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        result = _serialize(self)
        if not isinstance(result, dict):
            raise TypeError("scheduling model did not serialize to a dictionary")
        return result


@dataclass(frozen=True, slots=True)
class SchedulingWindow(SerializableSchedulingModel):
    window_id: str
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        _id("window_id", self.window_id)
        _time("starts_at", self.starts_at)
        _time("ends_at", self.ends_at)
        if self.ends_at <= self.starts_at:
            raise ValueError("scheduling window must have positive duration")


@dataclass(frozen=True, slots=True)
class SchedulingPolicy(SerializableSchedulingModel):
    policy_id: str
    policy_version: str
    minimum_inter_action_seconds: int = 0

    def __post_init__(self) -> None:
        _id("policy_id", self.policy_id)
        _version("policy_version", self.policy_version)
        if (
            isinstance(self.minimum_inter_action_seconds, bool)
            or not isinstance(self.minimum_inter_action_seconds, int)
            or self.minimum_inter_action_seconds < 0
        ):
            raise ValueError("minimum_inter_action_seconds must be non-negative")


@dataclass(frozen=True, slots=True)
class SchedulingRequest(SerializableSchedulingModel):
    request_id: str
    plan: IrrigationPlan
    windows: tuple[SchedulingWindow, ...]
    policy: SchedulingPolicy
    created_at: datetime
    blocking_constraints: tuple[str, ...] = ()
    schema_version: int = SCHEDULING_SCHEMA_VERSION
    algorithm_version: str = SCHEDULING_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        if not isinstance(self.plan, IrrigationPlan):
            raise ValueError("plan must use IrrigationPlan")
        if not isinstance(self.windows, tuple) or any(
            not isinstance(window, SchedulingWindow) for window in self.windows
        ):
            raise ValueError("windows must contain SchedulingWindow values")
        ordered = tuple(
            (window.starts_at, window.ends_at, window.window_id)
            for window in self.windows
        )
        if ordered != tuple(sorted(set(ordered))):
            raise ValueError("windows must use deterministic unique ordering")
        if not isinstance(self.policy, SchedulingPolicy):
            raise ValueError("policy must be canonical")
        _time("created_at", self.created_at)
        _sorted_text("blocking_constraints", self.blocking_constraints)
        if self.schema_version != SCHEDULING_SCHEMA_VERSION:
            raise ValueError("unsupported scheduling schema version")
        _version("algorithm_version", self.algorithm_version)


@dataclass(frozen=True, slots=True)
class ScheduledAction(SerializableSchedulingModel):
    scheduled_action_id: str
    plan_action_id: str
    disposition: ScheduledActionDisposition
    target_id: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    cycle_starts_at: tuple[datetime, ...]
    cycle_runtime_seconds: int | None
    window_id: str | None
    blocking_reasons: tuple[str, ...]
    source_action: PlanAction

    def __post_init__(self) -> None:
        _id("scheduled_action_id", self.scheduled_action_id)
        _id("plan_action_id", self.plan_action_id)
        if not isinstance(self.disposition, ScheduledActionDisposition):
            raise ValueError("disposition must be canonical")
        if self.target_id is not None:
            _id("target_id", self.target_id)
        if not isinstance(self.source_action, PlanAction):
            raise ValueError("source_action must use PlanAction")
        _sorted_text("blocking_reasons", self.blocking_reasons)
        if self.disposition is ScheduledActionDisposition.SCHEDULED:
            if self.starts_at is None or self.ends_at is None or self.window_id is None:
                raise ValueError("scheduled actions require times and window")
            _time("starts_at", self.starts_at)
            _time("ends_at", self.ends_at)
            if self.ends_at <= self.starts_at:
                raise ValueError("scheduled action must have positive duration")
            if not self.cycle_starts_at:
                raise ValueError("scheduled action requires cycle starts")
            for value in self.cycle_starts_at:
                _time("cycle_starts_at", value)
            if self.cycle_runtime_seconds is None or self.cycle_runtime_seconds <= 0:
                raise ValueError("scheduled action requires positive cycle runtime")
        elif any(
            value is not None
            for value in (self.starts_at, self.ends_at, self.window_id, self.cycle_runtime_seconds)
        ) or self.cycle_starts_at:
            raise ValueError("unscheduled actions cannot contain schedule timing")


@dataclass(frozen=True, slots=True)
class IrrigationSchedule(SerializableSchedulingModel):
    schedule_id: str
    request_id: str
    plan_id: str
    status: ScheduleStatus
    actions: tuple[ScheduledAction, ...]
    unresolved_issues: tuple[str, ...]
    policy_id: str
    policy_version: str
    algorithm_version: str
    created_at: datetime
    schema_version: int = SCHEDULING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("schedule_id", self.schedule_id),
            ("request_id", self.request_id),
            ("plan_id", self.plan_id),
            ("policy_id", self.policy_id),
        ):
            _id(name, value)
        if not isinstance(self.status, ScheduleStatus):
            raise ValueError("status must be canonical")
        if not isinstance(self.actions, tuple) or any(
            not isinstance(action, ScheduledAction) for action in self.actions
        ):
            raise ValueError("actions must contain ScheduledAction values")
        ids = tuple(action.scheduled_action_id for action in self.actions)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("actions must use deterministic unique ordering")
        _sorted_text("unresolved_issues", self.unresolved_issues)
        _version("policy_version", self.policy_version)
        _version("algorithm_version", self.algorithm_version)
        _time("created_at", self.created_at)
        if self.schema_version != SCHEDULING_SCHEMA_VERSION:
            raise ValueError("unsupported scheduling schema version")
