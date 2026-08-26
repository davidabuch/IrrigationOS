"""Provider-neutral domain models for Visual Landscape Intelligence."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any, Self

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class VisualAssessmentSessionState(StrEnum):
    """Lifecycle states for a visual assessment session."""

    CREATED = "created"
    COLLECTING_EVIDENCE = "collecting_evidence"
    AWAITING_USER_INPUT = "awaiting_user_input"
    READY_FOR_REVIEW = "ready_for_review"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    """Human-verification status for an inferred value."""

    UNVERIFIED = "unverified"
    USER_CONFIRMED = "user_confirmed"
    USER_CORRECTED = "user_corrected"
    REJECTED = "rejected"


class PhotoEvidenceType(StrEnum):
    """Purpose of a photo in an assessment."""

    AREA_OVERVIEW = "area_overview"
    PLANT_DETAIL = "plant_detail"
    IRRIGATION_HARDWARE = "irrigation_hardware"
    SOIL = "soil"
    DRY_CONDITION = "dry_condition"
    RUNNING_CONDITION = "running_condition"
    DIAGNOSTIC = "diagnostic"
    OTHER = "other"


class PhotoSource(StrEnum):
    """Origin of photo evidence, independent of its storage provider."""

    USER_CAPTURE = "user_capture"
    USER_SELECTED = "user_selected"
    LOCAL_CAMERA = "local_camera"
    IMPORTED = "imported"


class PrivacyClassification(StrEnum):
    """Privacy sensitivity assigned to photo evidence."""

    PRIVATE = "private"
    SENSITIVE = "sensitive"


class RetentionPolicy(StrEnum):
    """Requested lifetime for externally stored photo evidence."""

    SESSION = "session"
    CONFIGURABLE_DURATION = "configurable_duration"
    UNTIL_DELETED = "until_deleted"


class PlantCategory(StrEnum):
    """Broad, provider-neutral plant categories."""

    TREE = "tree"
    SHRUB = "shrub"
    TURF = "turf"
    GROUNDCOVER = "groundcover"
    VINE = "vine"
    FLOWER = "flower"
    VEGETABLE = "vegetable"
    SUCCULENT = "succulent"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class PlantQuantityMode(StrEnum):
    """Meaning of a detected plant quantity."""

    COUNT = "count"
    PERCENTAGE = "percentage"
    AREA = "area"


class AreaUnit(StrEnum):
    """Supported units for plant coverage area."""

    SQUARE_FEET = "square_feet"
    SQUARE_METERS = "square_meters"


class EstablishmentStage(StrEnum):
    """Observed maturity of a planting."""

    NEWLY_PLANTED = "newly_planted"
    YOUNG = "young"
    ESTABLISHED = "established"
    MATURE = "mature"
    UNKNOWN = "unknown"


class IrrigationHardwareType(StrEnum):
    """Visually detectable irrigation delivery hardware."""

    DRIP_EMITTER = "drip_emitter"
    MICROJET = "microjet"
    MISTER = "mister"
    SPRAY = "spray"
    ROTOR = "rotor"
    BUBBLER = "bubbler"
    SUBSURFACE_DRIP = "subsurface_drip"
    UNKNOWN = "unknown"


class HardwareQuantityMode(StrEnum):
    """Meaning of an irrigation-hardware quantity."""

    COUNT = "count"
    SHARE_PERCENTAGE = "share_percentage"


class SoilClass(StrEnum):
    """Operational soil classes used by visual assessment."""

    SAND = "sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    CLAY_LOAM = "clay_loam"
    CLAY = "clay"
    AMENDED = "amended"
    UNKNOWN = "unknown"


class GuidedTestType(StrEnum):
    """Supported user-guided evidence collection tests."""

    EMITTER_MEASURED_VOLUME = "emitter_measured_volume"
    EMITTER_DRIP_COUNT = "emitter_drip_count"
    MICROJET_RADIUS = "microjet_radius"
    SPRAY_ARC = "spray_arc"
    INFILTRATION = "infiltration"
    DRY_VS_RUNNING_PHOTO = "dry_vs_running_photo"
    SOIL_MOISTURE_DEPTH_CHECK = "soil_moisture_depth_check"
    HARDWARE_FUNCTION_CHECK = "hardware_function_check"


class GuidedTestState(StrEnum):
    """Lifecycle state for a guided test."""

    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class MeasurementType(StrEnum):
    """Expected or supplied result from a guided test."""

    VOLUME = "volume"
    COUNT = "count"
    DISTANCE = "distance"
    ANGLE = "angle"
    DURATION = "duration"
    DEPTH = "depth"
    BOOLEAN = "boolean"
    PHOTO_COMPARISON = "photo_comparison"
    TEXT = "text"


class RecommendedActionType(StrEnum):
    """Advisory actions that visual reasoning may propose."""

    OBSERVE_ONLY = "observe_only"
    REQUEST_MORE_PHOTOS = "request_more_photos"
    RUN_GUIDED_TEST = "run_guided_test"
    INSPECT_EMITTER = "inspect_emitter"
    CLEAN_EMITTER = "clean_emitter"
    REPLACE_EMITTER = "replace_emitter"
    REPOSITION_EMITTER = "reposition_emitter"
    ADD_EMITTER = "add_emitter"
    CHANGE_CYCLE_AND_SOAK = "change_cycle_and_soak"
    PROPOSE_TEMPORARY_ADJUSTMENT = "propose_temporary_adjustment"
    PROPOSE_BASELINE_ADJUSTMENT = "propose_baseline_adjustment"
    SEEK_PROFESSIONAL_EVALUATION = "seek_professional_evaluation"


class AdjustmentKind(StrEnum):
    """Unit family for a temporary adjustment proposal."""

    PERCENTAGE = "percentage"
    DURATION_SECONDS = "duration_seconds"


class UncertaintyKind(StrEnum):
    """Reason that an inferred finding is uncertain."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    LOW_IMAGE_QUALITY = "low_image_quality"
    OCCLUDED = "occluded"
    REQUIRES_MEASUREMENT = "requires_measurement"
    OTHER = "other"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_confidence(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be a number between 0.0 and 1.0")
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")


def _validate_positive(name: str, value: float, *, allow_zero: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 if allow_zero else value <= 0:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {qualifier}")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_unique_ids(name: str, values: tuple[str, ...]) -> None:
    for value in values:
        _validate_identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")


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
        raise TypeError("raw bytes cannot be serialized in visual assessment models")
    return value


class SerializableModel:
    """Mixin for deterministic serialization to persistence-safe dictionaries."""

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, plain-Python representation."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover - mixin contract
            raise TypeError("serializable model did not produce a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class Provenance(SerializableModel):
    """Provider-neutral origin of an observation, inference, or correction."""

    source: str
    detail: str | None = None

    def __post_init__(self) -> None:
        _validate_text("source", self.source)
        if self.detail is not None:
            _validate_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class InferenceMetadata(SerializableModel):
    """Confidence, provenance, verification, and time for an inferred finding."""

    confidence: float
    provenance: Provenance
    verification_status: VerificationStatus
    assessed_at: datetime

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)
        _validate_timestamp("assessed_at", self.assessed_at)


@dataclass(frozen=True, slots=True)
class VisualAssessmentSession(SerializableModel):
    """Immutable state of one visual-assessment workflow."""

    session_id: str
    area_id: str
    state: VisualAssessmentSessionState
    created_at: datetime
    updated_at: datetime
    evidence_ids: tuple[str, ...] = ()
    supersedes_session_id: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("session_id", self.session_id)
        _validate_identifier("area_id", self.area_id)
        _validate_timestamp("created_at", self.created_at)
        _validate_timestamp("updated_at", self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        _validate_unique_ids("evidence_ids", self.evidence_ids)
        if self.supersedes_session_id is not None:
            _validate_identifier("supersedes_session_id", self.supersedes_session_id)
            if self.supersedes_session_id == self.session_id:
                raise ValueError("a session cannot supersede itself")
        if self.state is VisualAssessmentSessionState.FAILED:
            if self.failure_reason is None:
                raise ValueError("failed sessions require a failure_reason")
            _validate_text("failure_reason", self.failure_reason)
        elif self.failure_reason is not None:
            raise ValueError("failure_reason is only valid for failed sessions")

    def transition(
        self,
        state: VisualAssessmentSessionState,
        *,
        updated_at: datetime,
        failure_reason: str | None = None,
    ) -> Self:
        """Return a validated new lifecycle state without mutating this session."""
        allowed = {
            VisualAssessmentSessionState.CREATED: {
                VisualAssessmentSessionState.COLLECTING_EVIDENCE,
                VisualAssessmentSessionState.FAILED,
            },
            VisualAssessmentSessionState.COLLECTING_EVIDENCE: {
                VisualAssessmentSessionState.AWAITING_USER_INPUT,
                VisualAssessmentSessionState.READY_FOR_REVIEW,
                VisualAssessmentSessionState.FAILED,
            },
            VisualAssessmentSessionState.AWAITING_USER_INPUT: {
                VisualAssessmentSessionState.COLLECTING_EVIDENCE,
                VisualAssessmentSessionState.READY_FOR_REVIEW,
                VisualAssessmentSessionState.FAILED,
            },
            VisualAssessmentSessionState.READY_FOR_REVIEW: {
                VisualAssessmentSessionState.CONFIRMED,
                VisualAssessmentSessionState.COLLECTING_EVIDENCE,
                VisualAssessmentSessionState.SUPERSEDED,
                VisualAssessmentSessionState.FAILED,
            },
            VisualAssessmentSessionState.CONFIRMED: {
                VisualAssessmentSessionState.SUPERSEDED,
            },
            VisualAssessmentSessionState.SUPERSEDED: set(),
            VisualAssessmentSessionState.FAILED: set(),
        }
        if state not in allowed[self.state]:
            raise ValueError(f"invalid session transition: {self.state.value} -> {state.value}")
        return replace(self, state=state, updated_at=updated_at, failure_reason=failure_reason)


@dataclass(frozen=True, slots=True)
class PhotoEvidence(SerializableModel):
    """Metadata and an opaque reference for a photo; never raw image bytes."""

    evidence_id: str
    area_id: str
    evidence_type: PhotoEvidenceType
    captured_at: datetime
    source: PhotoSource
    privacy_classification: PrivacyClassification
    retention_policy: RetentionPolicy
    content_reference: str | None = None
    retention_days: int | None = None
    user_note: str | None = None
    property_id: str | None = None
    commissioning_session_id: str | None = None
    zone_running_context: bool = False

    def __post_init__(self) -> None:
        _validate_identifier("evidence_id", self.evidence_id)
        _validate_identifier("area_id", self.area_id)
        _validate_timestamp("captured_at", self.captured_at)
        if self.content_reference is not None:
            if not isinstance(self.content_reference, str):
                raise TypeError("content_reference must be an opaque string, never raw bytes")
            _validate_text("content_reference", self.content_reference)
            if self.content_reference.lstrip().lower().startswith("data:"):
                raise ValueError("content_reference must not embed image data")
        if self.retention_policy is RetentionPolicy.CONFIGURABLE_DURATION:
            if (
                self.retention_days is None
                or isinstance(self.retention_days, bool)
                or not isinstance(self.retention_days, int)
                or self.retention_days <= 0
            ):
                raise ValueError("configurable retention requires positive retention_days")
        elif self.retention_days is not None:
            raise ValueError("retention_days is only valid for configurable retention")
        if self.user_note is not None:
            _validate_text("user_note", self.user_note)
        if self.property_id is not None:
            _validate_identifier("property_id", self.property_id)
        if self.commissioning_session_id is not None:
            _validate_identifier("commissioning_session_id", self.commissioning_session_id)


@dataclass(frozen=True, slots=True)
class DetectedPlant(SerializableModel):
    """A plant or planting group inferred from visual evidence."""

    plant_id: str
    area_id: str
    category: PlantCategory
    quantity_mode: PlantQuantityMode
    quantity: float
    establishment_stage: EstablishmentStage
    metadata: InferenceMetadata
    evidence_ids: tuple[str, ...]
    likely_common_name: str | None = None
    likely_species: str | None = None
    area_unit: AreaUnit | None = None
    age_estimate_months: float | None = None
    canopy_size_meters: float | None = None
    user_confirmed_category: PlantCategory | None = None
    user_confirmed_common_name: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("plant_id", self.plant_id)
        _validate_identifier("area_id", self.area_id)
        _validate_positive("quantity", self.quantity)
        _validate_unique_ids("evidence_ids", self.evidence_ids)
        if self.quantity_mode is PlantQuantityMode.COUNT and not float(self.quantity).is_integer():
            raise ValueError("count quantity must be a whole number")
        if self.quantity_mode is PlantQuantityMode.PERCENTAGE and self.quantity > 100:
            raise ValueError("percentage quantity cannot exceed 100")
        if self.quantity_mode is PlantQuantityMode.AREA:
            if self.area_unit is None:
                raise ValueError("area quantity requires area_unit")
        elif self.area_unit is not None:
            raise ValueError("area_unit is only valid for area quantities")
        for name, value in (
            ("likely_common_name", self.likely_common_name),
            ("likely_species", self.likely_species),
            ("user_confirmed_common_name", self.user_confirmed_common_name),
        ):
            if value is not None:
                _validate_text(name, value)
        if self.age_estimate_months is not None:
            _validate_positive("age_estimate_months", self.age_estimate_months, allow_zero=True)
        if self.canopy_size_meters is not None:
            _validate_positive("canopy_size_meters", self.canopy_size_meters)
        has_correction = (
            self.user_confirmed_category is not None
            or self.user_confirmed_common_name is not None
        )
        if has_correction and self.metadata.verification_status not in {
            VerificationStatus.USER_CONFIRMED,
            VerificationStatus.USER_CORRECTED,
        }:
            raise ValueError("user-confirmed plant values require a user verification status")

    @property
    def effective_category(self) -> PlantCategory:
        """Resolve the user-confirmed category ahead of the preserved inference."""
        return self.user_confirmed_category or self.category

    @property
    def effective_common_name(self) -> str | None:
        """Resolve the user-confirmed name ahead of the preserved inference."""
        return self.user_confirmed_common_name or self.likely_common_name


@dataclass(frozen=True, slots=True)
class DetectedIrrigationHardware(SerializableModel):
    """Irrigation hardware inferred from visual evidence."""

    hardware_id: str
    area_id: str
    hardware_type: IrrigationHardwareType
    quantity_mode: HardwareQuantityMode
    quantity: float
    metadata: InferenceMetadata
    evidence_ids: tuple[str, ...]
    guided_verification_required: bool
    manufacturer: str | None = None
    model: str | None = None
    flow_liters_per_hour: float | None = None
    application_rate_mm_per_hour: float | None = None
    coverage_radius_meters: float | None = None
    arc_degrees: float | None = None

    def __post_init__(self) -> None:
        _validate_identifier("hardware_id", self.hardware_id)
        _validate_identifier("area_id", self.area_id)
        _validate_positive("quantity", self.quantity)
        _validate_unique_ids("evidence_ids", self.evidence_ids)
        if (
            self.quantity_mode is HardwareQuantityMode.COUNT
            and not float(self.quantity).is_integer()
        ):
            raise ValueError("hardware count must be a whole number")
        if self.quantity_mode is HardwareQuantityMode.SHARE_PERCENTAGE and self.quantity > 100:
            raise ValueError("hardware share cannot exceed 100 percent")
        for text_name, text_value in (
            ("manufacturer", self.manufacturer),
            ("model", self.model),
        ):
            if text_value is not None:
                _validate_text(text_name, text_value)
        for name, value in (
            ("flow_liters_per_hour", self.flow_liters_per_hour),
            ("application_rate_mm_per_hour", self.application_rate_mm_per_hour),
            ("coverage_radius_meters", self.coverage_radius_meters),
        ):
            if value is not None:
                _validate_positive(name, value)
        if self.arc_degrees is not None:
            _validate_positive("arc_degrees", self.arc_degrees)
            if self.arc_degrees > 360:
                raise ValueError("arc_degrees cannot exceed 360")


@dataclass(frozen=True, slots=True)
class UserMeasurement(SerializableModel):
    """A user-supplied result from direct observation or a guided test."""

    measurement_id: str
    area_id: str
    measurement_type: MeasurementType
    value: float | int | bool | str
    observed_at: datetime
    provenance: Provenance
    unit: str | None = None
    guided_test_id: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("measurement_id", self.measurement_id)
        _validate_identifier("area_id", self.area_id)
        _validate_timestamp("observed_at", self.observed_at)
        if self.guided_test_id is not None:
            _validate_identifier("guided_test_id", self.guided_test_id)
        if self.unit is not None:
            _validate_text("unit", self.unit)
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("measurement value must be finite")
        if self.measurement_type is MeasurementType.BOOLEAN:
            if not isinstance(self.value, bool):
                raise ValueError("boolean measurements require a boolean value")
        elif self.measurement_type in {
            MeasurementType.PHOTO_COMPARISON,
            MeasurementType.TEXT,
        }:
            if not isinstance(self.value, str):
                raise ValueError("textual measurements require a string value")
            _validate_text("value", self.value)
        elif isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("numeric measurements require a numeric value")
        elif self.value < 0:
            raise ValueError("measurement value cannot be negative")
        if self.measurement_type is MeasurementType.COUNT and not float(self.value).is_integer():
            raise ValueError("count measurements require a whole-number value")


@dataclass(frozen=True, slots=True)
class SoilAssessment(SerializableModel):
    """Visual, dataset, and user-confirmed soil evidence kept side by side."""

    area_id: str
    assessed_at: datetime
    visual_class: SoilClass | None = None
    visual_metadata: InferenceMetadata | None = None
    dataset_suggested_class: SoilClass | None = None
    dataset_metadata: InferenceMetadata | None = None
    user_confirmed_class: SoilClass | None = None
    user_confirmation_provenance: Provenance | None = None
    user_confirmed_at: datetime | None = None
    infiltration_observations: tuple[UserMeasurement, ...] = ()
    drainage_observations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("area_id", self.area_id)
        _validate_timestamp("assessed_at", self.assessed_at)
        if (self.visual_class is None) != (self.visual_metadata is None):
            raise ValueError("visual soil class and metadata must be provided together")
        if (self.dataset_suggested_class is None) != (self.dataset_metadata is None):
            raise ValueError("dataset soil class and metadata must be provided together")
        confirmation_fields = (
            self.user_confirmation_provenance,
            self.user_confirmed_at,
        )
        if self.user_confirmed_class is None and any(
            value is not None for value in confirmation_fields
        ):
            raise ValueError("user confirmation metadata requires a user-confirmed class")
        if self.user_confirmed_class is not None and any(
            value is None for value in confirmation_fields
        ):
            raise ValueError("user-confirmed class requires provenance and timestamp")
        if self.user_confirmed_at is not None:
            _validate_timestamp("user_confirmed_at", self.user_confirmed_at)
        if any(item.area_id != self.area_id for item in self.infiltration_observations):
            raise ValueError("soil measurements must belong to the assessment area")
        for observation in self.drainage_observations:
            _validate_text("drainage_observation", observation)

    @property
    def effective_class(self) -> SoilClass | None:
        """Return user truth first, preserving lower-priority source values."""
        return self.user_confirmed_class or self.visual_class or self.dataset_suggested_class

    @property
    def has_class_conflict(self) -> bool:
        """Return whether available sources disagree about soil class."""
        classes = {
            value
            for value in (
                self.visual_class,
                self.dataset_suggested_class,
                self.user_confirmed_class,
            )
            if value is not None and value is not SoilClass.UNKNOWN
        }
        return len(classes) > 1


@dataclass(frozen=True, slots=True)
class Uncertainty(SerializableModel):
    """An explicit limitation in an assessment finding."""

    uncertainty_id: str
    kind: UncertaintyKind
    description: str
    metadata: InferenceMetadata
    evidence_ids: tuple[str, ...] = ()
    resolvable_by_test_id: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("uncertainty_id", self.uncertainty_id)
        _validate_text("description", self.description)
        _validate_unique_ids("evidence_ids", self.evidence_ids)
        if self.resolvable_by_test_id is not None:
            _validate_identifier("resolvable_by_test_id", self.resolvable_by_test_id)


@dataclass(frozen=True, slots=True)
class GuidedTest(SerializableModel):
    """A safe, user-performed test requested to resolve uncertainty."""

    test_id: str
    area_id: str
    test_type: GuidedTestType
    why_it_matters: str
    instructions: tuple[str, ...]
    requested_unit: str | None
    expected_measurement_type: MeasurementType
    state: GuidedTestState
    safety_note: str
    timer_duration_seconds: int | None = None
    measurement_ids: tuple[str, ...] = ()
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_identifier("test_id", self.test_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("why_it_matters", self.why_it_matters)
        _validate_text("safety_note", self.safety_note)
        if not self.instructions:
            raise ValueError("guided test requires at least one instruction")
        for instruction in self.instructions:
            _validate_text("instruction", instruction)
        if self.requested_unit is not None:
            _validate_text("requested_unit", self.requested_unit)
        if self.timer_duration_seconds is not None:
            if isinstance(self.timer_duration_seconds, bool) or not isinstance(
                self.timer_duration_seconds, int
            ):
                raise ValueError("timer_duration_seconds must be a whole number")
            _validate_positive("timer_duration_seconds", self.timer_duration_seconds)
        _validate_unique_ids("measurement_ids", self.measurement_ids)
        if self.state is GuidedTestState.COMPLETED:
            if self.completed_at is None:
                raise ValueError("completed guided tests require completed_at")
            if not self.measurement_ids:
                raise ValueError("completed guided tests require a measurement")
        elif self.completed_at is not None:
            raise ValueError("completed_at is only valid for completed tests")
        if self.completed_at is not None:
            _validate_timestamp("completed_at", self.completed_at)

    def complete(self, *, measurement_ids: tuple[str, ...], completed_at: datetime) -> Self:
        """Return a completed test while preserving immutable history."""
        if self.state not in {GuidedTestState.REQUESTED, GuidedTestState.IN_PROGRESS}:
            raise ValueError("only an active guided test can be completed")
        return replace(
            self,
            state=GuidedTestState.COMPLETED,
            measurement_ids=measurement_ids,
            completed_at=completed_at,
        )


@dataclass(frozen=True, slots=True)
class DiagnosisHypothesis(SerializableModel):
    """An evidence-linked, explicitly uncertain diagnostic hypothesis."""

    hypothesis_id: str
    likely_cause: str
    metadata: InferenceMetadata
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    alternative_causes: tuple[str, ...]
    recommended_next_diagnostic_step: str

    def __post_init__(self) -> None:
        _validate_identifier("hypothesis_id", self.hypothesis_id)
        _validate_text("likely_cause", self.likely_cause)
        _validate_text("recommended_next_diagnostic_step", self.recommended_next_diagnostic_step)
        _validate_unique_ids("supporting_evidence_ids", self.supporting_evidence_ids)
        _validate_unique_ids("contradicting_evidence_ids", self.contradicting_evidence_ids)
        if set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids):
            raise ValueError("evidence cannot both support and contradict a hypothesis")
        for cause in self.alternative_causes:
            _validate_text("alternative_cause", cause)


@dataclass(frozen=True, slots=True)
class RecommendedAction(SerializableModel):
    """A reviewable advisory action, never an executable irrigation command."""

    action_id: str
    area_id: str
    action_type: RecommendedActionType
    rationale: str
    metadata: InferenceMetadata
    related_hypothesis_ids: tuple[str, ...] = ()
    guided_test_id: str | None = None
    temporary_adjustment_id: str | None = None
    baseline_adjustment_id: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("action_id", self.action_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("rationale", self.rationale)
        _validate_unique_ids("related_hypothesis_ids", self.related_hypothesis_ids)
        for name, value in (
            ("guided_test_id", self.guided_test_id),
            ("temporary_adjustment_id", self.temporary_adjustment_id),
            ("baseline_adjustment_id", self.baseline_adjustment_id),
        ):
            if value is not None:
                _validate_identifier(name, value)


@dataclass(frozen=True, slots=True)
class TemporaryAdjustment(SerializableModel):
    """A bounded, temporary proposal that cannot execute itself."""

    adjustment_id: str
    area_id: str
    kind: AdjustmentKind
    change: float
    safety_minimum: float
    safety_maximum: float
    reason: str
    metadata: InferenceMetadata
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    event_count_limit: int | None = None
    proposal_only: bool = True

    def __post_init__(self) -> None:
        _validate_identifier("adjustment_id", self.adjustment_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("reason", self.reason)
        for name, value in (
            ("change", self.change),
            ("safety_minimum", self.safety_minimum),
            ("safety_maximum", self.safety_maximum),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number")
        if self.safety_minimum > self.safety_maximum:
            raise ValueError("safety_minimum cannot exceed safety_maximum")
        if not self.safety_minimum <= self.change <= self.safety_maximum:
            raise ValueError("change must remain within safety bounds")
        if self.kind is AdjustmentKind.PERCENTAGE and not -100 <= self.change <= 100:
            raise ValueError("percentage change must be between -100 and 100")
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("temporary time bounds require both starts_at and ends_at")
        if self.starts_at is not None and self.ends_at is not None:
            _validate_timestamp("starts_at", self.starts_at)
            _validate_timestamp("ends_at", self.ends_at)
            if self.ends_at <= self.starts_at:
                raise ValueError("ends_at must follow starts_at")
        if self.event_count_limit is not None:
            if isinstance(self.event_count_limit, bool) or not isinstance(
                self.event_count_limit, int
            ):
                raise ValueError("event_count_limit must be a whole number")
            _validate_positive("event_count_limit", self.event_count_limit)
        if self.ends_at is None and self.event_count_limit is None:
            raise ValueError("temporary adjustment requires time bounds or an event-count limit")
        if not self.proposal_only:
            raise ValueError("temporary adjustments are proposals only")


@dataclass(frozen=True, slots=True)
class BaselineAdjustment(SerializableModel):
    """A proposed persistent model change requiring explicit approval."""

    adjustment_id: str
    area_id: str
    field_name: str
    old_value: str | int | float | bool | None
    proposed_value: str | int | float | bool
    rationale: str
    metadata: InferenceMetadata
    requires_explicit_approval: bool = True

    def __post_init__(self) -> None:
        _validate_identifier("adjustment_id", self.adjustment_id)
        _validate_identifier("area_id", self.area_id)
        _validate_identifier("field_name", self.field_name)
        _validate_text("rationale", self.rationale)
        for name, value in (("old_value", self.old_value), ("proposed_value", self.proposed_value)):
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise ValueError(f"{name} must be a plain scalar value")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not self.requires_explicit_approval:
            raise ValueError("baseline adjustments must require explicit approval")


@dataclass(frozen=True, slots=True)
class VisualLandscapeAssessment(SerializableModel):
    """Complete provider-neutral, advisory result for one assessment session."""

    assessment_id: str
    session: VisualAssessmentSession
    assessed_at: datetime
    photo_evidence: tuple[PhotoEvidence, ...] = ()
    plants: tuple[DetectedPlant, ...] = ()
    irrigation_hardware: tuple[DetectedIrrigationHardware, ...] = ()
    soil: SoilAssessment | None = None
    uncertainties: tuple[Uncertainty, ...] = ()
    guided_tests: tuple[GuidedTest, ...] = ()
    user_measurements: tuple[UserMeasurement, ...] = ()
    hypotheses: tuple[DiagnosisHypothesis, ...] = ()
    recommended_actions: tuple[RecommendedAction, ...] = ()
    temporary_adjustments: tuple[TemporaryAdjustment, ...] = ()
    baseline_adjustments: tuple[BaselineAdjustment, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("assessment_id", self.assessment_id)
        _validate_timestamp("assessed_at", self.assessed_at)
        collections = (
            ("photo_evidence", self.photo_evidence, "evidence_id"),
            ("plants", self.plants, "plant_id"),
            ("irrigation_hardware", self.irrigation_hardware, "hardware_id"),
            ("uncertainties", self.uncertainties, "uncertainty_id"),
            ("guided_tests", self.guided_tests, "test_id"),
            ("user_measurements", self.user_measurements, "measurement_id"),
            ("hypotheses", self.hypotheses, "hypothesis_id"),
            ("recommended_actions", self.recommended_actions, "action_id"),
            ("temporary_adjustments", self.temporary_adjustments, "adjustment_id"),
            ("baseline_adjustments", self.baseline_adjustments, "adjustment_id"),
        )
        for name, collection, id_field in collections:
            identifiers = tuple(getattr(item, id_field) for item in collection)
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{name} must have unique identifiers")
        area_ids = (
            *(item.area_id for item in self.photo_evidence),
            *(item.area_id for item in self.plants),
            *(item.area_id for item in self.irrigation_hardware),
            *(item.area_id for item in self.guided_tests),
            *(item.area_id for item in self.user_measurements),
            *(item.area_id for item in self.recommended_actions),
            *(item.area_id for item in self.temporary_adjustments),
            *(item.area_id for item in self.baseline_adjustments),
        )
        if any(area_id != self.session.area_id for area_id in area_ids):
            raise ValueError("all assessment records must belong to the session area")
        if self.soil is not None and self.soil.area_id != self.session.area_id:
            raise ValueError("soil assessment must belong to the session area")
        plant_percentage = sum(
            item.quantity
            for item in self.plants
            if item.quantity_mode is PlantQuantityMode.PERCENTAGE
        )
        if plant_percentage > 100:
            raise ValueError("percentage-based plant quantities cannot total more than 100")
        hardware_percentage = sum(
            item.quantity
            for item in self.irrigation_hardware
            if item.quantity_mode is HardwareQuantityMode.SHARE_PERCENTAGE
        )
        if hardware_percentage > 100:
            raise ValueError("hardware shares cannot total more than 100 percent")
        evidence_ids = {item.evidence_id for item in self.photo_evidence}
        referenced_evidence_ids = {
            evidence_id
            for item in self.plants
            for evidence_id in item.evidence_ids
        }
        referenced_evidence_ids.update(
            evidence_id
            for item in self.irrigation_hardware
            for evidence_id in item.evidence_ids
        )
        referenced_evidence_ids.update(
            evidence_id
            for hypothesis in self.hypotheses
            for evidence_id in (
                *hypothesis.supporting_evidence_ids,
                *hypothesis.contradicting_evidence_ids,
            )
        )
        referenced_evidence_ids.update(
            evidence_id
            for uncertainty in self.uncertainties
            for evidence_id in uncertainty.evidence_ids
        )
        if not referenced_evidence_ids <= evidence_ids:
            raise ValueError("findings reference photo evidence absent from the assessment")
        if not set(self.session.evidence_ids) <= evidence_ids:
            raise ValueError("session references photo evidence absent from the assessment")
        guided_test_ids = {item.test_id for item in self.guided_tests}
        measurement_ids = {item.measurement_id for item in self.user_measurements}
        hypothesis_ids = {item.hypothesis_id for item in self.hypotheses}
        temporary_ids = {item.adjustment_id for item in self.temporary_adjustments}
        baseline_ids = {item.adjustment_id for item in self.baseline_adjustments}
        if any(
            item.resolvable_by_test_id is not None
            and item.resolvable_by_test_id not in guided_test_ids
            for item in self.uncertainties
        ):
            raise ValueError("uncertainty references a guided test absent from the assessment")
        if any(
            not set(item.measurement_ids) <= measurement_ids for item in self.guided_tests
        ):
            raise ValueError("guided test references a measurement absent from the assessment")
        if any(
            item.guided_test_id is not None and item.guided_test_id not in guided_test_ids
            for item in self.user_measurements
        ):
            raise ValueError("measurement references a guided test absent from the assessment")
        for action in self.recommended_actions:
            if not set(action.related_hypothesis_ids) <= hypothesis_ids:
                raise ValueError("action references a hypothesis absent from the assessment")
            if action.guided_test_id is not None and action.guided_test_id not in guided_test_ids:
                raise ValueError("action references a guided test absent from the assessment")
            if (
                action.temporary_adjustment_id is not None
                and action.temporary_adjustment_id not in temporary_ids
            ):
                raise ValueError(
                    "action references a temporary adjustment absent from the assessment"
                )
            if (
                action.baseline_adjustment_id is not None
                and action.baseline_adjustment_id not in baseline_ids
            ):
                raise ValueError(
                    "action references a baseline adjustment absent from the assessment"
                )
