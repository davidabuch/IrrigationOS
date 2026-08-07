"""Immutable foundation models for plant water-requirement assessment."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..landscape import EstablishmentStage
from ..plant_knowledge import (
    EvidenceGrade,
    InheritedClaimTrace,
    KnowledgeRange,
    KnowledgeUnit,
    PlantKnowledgeResolution,
    RegionalApplicability,
    ReviewState,
    Season,
)

PLANT_WATER_REQUIREMENT_SCHEMA_VERSION = 2
PLANT_WATER_REQUIREMENT_ALGORITHM_VERSION = "1.0.0"

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_FIELD_PATH_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class ExposureClassification(StrEnum):
    """Broad exposure context without implied calculation behavior."""

    SHELTERED = "sheltered"
    TYPICAL = "typical"
    EXPOSED = "exposed"
    UNKNOWN = "unknown"


class MicroclimateClassification(StrEnum):
    """Broad microclimate context without hidden adjustment factors."""

    COOL = "cool"
    TYPICAL = "typical"
    WARM = "warm"
    UNKNOWN = "unknown"


class RegionalApplicabilityResult(StrEnum):
    """Outcome of comparing claim scope with evaluation context."""

    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    UNAVAILABLE_CONTEXT = "unavailable_context"
    MISMATCH = "mismatch"
    UNRESTRICTED = "unrestricted"
    NOT_EVALUATED = "not_evaluated"


class PlantWaterRequirementStatus(StrEnum):
    """Typed outcome states for a future deterministic assessment."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    REGIONAL_MISMATCH = "regional_mismatch"
    INSUFFICIENT_QUALITY = "insufficient_quality"


class MissingDataBehavior(StrEnum):
    """Explicit policy behavior when required evidence is absent."""

    RETURN_UNAVAILABLE = "return_unavailable"
    RETURN_PARTIAL = "return_partial"


class ConflictBehavior(StrEnum):
    """Explicit policy behavior for unresolved competing evidence."""

    RETURN_CONFLICT = "return_conflict"
    REQUIRE_RESOLUTION = "require_resolution"


class RangeHandling(StrEnum):
    """Explicit policy treatment of evidence-backed ranges."""

    PRESERVE = "preserve"
    USE_TYPICAL_IF_PRESENT = "use_typical_if_present"


class PlantWaterRequirementReasonCode(StrEnum):
    """Stable machine-readable explanation reasons."""

    REQUIREMENT_AVAILABLE = "requirement_available"
    REQUIREMENT_PARTIAL = "requirement_partial"
    MISSING_WATER_EVIDENCE = "missing_water_evidence"
    CONFLICTING_WATER_EVIDENCE = "conflicting_water_evidence"
    REGIONAL_SCOPE_MISMATCH = "regional_scope_mismatch"
    EVIDENCE_BELOW_POLICY = "evidence_below_policy"
    PROFILE_NOT_RESOLVED = "profile_not_resolved"
    RANGE_PRESERVED = "range_preserved"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


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


def _validate_sorted_unique_identifiers(name: str, values: tuple[str, ...]) -> None:
    _validate_sorted_unique_text(name, values)
    for value in values:
        _validate_identifier(name, value)


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
        raise TypeError("raw bytes are not permitted in plant water-requirement records")
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"unsupported serialization type: {type(value).__name__}")


