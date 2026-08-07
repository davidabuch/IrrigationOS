"""Canonical Landscape Digital Twin models for IrrigationOS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProfileValueSource(StrEnum):
    """Source of a Landscape Digital Twin value."""

    CONTROLLER = "controller"
    USER = "user"
    DEFAULT = "default"
    DERIVED = "derived"
    USDA = "usda"
    UNKNOWN = "unknown"


class EstablishmentStage(StrEnum):
    """Canonical establishment stage for a landscape planting."""

    NEWLY_PLANTED = "newly_planted"
    ESTABLISHING = "establishing"
    ESTABLISHED = "established"
    UNKNOWN = "unknown"


class PlantType(StrEnum):
    """Canonical plant categories used by IrrigationOS."""

    TURF_COOL_SEASON = "turf_cool_season"
    TURF_WARM_SEASON = "turf_warm_season"
    TREE = "tree"
    SHRUB = "shrub"
    HEDGE = "hedge"
    SUCCULENT = "succulent"
    VEGETABLE = "vegetable"
    FLOWER = "flower"
    MIXED = "mixed"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class IrrigationMethod(StrEnum):
    """Canonical irrigation delivery methods."""

    SPRAY = "spray"
    ROTOR = "rotor"
    DRIP = "drip"
    BUBBLER = "bubbler"
    MICRO_SPRAY = "micro_spray"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class SunExposure(StrEnum):
    """Canonical sun-exposure classes."""

    FULL_SUN = "full_sun"
    MOSTLY_SUN = "mostly_sun"
    PART_SUN = "part_sun"
    MOSTLY_SHADE = "mostly_shade"
    FULL_SHADE = "full_shade"
    UNKNOWN = "unknown"


class SoilTexture(StrEnum):
    """Operational soil-texture classes."""

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


@dataclass(frozen=True, slots=True)
class ProfileValue[T]:
    """A value plus its provenance and confidence."""

    value: T
    source: ProfileValueSource
    confidence_percent: int

    def __post_init__(self) -> None:
        if not 0 <= self.confidence_percent <= 100:
            raise ValueError("confidence_percent must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class IrrigationAreaProfile:
    """Landscape Digital Twin profile for one irrigation area."""

    area_id: str
    display_name: ProfileValue[str]
    plant_type: ProfileValue[PlantType]
    plant_description: ProfileValue[str | None]
    irrigation_method: ProfileValue[IrrigationMethod]
    sun_exposure: ProfileValue[SunExposure]
    slope_percent: ProfileValue[float | None]
    soil_texture: ProfileValue[SoilTexture]
    soil_description: ProfileValue[str | None]
    root_depth_inches: ProfileValue[float | None]
    application_rate_inches_per_hour: ProfileValue[float | None]
    distribution_efficiency: ProfileValue[float | None]
    establishment_stage: ProfileValue[EstablishmentStage] = ProfileValue(
        EstablishmentStage.UNKNOWN, ProfileValueSource.UNKNOWN, 0
    )

    @property
    def is_complete(self) -> bool:
        """Return whether the minimum planning fields are known."""
        return all(
            (
                self.plant_type.value is not PlantType.UNKNOWN,
                self.irrigation_method.value is not IrrigationMethod.UNKNOWN,
                self.sun_exposure.value is not SunExposure.UNKNOWN,
                self.soil_texture.value is not SoilTexture.UNKNOWN,
                self.root_depth_inches.value is not None,
                self.application_rate_inches_per_hour.value is not None,
                self.distribution_efficiency.value is not None,
            )
        )

    @property
    def completion_percent(self) -> int:
        """Return completion across the minimum planning fields."""
        checks = (
            self.plant_type.value is not PlantType.UNKNOWN,
            self.irrigation_method.value is not IrrigationMethod.UNKNOWN,
            self.sun_exposure.value is not SunExposure.UNKNOWN,
            self.slope_percent.value is not None,
            self.soil_texture.value is not SoilTexture.UNKNOWN,
            self.root_depth_inches.value is not None,
            self.application_rate_inches_per_hour.value is not None,
            self.distribution_efficiency.value is not None,
        )
        return round(sum(checks) / len(checks) * 100)


@dataclass(frozen=True, slots=True)
class LandscapeProfile:
    """Canonical Landscape Digital Twin for an installation."""

    schema_version: int
    areas: tuple[IrrigationAreaProfile, ...]

    def get_area(self, area_id: str) -> IrrigationAreaProfile:
        """Return a profile by canonical area ID."""
        for profile in self.areas:
            if profile.area_id == area_id:
                return profile
        raise KeyError(f"Unknown irrigation area profile: {area_id}")

    @property
    def complete_area_count(self) -> int:
        """Return the number of complete area profiles."""
        return sum(profile.is_complete for profile in self.areas)
