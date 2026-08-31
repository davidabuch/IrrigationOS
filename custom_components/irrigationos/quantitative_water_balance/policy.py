"""Versioned conservative baseline water-budget policy data."""

from __future__ import annotations

from ..landscape import EstablishmentStage, PlantType, SoilTexture
from .models import EffectivePrecipitationPolicy, RatioQuantity, WaterQuantity

BASELINE_WATER_BUDGET_POLICY_VERSION = "1.0.0"

# Conservative planning ranges in millimetres of plant-available water per metre
# of soil. They are generic texture-class policy values, not site measurements.
_SOIL_AVAILABLE_WATER_MM_PER_M: dict[SoilTexture, tuple[float, float, float]] = {
    SoilTexture.SAND: (50.0, 75.0, 100.0),
    SoilTexture.SANDY_LOAM: (90.0, 115.0, 140.0),
    SoilTexture.LOAM: (130.0, 165.0, 200.0),
    SoilTexture.SILT_LOAM: (160.0, 195.0, 230.0),
    SoilTexture.CLAY_LOAM: (140.0, 175.0, 210.0),
    SoilTexture.CLAY: (120.0, 160.0, 200.0),
    SoilTexture.AMENDED: (100.0, 150.0, 200.0),
    SoilTexture.CONTAINER: (80.0, 120.0, 160.0),
}

# Provider-neutral landscape-class factors. Curated admitted species evidence has
# precedence; these deliberately broad ranges retain lower-confidence uncertainty.
_GENERIC_DEMAND_FACTORS: dict[PlantType, tuple[float, float, float]] = {
    PlantType.TURF_COOL_SEASON: (0.70, 0.80, 0.90),
    PlantType.TURF_WARM_SEASON: (0.55, 0.65, 0.75),
    PlantType.TREE: (0.40, 0.55, 0.70),
    PlantType.SHRUB: (0.30, 0.45, 0.60),
    PlantType.HEDGE: (0.40, 0.55, 0.70),
    PlantType.SUCCULENT: (0.15, 0.225, 0.30),
    PlantType.VEGETABLE: (0.80, 0.95, 1.10),
    PlantType.FLOWER: (0.50, 0.65, 0.80),
    PlantType.MIXED: (0.40, 0.60, 0.80),
}

_ESTABLISHED_DEPLETION: dict[PlantType, float] = {
    PlantType.TURF_COOL_SEASON: 0.40,
    PlantType.TURF_WARM_SEASON: 0.45,
    PlantType.TREE: 0.50,
    PlantType.SHRUB: 0.50,
    PlantType.HEDGE: 0.45,
    PlantType.SUCCULENT: 0.55,
    PlantType.VEGETABLE: 0.35,
    PlantType.FLOWER: 0.35,
    PlantType.MIXED: 0.40,
}

PRODUCTION_EFFECTIVE_PRECIPITATION_POLICY = EffectivePrecipitationPolicy(
    policy_id="water.effective.baseline_v1",
    effective_fraction=0.65,
    confidence=0.60,
    rationale_code="conservative_generic_site_retention",
)


def generic_demand_factor(plant_type: PlantType) -> RatioQuantity | None:
    """Return a bounded generic factor, or fail closed for unsupported classes."""

    values = _GENERIC_DEMAND_FACTORS.get(plant_type)
    if values is None:
        return None
    return RatioQuantity(minimum=values[0], typical=values[1], maximum=values[2])


def root_zone_reservoir(
    soil_texture: SoilTexture, root_depth_inches: float | None
) -> WaterQuantity | None:
    """Resolve root-zone available water from explicit soil and root-depth facts."""

    values = _SOIL_AVAILABLE_WATER_MM_PER_M.get(soil_texture)
    if values is None or root_depth_inches is None or root_depth_inches <= 0:
        return None
    depth_m = root_depth_inches * 0.0254
    return WaterQuantity(
        minimum=round(values[0] * depth_m, 6),
        typical=round(values[1] * depth_m, 6),
        maximum=round(values[2] * depth_m, 6),
    )


def allowable_depletion_fraction(
    plant_type: PlantType, establishment_stage: EstablishmentStage
) -> RatioQuantity | None:
    """Return the management depletion fraction for class and establishment."""

    established = _ESTABLISHED_DEPLETION.get(plant_type)
    if established is None:
        return None
    if establishment_stage is EstablishmentStage.NEWLY_PLANTED:
        return RatioQuantity(scalar=min(established, 0.20))
    if establishment_stage is EstablishmentStage.ESTABLISHING:
        return RatioQuantity(scalar=min(established, 0.30))
    if establishment_stage is EstablishmentStage.ESTABLISHED:
        return RatioQuantity(scalar=established)
    return None
