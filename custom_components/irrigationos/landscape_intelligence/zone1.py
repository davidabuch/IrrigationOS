"""Human-reviewed Zone 1 commissioning seed for v1.0.49."""

from __future__ import annotations

from datetime import datetime

from .models import (
    Confidence,
    EstablishmentState,
    HealthState,
    HydrozoneQuality,
    HydrozoneType,
    IrrigationRole,
    LandscapeIntelligenceProfile,
    ObservationSource,
    PlantGroup,
    PlantHealthObservation,
)


def build_zone_1_landscape_intelligence(
    observed_at: datetime,
) -> LandscapeIntelligenceProfile:
    """Return the advisory Zone 1 profile agreed during commissioning."""
    groups = (
        PlantGroup(
            "mature_palms", "Mature palms", None, Confidence.HIGH,
            IrrigationRole.INCIDENTAL, EstablishmentState.ESTABLISHED, False, False,
            controls_zone_demand=False,
        ),
        PlantGroup(
            "fig", "Fig", "Ficus carica", Confidence.HIGH,
            IrrigationRole.PRIMARY_TARGET, EstablishmentState.ESTABLISHED, True, True,
            "microjet", "about_3", controls_zone_demand=None,
        ),
        PlantGroup(
            "citrus", "Citrus", "Citrus spp.", Confidence.HIGH,
            IrrigationRole.PRIMARY_TARGET, EstablishmentState.ESTABLISHING, True, True,
            "microjet", "about_1_to_2", controls_zone_demand=None,
        ),
        PlantGroup(
            "passion_fruit", "Passion fruit", "Passiflora edulis", Confidence.HIGH,
            IrrigationRole.PRIMARY_TARGET, EstablishmentState.ESTABLISHED_OR_UNKNOWN,
            True, True, "microjet", controls_zone_demand=None,
        ),
        PlantGroup(
            "podocarpus", "Podocarpus", "Podocarpus spp.", Confidence.HIGH,
            IrrigationRole.PRIMARY_TARGET, EstablishmentState.ESTABLISHED, True, False,
            "two_sided_microjet",
            emitter_relationship="one_two_sided_microjet_serves_two_trees",
            controls_zone_demand=None,
        ),
        PlantGroup(
            "peruvian_lilies", "Peruvian lilies", "Alstroemeria spp.", Confidence.HIGH,
            IrrigationRole.PRIMARY_TARGET, EstablishmentState.ESTABLISHED_OR_UNKNOWN,
            True, True, "microjet", controls_zone_demand=None,
        ),
        PlantGroup(
            "drought_tolerant_ornamentals", "Drought-tolerant ornamentals", None,
            Confidence.MODERATE, IrrigationRole.SECONDARY_TARGET,
            EstablishmentState.ESTABLISHED, True, False, "microjet",
            controls_zone_demand=None,
        ),
    )
    observation = PlantHealthObservation(
        "zone1-peruvian-lilies-initial",
        "peruvian_lilies",
        observed_at,
        ObservationSource.HUMAN_REVIEWED_PHOTO,
        Confidence.MODERATE,
        HealthState.STRESSED,
        ("browning_or_dieback", "reduced_vigor", "sparse_foliage"),
        True,
        False,
        "unresolved",
        "possible",
        "unresolved",
        False,
    )
    return LandscapeIntelligenceProfile(
        1, 1, "commissioned", HydrozoneType.MIXED,
        HydrozoneQuality.MIXED_WITH_EXCEPTIONS, "micro_spray", "microjet",
        3.0, "blue", "unresolved", groups, (observation,),
    )
