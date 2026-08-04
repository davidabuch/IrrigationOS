"""Immutable foundation models for plant stress-risk assessment."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..environment import EnvironmentalIntelligenceReport
from ..plant_knowledge import PlantKnowledgeResolution, RegionalApplicability, Season
from ..plant_water_requirement import PlantWaterRequirementAssessment

PLANT_STRESS_RISK_SCHEMA_VERSION = 1
PLANT_STRESS_RISK_ALGORITHM_VERSION = "1.0.0"

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class PlantStressDimension(StrEnum):
    """Independent plant stress-risk dimensions supported by the foundation."""

    WATER_DEFICIT = "water_deficit"
    HEAT = "heat"
    FREEZE = "freeze"


class PlantStressRiskClassification(StrEnum):
    """Canonical non-numeric plant stress-risk vocabulary."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    UNKNOWN = "unknown"


class PlantStressRiskStatus(StrEnum):
    """Typed outcomes for dimension and aggregate stress-risk assessments."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_PLANT_KNOWLEDGE = "insufficient_plant_knowledge"
    INSUFFICIENT_ENVIRONMENTAL_EVIDENCE = "insufficient_environmental_evidence"
    REGIONAL_MISMATCH = "regional_mismatch"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class PartialEvidenceBehavior(StrEnum):
    """Policy behavior when some required evidence is unavailable."""

    RETURN_PARTIAL = "return_partial"
    REQUIRE_COMPLETE = "require_complete"


class MissingEvidenceBehavior(StrEnum):
    """Policy behavior when a dimension lacks required evidence."""

    RETURN_UNAVAILABLE = "return_unavailable"
    RETURN_SPECIFIC_STATUS = "return_specific_status"


class OverallRiskAggregation(StrEnum):
    """Explicit aggregate reporting behavior for independent dimensions."""

    NONE = "none"
    HIGHEST_AVAILABLE = "highest_available"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_optional_identifier(name: str, value: str | None) -> None:
    if value is not None:
        _validate_identifier(name, value)


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _validate_fraction(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def _validate_sorted_unique_identifiers(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    for value in values:
        _validate_identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    if values != tuple(sorted(values)):
        raise ValueError(f"{name} must use deterministic ordering")


def _validate_sorted_unique_text(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    normalized: list[str] = []
    for value in values:
        _validate_text(name, value)
        normalized.append(value.strip().casefold())
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} must not contain duplicates")
    if normalized != sorted(normalized):
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
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError("raw bytes are not permitted in plant stress-risk records")
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"unsupported plant stress-risk serialization type: {type(value).__name__}")


class SerializablePlantStressRiskModel:
    """Mixin for deterministic runtime-neutral serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic plain data suitable for audit and persistence."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover
            raise TypeError("plant stress-risk model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class PlantStressRiskContext(SerializablePlantStressRiskModel):
    """Explicit location, analysis-window, region, and season context."""

    location_id: str
    analysis_window_id: str
    regional_applicability: RegionalApplicability
    season: Season

    def __post_init__(self) -> None:
        _validate_identifier("location_id", self.location_id)
        _validate_identifier("analysis_window_id", self.analysis_window_id)
        if not isinstance(self.regional_applicability, RegionalApplicability):
            raise ValueError("regional_applicability must use the Plant Knowledge contract")
        if not isinstance(self.season, Season):
            raise ValueError("season must use a canonical Season value")


@dataclass(frozen=True, slots=True)
class PlantStressRiskPolicy(SerializablePlantStressRiskModel):
    """Versioned policy for future independent stress-risk engines."""

    policy_id: str
    policy_version: str
    enabled_dimensions: tuple[PlantStressDimension, ...]
    minimum_confidence: float
    partial_evidence_behavior: PartialEvidenceBehavior
    missing_evidence_behavior: MissingEvidenceBehavior
    overall_risk_aggregation: OverallRiskAggregation

    def __post_init__(self) -> None:
        _validate_identifier("policy_id", self.policy_id)
        _validate_version("policy_version", self.policy_version)
        if not isinstance(self.enabled_dimensions, tuple):
            raise ValueError("enabled_dimensions must be an immutable tuple")
        if not self.enabled_dimensions:
            raise ValueError("policy requires at least one enabled dimension")
        if any(not isinstance(item, PlantStressDimension) for item in self.enabled_dimensions):
            raise ValueError("enabled_dimensions must contain canonical dimensions")
        values = tuple(item.value for item in self.enabled_dimensions)
        if len(values) != len(set(values)):
            raise ValueError("enabled_dimensions must not contain duplicates")
        if values != tuple(sorted(values)):
            raise ValueError("enabled_dimensions must use deterministic ordering")
        _validate_fraction("minimum_confidence", self.minimum_confidence)
        if not isinstance(self.partial_evidence_behavior, PartialEvidenceBehavior):
            raise ValueError("partial_evidence_behavior must be canonical")
        if not isinstance(self.missing_evidence_behavior, MissingEvidenceBehavior):
            raise ValueError("missing_evidence_behavior must be canonical")
        if not isinstance(self.overall_risk_aggregation, OverallRiskAggregation):
            raise ValueError("overall_risk_aggregation must be canonical")


@dataclass(frozen=True, slots=True)
class PlantStressRiskRequest(SerializablePlantStressRiskModel):
    """Immutable composition request for future stress-risk engines."""

    request_id: str
    knowledge_resolution: PlantKnowledgeResolution
    water_requirement_assessment: PlantWaterRequirementAssessment
    environmental_report: EnvironmentalIntelligenceReport
    context: PlantStressRiskContext
    policy: PlantStressRiskPolicy
    created_at: datetime
    schema_version: int = PLANT_STRESS_RISK_SCHEMA_VERSION
    algorithm_version: str = PLANT_STRESS_RISK_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _validate_identifier("request_id", self.request_id)
        if not isinstance(self.knowledge_resolution, PlantKnowledgeResolution):
            raise ValueError("knowledge_resolution must use PlantKnowledgeResolution")
        if not isinstance(self.water_requirement_assessment, PlantWaterRequirementAssessment):
            raise ValueError(
                "water_requirement_assessment must use PlantWaterRequirementAssessment"
            )
        if not isinstance(self.environmental_report, EnvironmentalIntelligenceReport):
            raise ValueError("environmental_report must use EnvironmentalIntelligenceReport")
        if not isinstance(self.context, PlantStressRiskContext):
            raise ValueError("context must use PlantStressRiskContext")
        if not isinstance(self.policy, PlantStressRiskPolicy):
            raise ValueError("policy must use PlantStressRiskPolicy")
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != PLANT_STRESS_RISK_SCHEMA_VERSION:
            raise ValueError("unsupported plant stress-risk schema version")
        _validate_version("algorithm_version", self.algorithm_version)
        if self.environmental_report.analysis_window.location_id != self.context.location_id:
            raise ValueError("environmental report and request context location must agree")
        if self.environmental_report.analysis_window.window_id != self.context.analysis_window_id:
            raise ValueError("environmental report and request analysis window must agree")

    @property
    def selected_profile_id(self) -> str | None:
        """Expose the selected profile without copying canonical knowledge."""
        return self.knowledge_resolution.selected_profile_id


@dataclass(frozen=True, slots=True)
class PlantStressRiskConfidence(SerializablePlantStressRiskModel):
    """Separate assessment confidence from evidence completeness."""

    confidence: float
    completeness: float
    known_required_input_count: int
    required_input_count: int

    def __post_init__(self) -> None:
        _validate_fraction("confidence", self.confidence)
        _validate_fraction("completeness", self.completeness)
        for name, value in (
            ("known_required_input_count", self.known_required_input_count),
            ("required_input_count", self.required_input_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.known_required_input_count > self.required_input_count:
            raise ValueError("known required inputs cannot exceed required inputs")
        expected = (
            0.0
            if self.required_input_count == 0
            else self.known_required_input_count / self.required_input_count
        )
        if abs(self.completeness - expected) > 1e-9:
            raise ValueError("completeness must match required input counts")


@dataclass(frozen=True, slots=True)
class PlantStressRiskExplanation(SerializablePlantStressRiskModel):
    """Deterministic machine- and human-readable assessment explanation."""

    reason_codes: tuple[str, ...]
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("explanation requires immutable reason codes")
        for code in self.reason_codes:
            if not isinstance(code, str) or not _REASON_CODE_PATTERN.fullmatch(code):
                raise ValueError("reason codes must use stable lower_snake_case")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason codes must not contain duplicates")
        if self.reason_codes != tuple(sorted(self.reason_codes)):
            raise ValueError("reason codes must use deterministic ordering")
        _validate_text("summary", self.summary)
        if self.detail is not None:
            _validate_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class PlantStressDimensionAssessment(SerializablePlantStressRiskModel):
    """One independent, immutable plant stress-risk dimension assessment."""

    assessment_id: str
    dimension: PlantStressDimension
    status: PlantStressRiskStatus
    risk: PlantStressRiskClassification
    confidence: PlantStressRiskConfidence
    selected_profile_id: str | None
    plant_knowledge_claim_ids: tuple[str, ...]
    plant_knowledge_source_ids: tuple[str, ...]
    water_requirement_assessment_id: str | None
    environmental_report_id: str | None
    environmental_signal_ids: tuple[str, ...]
    regional_applicability: RegionalApplicability
    policy_id: str
    policy_version: str
    algorithm_version: str
    explanation: PlantStressRiskExplanation
    unresolved_issues: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_identifier("assessment_id", self.assessment_id)
        if not isinstance(self.dimension, PlantStressDimension):
            raise ValueError("dimension must be canonical")
        if not isinstance(self.status, PlantStressRiskStatus):
            raise ValueError("status must be canonical")
        if not isinstance(self.risk, PlantStressRiskClassification):
            raise ValueError("risk must be canonical")
        if not isinstance(self.confidence, PlantStressRiskConfidence):
            raise ValueError("confidence must be canonical")
        _validate_optional_identifier("selected_profile_id", self.selected_profile_id)
        _validate_sorted_unique_identifiers(
            "plant_knowledge_claim_ids", self.plant_knowledge_claim_ids
        )
        _validate_sorted_unique_identifiers(
            "plant_knowledge_source_ids", self.plant_knowledge_source_ids
        )
        _validate_optional_identifier(
            "water_requirement_assessment_id", self.water_requirement_assessment_id
        )
        _validate_optional_identifier("environmental_report_id", self.environmental_report_id)
        _validate_sorted_unique_identifiers(
            "environmental_signal_ids", self.environmental_signal_ids
        )
        if not isinstance(self.regional_applicability, RegionalApplicability):
            raise ValueError("regional_applicability must be canonical")
        _validate_identifier("policy_id", self.policy_id)
        _validate_version("policy_version", self.policy_version)
        _validate_version("algorithm_version", self.algorithm_version)
        if not isinstance(self.explanation, PlantStressRiskExplanation):
            raise ValueError("explanation must be canonical")
        _validate_sorted_unique_text("unresolved_issues", self.unresolved_issues)
        successful = self.status in {
            PlantStressRiskStatus.AVAILABLE,
            PlantStressRiskStatus.PARTIAL,
        }
        if successful and self.risk is PlantStressRiskClassification.UNKNOWN:
            raise ValueError("available or partial dimensions require a concrete risk")
        if not successful and self.risk is not PlantStressRiskClassification.UNKNOWN:
            raise ValueError("non-success dimensions must use unknown risk")
        if successful and self.selected_profile_id is None:
            raise ValueError("successful dimensions require a selected profile")


@dataclass(frozen=True, slots=True)
class PlantStressRiskAssessment(SerializablePlantStressRiskModel):
    """Canonical aggregate envelope for independent stress-risk dimensions."""

    assessment_id: str
    request_id: str
    selected_profile_id: str | None
    location_id: str
    analysis_window_id: str
    dimensions: tuple[PlantStressDimensionAssessment, ...]
    overall_status: PlantStressRiskStatus
    overall_risk: PlantStressRiskClassification | None
    confidence: PlantStressRiskConfidence
    knowledge_resolution_id: str
    water_requirement_assessment_id: str
    environmental_report_id: str
    policy_id: str
    policy_version: str
    algorithm_version: str
    explanation: PlantStressRiskExplanation
    unresolved_issues: tuple[str, ...]
    created_at: datetime
    schema_version: int = PLANT_STRESS_RISK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("assessment_id", self.assessment_id),
            ("request_id", self.request_id),
            ("location_id", self.location_id),
            ("analysis_window_id", self.analysis_window_id),
            ("knowledge_resolution_id", self.knowledge_resolution_id),
            ("water_requirement_assessment_id", self.water_requirement_assessment_id),
            ("environmental_report_id", self.environmental_report_id),
            ("policy_id", self.policy_id),
        ):
            _validate_identifier(name, value)
        _validate_optional_identifier("selected_profile_id", self.selected_profile_id)
        if not isinstance(self.dimensions, tuple):
            raise ValueError("dimensions must be an immutable tuple")
        if any(not isinstance(item, PlantStressDimensionAssessment) for item in self.dimensions):
            raise ValueError("dimensions must contain canonical assessments")
        values = tuple(item.dimension.value for item in self.dimensions)
        if len(values) != len(set(values)):
            raise ValueError("dimensions must not contain duplicates")
        if values != tuple(sorted(values)):
            raise ValueError("dimensions must use deterministic ordering")
        if not isinstance(self.overall_status, PlantStressRiskStatus):
            raise ValueError("overall_status must be canonical")
        if self.overall_risk is not None and not isinstance(
            self.overall_risk, PlantStressRiskClassification
        ):
            raise ValueError("overall_risk must be canonical when present")
        if not isinstance(self.confidence, PlantStressRiskConfidence):
            raise ValueError("confidence must be canonical")
        _validate_version("policy_version", self.policy_version)
        _validate_version("algorithm_version", self.algorithm_version)
        if not isinstance(self.explanation, PlantStressRiskExplanation):
            raise ValueError("explanation must be canonical")
        _validate_sorted_unique_text("unresolved_issues", self.unresolved_issues)
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != PLANT_STRESS_RISK_SCHEMA_VERSION:
            raise ValueError("unsupported plant stress-risk schema version")
        if not self.dimensions and self.overall_status in {
            PlantStressRiskStatus.AVAILABLE,
            PlantStressRiskStatus.PARTIAL,
        }:
            raise ValueError("available or partial aggregate requires dimensions")
        if self.overall_risk is PlantStressRiskClassification.UNKNOWN:
            raise ValueError("overall_risk must be concrete or omitted")
