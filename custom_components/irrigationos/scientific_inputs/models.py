"""Immutable scientific-input contracts for Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..plant_knowledge import PlantKnowledgeResolution


class ScientificInputStatus(StrEnum):
    """Overall readiness of normalized scientific inputs."""

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class Hemisphere(StrEnum):
    """Hemisphere derived from Home Assistant location without retaining coordinates."""

    NORTHERN = "northern"
    SOUTHERN = "southern"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RegionalContextInput:
    """Privacy-preserving location context for scientific applicability."""

    country_code: str | None
    hemisphere: Hemisphere
    elevation_meters: float | None


@dataclass(frozen=True, slots=True)
class WeatherInputSnapshot:
    """Normalized current conditions from one Home Assistant weather entity."""

    entity_id: str
    observed_at: datetime
    condition: str | None
    temperature_celsius: float | None
    relative_humidity_percent: float | None
    pressure_hpa: float | None
    wind_speed_meters_per_second: float | None
    wind_bearing_degrees: float | None
    attribution: str | None
    known_fact_count: int

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("weather observed_at must be timezone-aware")
        if self.known_fact_count < 0:
            raise ValueError("known_fact_count must not be negative")


@dataclass(frozen=True, slots=True)
class AreaKnowledgeInput:
    """Plant-knowledge resolution for one landscape area."""

    area_id: str
    requested_identity: str
    selected_profile_id: str | None
    resolution_confidence: float
    blocker_codes: tuple[str, ...] = ()
    knowledge_resolution: PlantKnowledgeResolution | None = None


@dataclass(frozen=True, slots=True)
class ScientificInputSnapshot:
    """One immutable scientific-input snapshot for a coordinator refresh."""

    evaluated_at: datetime
    status: ScientificInputStatus
    weather: WeatherInputSnapshot | None
    area_knowledge: tuple[AreaKnowledgeInput, ...]
    blocker_codes: tuple[str, ...]
    regional_context: RegionalContextInput = RegionalContextInput(
        country_code=None,
        hemisphere=Hemisphere.UNKNOWN,
        elevation_meters=None,
    )

    @property
    def resolved_area_count(self) -> int:
        """Return the number of areas with selected knowledge profiles."""
        return sum(item.selected_profile_id is not None for item in self.area_knowledge)
