"""Immutable scientific-input contracts for Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ScientificInputStatus(StrEnum):
    """Overall readiness of normalized scientific inputs."""

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


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


@dataclass(frozen=True, slots=True)
class AreaKnowledgeInput:
    """Plant-knowledge resolution for one landscape area."""

    area_id: str
    requested_identity: str
    selected_profile_id: str | None
    resolution_confidence: float
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScientificInputSnapshot:
    """One immutable scientific-input snapshot for a coordinator refresh."""

    evaluated_at: datetime
    status: ScientificInputStatus
    weather: WeatherInputSnapshot | None
    area_knowledge: tuple[AreaKnowledgeInput, ...]
    blocker_codes: tuple[str, ...]

    @property
    def resolved_area_count(self) -> int:
        """Return the number of areas with selected knowledge profiles."""
        return sum(item.selected_profile_id is not None for item in self.area_knowledge)
