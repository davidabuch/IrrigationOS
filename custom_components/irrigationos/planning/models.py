"""Immutable contracts for deterministic irrigation planning."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..recommendations import RecommendationAssessment

PLANNING_SCHEMA_VERSION = 1
PLANNING_ALGORITHM_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class PlanStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    NOT_EXECUTABLE = "not_executable"


class PlanActionType(StrEnum):
    IRRIGATE = "irrigate"
    INSPECT = "inspect"
    MONITOR = "monitor"
    NO_ACTION = "no_action"
    PROTECT_FROM_FREEZE = "protect_from_freeze"
    PROTECT_FROM_HEAT = "protect_from_heat"
    SEEK_EXPERT_REVIEW = "seek_expert_review"


class PlanExecutionDisposition(StrEnum):
    READY = "ready"
    MANUAL_ONLY = "manual_only"
    BLOCKED = "blocked"


class PlanQuantityUnit(StrEnum):
    MILLIMETERS = "millimeters"
    INCHES = "inches"
    LITERS = "liters"
    GALLONS = "gallons"


def _id(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _time(name: str, value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")


def _sorted_text(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    normalized = tuple(v.strip().casefold() for v in values)
    if any(not v for v in normalized) or normalized != tuple(sorted(set(normalized))):
        raise ValueError(f"{name} must use deterministic unique ordering")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _serialize(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple | list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize(value[k]) for k in sorted(value, key=str)}
    return value


class SerializablePlanningModel:
    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        result = _serialize(self)
        if not isinstance(result, dict):
            raise TypeError("planning model did not serialize to a dictionary")
        return result


@dataclass(frozen=True, slots=True)
class PlanningDirective(SerializablePlanningModel):
    """Explicit target and quantity supplied to Planning without recomputing science."""
    recommendation_id: str
    target_id: str
    quantity: float | None = None
    quantity_unit: PlanQuantityUnit | None = None
    runtime_seconds: int | None = None
    cycle_count: int = 1
    soak_seconds: int = 0

    def __post_init__(self) -> None:
        _id("recommendation_id", self.recommendation_id)
        _id("target_id", self.target_id)
        if self.quantity is not None:
            if (
                isinstance(self.quantity, bool)
                or not isinstance(self.quantity, (int, float))
                or not isfinite(self.quantity)
                or self.quantity <= 0
            ):
                raise ValueError("quantity must be finite and positive")
            if not isinstance(self.quantity_unit, PlanQuantityUnit):
                raise ValueError("quantity requires a canonical quantity_unit")
        elif self.quantity_unit is not None:
            raise ValueError("quantity_unit requires quantity")
        if self.runtime_seconds is not None and (
            isinstance(self.runtime_seconds, bool)
            or not isinstance(self.runtime_seconds, int)
            or self.runtime_seconds <= 0
        ):
            raise ValueError("runtime_seconds must be a positive integer")
        if (
            isinstance(self.cycle_count, bool)
            or not isinstance(self.cycle_count, int)
            or self.cycle_count < 1
        ):
            raise ValueError("cycle_count must be at least 1")
        if (
            isinstance(self.soak_seconds, bool)
            or not isinstance(self.soak_seconds, int)
            or self.soak_seconds < 0
        ):
            raise ValueError("soak_seconds must be non-negative")
        if self.cycle_count == 1 and self.soak_seconds:
            raise ValueError("soak_seconds requires multiple cycles")


@dataclass(frozen=True, slots=True)
class PlanningPolicy(SerializablePlanningModel):
    policy_id: str
    policy_version: str
    require_runtime_for_automatic_execution: bool = True

    def __post_init__(self) -> None:
        _id("policy_id", self.policy_id)
        _version("policy_version", self.policy_version)
        if not isinstance(self.require_runtime_for_automatic_execution, bool):
            raise ValueError("require_runtime_for_automatic_execution must be boolean")


@dataclass(frozen=True, slots=True)
class PlanningRequest(SerializablePlanningModel):
    request_id: str
    recommendations: RecommendationAssessment
    directives: tuple[PlanningDirective, ...]
    policy: PlanningPolicy
    created_at: datetime
    schema_version: int = PLANNING_SCHEMA_VERSION
    algorithm_version: str = PLANNING_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        if not isinstance(self.recommendations, RecommendationAssessment):
            raise ValueError("recommendations must use RecommendationAssessment")
        if not isinstance(self.directives, tuple) or any(
            not isinstance(value, PlanningDirective) for value in self.directives
        ):
            raise ValueError("directives must contain PlanningDirective values")
        ids = tuple(v.recommendation_id for v in self.directives)
        if ids != tuple(sorted(set(ids))):
            raise ValueError(
                "directives must use deterministic unique recommendation ordering"
            )
        if not isinstance(self.policy, PlanningPolicy):
            raise ValueError("policy must be canonical")
        _time("created_at", self.created_at)
        if self.schema_version != PLANNING_SCHEMA_VERSION:
            raise ValueError("unsupported planning schema version")
        _version("algorithm_version", self.algorithm_version)


@dataclass(frozen=True, slots=True)
class PlanAction(SerializablePlanningModel):
    action_id: str
    recommendation_id: str
    action_type: PlanActionType
    disposition: PlanExecutionDisposition
    target_id: str | None
    quantity: float | None
    quantity_unit: PlanQuantityUnit | None
    runtime_seconds: int | None
    cycle_count: int
    soak_seconds: int
    preconditions: tuple[str, ...]
    safety_constraints: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    supporting_assessment_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _id("action_id", self.action_id)
        _id("recommendation_id", self.recommendation_id)
        if not isinstance(self.action_type, PlanActionType) or not isinstance(
            self.disposition, PlanExecutionDisposition
        ):
            raise ValueError("action type and disposition must be canonical")
        if self.target_id is not None:
            _id("target_id", self.target_id)
        if self.quantity is not None and self.quantity_unit is None:
            raise ValueError("quantity requires quantity_unit")
        for name, values in (
            ("preconditions", self.preconditions),
            ("safety_constraints", self.safety_constraints),
            ("blocking_reasons", self.blocking_reasons),
            ("supporting_assessment_ids", self.supporting_assessment_ids),
        ):
            _sorted_text(name, values)


@dataclass(frozen=True, slots=True)
class IrrigationPlan(SerializablePlanningModel):
    plan_id: str
    request_id: str
    recommendation_assessment_id: str
    status: PlanStatus
    actions: tuple[PlanAction, ...]
    unresolved_issues: tuple[str, ...]
    policy_id: str
    policy_version: str
    algorithm_version: str
    created_at: datetime
    schema_version: int = PLANNING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("plan_id", self.plan_id),
            ("request_id", self.request_id),
            ("recommendation_assessment_id", self.recommendation_assessment_id),
            ("policy_id", self.policy_id),
        ):
            _id(name, value)
        if not isinstance(self.status, PlanStatus):
            raise ValueError("status must be canonical")
        if not isinstance(self.actions, tuple) or any(
            not isinstance(value, PlanAction) for value in self.actions
        ):
            raise ValueError("actions must contain PlanAction values")
        ids = tuple(v.action_id for v in self.actions)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("actions must use deterministic unique ordering")
        _sorted_text("unresolved_issues", self.unresolved_issues)
        _version("policy_version", self.policy_version)
        _version("algorithm_version", self.algorithm_version)
        _time("created_at", self.created_at)
        if self.schema_version != PLANNING_SCHEMA_VERSION:
            raise ValueError("unsupported planning schema version")