class SerializablePlantWaterRequirementModel:
    """Mixin for deterministic plain-dictionary serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic runtime-neutral data."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover
            raise TypeError("plant water-requirement model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class PlantWaterRequirementContext(SerializablePlantWaterRequirementModel):
    """Explicit regional, seasonal, and plant-stage evaluation context."""

    regional_applicability: RegionalApplicability
    season: Season
    establishment_stage: EstablishmentStage
    exposure: ExposureClassification = ExposureClassification.UNKNOWN
    microclimate: MicroclimateClassification = MicroclimateClassification.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.regional_applicability, RegionalApplicability):
            raise ValueError("regional_applicability must use the Plant Knowledge contract")
        if not isinstance(self.season, Season):
            raise ValueError("season must use a canonical Season value")
        if not isinstance(self.establishment_stage, EstablishmentStage):
            raise ValueError("establishment_stage must be canonical")
        if not isinstance(self.exposure, ExposureClassification):
            raise ValueError("exposure must be canonical")
        if not isinstance(self.microclimate, MicroclimateClassification):
            raise ValueError("microclimate must be canonical")


@dataclass(frozen=True, slots=True)
class PlantWaterRequirementPolicy(SerializablePlantWaterRequirementModel):
    """Versioned explicit evidence-admission and interpretation policy."""

    policy_id: str
    policy_version: str
    accepted_claim_paths: tuple[str, ...]
    minimum_review_state: ReviewState
    minimum_evidence_grade: EvidenceGrade
    minimum_confidence: float
    require_regional_match: bool
    range_handling: RangeHandling
    missing_data_behavior: MissingDataBehavior
    conflict_behavior: ConflictBehavior

    def __post_init__(self) -> None:
        _validate_identifier("policy_id", self.policy_id)
        _validate_version("policy_version", self.policy_version)
        _validate_sorted_unique_text("accepted_claim_paths", self.accepted_claim_paths)
        if not self.accepted_claim_paths:
            raise ValueError("policy requires at least one accepted claim path")
        if any(not _FIELD_PATH_PATTERN.fullmatch(path) for path in self.accepted_claim_paths):
            raise ValueError("accepted claim paths must be canonical field paths")
        if not isinstance(self.minimum_review_state, ReviewState):
            raise ValueError("minimum_review_state must be canonical")
        if not isinstance(self.minimum_evidence_grade, EvidenceGrade):
            raise ValueError("minimum_evidence_grade must be canonical")
        _validate_fraction("minimum_confidence", self.minimum_confidence)
        if not isinstance(self.require_regional_match, bool):
            raise ValueError("require_regional_match must be a boolean")
        if not isinstance(self.range_handling, RangeHandling):
            raise ValueError("range_handling must be canonical")
        if not isinstance(self.missing_data_behavior, MissingDataBehavior):
            raise ValueError("missing_data_behavior must be canonical")
        if not isinstance(self.conflict_behavior, ConflictBehavior):
            raise ValueError("conflict_behavior must be canonical")


@dataclass(frozen=True, slots=True)
class PlantWaterRequirementRequest(SerializablePlantWaterRequirementModel):
    """Immutable request linking resolved knowledge to explicit context and policy."""

    request_id: str
    knowledge_resolution: PlantKnowledgeResolution
    context: PlantWaterRequirementContext
    policy: PlantWaterRequirementPolicy
    created_at: datetime
    schema_version: int = PLANT_WATER_REQUIREMENT_SCHEMA_VERSION
    algorithm_version: str = PLANT_WATER_REQUIREMENT_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _validate_identifier("request_id", self.request_id)
        if not isinstance(self.knowledge_resolution, PlantKnowledgeResolution):
            raise ValueError("knowledge_resolution must use PlantKnowledgeResolution")
        if not isinstance(self.context, PlantWaterRequirementContext):
            raise ValueError("context must use PlantWaterRequirementContext")
        if not isinstance(self.policy, PlantWaterRequirementPolicy):
            raise ValueError("policy must use PlantWaterRequirementPolicy")
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != PLANT_WATER_REQUIREMENT_SCHEMA_VERSION:
            raise ValueError("unsupported plant water-requirement schema version")
        _validate_version("algorithm_version", self.algorithm_version)

    @property
    def selected_profile_id(self) -> str | None:
        """Expose the selected profile without copying canonical Plant Knowledge."""
        return self.knowledge_resolution.selected_profile_id


@dataclass(frozen=True, slots=True)
class PlantWaterRequirementConfidence(SerializablePlantWaterRequirementModel):
    """Separate evidence confidence from input completeness."""

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
class PlantWaterRequirementExplanation(SerializablePlantWaterRequirementModel):
    """Machine- and human-readable assessment explanation."""

    reason_codes: tuple[PlantWaterRequirementReasonCode, ...]
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("explanation requires at least one reason code")
        if any(not isinstance(code, PlantWaterRequirementReasonCode) for code in self.reason_codes):
            raise ValueError("reason_codes must use canonical values")
        serialized = tuple(code.value for code in self.reason_codes)
        if len(serialized) != len(set(serialized)) or serialized != tuple(sorted(serialized)):
            raise ValueError("reason_codes must be unique and deterministically ordered")
        _validate_text("summary", self.summary)
        if self.detail is not None:
            _validate_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class PlantWaterRequirementAssessment(SerializablePlantWaterRequirementModel):
    """Canonical result envelope for a future deterministic engine."""

    assessment_id: str
    request_id: str
    selected_profile_id: str | None
    status: PlantWaterRequirementStatus
    value: float | KnowledgeRange | None
    unit: KnowledgeUnit | None
    regional_result: RegionalApplicabilityResult
    applicable_region: RegionalApplicability
    applicable_season: Season
    confidence: PlantWaterRequirementConfidence
    claim_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    claim_resolution_ids: tuple[str, ...]
    claim_traces: tuple[InheritedClaimTrace, ...]
    policy_id: str
    policy_version: str
    algorithm_version: str
    explanation: PlantWaterRequirementExplanation
    unresolved_issues: tuple[str, ...]
    created_at: datetime
    schema_version: int = PLANT_WATER_REQUIREMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _validate_identifier("assessment_id", self.assessment_id)
        _validate_identifier("request_id", self.request_id)
        if self.selected_profile_id is not None:
            _validate_identifier("selected_profile_id", self.selected_profile_id)
        if not isinstance(self.status, PlantWaterRequirementStatus):
            raise ValueError("status must be canonical")
        if self.value is not None and not isinstance(self.value, KnowledgeRange):
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise ValueError("value must be numeric, a KnowledgeRange, or None")
            if not isfinite(self.value) or self.value < 0:
                raise ValueError("numeric value must be finite and non-negative")
        if isinstance(self.value, KnowledgeRange):
            if self.unit is not self.value.unit:
                raise ValueError("range value and assessment unit must agree")
        elif self.value is not None and self.unit is None:
            raise ValueError("numeric values require a canonical unit")
        elif self.value is None and self.unit is not None:
            raise ValueError("unit is only valid when a value is present")
        if not isinstance(self.regional_result, RegionalApplicabilityResult):
            raise ValueError("regional_result must be canonical")
        if not isinstance(self.applicable_region, RegionalApplicability):
            raise ValueError("applicable_region must be canonical")
        if not isinstance(self.applicable_season, Season):
            raise ValueError("applicable_season must be canonical")
        if not isinstance(self.confidence, PlantWaterRequirementConfidence):
            raise ValueError("confidence must use PlantWaterRequirementConfidence")
        _validate_sorted_unique_text("claim_ids", self.claim_ids)
        _validate_sorted_unique_text("source_ids", self.source_ids)
        _validate_sorted_unique_identifiers(
            "claim_resolution_ids", self.claim_resolution_ids
        )
        if any(not isinstance(trace, InheritedClaimTrace) for trace in self.claim_traces):
            raise ValueError("claim_traces must contain InheritedClaimTrace values")
        _validate_identifier("policy_id", self.policy_id)
        _validate_version("policy_version", self.policy_version)
        _validate_version("algorithm_version", self.algorithm_version)
        if not isinstance(self.explanation, PlantWaterRequirementExplanation):
            raise ValueError("explanation must be canonical")
        _validate_sorted_unique_text("unresolved_issues", self.unresolved_issues)
        _validate_timestamp("created_at", self.created_at)
        if self.schema_version != PLANT_WATER_REQUIREMENT_SCHEMA_VERSION:
            raise ValueError("unsupported plant water-requirement schema version")
        successful = self.status in {
            PlantWaterRequirementStatus.AVAILABLE,
            PlantWaterRequirementStatus.PARTIAL,
        }
        if successful and self.value is None:
            raise ValueError("available or partial assessments require a value")
        if not successful and self.value is not None:
            raise ValueError("non-success assessments must not contain a value")
        if successful and self.selected_profile_id is None:
            raise ValueError("successful assessments require a selected profile")
