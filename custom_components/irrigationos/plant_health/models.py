"""Immutable contracts for evidence-gated plant health assessment."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..plant_stress import PlantStressRiskAssessment

PLANT_HEALTH_SCHEMA_VERSION = 1
PLANT_HEALTH_ALGORITHM_VERSION = "1.0.0"

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class PlantHealthClassification(StrEnum):
    """Canonical health-state vocabulary."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PlantHealthStatus(StrEnum):
    """Typed outcomes for plant health assessment."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    INSUFFICIENT_DIRECT_EVIDENCE = "insufficient_direct_evidence"
    CONFLICTING_DIRECT_EVIDENCE = "conflicting_direct_evidence"
    UNAVAILABLE = "unavailable"


class PlantHealthEvidenceKind(StrEnum):
    """Supported direct evidence channels."""

    MANUAL_OBSERVATION = "manual_observation"
    SENSOR_OBSERVATION = "sensor_observation"
    VISUAL_OBSERVATION = "visual_observation"


class PlantHealthIndicator(StrEnum):
    """Canonical directly observed health indicators."""

    VIGOR = "vigor"
    WILTING = "wilting"
    DISCOLORATION = "discoloration"
    DEFOLIATION = "defoliation"
    TISSUE_DAMAGE = "tissue_damage"
    DISEASE_SIGNS = "disease_signs"
    PEST_SIGNS = "pest_signs"
    NUTRIENT_DEFICIENCY_SIGNS = "nutrient_deficiency_signs"
    RECOVERY = "recovery"


class PlantHealthSeverity(StrEnum):
    """Observed severity independent of diagnosis."""

    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


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
    raise TypeError(f"unsupported plant health serialization type: {type(value).__name__}")


class SerializablePlantHealthModel:
    """Mixin for deterministic plain-data serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover
            raise TypeError("plant health model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class PlantHealthEvidence(SerializablePlantHealthModel):
    """One direct, immutable observation about plant condition."""

    evidence_id: str
    kind: PlantHealthEvidenceKind
    indicator: PlantHealthIndicator
    severity: PlantHealthSeverity
    confidence: float
    observed_at: datetime
    source_id: str
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("evidence_id", self.evidence_id)
        _validate_identifier("source_id", self.source_id)
        if not isinstance(self.kind, PlantHealthEvidenceKind):
            raise ValueError("kind must be canonical")
        if not isinstance(self.indicator, PlantHealthIndicator):
            raise ValueError("indicator must be canonical")
        if not isinstance(self.severity, PlantHealthSeverity):
            raise ValueError("severity must be canonical")
        _validate_fraction("confidence", self.confidence)
        _validate_timestamp("observed_at", self.observed_at)
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes must not be blank")


@dataclass(frozen=True, slots=True)
class PlantHealthPolicy(SerializablePlantHealthModel):
    """Explicit evidence-admission policy."""

    policy_id: str
    policy_version: str
    minimum_direct_evidence_count: int = 1
    minimum_confidence: float = 0.5

    def __post_init__(self) -> None:
        _validate_identifier("policy_id", self.policy_id)
        _validate_version("policy_version", self.policy_version)
        if (
            isinstance(self.minimum_direct_evidence_count, bool)
            or not isinstance(self.minimum_direct_evidence_count, int)
            or self.minimum_direct_evidence_count < 1
        ):
            raise ValueError("minimum_direct_evidence_count must be a positive integer")
        _validate_fraction("minimum_confidence", self.minimum_confidence)


@dataclass(frozen=True, slots=True)
class PlantHealthRequest(SerializablePlantHealthModel):
    """Immutable request linking direct evidence and stress context."""

    request_id: str
    plant_instance_id: str
    selected_profile_id: str | None
    direct_evidence: tuple[PlantHealthEvidence, ...]
    aggregate_stress: PlantStressRiskAssessment
    policy: PlantHealthPolicy
    created_at: datetime
    schema_version: int = PLANT_HEALTH_SCHEMA_VERSION
    algorithm_version: str = PLANT_HEALTH_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _validate_identifier("request_id", self.request_id)
        _validate_identifier("plant_instance_id", self.plant_instance_id)
        if self.selected_profile_id is not None:
            _validate_identifier("selected_profile_id", self.selected_profile_id)
        if not isinstance(self.direct_evidence, tuple):
            raise ValueError("direct_evidence must be an immutable tuple")
        if any(not isinstance(item, PlantHealthEvidence) for item in self.direct_evidence):
            raise ValueError("direct_evidence must contain PlantHealthEvidence")
        evidence_ids = tuple(item.evidence_id for item in self.direct_evidence)
        if evidence_ids != tuple(sorted(evidence_ids)):
            raise ValueError("direct_evidence must use deterministic ordering")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("direct_evidence must not contain duplicates")
        if not isinstance(self.aggregate_stress, PlantStressRiskAssessment):
            raise ValueError("aggregate_stress must use PlantStressRiskAssessment")
        if not isinstance(self.policy, PlantHealthPolicy):
            raise ValueError("policy must be canonical")
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != PLANT_HEALTH_SCHEMA_VERSION:
            raise ValueError("unsupported plant health schema version")
        _validate_version("algorithm_version", self.algorithm_version)


@dataclass(frozen=True, slots=True)
class PlantHealthConfidence(SerializablePlantHealthModel):
    """Separate confidence from evidence completeness."""

    confidence: float
    completeness: float
    admitted_evidence_count: int
    required_evidence_count: int

    def __post_init__(self) -> None:
        _validate_fraction("confidence", self.confidence)
        _validate_fraction("completeness", self.completeness)
        for name, value in (
            ("admitted_evidence_count", self.admitted_evidence_count),
            ("required_evidence_count", self.required_evidence_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.admitted_evidence_count > self.required_evidence_count:
            raise ValueError("admitted evidence cannot exceed required evidence")
        expected = (
            0.0
            if self.required_evidence_count == 0
            else self.admitted_evidence_count / self.required_evidence_count
        )
        if abs(self.completeness - expected) > 1e-9:
            raise ValueError("completeness must match evidence counts")


@dataclass(frozen=True, slots=True)
class PlantHealthExplanation(SerializablePlantHealthModel):
    """Deterministic explanation of a health assessment."""

    reason_codes: tuple[str, ...]
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        if self.reason_codes != tuple(sorted(self.reason_codes)):
            raise ValueError("reason_codes must use deterministic ordering")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must not contain duplicates")
        if any(not _REASON_CODE_PATTERN.fullmatch(code) for code in self.reason_codes):
            raise ValueError("reason_codes must use lower_snake_case")
        if not self.summary.strip():
            raise ValueError("summary must not be blank")
        if self.detail is not None and not self.detail.strip():
            raise ValueError("detail must not be blank")


@dataclass(frozen=True, slots=True)
class PlantHealthAssessment(SerializablePlantHealthModel):
    """Canonical evidence-gated plant health conclusion."""

    assessment_id: str
    request_id: str
    plant_instance_id: str
    selected_profile_id: str | None
    status: PlantHealthStatus
    classification: PlantHealthClassification
    confidence: PlantHealthConfidence
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    aggregate_stress_assessment_id: str
    policy_id: str
    policy_version: str
    algorithm_version: str
    explanation: PlantHealthExplanation
    unresolved_issues: tuple[str, ...]
    created_at: datetime
    schema_version: int = PLANT_HEALTH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("assessment_id", self.assessment_id),
            ("request_id", self.request_id),
            ("plant_instance_id", self.plant_instance_id),
            ("aggregate_stress_assessment_id", self.aggregate_stress_assessment_id),
            ("policy_id", self.policy_id),
        ):
            _validate_identifier(name, value)
        if self.selected_profile_id is not None:
            _validate_identifier("selected_profile_id", self.selected_profile_id)
        if not isinstance(self.status, PlantHealthStatus):
            raise ValueError("status must be canonical")
        if not isinstance(self.classification, PlantHealthClassification):
            raise ValueError("classification must be canonical")
        if not isinstance(self.confidence, PlantHealthConfidence):
            raise ValueError("confidence must be canonical")
        _validate_sorted_unique_text("evidence_ids", self.evidence_ids)
        _validate_sorted_unique_text("source_ids", self.source_ids)
        _validate_version("policy_version", self.policy_version)
        _validate_version("algorithm_version", self.algorithm_version)
        if not isinstance(self.explanation, PlantHealthExplanation):
            raise ValueError("explanation must be canonical")
        _validate_sorted_unique_text("unresolved_issues", self.unresolved_issues)
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != PLANT_HEALTH_SCHEMA_VERSION:
            raise ValueError("unsupported plant health schema version")
        successful = self.status in {PlantHealthStatus.AVAILABLE, PlantHealthStatus.PARTIAL}
        if successful and self.classification is PlantHealthClassification.UNKNOWN:
            raise ValueError("successful assessments require a concrete classification")
        if not successful and self.classification is not PlantHealthClassification.UNKNOWN:
            raise ValueError("non-success assessments must use unknown classification")
