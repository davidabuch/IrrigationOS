"""Immutable contracts for deterministic irrigation runtime monitoring."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from ..execution import CommandResult, ExecutionPlan

RUNTIME_MONITORING_SCHEMA_VERSION = 1
RUNTIME_MONITORING_ALGORITHM_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class RuntimeStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    MISSED = "missed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    BLOCKED = "blocked"
    NO_EXECUTION = "no_execution"


class RuntimeIssueType(StrEnum):
    MISSING_RESULT = "missing_result"
    RETRY_REQUIRED = "retry_required"
    COMMAND_TIMED_OUT = "command_timed_out"
    COMMAND_REJECTED = "command_rejected"
    TARGET_STATE_MISMATCH = "target_state_mismatch"
    CONTROLLER_OFFLINE = "controller_offline"
    EXTERNAL_INTERRUPTION = "external_interruption"


class RecoveryActionType(StrEnum):
    NONE = "none"
    RETRY_COMMAND = "retry_command"
    RESCHEDULE_REMAINDER = "reschedule_remainder"
    INSPECT_CONTROLLER = "inspect_controller"
    MANUAL_REVIEW = "manual_review"


def _id(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _time(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


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


class SerializableRuntimeModel:
    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        result = _serialize(self)
        if not isinstance(result, dict):
            raise TypeError("runtime model did not serialize to a dictionary")
        return result


@dataclass(frozen=True, slots=True)
class RuntimePolicy(SerializableRuntimeModel):
    policy_id: str
    policy_version: str
    missing_result_grace_seconds: int = 60

    def __post_init__(self) -> None:
        _id("policy_id", self.policy_id)
        _version("policy_version", self.policy_version)
        _non_negative_int("missing_result_grace_seconds", self.missing_result_grace_seconds)


@dataclass(frozen=True, slots=True)
class RuntimeObservation(SerializableRuntimeModel):
    observation_id: str
    observed_at: datetime
    controller_online: bool = True
    interrupted: bool = False
    interruption_reason: str | None = None
    active_target_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _id("observation_id", self.observation_id)
        _time("observed_at", self.observed_at)
        if not isinstance(self.controller_online, bool) or not isinstance(self.interrupted, bool):
            raise ValueError("runtime flags must be boolean")
        if self.interruption_reason is not None and not self.interruption_reason.strip():
            raise ValueError("interruption_reason cannot be blank")
        if self.interrupted and self.interruption_reason is None:
            raise ValueError("interrupted observations require a reason")
        _sorted_text("active_target_ids", self.active_target_ids)


@dataclass(frozen=True, slots=True)
class RuntimeMonitoringRequest(SerializableRuntimeModel):
    request_id: str
    execution_plan: ExecutionPlan
    command_results: tuple[CommandResult, ...]
    observation: RuntimeObservation
    policy: RuntimePolicy
    created_at: datetime
    schema_version: int = RUNTIME_MONITORING_SCHEMA_VERSION
    algorithm_version: str = RUNTIME_MONITORING_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        if not isinstance(self.execution_plan, ExecutionPlan):
            raise ValueError("execution_plan must use ExecutionPlan")
        if not isinstance(self.command_results, tuple) or any(
            not isinstance(result, CommandResult) for result in self.command_results
        ):
            raise ValueError("command_results must contain CommandResult values")
        order = tuple((result.observed_at, result.command_id) for result in self.command_results)
        if order != tuple(sorted(set(order))):
            raise ValueError("command_results must use deterministic unique ordering")
        if not isinstance(self.observation, RuntimeObservation):
            raise ValueError("observation must be canonical")
        if not isinstance(self.policy, RuntimePolicy):
            raise ValueError("policy must be canonical")
        _time("created_at", self.created_at)
        if self.schema_version != RUNTIME_MONITORING_SCHEMA_VERSION:
            raise ValueError("unsupported runtime monitoring schema version")
        _version("algorithm_version", self.algorithm_version)


@dataclass(frozen=True, slots=True)
class RuntimeIssue(SerializableRuntimeModel):
    issue_id: str
    issue_type: RuntimeIssueType
    command_id: str | None
    detail: str

    def __post_init__(self) -> None:
        _id("issue_id", self.issue_id)
        if not isinstance(self.issue_type, RuntimeIssueType):
            raise ValueError("issue_type must be canonical")
        if self.command_id is not None:
            _id("command_id", self.command_id)
        if not self.detail.strip():
            raise ValueError("detail cannot be blank")


@dataclass(frozen=True, slots=True)
class RecoveryRecommendation(SerializableRuntimeModel):
    recommendation_id: str
    action_type: RecoveryActionType
    command_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _id("recommendation_id", self.recommendation_id)
        if not isinstance(self.action_type, RecoveryActionType):
            raise ValueError("action_type must be canonical")
        _sorted_text("command_ids", self.command_ids)
        if not self.reason.strip():
            raise ValueError("reason cannot be blank")


@dataclass(frozen=True, slots=True)
class RuntimeReport(SerializableRuntimeModel):
    report_id: str
    request_id: str
    execution_plan_id: str
    status: RuntimeStatus
    expected_command_count: int
    acknowledged_command_count: int
    unresolved_command_count: int
    issues: tuple[RuntimeIssue, ...]
    recovery_recommendations: tuple[RecoveryRecommendation, ...]
    policy_id: str
    policy_version: str
    algorithm_version: str
    created_at: datetime
    source_execution_plan: ExecutionPlan
    schema_version: int = RUNTIME_MONITORING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("report_id", self.report_id),
            ("request_id", self.request_id),
            ("execution_plan_id", self.execution_plan_id),
            ("policy_id", self.policy_id),
        ):
            _id(name, value)
        if not isinstance(self.status, RuntimeStatus):
            raise ValueError("status must be canonical")
        for count_name, count_value in (
            ("expected_command_count", self.expected_command_count),
            ("acknowledged_command_count", self.acknowledged_command_count),
            ("unresolved_command_count", self.unresolved_command_count),
        ):
            _non_negative_int(count_name, count_value)
        if (
            self.acknowledged_command_count + self.unresolved_command_count
            != self.expected_command_count
        ):
            raise ValueError("runtime command counts must reconcile")
        if not isinstance(self.issues, tuple) or any(
            not isinstance(issue, RuntimeIssue) for issue in self.issues
        ):
            raise ValueError("issues must contain RuntimeIssue values")
        issue_ids = tuple(issue.issue_id for issue in self.issues)
        if issue_ids != tuple(sorted(set(issue_ids))):
            raise ValueError("issues must use deterministic unique ordering")
        if not isinstance(self.recovery_recommendations, tuple) or any(
            not isinstance(item, RecoveryRecommendation) for item in self.recovery_recommendations
        ):
            raise ValueError("recovery_recommendations must be canonical")
        recommendation_ids = tuple(item.recommendation_id for item in self.recovery_recommendations)
        if recommendation_ids != tuple(sorted(set(recommendation_ids))):
            raise ValueError("recovery recommendations must use deterministic unique ordering")
        _version("policy_version", self.policy_version)
        _version("algorithm_version", self.algorithm_version)
        _time("created_at", self.created_at)
        if not isinstance(self.source_execution_plan, ExecutionPlan):
            raise ValueError("source_execution_plan must use ExecutionPlan")
        if self.schema_version != RUNTIME_MONITORING_SCHEMA_VERSION:
            raise ValueError("unsupported runtime monitoring schema version")
