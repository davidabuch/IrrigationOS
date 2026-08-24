"""Human-reviewed Zone 1 commissioning seed for v1.0.49."""

from __future__ import annotations

from datetime import datetime

from .commissioning import (
    ZONE_COMMISSIONING_SCHEMA_VERSION,
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    CommissioningEvidenceSource,
    DeliveryLinkStatus,
    IrrigationDeliveryLink,
    PlantCommissioningDetails,
    ZoneDemandSource,
    ZoneDemandSourceMode,
)
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


def _build_zone_1_landscape_intelligence(
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


def build_zone_1_commissioning_profile(
    observed_at: datetime,
) -> CommissionedZoneProfile:
    """Return Zone 1 through the generic commissioning contract."""
    landscape_profile = _build_zone_1_landscape_intelligence(observed_at)
    group_ids = tuple(group.plant_group_id for group in landscape_profile.plant_groups)
    details = tuple(
        PlantCommissioningDetails(
            plant_group_id=group.plant_group_id,
            source=CommissioningEvidenceSource.USER_CONFIRMED,
            confidence=group.identification_confidence,
            observed_at=observed_at,
        )
        for group in landscape_profile.plant_groups
    )
    links = tuple(
        IrrigationDeliveryLink(
            link_id=f"zone1.delivery.{group.plant_group_id}",
            plant_group_id=group.plant_group_id,
            status=DeliveryLinkStatus.DOCUMENTED,
            delivery_profile_id="zone1.delivery.microjet",
            component_ids=(f"zone1.component.{group.plant_group_id}",),
            dedicated_delivery=group.dedicated_emitter,
        )
        for group in landscape_profile.plant_groups
        if group.irrigation_role is not IrrigationRole.INCIDENTAL
    )
    return CommissionedZoneProfile(
        schema_version=ZONE_COMMISSIONING_SCHEMA_VERSION,
        identity=CanonicalZoneIdentity("property.primary", "zone.1", 1, 1),
        display_name="Zone 1",
        landscape_profile=landscape_profile,
        plant_details=details,
        demand_sources=(
            ZoneDemandSource(
                "zone1.source.manual",
                ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
                plant_group_ids=group_ids,
            ),
        ),
        delivery_links=links,
    )


def build_zone_1_landscape_intelligence(
    observed_at: datetime,
) -> LandscapeIntelligenceProfile:
    """Return the backward-compatible Zone 1 profile fixture."""
    return build_zone_1_commissioning_profile(
        observed_at
    ).to_landscape_intelligence_profile()
