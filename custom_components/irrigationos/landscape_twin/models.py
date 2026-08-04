"""Canonical, provider-neutral Landscape Digital Twin domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any, Self

LANDSCAPE_TWIN_SCHEMA_VERSION = 1
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class VerificationStatus(StrEnum):
    """Verification state of a canonical landscape fact."""

    UNVERIFIED = "unverified"
    MEASURED = "measured"
    USER_CONFIRMED = "user_confirmed"
    USER_CORRECTED = "user_corrected"


class PlantGroupType(StrEnum):
    """Broad canonical planting categories."""

    TURF_COOL_SEASON = "turf_cool_season"
    TURF_WARM_SEASON = "turf_warm_season"
    TREE = "tree"
    SHRUB = "shrub"
    HEDGE = "hedge"
    GROUNDCOVER = "groundcover"
    VINE = "vine"
    SUCCULENT = "succulent"
    VEGETABLE = "vegetable"
    FLOWER = "flower"
    MIXED = "mixed"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class PlantQuantityMode(StrEnum):
    """Meaning of a plant-group quantity."""

    COUNT = "count"
    PERCENTAGE = "percentage"
    AREA = "area"


class EstablishmentStage(StrEnum):
    """Canonical plant establishment stage."""

    NEWLY_PLANTED = "newly_planted"
    YOUNG = "young"
    ESTABLISHED = "established"
    MATURE = "mature"
    UNKNOWN = "unknown"


class AreaUnit(StrEnum):
    """Canonical units for physical landscape area."""

    SQUARE_FEET = "square_feet"
    SQUARE_METERS = "square_meters"


class SoilTexture(StrEnum):
    """Operational soil texture classes."""

    SAND = "sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    CLAY_LOAM = "clay_loam"
    CLAY = "clay"
    AMENDED = "amended"
    CONTAINER = "container"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class DrainageClass(StrEnum):
    """Observed or measured landscape drainage behavior."""

    RAPID = "rapid"
    WELL_DRAINED = "well_drained"
    MODERATE = "moderate"
    SLOW = "slow"
    POOR = "poor"
    UNKNOWN = "unknown"


class IrrigationDeliveryMethod(StrEnum):
    """Canonical irrigation delivery methods."""

    DRIP = "drip"
    MICROJET = "microjet"
    MISTER = "mister"
    SPRAY = "spray"
    ROTOR = "rotor"
    BUBBLER = "bubbler"
    SUBSURFACE_DRIP = "subsurface_drip"
    MIXED = "mixed"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class SunExposure(StrEnum):
    """Canonical sunlight exposure classes."""

    FULL_SUN = "full_sun"
    MOSTLY_SUN = "mostly_sun"
    PART_SUN = "part_sun"
    MOSTLY_SHADE = "mostly_shade"
    FULL_SHADE = "full_shade"
    UNKNOWN = "unknown"


class WindExposure(StrEnum):
    """Relative wind exposure of an area."""

    SHELTERED = "sheltered"
    MODERATE = "moderate"
    EXPOSED = "exposed"
    UNKNOWN = "unknown"


class HeatExposure(StrEnum):
    """Local reflected and retained heat exposure."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class HealthStatus(StrEnum):
    """Observed health of a landscape area or plant group."""

    HEALTHY = "healthy"
    WATCH = "watch"
    STRESSED = "stressed"
    DECLINING = "declining"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ObservationSeverity(StrEnum):
    """Severity of a health observation."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class WaterDemandBasis(StrEnum):
    """Basis used to characterize landscape water demand."""

    REFERENCE_ET = "reference_et"
    CROP_COEFFICIENT = "crop_coefficient"
    MEASURED_USE = "measured_use"
    USER_ESTIMATE = "user_estimate"
    UNKNOWN = "unknown"


class LandscapeGoalType(StrEnum):
    """User-selected landscape management outcomes."""

    PLANT_HEALTH = "plant_health"
    WATER_CONSERVATION = "water_conservation"
    ESTABLISHMENT = "establishment"
    APPEARANCE = "appearance"
    FOOD_PRODUCTION = "food_production"
    DIAGNOSTIC_RECOVERY = "diagnostic_recovery"
    CUSTOM = "custom"


class GoalPriority(StrEnum):
    """Relative priority of a landscape goal."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class BindingStatus(StrEnum):
    """Lifecycle of a controller-slot binding."""

    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    RETIRED = "retired"


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


