"""Canonical Landscape Intelligence Profile contracts."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

LANDSCAPE_INTELLIGENCE_SCHEMA_VERSION = 1


class IrrigationRole(StrEnum):
    """Relationship between a plant group and zone irrigation."""

    PRIMARY_TARGET = "primary_target"
    SECONDARY_TARGET = "secondary_target"
    INCIDENTAL = "incidental"


class EstablishmentState(StrEnum):
    """Canonical establishment vocabulary."""

    NEWLY_PLANTED = "newly_planted"
    ESTABLISHING = "establishing"
    ESTABLISHED = "established"
    ESTABLISHED_OR_UNKNOWN = "established_or_unknown"
    UNKNOWN = "unknown"


class HealthState(StrEnum):
    """Directly observed plant-condition state, independent of diagnosis."""

    HEALTHY = "healthy"
    MILDLY_STRESSED = "mildly_stressed"
    STRESSED = "stressed"
    SEVERELY_STRESSED = "severely_stressed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


class HealthTrend(StrEnum):
    """Derived longitudinal condition trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"
    INSUFFICIENT_HISTORY = "insufficient_history"


class ObservationSource(StrEnum):
    """Permitted structured observation sources."""

    HUMAN_REVIEWED_PHOTO = "human_reviewed_photo"
    HUMAN_DIRECT = "human_direct"
    SENSOR = "sensor"


class Confidence(StrEnum):
    """Qualitative evidence confidence."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class HydrozoneType(StrEnum):
    """Landscape composition of one controllable irrigation zone."""

    UNIFORM = "uniform"
    MIXED = "mixed"
    UNRESOLVED = "unresolved"


class HydrozoneQuality(StrEnum):
    """Compatibility of plant groups sharing a controllable zone."""

    UNRESOLVED = "unresolved"
    COMPATIBLE = "compatible"
    MIXED_COMPATIBLE = "mixed_compatible"
    MIXED_WITH_EXCEPTIONS = "mixed_with_exceptions"
    POOR = "poor"


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"unsupported landscape intelligence type: {type(value).__name__}")


class Serializable:
    """Deterministic plain-data serialization mixin."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        result = _serialize(self)
        if not isinstance(result, dict):  # pragma: no cover
            raise TypeError("model did not serialize to dict")
        return result


@dataclass(frozen=True, slots=True)
class PlantGroup(Serializable):
    """One functionally meaningful plant group within a zone."""

    plant_group_id: str
    common_name: str
    botanical_name: str | None
    identification_confidence: Confidence
    irrigation_role: IrrigationRole
    establishment_state: EstablishmentState
    direct_irrigation: bool
    dedicated_emitter: bool
    emitter_type: str | None = None
    approximate_age_years: str | None = None
    emitter_relationship: str | None = None
    expected_water_use_class: str | None = None
    scientific_source: str | None = None
    controls_zone_demand: bool | None = None

    def __post_init__(self) -> None:
        if not self.plant_group_id.strip() or not self.common_name.strip():
            raise ValueError("plant identity is required")
        if self.irrigation_role is IrrigationRole.INCIDENTAL and self.controls_zone_demand is True:
            raise ValueError("incidental plants cannot control zone demand")
        if not self.direct_irrigation and self.dedicated_emitter:
            raise ValueError("dedicated emitter requires direct irrigation")


@dataclass(frozen=True, slots=True)
class PlantHealthObservation(Serializable):
    """Immutable structured finding from one plant-health observation."""

    observation_id: str
    plant_group_id: str
    observed_at: datetime
    source: ObservationSource
    confidence: Confidence
    overall_state: HealthState
    findings: tuple[str, ...]
    direct_irrigation: bool
    visible_coverage_problem: bool | None
    application_adequacy: str
    suspected_water_stress: str
    diagnosis: str
    automatic_runtime_adjustment: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.observation_id.strip() or not self.plant_group_id.strip():
            raise ValueError("observation identity is required")
        if self.automatic_runtime_adjustment:
            raise ValueError("health observations cannot authorize runtime adjustment")
        if len(self.findings) != len(set(self.findings)):
            raise ValueError("findings must not contain duplicates")


@dataclass(frozen=True, slots=True)
class PlantHealthSummary(Serializable):
    """Derived longitudinal summary for one plant group."""

    plant_group_id: str
    latest_state: HealthState
    trend: HealthTrend
    trend_confidence: Confidence | None
    observation_count: int


@dataclass(frozen=True, slots=True)
class LandscapeIntelligenceProfile(Serializable):
    """Advisory landscape intelligence for one irrigation zone."""

    schema_version: int
    area_slot: int
    profile_status: str
    hydrozone_type: HydrozoneType
    hydrozone_quality: HydrozoneQuality
    irrigation_method: str
    emitter_family: str
    predominant_radius_ft: float | None
    predominant_emitter_color: str | None
    application_rate_status: str
    plant_groups: tuple[PlantGroup, ...]
    health_observations: tuple[PlantHealthObservation, ...]
    plant_factor_status: str = "unresolved"
    landscape_factor_status: str = "unresolved"
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != LANDSCAPE_INTELLIGENCE_SCHEMA_VERSION:
            raise ValueError("unsupported landscape intelligence schema version")
        group_ids = [plant.plant_group_id for plant in self.plant_groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("plant_group_id must be unique")
        known_groups = set(group_ids)
        observation_ids: set[str] = set()
        previous: dict[str, datetime] = {}
        for observation in self.health_observations:
            if observation.plant_group_id not in known_groups:
                raise ValueError("health observation references unknown plant group")
            if observation.observation_id in observation_ids:
                raise ValueError("observation_id must be unique")
            observation_ids.add(observation.observation_id)
            prior = previous.get(observation.plant_group_id)
            if prior is not None and observation.observed_at < prior:
                raise ValueError("health observations must be chronological per plant group")
            previous[observation.plant_group_id] = observation.observed_at
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("landscape intelligence is advisory only")


_SEVERITY = {
    HealthState.HEALTHY: 0,
    HealthState.RECOVERING: 1,
    HealthState.MILDLY_STRESSED: 1,
    HealthState.STRESSED: 2,
    HealthState.SEVERELY_STRESSED: 3,
    HealthState.UNKNOWN: None,
}


def summarize_health(
    profile: LandscapeIntelligenceProfile, plant_group_id: str
) -> PlantHealthSummary:
    """Derive a conservative trend from immutable observations."""
    observations = [
        observation
        for observation in profile.health_observations
        if observation.plant_group_id == plant_group_id
    ]
    if not observations:
        return PlantHealthSummary(
            plant_group_id, HealthState.UNKNOWN, HealthTrend.INSUFFICIENT_HISTORY, None, 0
        )
    latest = observations[-1]
    if len(observations) < 2:
        return PlantHealthSummary(
            plant_group_id,
            latest.overall_state,
            HealthTrend.INSUFFICIENT_HISTORY,
            None,
            1,
        )
    previous_severity = _SEVERITY[observations[-2].overall_state]
    latest_severity = _SEVERITY[latest.overall_state]
    if previous_severity is None or latest_severity is None:
        trend = HealthTrend.INSUFFICIENT_HISTORY
    elif latest_severity < previous_severity:
        trend = HealthTrend.IMPROVING
    elif latest_severity > previous_severity:
        trend = HealthTrend.WORSENING
    else:
        trend = HealthTrend.STABLE
    confidence = Confidence.LOW if len(observations) == 2 else Confidence.MODERATE
    return PlantHealthSummary(
        plant_group_id, latest.overall_state, trend, confidence, len(observations)
    )
