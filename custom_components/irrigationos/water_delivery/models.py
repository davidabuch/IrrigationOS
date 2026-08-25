"""Canonical, provider-neutral water-delivery domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class WaterDeliveryType(StrEnum):
    """Canonical water-delivery component types."""

    DRIPPER = "dripper"
    MICROJET = "microjet"
    MISTER = "mister"
    SPRAY = "spray"
    ROTOR = "rotor"
    BUBBLER = "bubbler"
    SUBSURFACE_DRIP = "subsurface_drip"
    MANUAL_WATERING = "manual_watering"
    UNKNOWN = "unknown"


class DeliveryQuantityMode(StrEnum):
    """Meaning of a water-delivery component quantity."""

    COUNT = "count"
    PERCENTAGE = "percentage"
    SERVED_AREA = "served_area"


class AreaUnit(StrEnum):
    """Supported units for served landscape area."""

    SQUARE_FEET = "square_feet"
    SQUARE_METERS = "square_meters"


class FlowBasis(StrEnum):
    """Scope represented by nominal and measured flow values."""

    PER_EMITTER = "per_emitter"
    COMPONENT_TOTAL = "component_total"
    MANUAL_SOURCE = "manual_source"
    UNKNOWN = "unknown"


class DeliveryEvidenceLevel(StrEnum):
    """Strength of one delivery fact without conflating rated and measured data."""

    UNKNOWN = "unknown"
    MANUFACTURER_RATED = "manufacturer_rated"
    USER_ESTIMATED = "user_estimated"
    MEASURED = "measured"


class SprayPattern(StrEnum):
    """Canonical delivery coverage patterns."""

    POINT_SOURCE = "point_source"
    LINE_SOURCE = "line_source"
    FULL_CIRCLE = "full_circle"
    PART_CIRCLE = "part_circle"
    STRIP = "strip"
    RECTANGULAR = "rectangular"
    IRREGULAR = "irregular"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class PressureCompensation(StrEnum):
    """Pressure-compensation behavior of a delivery component."""

    PRESSURE_COMPENSATING = "pressure_compensating"
    NON_PRESSURE_COMPENSATING = "non_pressure_compensating"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CloggingRisk(StrEnum):
    """Relative clogging risk for a delivery component."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class CalibrationTestType(StrEnum):
    """Supported guided calibration procedures."""

    DRIP_COUNTING = "drip_counting"
    COLLECTED_VOLUME = "collected_volume"
    SPRAY_RADIUS = "spray_radius"
    SPRAY_ARC = "spray_arc"
    PHOTO_REFERENCE = "photo_reference"
    FUNCTION_INSPECTION = "function_inspection"


class CalibrationState(StrEnum):
    """Lifecycle of a guided calibration."""

    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    INVALIDATED = "invalidated"


class CalibrationMeasurementType(StrEnum):
    """Typed result produced by guided calibration."""

    DRIP_COUNT = "drip_count"
    COLLECTED_VOLUME = "collected_volume"
    RADIUS = "radius"
    ARC = "arc"
    FUNCTIONAL = "functional"


