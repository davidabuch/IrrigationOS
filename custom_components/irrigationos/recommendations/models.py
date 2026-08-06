"""Immutable contracts for deterministic irrigation recommendations."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..plant_health import PlantHealthAssessment
from ..plant_stress import PlantStressRiskAssessment
from ..plant_water_requirement import PlantWaterRequirementAssessment

RECOMMENDATION_SCHEMA_VERSION = 1
RECOMMENDATION_ALGORITHM_VERSION = "1.0.0"

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class RecommendationCategory(StrEnum):
    """Initial advisory recommendation categories."""

    ADJUST_IRRIGATION = "adjust_irrigation"
    INSPECT = "inspect"
    MONITOR = "monitor"
    NO_ACTION = "no_action"
    PROTECT_FROM_FREEZE = "protect_from_freeze"
    PROTECT_FROM_HEAT = "protect_from_heat"
    SEEK_EXPERT_REVIEW = "seek_expert_review"


class RecommendationPriority(StrEnum):
    """Canonical relative priority without scheduling semantics."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    URGENT = "urgent"


class RecommendationStatus(StrEnum):
    """Typed recommendation outcomes."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RecommendationSafetyFlag(StrEnum):
    """Machine-readable boundaries for downstream consumers."""

    ADVISORY_ONLY = "advisory_only"
    EXPERT_REVIEW_RECOMMENDED = "expert_review_recommended"
    NO_AUTOMATIC_EXECUTION = "no_automatic_execution"
    VERIFY_SITE_CONDITIONS = "verify_site_conditions"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_fraction(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def _validate_sorted_unique_text(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    normalized = tuple(value.strip().casefold() for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{name} must not contain blank values")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} must not contain duplicates")
    if normalized != tuple(sorted(normalized)):
        raise ValueError(f"{name} must use deterministic ordering")


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
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"unsupported recommendation serialization type: {type(value).__name__}")


class SerializableRecommendationModel:
    """Mixin for deterministic runtime-neutral serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover
            raise TypeError("recommendation model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class RecommendationPolicy(SerializableRecommendationModel):
    """Explicit policy for conservative recommendation generation."""

    policy_id: str
    policy_version: str
    minimum_confidence: float = 0.5

    def __post_init__(self) -> None:
        _validate_identifier("policy_id", self.policy_id)
        _validate_version("policy_version", self.policy_version)
        _validate_fraction("minimum_confidence", self.minimum_confidence)


@dataclass(frozen=True, slots=True)
class RecommendationRequest(SerializableRecommendationModel):
    """Immutable composition request from accepted upstream assessments."""

    request_id: str
    plant_health: PlantHealthAssessment
    aggregate_stress: PlantStressRiskAssessment
    water_requirement: PlantWaterRequirementAssessment
    policy: RecommendationPolicy
    created_at: datetime
    schema_version: int = RECOMMENDATION_SCHEMA_VERSION
    algorithm_version: str = RECOMMENDATION_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _validate_identifier("request_id", self.request_id)
        if not isinstance(self.plant_health, PlantHealthAssessment):
            raise ValueError("plant_health must use PlantHealthAssessment")
        if not isinstance(self.aggregate_stress, PlantStressRiskAssessment):
            raise ValueError("aggregate_stress must use PlantStressRiskAssessment")
        if not isinstance(self.water_requirement, PlantWaterRequirementAssessment):
            raise ValueError("water_requirement must use PlantWaterRequirementAssessment")
        if not isinstance(self.policy, RecommendationPolicy):
            raise ValueError("policy must be canonical")
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != RECOMMENDATION_SCHEMA_VERSION:
            raise ValueError("unsupported recommendation schema version")
        _validate_version("algorithm_version", self.algorithm_version)


@dataclass(frozen=True, slots=True)
class RecommendationExplanation(SerializableRecommendationModel):
    """Deterministic human- and machine-readable recommendation explanation."""

    reason_codes: tuple[str, ...]
    summary: str

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        for code in self.reason_codes:
            if not _REASON_CODE_PATTERN.fullmatch(code):
                raise ValueError("reason codes must use lower_snake_case")
        _validate_sorted_unique_text("reason_codes", self.reason_codes)
        if not self.summary.strip():
            raise ValueError("summary must not be blank")


@dataclass(frozen=True, slots=True)
class Recommendation(SerializableRecommendationModel):
    """One immutable advisory recommendation."""

    recommendation_id: str
    category: RecommendationCategory
    priority: RecommendationPriority
    confidence: float
    supporting_assessment_ids: tuple[str, ...]
    preconditions: tuple[str, ...]
    safety_flags: tuple[RecommendationSafetyFlag, ...]
    explanation: RecommendationExplanation

    def __post_init__(self) -> None:
        _validate_identifier("recommendation_id", self.recommendation_id)
        if not isinstance(self.category, RecommendationCategory):
            raise ValueError("category must be canonical")
        if not isinstance(self.priority, RecommendationPriority):
            raise ValueError("priority must be canonical")
        _validate_fraction("confidence", self.confidence)
        _validate_sorted_unique_text("supporting_assessment_ids", self.supporting_assessment_ids)
        _validate_sorted_unique_text("preconditions", self.preconditions)
        if not isinstance(self.safety_flags, tuple) or any(
            not isinstance(item, RecommendationSafetyFlag) for item in self.safety_flags
        ):
            raise ValueError("safety_flags must contain canonical values")
        flag_values = tuple(item.value for item in self.safety_flags)
        if flag_values != tuple(sorted(set(flag_values))):
            raise ValueError("safety_flags must use deterministic unique ordering")
        if not isinstance(self.explanation, RecommendationExplanation):
            raise ValueError("explanation must be canonical")


@dataclass(frozen=True, slots=True)
class RecommendationAssessment(SerializableRecommendationModel):
    """Canonical envelope for deterministic advisory recommendations."""

    assessment_id: str
    request_id: str
    status: RecommendationStatus
    recommendations: tuple[Recommendation, ...]
    plant_health_assessment_id: str
    aggregate_stress_assessment_id: str
    water_requirement_assessment_id: str
    policy_id: str
    policy_version: str
    algorithm_version: str
    unresolved_issues: tuple[str, ...]
    created_at: datetime
    schema_version: int = RECOMMENDATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("assessment_id", self.assessment_id),
            ("request_id", self.request_id),
            ("plant_health_assessment_id", self.plant_health_assessment_id),
            ("aggregate_stress_assessment_id", self.aggregate_stress_assessment_id),
            ("water_requirement_assessment_id", self.water_requirement_assessment_id),
            ("policy_id", self.policy_id),
        ):
            _validate_identifier(name, value)
        if not isinstance(self.status, RecommendationStatus):
            raise ValueError("status must be canonical")
        if not isinstance(self.recommendations, tuple) or any(
            not isinstance(item, Recommendation) for item in self.recommendations
        ):
            raise ValueError("recommendations must contain Recommendation values")
        recommendation_ids = tuple(item.recommendation_id for item in self.recommendations)
        if recommendation_ids != tuple(sorted(set(recommendation_ids))):
            raise ValueError("recommendations must use deterministic unique ordering")
        if self.status is RecommendationStatus.AVAILABLE and not self.recommendations:
            raise ValueError("available assessments require recommendations")
        _validate_version("policy_version", self.policy_version)
        _validate_version("algorithm_version", self.algorithm_version)
        _validate_sorted_unique_text("unresolved_issues", self.unresolved_issues)
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != RECOMMENDATION_SCHEMA_VERSION:
            raise ValueError("unsupported recommendation schema version")
