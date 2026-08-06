"""Immutable contracts for deterministic irrigation execution planning."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from ..scheduling import IrrigationSchedule, ScheduledAction

EXECUTION_SCHEMA_VERSION = 1
EXECUTION_ALGORITHM_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ExecutionPlanStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NO_COMMANDS = "no_commands"


class ControllerCommandType(StrEnum):
    START_ZONE = "start_zone"
    STOP_ZONE = "stop_zone"


class ControllerCommandDisposition(StrEnum):
    READY = "ready"
    SKIPPED_IDEMPOTENT = "skipped_idempotent"


class CommandOutcome(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    RETRY_REQUIRED = "retry_required"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


def _id(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _time(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


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


class SerializableExecutionModel:
    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        result = _serialize(self)
        if not isinstance(result, dict):
            raise TypeError("execution model did not serialize to a dictionary")
        return result


@dataclass(frozen=True, slots=True)
class ExecutionPolicy(SerializableExecutionModel):
    policy_id: str
    policy_version: str
    acknowledgement_timeout_seconds: int = 30
    maximum_attempts: int = 3
    retry_delay_seconds: int = 15

    def __post_init__(self) -> None:
        _id("policy_id", self.policy_id)
        _version("policy_version", self.policy_version)
        _positive_int("acknowledgement_timeout_seconds", self.acknowledgement_timeout_seconds)
        _positive_int("maximum_attempts", self.maximum_attempts)
        _positive_int("retry_delay_seconds", self.retry_delay_seconds)


@dataclass(frozen=True, slots=True)
class ExecutionRequest(SerializableExecutionModel):
    request_id: str
    schedule: IrrigationSchedule
    policy: ExecutionPolicy
    created_at: datetime
    safety_blocks: tuple[str, ...] = ()
    completed_idempotency_keys: tuple[str, ...] = ()
    schema_version: int = EXECUTION_SCHEMA_VERSION
    algorithm_version: str = EXECUTION_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        if not isinstance(self.schedule, IrrigationSchedule):
            raise ValueError("schedule must use IrrigationSchedule")
        if not isinstance(self.policy, ExecutionPolicy):
            raise ValueError("policy must be canonical")
        _time("created_at", self.created_at)
        _sorted_text("safety_blocks", self.safety_blocks)
        _sorted_text("completed_idempotency_keys", self.completed_idempotency_keys)
        if self.schema_version != EXECUTION_SCHEMA_VERSION:
            raise ValueError("unsupported execution schema version")
        _version("algorithm_version", self.algorithm_version)


@dataclass(frozen=True, slots=True)
class ControllerCommand(SerializableExecutionModel):
    command_id: str
    idempotency_key: str
    scheduled_action_id: str
    target_id: str
    command_type: ControllerCommandType
    disposition: ControllerCommandDisposition
    planned_at: datetime
    cycle_number: int
    runtime_seconds: int | None
    acknowledgement_timeout_seconds: int
    maximum_attempts: int
    retry_delay_seconds: int
    attribution_source: str
    source_action: ScheduledAction

    def __post_init__(self) -> None:
        for name, value in (
            ("command_id", self.command_id),
            ("idempotency_key", self.idempotency_key),
            ("scheduled_action_id", self.scheduled_action_id),
            ("target_id", self.target_id),
            ("attribution_source", self.attribution_source),
        ):
            _id(name, value)
        if not isinstance(self.command_type, ControllerCommandType):
            raise ValueError("command_type must be canonical")
        if not isinstance(self.disposition, ControllerCommandDisposition):
            raise ValueError("disposition must be canonical")
        _time("planned_at", self.planned_at)
        _positive_int("cycle_number", self.cycle_number)
        if self.command_type is ControllerCommandType.START_ZONE:
            if self.runtime_seconds is None:
                raise ValueError("start commands require runtime_seconds")
            _positive_int("runtime_seconds", self.runtime_seconds)
        elif self.runtime_seconds is not None:
            raise ValueError("stop commands cannot include runtime_seconds")
        _positive_int("acknowledgement_timeout_seconds", self.acknowledgement_timeout_seconds)
        _positive_int("maximum_attempts", self.maximum_attempts)
        _positive_int("retry_delay_seconds", self.retry_delay_seconds)
        if not isinstance(self.source_action, ScheduledAction):
            raise ValueError("source_action must use ScheduledAction")


@dataclass(frozen=True, slots=True)
class ExecutionPlan(SerializableExecutionModel):
    execution_plan_id: str
    request_id: str
    schedule_id: str
    status: ExecutionPlanStatus
    commands: tuple[ControllerCommand, ...]
    unresolved_issues: tuple[str, ...]
    policy_id: str
    policy_version: str
    algorithm_version: str
    created_at: datetime
    source_schedule: IrrigationSchedule
    schema_version: int = EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("execution_plan_id", self.execution_plan_id),
            ("request_id", self.request_id),
            ("schedule_id", self.schedule_id),
            ("policy_id", self.policy_id),
        ):
            _id(name, value)
        if not isinstance(self.status, ExecutionPlanStatus):
            raise ValueError("status must be canonical")
        if not isinstance(self.commands, tuple) or any(
            not isinstance(command, ControllerCommand) for command in self.commands
        ):
            raise ValueError("commands must contain ControllerCommand values")
        order = tuple((command.planned_at, command.command_id) for command in self.commands)
        if order != tuple(sorted(set(order))):
            raise ValueError("commands must use deterministic unique ordering")
        _sorted_text("unresolved_issues", self.unresolved_issues)
        _version("policy_version", self.policy_version)
        _version("algorithm_version", self.algorithm_version)
        _time("created_at", self.created_at)
        if not isinstance(self.source_schedule, IrrigationSchedule):
            raise ValueError("source_schedule must use IrrigationSchedule")
        if self.schema_version != EXECUTION_SCHEMA_VERSION:
            raise ValueError("unsupported execution schema version")


@dataclass(frozen=True, slots=True)
class CommandResult(SerializableExecutionModel):
    command_id: str
    idempotency_key: str
    outcome: CommandOutcome
    attempt_number: int
    observed_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        _id("command_id", self.command_id)
        _id("idempotency_key", self.idempotency_key)
        if not isinstance(self.outcome, CommandOutcome):
            raise ValueError("outcome must be canonical")
        _positive_int("attempt_number", self.attempt_number)
        _time("observed_at", self.observed_at)
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason cannot be blank")