def _validate_finite_number(
    name: str,
    value: float | int,
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
            raise ValueError("landscape fact value must be finite")
        return
    if isinstance(value, str):
        _validate_text("landscape fact value", value)
        return
    raise TypeError("landscape fact value must be a plain scalar or stable enum")


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
        raise TypeError("raw bytes are not permitted in Landscape Digital Twin records")
    return value


class SerializableTwinModel:
    """Mixin for deterministic plain-dictionary serialization."""

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic persistence- and audit-safe dictionary."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover - mixin contract
            raise TypeError("Landscape Digital Twin model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class FactProvenance(SerializableTwinModel):
    """Provider-neutral origin of a canonical landscape fact."""

    source: str
    source_reference: str | None = None
    method: str | None = None

    def __post_init__(self) -> None:
        _validate_text("source", self.source)
        for name, value in (
            ("source_reference", self.source_reference),
            ("method", self.method),
        ):
            if value is not None:
                _validate_text(name, value)


@dataclass(frozen=True, slots=True)
class FactRevision[T](SerializableTwinModel):
    """An immutable prior value retained when a fact is superseded."""

    value: T | None
    confidence: float
    provenance: FactProvenance
    verification_status: VerificationStatus
    assessed_at: datetime

    def __post_init__(self) -> None:
        _validate_fact_value(self.value)
        _validate_confidence(self.confidence)
        _validate_timestamp("assessed_at", self.assessed_at)
        if (
            self.value is None
            or (isinstance(self.value, StrEnum) and self.value.value == "unknown")
        ) and self.confidence != 0:
            raise ValueError("unknown revisions must have zero confidence")


@dataclass(frozen=True, slots=True)
class LandscapeFact[T](SerializableTwinModel):
    """A value with confidence, provenance, verification, time, and history."""

    value: T | None
    confidence: float
    provenance: FactProvenance
    verification_status: VerificationStatus
    assessed_at: datetime
    history: tuple[FactRevision[T], ...] = ()

    def __post_init__(self) -> None:
        _validate_fact_value(self.value)
        _validate_confidence(self.confidence)
        _validate_timestamp("assessed_at", self.assessed_at)
        if (
            self.value is None
            or (isinstance(self.value, StrEnum) and self.value.value == "unknown")
        ) and self.confidence != 0:
            raise ValueError("unknown facts must have zero confidence")
        if any(revision.assessed_at > self.assessed_at for revision in self.history):
            raise ValueError("fact history cannot postdate the current value")
        history_times = tuple(revision.assessed_at for revision in self.history)
        if history_times != tuple(sorted(history_times)):
            raise ValueError("fact history must be chronological")

    @property
    def is_known(self) -> bool:
        """Return whether the fact contains a usable non-unknown value."""
        if self.value is None:
            return False
        return not isinstance(self.value, StrEnum) or self.value.value != "unknown"

    @property
    def effective_confidence(self) -> float:
        """Treat human-confirmed facts as fully resolved confidence debt."""
        if self.verification_status in {
            VerificationStatus.MEASURED,
            VerificationStatus.USER_CONFIRMED,
            VerificationStatus.USER_CORRECTED,
        }:
            return 1.0
        return self.confidence

    def supersede(
        self,
        value: T | None,
        *,
        confidence: float,
        provenance: FactProvenance,
        verification_status: VerificationStatus,
        assessed_at: datetime,
    ) -> Self:
        """Return a replacement fact while preserving the current fact in history."""
        revision = FactRevision(
            value=self.value,
            confidence=self.confidence,
            provenance=self.provenance,
            verification_status=self.verification_status,
            assessed_at=self.assessed_at,
        )
        return type(self)(
            value=value,
            confidence=confidence,
            provenance=provenance,
            verification_status=verification_status,
            assessed_at=assessed_at,
            history=(*self.history, revision),
        )


@dataclass(frozen=True, slots=True)
class PropertyProfile(SerializableTwinModel):
    """Canonical property identity and property-wide landscape facts."""

    property_id: str
    display_name: str
    timezone: str
    area_ids: tuple[str, ...]
    total_landscape_area_square_meters: LandscapeFact[float]
    climate_zone: LandscapeFact[str]
    created_at: datetime
    updated_at: datetime
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("property_id", self.property_id)
        _validate_text("display_name", self.display_name)
        _validate_text("timezone", self.timezone)
        _validate_unique_ids("area_ids", self.area_ids)
        _validate_timestamp("created_at", self.created_at)
        _validate_timestamp("updated_at", self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.notes is not None:
            _validate_text("notes", self.notes)
        value = self.total_landscape_area_square_meters.value
        if value is not None:
            _validate_finite_number("total landscape area", value, minimum=0.01)


@dataclass(frozen=True, slots=True)
class LandscapeArea(SerializableTwinModel):
    """Stable landscape area independent of names and controller bindings."""

    area_id: str
    property_id: str
    display_name: str
    area_square_meters: LandscapeFact[float]
    slope_percent: LandscapeFact[float]
    plant_group_ids: tuple[str, ...] = ()
    soil_profile_id: str | None = None
    irrigation_delivery_profile_id: str | None = None
    weather_exposure_profile_id: str | None = None
    water_demand_profile_id: str | None = None
    health_observation_ids: tuple[str, ...] = ()
    goal_ids: tuple[str, ...] = ()
    controller_binding_ids: tuple[str, ...] = ()
    active: bool = True

    def __post_init__(self) -> None:
        _validate_identifier("area_id", self.area_id)
        _validate_identifier("property_id", self.property_id)
        _validate_text("display_name", self.display_name)
        for name, values in (
            ("plant_group_ids", self.plant_group_ids),
            ("health_observation_ids", self.health_observation_ids),
            ("goal_ids", self.goal_ids),
            ("controller_binding_ids", self.controller_binding_ids),
        ):
            _validate_unique_ids(name, values)
        for name, value in (
            ("soil_profile_id", self.soil_profile_id),
            ("irrigation_delivery_profile_id", self.irrigation_delivery_profile_id),
            ("weather_exposure_profile_id", self.weather_exposure_profile_id),
            ("water_demand_profile_id", self.water_demand_profile_id),
        ):
            if value is not None:
                _validate_identifier(name, value)
        if self.area_square_meters.value is not None:
            _validate_finite_number(
                "area_square_meters", self.area_square_meters.value, minimum=0.01
            )
        if self.slope_percent.value is not None:
            _validate_finite_number("slope_percent", self.slope_percent.value, minimum=0)


@dataclass(frozen=True, slots=True)
class PlantGroup(SerializableTwinModel):
    """Canonical group of plants with consistent water-management characteristics."""

    plant_group_id: str
    area_id: str
    display_name: str
    category: LandscapeFact[PlantGroupType]
    quantity_mode: PlantQuantityMode
    quantity: LandscapeFact[float]
    establishment_stage: LandscapeFact[EstablishmentStage]
    root_depth_meters: LandscapeFact[float]
    common_name: LandscapeFact[str]
    botanical_name: LandscapeFact[str]
    canopy_diameter_meters: LandscapeFact[float]
    area_unit: AreaUnit | None = None

    def __post_init__(self) -> None:
        _validate_identifier("plant_group_id", self.plant_group_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("display_name", self.display_name)
        quantity = self.quantity.value
        if quantity is not None:
            _validate_finite_number("plant quantity", quantity, minimum=0.01)
            if self.quantity_mode is PlantQuantityMode.COUNT and not float(quantity).is_integer():
                raise ValueError("count-based plant quantity must be a whole number")
            if self.quantity_mode is PlantQuantityMode.PERCENTAGE and quantity > 100:
                raise ValueError("plant percentage cannot exceed 100")
        if self.quantity_mode is PlantQuantityMode.AREA:
            if self.area_unit is None:
                raise ValueError("area-based plant quantity requires area_unit")
        elif self.area_unit is not None:
            raise ValueError("area_unit is only valid for area-based plant quantity")
        for name, fact in (
            ("root_depth_meters", self.root_depth_meters),
            ("canopy_diameter_meters", self.canopy_diameter_meters),
        ):
            if fact.value is not None:
                _validate_finite_number(name, fact.value, minimum=0.01)


@dataclass(frozen=True, slots=True)
class SoilProfile(SerializableTwinModel):
    """Canonical soil and root-zone characteristics for one landscape area."""

    soil_profile_id: str
    area_id: str
    texture: LandscapeFact[SoilTexture]
    infiltration_rate_mm_per_hour: LandscapeFact[float]
    available_water_capacity_mm_per_meter: LandscapeFact[float]
    drainage_class: LandscapeFact[DrainageClass]
    root_zone_depth_meters: LandscapeFact[float]
    organic_matter_percent: LandscapeFact[float]
    ph: LandscapeFact[float]
    description: LandscapeFact[str]

    def __post_init__(self) -> None:
        _validate_identifier("soil_profile_id", self.soil_profile_id)
        _validate_identifier("area_id", self.area_id)
        for name, fact, minimum, maximum in (
            ("infiltration_rate_mm_per_hour", self.infiltration_rate_mm_per_hour, 0.0, None),
            (
                "available_water_capacity_mm_per_meter",
                self.available_water_capacity_mm_per_meter,
                0.0,
                None,
            ),
            ("root_zone_depth_meters", self.root_zone_depth_meters, 0.01, None),
            ("organic_matter_percent", self.organic_matter_percent, 0.0, 100.0),
            ("ph", self.ph, 0.0, 14.0),
        ):
            if fact.value is not None:
                _validate_finite_number(name, fact.value, minimum=minimum, maximum=maximum)


@dataclass(frozen=True, slots=True)
class IrrigationDeliveryProfile(SerializableTwinModel):
    """Observed delivery characteristics without any command-delivery behavior."""

    delivery_profile_id: str
    area_id: str
    method: LandscapeFact[IrrigationDeliveryMethod]
    application_rate_mm_per_hour: LandscapeFact[float]
    distribution_efficiency: LandscapeFact[float]
    distribution_uniformity: LandscapeFact[float]
    nominal_flow_liters_per_minute: LandscapeFact[float]
    minimum_cycle_minutes: LandscapeFact[float]
    maximum_cycle_minutes: LandscapeFact[float]

    def __post_init__(self) -> None:
        _validate_identifier("delivery_profile_id", self.delivery_profile_id)
        _validate_identifier("area_id", self.area_id)
        for name, fact in (
            ("application_rate_mm_per_hour", self.application_rate_mm_per_hour),
            ("nominal_flow_liters_per_minute", self.nominal_flow_liters_per_minute),
            ("minimum_cycle_minutes", self.minimum_cycle_minutes),
            ("maximum_cycle_minutes", self.maximum_cycle_minutes),
        ):
            if fact.value is not None:
                _validate_finite_number(name, fact.value, minimum=0)
        for name, fact in (
            ("distribution_efficiency", self.distribution_efficiency),
            ("distribution_uniformity", self.distribution_uniformity),
        ):
            if fact.value is not None:
                _validate_finite_number(name, fact.value, minimum=0, maximum=1)
        minimum = self.minimum_cycle_minutes.value
        maximum = self.maximum_cycle_minutes.value
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("minimum_cycle_minutes cannot exceed maximum_cycle_minutes")


@dataclass(frozen=True, slots=True)
class WeatherExposureProfile(SerializableTwinModel):
    """Static microclimate exposure facts, not live weather observations."""

    exposure_profile_id: str
    area_id: str
    sun_exposure: LandscapeFact[SunExposure]
    direct_sun_hours: LandscapeFact[float]
    wind_exposure: LandscapeFact[WindExposure]
    heat_exposure: LandscapeFact[HeatExposure]
    shade_percent: LandscapeFact[float]
    microclimate_notes: LandscapeFact[str]

    def __post_init__(self) -> None:
        _validate_identifier("exposure_profile_id", self.exposure_profile_id)
        _validate_identifier("area_id", self.area_id)
        if self.direct_sun_hours.value is not None:
            _validate_finite_number(
                "direct_sun_hours", self.direct_sun_hours.value, minimum=0, maximum=24
            )
        if self.shade_percent.value is not None:
            _validate_finite_number(
                "shade_percent", self.shade_percent.value, minimum=0, maximum=100
            )


@dataclass(frozen=True, slots=True)
class HealthObservation(SerializableTwinModel):
    """Evidence-linked landscape health observation."""

    observation_id: str
    area_id: str
    observed_at: datetime
    status: LandscapeFact[HealthStatus]
    severity: LandscapeFact[ObservationSeverity]
    summary: str
    symptoms: tuple[str, ...] = ()
    plant_group_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_identifier("observation_id", self.observation_id)
        _validate_identifier("area_id", self.area_id)
        _validate_timestamp("observed_at", self.observed_at)
        _validate_text("summary", self.summary)
        if self.plant_group_id is not None:
            _validate_identifier("plant_group_id", self.plant_group_id)
        _validate_unique_ids("evidence_ids", self.evidence_ids)
        for symptom in self.symptoms:
            _validate_text("symptom", symptom)
        if self.resolved_at is not None:
            _validate_timestamp("resolved_at", self.resolved_at)
            if self.resolved_at < self.observed_at:
                raise ValueError("resolved_at cannot precede observed_at")


@dataclass(frozen=True, slots=True)
class WaterDemandProfile(SerializableTwinModel):
    """Descriptive water-demand facts for planning and future recommendations."""

    demand_profile_id: str
    area_id: str
    basis: LandscapeFact[WaterDemandBasis]
    crop_coefficient: LandscapeFact[float]
    peak_daily_demand_mm: LandscapeFact[float]
    allowable_depletion_fraction: LandscapeFact[float]
    seasonal_adjustment_factor: LandscapeFact[float]
    target_soil_moisture_fraction: LandscapeFact[float]

    def __post_init__(self) -> None:
        _validate_identifier("demand_profile_id", self.demand_profile_id)
        _validate_identifier("area_id", self.area_id)
        for name, fact, minimum, maximum in (
            ("crop_coefficient", self.crop_coefficient, 0.0, 2.0),
            ("peak_daily_demand_mm", self.peak_daily_demand_mm, 0.0, None),
            (
                "allowable_depletion_fraction",
                self.allowable_depletion_fraction,
                0.0,
                1.0,
            ),
            (
                "seasonal_adjustment_factor",
                self.seasonal_adjustment_factor,
                0.0,
                3.0,
            ),
            (
                "target_soil_moisture_fraction",
                self.target_soil_moisture_fraction,
                0.0,
                1.0,
            ),
        ):
            if fact.value is not None:
                _validate_finite_number(name, fact.value, minimum=minimum, maximum=maximum)


@dataclass(frozen=True, slots=True)
class LandscapeGoal(SerializableTwinModel):
    """Explicit user landscape-management goal."""

    goal_id: str
    area_id: str
    goal_type: LandscapeGoalType
    priority: GoalPriority
    description: str
    target: LandscapeFact[str]
    created_at: datetime
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True

    def __post_init__(self) -> None:
        _validate_identifier("goal_id", self.goal_id)
        _validate_identifier("area_id", self.area_id)
        _validate_text("description", self.description)
        _validate_timestamp("created_at", self.created_at)
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("goal time bounds require both starts_at and ends_at")
        if self.starts_at is not None and self.ends_at is not None:
            _validate_timestamp("starts_at", self.starts_at)
            _validate_timestamp("ends_at", self.ends_at)
            if self.ends_at <= self.starts_at:
                raise ValueError("goal ends_at must follow starts_at")


@dataclass(frozen=True, slots=True)
class ControllerBinding(SerializableTwinModel):
    """Replaceable mapping from a canonical landscape area to a controller slot."""

    binding_id: str
    area_id: str
    controller_id: str
    slot_number: int
    provider: str
    status: BindingStatus
    bound_at: datetime
    vendor_controller_id: str | None = None
    vendor_area_id: str | None = None
    retired_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_identifier("binding_id", self.binding_id)
        _validate_identifier("area_id", self.area_id)
        _validate_identifier("controller_id", self.controller_id)
        if isinstance(self.slot_number, bool) or not isinstance(self.slot_number, int):
            raise ValueError("slot_number must be a positive integer")
        if self.slot_number <= 0:
            raise ValueError("slot_number must be a positive integer")
        _validate_text("provider", self.provider)
        _validate_timestamp("bound_at", self.bound_at)
        for name, value in (
            ("vendor_controller_id", self.vendor_controller_id),
            ("vendor_area_id", self.vendor_area_id),
        ):
            if value is not None:
                _validate_text(name, value)
        if self.status is BindingStatus.RETIRED:
            if self.retired_at is None:
                raise ValueError("retired bindings require retired_at")
        elif self.retired_at is not None:
            raise ValueError("retired_at is only valid for retired bindings")
        if self.retired_at is not None:
            _validate_timestamp("retired_at", self.retired_at)
            if self.retired_at < self.bound_at:
                raise ValueError("retired_at cannot precede bound_at")


@dataclass(frozen=True, slots=True)
class CompletenessReport(SerializableTwinModel):
    """Coverage of planning-critical Landscape Digital Twin facts."""

    required_fact_count: int
    known_fact_count: int
    completeness_percent: int
    missing_fact_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("required_fact_count", self.required_fact_count),
            ("known_fact_count", self.known_fact_count),
            ("completeness_percent", self.completeness_percent),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.known_fact_count > self.required_fact_count:
            raise ValueError("known_fact_count cannot exceed required_fact_count")
        if self.completeness_percent > 100:
            raise ValueError("completeness_percent cannot exceed 100")
        for path in self.missing_fact_paths:
            _validate_text("missing fact path", path)
        if len(self.missing_fact_paths) != len(set(self.missing_fact_paths)):
            raise ValueError("missing_fact_paths must not contain duplicates")
        if len(self.missing_fact_paths) != self.required_fact_count - self.known_fact_count:
            raise ValueError("missing fact count must match required and known counts")

    @property
    def is_complete(self) -> bool:
        """Return whether every required planning fact is known."""
        return not self.missing_fact_paths


@dataclass(frozen=True, slots=True)
class ConfidenceDebtItem(SerializableTwinModel):
    """One known but insufficiently trusted planning fact."""

    fact_path: str
    confidence: float
    debt: float

    def __post_init__(self) -> None:
        _validate_text("fact_path", self.fact_path)
        _validate_confidence(self.confidence)
        _validate_confidence(self.debt)
        if abs(self.debt - (1 - self.confidence)) > 0.000001:
            raise ValueError("debt must equal one minus confidence")


@dataclass(frozen=True, slots=True)
class ConfidenceDebtReport(SerializableTwinModel):
    """Aggregate uncertainty among known planning-critical facts."""

    known_fact_count: int
    debt_points: float
    confidence_debt_percent: int
    threshold: float
    items: tuple[ConfidenceDebtItem, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.known_fact_count, bool)
            or not isinstance(self.known_fact_count, int)
            or self.known_fact_count < 0
        ):
            raise ValueError("known_fact_count must be a non-negative integer")
        _validate_finite_number("debt_points", self.debt_points, minimum=0)
        if (
            isinstance(self.confidence_debt_percent, bool)
            or not isinstance(self.confidence_debt_percent, int)
            or not 0 <= self.confidence_debt_percent <= 100
        ):
            raise ValueError("confidence_debt_percent must be between 0 and 100")
        _validate_confidence(self.threshold)
        paths = tuple(item.fact_path for item in self.items)
        if len(paths) != len(set(paths)):
            raise ValueError("confidence debt items must have unique fact paths")

    @property
    def has_review_items(self) -> bool:
        """Return whether facts fall below the selected review threshold."""
        return bool(self.items)


@dataclass(frozen=True, slots=True)
class _RequiredFact:
    path: str
    fact: LandscapeFact[Any] | None


@dataclass(frozen=True, slots=True)
class LandscapeDigitalTwin(SerializableTwinModel):
    """Canonical aggregate for one property's landscape-management state."""

    twin_id: str
    schema_version: int
    property_profile: PropertyProfile
    created_at: datetime
    updated_at: datetime
    areas: tuple[LandscapeArea, ...] = ()
    plant_groups: tuple[PlantGroup, ...] = ()
    soil_profiles: tuple[SoilProfile, ...] = ()
    irrigation_delivery_profiles: tuple[IrrigationDeliveryProfile, ...] = ()
    weather_exposure_profiles: tuple[WeatherExposureProfile, ...] = ()
    health_observations: tuple[HealthObservation, ...] = ()
    water_demand_profiles: tuple[WaterDemandProfile, ...] = ()
    goals: tuple[LandscapeGoal, ...] = ()
    controller_bindings: tuple[ControllerBinding, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("twin_id", self.twin_id)
        if self.schema_version != LANDSCAPE_TWIN_SCHEMA_VERSION:
            raise ValueError(f"unsupported landscape twin schema version: {self.schema_version}")
        _validate_timestamp("created_at", self.created_at)
        _validate_timestamp("updated_at", self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")

        area_by_id = self._unique_map("areas", self.areas, "area_id")
        plant_by_id = self._unique_map("plant_groups", self.plant_groups, "plant_group_id")
        soil_by_id = self._unique_map("soil_profiles", self.soil_profiles, "soil_profile_id")
        delivery_by_id = self._unique_map(
            "irrigation_delivery_profiles",
            self.irrigation_delivery_profiles,
            "delivery_profile_id",
        )
        exposure_by_id = self._unique_map(
            "weather_exposure_profiles",
            self.weather_exposure_profiles,
            "exposure_profile_id",
        )
        health_by_id = self._unique_map(
            "health_observations", self.health_observations, "observation_id"
        )
        demand_by_id = self._unique_map(
            "water_demand_profiles", self.water_demand_profiles, "demand_profile_id"
        )
        goal_by_id = self._unique_map("goals", self.goals, "goal_id")
        binding_by_id = self._unique_map(
            "controller_bindings", self.controller_bindings, "binding_id"
        )

        if set(self.property_profile.area_ids) != set(area_by_id):
            raise ValueError("property area_ids must exactly match aggregate areas")
        if any(area.property_id != self.property_profile.property_id for area in self.areas):
            raise ValueError("all areas must belong to the aggregate property")

        self._validate_area_references(
            area_by_id=area_by_id,
            plant_by_id=plant_by_id,
            soil_by_id=soil_by_id,
            delivery_by_id=delivery_by_id,
            exposure_by_id=exposure_by_id,
            health_by_id=health_by_id,
            demand_by_id=demand_by_id,
            goal_by_id=goal_by_id,
            binding_by_id=binding_by_id,
        )
        self._validate_reverse_area_ownership(area_by_id, plant_by_id)
        self._validate_active_bindings()
        self._validate_area_totals()

    @staticmethod
    def _unique_map(
        name: str, collection: tuple[Any, ...], identifier_field: str
    ) -> dict[str, Any]:
        identifiers = [getattr(item, identifier_field) for item in collection]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"{name} must have unique identifiers")
        return dict(zip(identifiers, collection, strict=True))

    def _validate_area_references(
        self,
        *,
        area_by_id: dict[str, LandscapeArea],
        plant_by_id: dict[str, PlantGroup],
        soil_by_id: dict[str, SoilProfile],
        delivery_by_id: dict[str, IrrigationDeliveryProfile],
        exposure_by_id: dict[str, WeatherExposureProfile],
        health_by_id: dict[str, HealthObservation],
        demand_by_id: dict[str, WaterDemandProfile],
        goal_by_id: dict[str, LandscapeGoal],
        binding_by_id: dict[str, ControllerBinding],
    ) -> None:
        """Validate every forward reference from an area."""
        for area in self.areas:
            if not set(area.plant_group_ids) <= set(plant_by_id):
                raise ValueError("area references an unknown plant group")
            if not set(area.health_observation_ids) <= set(health_by_id):
                raise ValueError("area references an unknown health observation")
            if not set(area.goal_ids) <= set(goal_by_id):
                raise ValueError("area references an unknown goal")
            if not set(area.controller_binding_ids) <= set(binding_by_id):
                raise ValueError("area references an unknown controller binding")
            for reference, values, label in (
                (area.soil_profile_id, soil_by_id, "soil profile"),
                (
                    area.irrigation_delivery_profile_id,
                    delivery_by_id,
                    "irrigation delivery profile",
                ),
                (
                    area.weather_exposure_profile_id,
                    exposure_by_id,
                    "weather exposure profile",
                ),
                (area.water_demand_profile_id, demand_by_id, "water demand profile"),
            ):
                if reference is not None and reference not in values:
                    raise ValueError(f"area references an unknown {label}")

            percent_total = sum(
                plant_by_id[plant_id].quantity.value or 0
                for plant_id in area.plant_group_ids
                if plant_by_id[plant_id].quantity_mode is PlantQuantityMode.PERCENTAGE
            )
            if percent_total > 100:
                raise ValueError("percentage-based plant groups cannot total more than 100")

        del area_by_id

    def _validate_reverse_area_ownership(
        self,
        area_by_id: dict[str, LandscapeArea],
        plant_by_id: dict[str, PlantGroup],
    ) -> None:
        """Reject orphaned records and cross-area references."""
        ownership_collections: tuple[tuple[str, tuple[Any, ...]], ...] = (
            ("plant group", self.plant_groups),
            ("soil profile", self.soil_profiles),
            ("irrigation delivery profile", self.irrigation_delivery_profiles),
            ("weather exposure profile", self.weather_exposure_profiles),
            ("health observation", self.health_observations),
            ("water demand profile", self.water_demand_profiles),
            ("goal", self.goals),
            ("controller binding", self.controller_bindings),
        )
        for label, collection in ownership_collections:
            for item in collection:
                if item.area_id not in area_by_id:
                    raise ValueError(f"{label} references an unknown area")

        for area in self.areas:
            expected = {
                "plant_group_ids": {
                    item.plant_group_id
                    for item in self.plant_groups
                    if item.area_id == area.area_id
                },
                "health_observation_ids": {
                    item.observation_id
                    for item in self.health_observations
                    if item.area_id == area.area_id
                },
                "goal_ids": {item.goal_id for item in self.goals if item.area_id == area.area_id},
                "controller_binding_ids": {
                    item.binding_id
                    for item in self.controller_bindings
                    if item.area_id == area.area_id
                },
            }
            for field_name, expected_ids in expected.items():
                if set(getattr(area, field_name)) != expected_ids:
                    raise ValueError(
                        f"area {field_name} must exactly match aggregate-owned records"
                    )

            for reference, collection, id_field, label in (
                (area.soil_profile_id, self.soil_profiles, "soil_profile_id", "soil profile"),
                (
                    area.irrigation_delivery_profile_id,
                    self.irrigation_delivery_profiles,
                    "delivery_profile_id",
                    "irrigation delivery profile",
                ),
                (
                    area.weather_exposure_profile_id,
                    self.weather_exposure_profiles,
                    "exposure_profile_id",
                    "weather exposure profile",
                ),
                (
                    area.water_demand_profile_id,
                    self.water_demand_profiles,
                    "demand_profile_id",
                    "water demand profile",
                ),
            ):
                owned = [item for item in collection if item.area_id == area.area_id]
                expected_reference = getattr(owned[0], id_field) if owned else None
                if len(owned) > 1:
                    raise ValueError(f"an area may have only one {label}")
                if reference != expected_reference:
                    raise ValueError(f"area {label} reference must match its owned profile")

        for observation in self.health_observations:
            if observation.plant_group_id is not None:
                plant = plant_by_id.get(observation.plant_group_id)
                if plant is None:
                    raise ValueError("health observation references an unknown plant group")
                if plant.area_id != observation.area_id:
                    raise ValueError("health observation plant group must belong to its area")

    def _validate_active_bindings(self) -> None:
        active = [
            binding
            for binding in self.controller_bindings
            if binding.status is BindingStatus.ACTIVE
        ]
        area_ids = [binding.area_id for binding in active]
        if len(area_ids) != len(set(area_ids)):
            raise ValueError("an area may have only one active controller binding")
        slots = [(binding.controller_id, binding.slot_number) for binding in active]
        if len(slots) != len(set(slots)):
            raise ValueError("a controller slot may bind to only one active landscape area")

    def _validate_area_totals(self) -> None:
        property_total = self.property_profile.total_landscape_area_square_meters.value
        active_area_values = [
            area.area_square_meters.value
            for area in self.areas
            if area.active and area.area_square_meters.value is not None
        ]
        if (
            property_total is not None
            and len(active_area_values) == sum(area.active for area in self.areas)
            and sum(active_area_values) > property_total
        ):
            raise ValueError("active landscape area total cannot exceed property landscape area")

    def get_area(self, area_id: str) -> LandscapeArea:
        """Return an area by stable canonical identity."""
        for area in self.areas:
            if area.area_id == area_id:
                return area
        raise KeyError(f"unknown landscape area: {area_id}")

    def _required_facts(self) -> tuple[_RequiredFact, ...]:
        """Return the versioned planning-readiness fact set."""
        required = [
            _RequiredFact(
                "property.total_landscape_area_square_meters",
                self.property_profile.total_landscape_area_square_meters,
            ),
            _RequiredFact("property.climate_zone", self.property_profile.climate_zone),
        ]
        plants_by_area = {
            area.area_id: tuple(
                plant for plant in self.plant_groups if plant.area_id == area.area_id
            )
            for area in self.areas
        }
        soils = {profile.area_id: profile for profile in self.soil_profiles}
        deliveries = {
            profile.area_id: profile for profile in self.irrigation_delivery_profiles
        }
        exposures = {
            profile.area_id: profile for profile in self.weather_exposure_profiles
        }
        demands = {profile.area_id: profile for profile in self.water_demand_profiles}
        goals_by_area = {
            area.area_id: tuple(
                goal for goal in self.goals if goal.area_id == area.area_id and goal.active
            )
            for area in self.areas
        }
        for area in self.areas:
            if not area.active:
                continue
            prefix = f"areas.{area.area_id}"
            required.extend(
                (
                    _RequiredFact(f"{prefix}.area_square_meters", area.area_square_meters),
                    _RequiredFact(f"{prefix}.slope_percent", area.slope_percent),
                )
            )
            plants = plants_by_area[area.area_id]
            if not plants:
                required.extend(
                    _RequiredFact(f"{prefix}.plant_groups.{field_name}", None)
                    for field_name in (
                        "category",
                        "quantity",
                        "establishment_stage",
                        "root_depth_meters",
                    )
                )
            for plant in plants:
                plant_prefix = f"{prefix}.plant_groups.{plant.plant_group_id}"
                required.extend(
                    (
                        _RequiredFact(f"{plant_prefix}.category", plant.category),
                        _RequiredFact(f"{plant_prefix}.quantity", plant.quantity),
                        _RequiredFact(
                            f"{plant_prefix}.establishment_stage",
                            plant.establishment_stage,
                        ),
                        _RequiredFact(
                            f"{plant_prefix}.root_depth_meters",
                            plant.root_depth_meters,
                        ),
                    )
                )
            soil = soils.get(area.area_id)
            required.extend(
                (
                    _RequiredFact(f"{prefix}.soil.texture", soil.texture if soil else None),
                    _RequiredFact(
                        f"{prefix}.soil.infiltration_rate_mm_per_hour",
                        soil.infiltration_rate_mm_per_hour if soil else None,
                    ),
                    _RequiredFact(
                        f"{prefix}.soil.available_water_capacity_mm_per_meter",
                        soil.available_water_capacity_mm_per_meter if soil else None,
                    ),
                )
            )
            delivery = deliveries.get(area.area_id)
            required.extend(
                (
                    _RequiredFact(
                        f"{prefix}.irrigation_delivery.method",
                        delivery.method if delivery else None,
                    ),
                    _RequiredFact(
                        f"{prefix}.irrigation_delivery.application_rate_mm_per_hour",
                        delivery.application_rate_mm_per_hour if delivery else None,
                    ),
                    _RequiredFact(
                        f"{prefix}.irrigation_delivery.distribution_efficiency",
                        delivery.distribution_efficiency if delivery else None,
                    ),
                )
            )
            exposure = exposures.get(area.area_id)
            required.extend(
                (
                    _RequiredFact(
                        f"{prefix}.weather_exposure.sun_exposure",
                        exposure.sun_exposure if exposure else None,
                    ),
                    _RequiredFact(
                        f"{prefix}.weather_exposure.wind_exposure",
                        exposure.wind_exposure if exposure else None,
                    ),
                    _RequiredFact(
                        f"{prefix}.weather_exposure.heat_exposure",
                        exposure.heat_exposure if exposure else None,
                    ),
                )
            )
            demand = demands.get(area.area_id)
            required.extend(
                (
                    _RequiredFact(
                        f"{prefix}.water_demand.basis", demand.basis if demand else None
                    ),
                    _RequiredFact(
                        f"{prefix}.water_demand.crop_coefficient",
                        demand.crop_coefficient if demand else None,
                    ),
                    _RequiredFact(
                        f"{prefix}.water_demand.peak_daily_demand_mm",
                        demand.peak_daily_demand_mm if demand else None,
                    ),
                )
            )
            goals = goals_by_area[area.area_id]
            if goals:
                required.extend(
                    _RequiredFact(f"{prefix}.goals.{goal.goal_id}.target", goal.target)
                    for goal in goals
                )
            else:
                required.append(_RequiredFact(f"{prefix}.goals.active_target", None))
        return tuple(required)

    @property
    def completeness(self) -> CompletenessReport:
        """Calculate completeness from versioned planning-critical facts."""
        required = self._required_facts()
        missing = tuple(
            item.path for item in required if item.fact is None or not item.fact.is_known
        )
        total = len(required)
        known = total - len(missing)
        percent = round(known / total * 100) if total else 100
        return CompletenessReport(
            required_fact_count=total,
            known_fact_count=known,
            completeness_percent=percent,
            missing_fact_paths=missing,
        )

    @property
    def completeness_percent(self) -> int:
        """Return the planning completeness percentage."""
        return self.completeness.completeness_percent

    @property
    def is_complete(self) -> bool:
        """Return whether every required planning fact is known."""
        return self.completeness.is_complete

    def calculate_confidence_debt(self, *, threshold: float = 0.8) -> ConfidenceDebtReport:
        """Calculate uncertainty among known planning facts, excluding missing facts."""
        _validate_confidence(threshold)
        known = tuple(
            item
            for item in self._required_facts()
            if item.fact is not None and item.fact.is_known
        )
        items = tuple(
            ConfidenceDebtItem(
                fact_path=item.path,
                confidence=item.fact.effective_confidence,
                debt=round(1 - item.fact.effective_confidence, 6),
            )
            for item in known
            if item.fact is not None and item.fact.effective_confidence < threshold
        )
        debt_points = round(
            sum(1 - item.fact.effective_confidence for item in known if item.fact is not None),
            6,
        )
        percent = round(debt_points / len(known) * 100) if known else 0
        return ConfidenceDebtReport(
            known_fact_count=len(known),
            debt_points=debt_points,
            confidence_debt_percent=percent,
            threshold=threshold,
            items=items,
        )

    @property
    def confidence_debt(self) -> ConfidenceDebtReport:
        """Return confidence debt using the default 0.8 review threshold."""
        return self.calculate_confidence_debt()

    @property
    def confidence_debt_percent(self) -> int:
        """Return average confidence deficit among known required facts."""
        return self.confidence_debt.confidence_debt_percent