class MeasurementUnit(StrEnum):
    """Stable units supported by calibration measurements."""

    COUNT = "count"
    MILLILITERS = "milliliters"
    LITERS = "liters"
    US_GALLONS = "us_gallons"
    CENTIMETERS = "centimeters"
    METERS = "meters"
    DEGREES = "degrees"
    BOOLEAN = "boolean"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_confidence(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("confidence must be between 0.0 and 1.0")


def _validate_number(
    name: str,
    value: int | float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}")


def _validate_unique_ids(name: str, values: tuple[str, ...]) -> None:
    for value in values:
        _validate_identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate identifiers")


def _validate_fact_value(value: object) -> None:
    if value is None or isinstance(value, StrEnum | bool | int):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("delivery fact value must be finite")
        return
    if isinstance(value, str):
        _validate_text("delivery fact value", value)
        return
    raise TypeError("delivery fact value must be a plain scalar or stable enum")


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
        raise TypeError("raw bytes are not permitted in water-delivery records")
    return value


class SerializableWaterDeliveryModel:
    """Mixin for deterministic plain-dictionary serialization."""

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic data suitable for future adapters and audit."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover - mixin contract
            raise TypeError("water-delivery model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class DeliveryProvenance(SerializableWaterDeliveryModel):
    """Provider- and controller-neutral origin of a delivery fact."""

    source: str
    detail: str | None = None

    def __post_init__(self) -> None:
        _validate_text("source", self.source)
        if self.detail is not None:
            _validate_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class DeliveryFact[T](SerializableWaterDeliveryModel):
    """A typed water-delivery value with confidence, source, and assessment time."""

    value: T | None
    confidence: float
    provenance: DeliveryProvenance
    assessed_at: datetime
    evidence_level: DeliveryEvidenceLevel = DeliveryEvidenceLevel.UNKNOWN

    def __post_init__(self) -> None:
        _validate_fact_value(self.value)
        _validate_confidence(self.confidence)
        _validate_timestamp("assessed_at", self.assessed_at)
        if (
            self.value is None
            or (isinstance(self.value, StrEnum) and self.value.value == "unknown")
        ) and self.confidence != 0:
            raise ValueError("unknown delivery facts must have zero confidence")

    @property
    def is_known(self) -> bool:
        """Return whether the fact has a usable value."""
        if self.value is None:
            return False
        return not isinstance(self.value, StrEnum) or self.value.value != "unknown"


@dataclass(frozen=True, slots=True)
class CalibrationPhotoReference(SerializableWaterDeliveryModel):
    """Opaque reference to calibration evidence, never embedded image content."""

    photo_id: str
    opaque_reference: str
    captured_at: datetime
    source: str
    note: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("photo_id", self.photo_id)
        if not isinstance(self.opaque_reference, str):
            raise TypeError("opaque_reference must be a string, never raw image bytes")
        _validate_text("opaque_reference", self.opaque_reference)
        if self.opaque_reference.lstrip().lower().startswith("data:"):
            raise ValueError("opaque_reference must not embed image data")
        _validate_timestamp("captured_at", self.captured_at)
        _validate_text("source", self.source)
        if self.note is not None:
            _validate_text("note", self.note)


@dataclass(frozen=True, slots=True)
class CalibrationMeasurement(SerializableWaterDeliveryModel):
    """Typed user-observed result of a guided calibration."""

    measurement_id: str
    measurement_type: CalibrationMeasurementType
    value: int | float | bool
    unit: MeasurementUnit
    observed_at: datetime
    provenance: DeliveryProvenance
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _validate_identifier("measurement_id", self.measurement_id)
        _validate_timestamp("observed_at", self.observed_at)
        _validate_confidence(self.confidence)
        expected_units = {
            CalibrationMeasurementType.DRIP_COUNT: {MeasurementUnit.COUNT},
            CalibrationMeasurementType.COLLECTED_VOLUME: {
                MeasurementUnit.MILLILITERS,
                MeasurementUnit.LITERS,
                MeasurementUnit.US_GALLONS,
            },
            CalibrationMeasurementType.RADIUS: {
                MeasurementUnit.CENTIMETERS,
                MeasurementUnit.METERS,
            },
            CalibrationMeasurementType.ARC: {MeasurementUnit.DEGREES},
            CalibrationMeasurementType.FUNCTIONAL: {MeasurementUnit.BOOLEAN},
        }
        if self.unit not in expected_units[self.measurement_type]:
            raise ValueError("measurement unit is inconsistent with measurement type")
        if self.measurement_type is CalibrationMeasurementType.FUNCTIONAL:
            if not isinstance(self.value, bool):
                raise ValueError("functional measurements require a boolean value")
            return
        _validate_number("measurement value", self.value, minimum=0)
        if self.value == 0:
            raise ValueError("calibration measurement must be positive")
        if (
            self.measurement_type is CalibrationMeasurementType.DRIP_COUNT
            and not float(self.value).is_integer()
        ):
            raise ValueError("drip count must be a whole number")
        if self.measurement_type is CalibrationMeasurementType.ARC and self.value > 360:
            raise ValueError("spray arc cannot exceed 360 degrees")


@dataclass(frozen=True, slots=True)
class GuidedCalibration(SerializableWaterDeliveryModel):
    """Immutable instructions and evidence for a user-performed calibration."""

    calibration_id: str
    area_id: str
    component_id: str
    test_type: CalibrationTestType
    state: CalibrationState
    why_it_matters: str
    instructions: tuple[str, ...]
    safety_note: str
    created_at: datetime
    updated_at: datetime
    requested_unit: MeasurementUnit | None = None
    timer_duration_seconds: int | None = None
    measurements: tuple[CalibrationMeasurement, ...] = ()
    photo_references: tuple[CalibrationPhotoReference, ...] = ()
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_identifier("calibration_id", self.calibration_id)
        _validate_identifier("area_id", self.area_id)
        _validate_identifier("component_id", self.component_id)
        _validate_text("why_it_matters", self.why_it_matters)
        _validate_text("safety_note", self.safety_note)
        if not self.instructions:
            raise ValueError("guided calibration requires at least one instruction")
        for instruction in self.instructions:
            _validate_text("instruction", instruction)
        _validate_timestamp("created_at", self.created_at)
        _validate_timestamp("updated_at", self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.timer_duration_seconds is not None:
            if isinstance(self.timer_duration_seconds, bool) or not isinstance(
                self.timer_duration_seconds, int
            ):
                raise ValueError("timer_duration_seconds must be a positive integer")
            if self.timer_duration_seconds <= 0:
                raise ValueError("timer_duration_seconds must be a positive integer")
        measurement_ids = tuple(item.measurement_id for item in self.measurements)
        photo_ids = tuple(item.photo_id for item in self.photo_references)
        _validate_unique_ids("measurement_ids", measurement_ids)
        _validate_unique_ids("photo_ids", photo_ids)
        expected_measurement = {
            CalibrationTestType.DRIP_COUNTING: CalibrationMeasurementType.DRIP_COUNT,
            CalibrationTestType.COLLECTED_VOLUME: CalibrationMeasurementType.COLLECTED_VOLUME,
            CalibrationTestType.SPRAY_RADIUS: CalibrationMeasurementType.RADIUS,
            CalibrationTestType.SPRAY_ARC: CalibrationMeasurementType.ARC,
            CalibrationTestType.FUNCTION_INSPECTION: CalibrationMeasurementType.FUNCTIONAL,
        }
        expected_units = {
            CalibrationTestType.DRIP_COUNTING: {MeasurementUnit.COUNT},
            CalibrationTestType.COLLECTED_VOLUME: {
                MeasurementUnit.MILLILITERS,
                MeasurementUnit.LITERS,
                MeasurementUnit.US_GALLONS,
            },
            CalibrationTestType.SPRAY_RADIUS: {
                MeasurementUnit.CENTIMETERS,
                MeasurementUnit.METERS,
            },
            CalibrationTestType.SPRAY_ARC: {MeasurementUnit.DEGREES},
            CalibrationTestType.FUNCTION_INSPECTION: {MeasurementUnit.BOOLEAN},
        }
        if self.test_type is CalibrationTestType.PHOTO_REFERENCE:
            if self.requested_unit is not None:
                raise ValueError("photo-reference calibration does not request a unit")
        elif (
            self.requested_unit is not None
            and self.requested_unit not in expected_units[self.test_type]
        ):
            raise ValueError("requested_unit is inconsistent with calibration test type")
        if self.test_type in expected_measurement and any(
            item.measurement_type is not expected_measurement[self.test_type]
            for item in self.measurements
        ):
            raise ValueError("calibration measurement is inconsistent with test type")
        if self.state is CalibrationState.COMPLETED:
            if self.completed_at is None:
                raise ValueError("completed calibration requires completed_at")
            if self.test_type is CalibrationTestType.PHOTO_REFERENCE:
                if not self.photo_references:
                    raise ValueError("completed photo calibration requires a photo reference")
            elif not self.measurements:
                raise ValueError("completed calibration requires a measurement")
        elif self.completed_at is not None:
            raise ValueError("completed_at is only valid for completed calibrations")
        if self.completed_at is not None:
            _validate_timestamp("completed_at", self.completed_at)
            if self.completed_at < self.created_at:
                raise ValueError("completed_at cannot precede created_at")
            if self.completed_at > self.updated_at:
                raise ValueError("completed_at cannot follow updated_at")
        if any(item.observed_at < self.created_at for item in self.measurements):
            raise ValueError("calibration measurements cannot predate calibration creation")


@dataclass(frozen=True, slots=True)
class DeliveryComponent(SerializableWaterDeliveryModel):
    """One homogeneous component of a potentially mixed water-delivery profile."""

    component_id: str
    area_id: str
    display_name: str
    delivery_type: WaterDeliveryType
    quantity_mode: DeliveryQuantityMode
    quantity: DeliveryFact[float]
    flow_basis: FlowBasis
    nominal_flow_liters_per_hour: DeliveryFact[float]
    measured_flow_liters_per_hour: DeliveryFact[float]
    application_rate_mm_per_hour: DeliveryFact[float]
    radius_meters: DeliveryFact[float]
    arc_degrees: DeliveryFact[float]
    spray_pattern: DeliveryFact[SprayPattern]
    efficiency: DeliveryFact[float]
    pressure_compensation: DeliveryFact[PressureCompensation]
    clogging_risk: DeliveryFact[CloggingRisk]
    calibration_ids: tuple[str, ...] = ()
    served_area_unit: AreaUnit | None = None
    manufacturer: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("component_id", self.component_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("display_name", self.display_name)
        _validate_unique_ids("calibration_ids", self.calibration_ids)
        quantity = self.quantity.value
        if quantity is not None:
            _validate_number("quantity", quantity, minimum=0)
            if quantity == 0:
                raise ValueError("quantity must be positive")
            if self.quantity_mode is DeliveryQuantityMode.COUNT and not float(
                quantity
            ).is_integer():
                raise ValueError("count quantity must be a whole number")
            if self.quantity_mode is DeliveryQuantityMode.PERCENTAGE and quantity > 100:
                raise ValueError("percentage quantity cannot exceed 100")
        if self.quantity_mode is DeliveryQuantityMode.SERVED_AREA:
            if self.served_area_unit is None:
                raise ValueError("served-area quantity requires served_area_unit")
        elif self.served_area_unit is not None:
            raise ValueError("served_area_unit is only valid for served-area quantity")
        for name, fact, allow_zero in (
            ("nominal_flow_liters_per_hour", self.nominal_flow_liters_per_hour, False),
            ("measured_flow_liters_per_hour", self.measured_flow_liters_per_hour, False),
            ("application_rate_mm_per_hour", self.application_rate_mm_per_hour, False),
            ("radius_meters", self.radius_meters, False),
            ("arc_degrees", self.arc_degrees, False),
            ("efficiency", self.efficiency, True),
        ):
            if fact.value is not None:
                _validate_number(name, fact.value, minimum=0)
                if not allow_zero and fact.value == 0:
                    raise ValueError(f"{name} must be positive")
        if self.arc_degrees.value is not None and self.arc_degrees.value > 360:
            raise ValueError("arc_degrees cannot exceed 360")
        if self.efficiency.value is not None and self.efficiency.value > 1:
            raise ValueError("efficiency cannot exceed 1")
        for name, value in (("manufacturer", self.manufacturer), ("model", self.model)):
            if value is not None:
                _validate_text(name, value)

    @property
    def preferred_flow_liters_per_hour(self) -> float | None:
        """Prefer measured flow while retaining nominal flow and provenance."""
        if self.measured_flow_liters_per_hour.is_known:
            return self.measured_flow_liters_per_hour.value
        return self.nominal_flow_liters_per_hour.value


@dataclass(frozen=True, slots=True)
class WaterDeliveryProfile(SerializableWaterDeliveryModel):
    """Canonical observation-only water-delivery model for one landscape area."""

    profile_id: str
    area_id: str
    display_name: str
    assessed_at: datetime
    components: tuple[DeliveryComponent, ...]
    calibrations: tuple[GuidedCalibration, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("profile_id", self.profile_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("display_name", self.display_name)
        _validate_timestamp("assessed_at", self.assessed_at)
        if not self.components:
            raise ValueError("water-delivery profile requires at least one component")
        component_ids = tuple(item.component_id for item in self.components)
        calibration_ids = tuple(item.calibration_id for item in self.calibrations)
        _validate_unique_ids("component_ids", component_ids)
        _validate_unique_ids("calibration_ids", calibration_ids)
        if any(item.area_id != self.area_id for item in self.components):
            raise ValueError("all delivery components must belong to the profile area")
        if any(item.area_id != self.area_id for item in self.calibrations):
            raise ValueError("all calibrations must belong to the profile area")
        components_by_id = {item.component_id: item for item in self.components}
        if any(item.component_id not in components_by_id for item in self.calibrations):
            raise ValueError("calibration references an unknown delivery component")
        for component in self.components:
            owned_ids = {
                item.calibration_id
                for item in self.calibrations
                if item.component_id == component.component_id
            }
            if set(component.calibration_ids) != owned_ids:
                raise ValueError(
                    "component calibration_ids must exactly match profile calibrations"
                )
        percentage_total = sum(
            component.quantity.value or 0
            for component in self.components
            if component.quantity_mode is DeliveryQuantityMode.PERCENTAGE
        )
        if percentage_total > 100:
            raise ValueError("percentage-based delivery components cannot total more than 100")
        if self.notes is not None:
            _validate_text("notes", self.notes)

    @property
    def delivery_types(self) -> tuple[WaterDeliveryType, ...]:
        """Return unique delivery types in first-seen component order."""
        return tuple(dict.fromkeys(component.delivery_type for component in self.components))

    @property
    def is_mixed(self) -> bool:
        """Return whether the area uses more than one delivery type."""
        return len(self.delivery_types) > 1
