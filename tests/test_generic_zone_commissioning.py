from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import load_integration_module

C = load_integration_module("landscape_intelligence.commissioning")
M = load_integration_module("landscape_intelligence.models")
Z = load_integration_module("landscape_intelligence.zone1")

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _plant(
    group_id: str,
    common_name: str,
    botanical_name: str | None,
    establishment: object,
) -> object:
    return M.PlantGroup(
        group_id,
        common_name,
        botanical_name,
        M.Confidence.HIGH,
        M.IrrigationRole.PRIMARY_TARGET,
        establishment,
        True,
        False,
        controls_zone_demand=None,
    )


def _landscape(area_slot: int, groups: tuple[object, ...]) -> object:
    return M.LandscapeIntelligenceProfile(
        M.LANDSCAPE_INTELLIGENCE_SCHEMA_VERSION,
        area_slot,
        "commissioned",
        M.HydrozoneType.UNIFORM,
        M.HydrozoneQuality.UNRESOLVED,
        "unresolved",
        "unresolved",
        None,
        None,
        "unresolved",
        groups,
        (),
    )


def _details(group_id: str, **kwargs: object) -> object:
    return C.PlantCommissioningDetails(
        group_id,
        C.CommissioningEvidenceSource.USER_CONFIRMED,
        M.Confidence.HIGH,
        NOW,
        **kwargs,
    )


def test_zone1_uses_generic_commissioning_without_behavior_change() -> None:
    commissioned = Z.build_zone_1_commissioning_profile(NOW)
    legacy = Z.build_zone_1_landscape_intelligence(NOW)

    assert commissioned.identity.controller_slot == 1
    assert commissioned.identity.area_slot == 1
    assert commissioned.demand_sources[0].mode is C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE
    assert commissioned.to_landscape_intelligence_profile() == legacy
    assert {group.plant_group_id for group in legacy.plant_groups} == {
        "mature_palms",
        "fig",
        "citrus",
        "passion_fruit",
        "podocarpus",
        "peruvian_lilies",
        "drought_tolerant_ornamentals",
    }
    assert commissioned.execution_authorized is False
    assert commissioned.live_control_authorized is False


def test_manual_podocarpus_zone_is_provider_independent() -> None:
    podocarpus = _plant(
        "podocarpus",
        "Podocarpus",
        "Podocarpus spp.",
        M.EstablishmentState.ESTABLISHING,
    )
    profile = C.CommissionedZoneProfile(
        C.ZONE_COMMISSIONING_SCHEMA_VERSION,
        C.CanonicalZoneIdentity("property.example", "zone.podocarpus", 1, 7),
        "Podocarpus screen",
        _landscape(7, (podocarpus,)),
        (
            _details(
                "podocarpus",
                planted_at=NOW - timedelta(days=365),
                source_container_gallons=5,
                current_height_meters=1.8288,
            ),
        ),
        (
            C.ZoneDemandSource(
                "source.podocarpus.manual",
                C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
                ("podocarpus",),
            ),
        ),
        (
            C.IrrigationDeliveryLink(
                "link.podocarpus",
                "podocarpus",
                C.DeliveryLinkStatus.DOCUMENTED,
                "delivery.podocarpus",
                ("component.podocarpus.drip",),
                True,
            ),
        ),
    )

    assert profile.plant_details[0].source_container_gallons == 5
    assert profile.plant_details[0].current_height_meters == pytest.approx(1.8288)
    assert C.assess_delivery_compatibility(profile).state is C.DeliveryCompatibilityState.DOCUMENTED


def test_landscape_change_preserves_removed_plant_and_flags_new_delivery_gap() -> None:
    olive = _plant("olive", "Olive", "Syntheticus oldii", M.EstablishmentState.ESTABLISHED)
    avocado = _plant(
        "hass_avocado",
        "Hass avocado",
        "Syntheticus replacementii",
        M.EstablishmentState.NEWLY_PLANTED,
    )
    removed = C.LandscapeChangeEvent(
        "event.olive.removed",
        C.LandscapeEventType.PLANT_GROUP_REMOVED,
        NOW - timedelta(days=7),
        C.LandscapePlantSnapshot(
            olive,
            C.PlantCommissioningDetails(
                "olive",
                C.CommissioningEvidenceSource.USER_CONFIRMED,
                M.Confidence.HIGH,
                NOW - timedelta(days=7),
            ),
        ),
    )
    added_details = C.PlantCommissioningDetails(
        "hass_avocado",
        C.CommissioningEvidenceSource.USER_CONFIRMED,
        M.Confidence.HIGH,
        NOW,
        planted_at=NOW - timedelta(days=7),
        source_container_gallons=5,
        current_height_meters=1.2192,
    )
    added = C.LandscapeChangeEvent(
        "event.avocado.added",
        C.LandscapeEventType.PLANT_GROUP_ADDED,
        NOW - timedelta(days=7),
        C.LandscapePlantSnapshot(avocado, added_details),
    )
    profile = C.CommissionedZoneProfile(
        1,
        C.CanonicalZoneIdentity("property.example", "zone.changed", 1, 8),
        "Changed planting",
        _landscape(8, (avocado,)),
        (added_details,),
        (
            C.ZoneDemandSource(
                "source.changed.manual",
                C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
                ("hass_avocado",),
            ),
        ),
        (
            C.IrrigationDeliveryLink(
                "link.avocado.unresolved",
                "hass_avocado",
                C.DeliveryLinkStatus.UNRESOLVED,
            ),
        ),
        (removed, added),
    )
    assessment = C.assess_delivery_compatibility(profile)

    assert profile.landscape_events[0].plant_snapshot.plant_group.common_name == "Olive"
    assert profile.landscape_events[1].plant_snapshot.plant_group.common_name == "Hass avocado"
    assert profile.plant_details[0].source_container_gallons == 5
    assert assessment.state is C.DeliveryCompatibilityState.INSUFFICIENT_EVIDENCE
    assert assessment.advisories[0].code == "irrigation_delivery_information_required"
    assert assessment.execution_authorized is False


def test_user_calibrated_baseline_carries_reference_without_weather_scaling() -> None:
    baseline = C.UserCalibratedBaseline(
        runtime_seconds=12 * 60,
        reference_air_temperature_celsius=(75 - 32) * 5 / 9,
        reference_recent_precipitation_mm=0,
        reference_condition="moderate dry day with no recent rain",
        calibrated_at=NOW,
        confidence=M.Confidence.HIGH,
    )
    profile = C.CommissionedZoneProfile(
        1,
        C.CanonicalZoneIdentity("property.baseline", "zone.baseline", None, 1),
        "User baseline zone",
        _landscape(1, ()),
        (),
        (
            C.ZoneDemandSource(
                "source.baseline.user",
                C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
                calibrated_baseline=baseline,
            ),
        ),
        (),
    )

    assert profile.demand_sources[0].calibrated_baseline.runtime_seconds == 720
    assert "scale" not in profile.to_dict()
    assert profile.execution_authorized is False


def test_synthetic_other_property_accepts_structured_visual_evidence_only() -> None:
    plant = _plant(
        "synthetic_groundcover",
        "Fictional groundcover",
        None,
        M.EstablishmentState.UNKNOWN,
    )
    profile = C.CommissionedZoneProfile(
        1,
        C.CanonicalZoneIdentity("property.synthetic_other", "zone.courtyard", None, 1),
        "Synthetic courtyard",
        _landscape(1, (plant,)),
        (
            C.PlantCommissioningDetails(
                "synthetic_groundcover",
                C.CommissioningEvidenceSource.AI_INFERRED,
                M.Confidence.MODERATE,
                NOW,
                structured_evidence_ids=("finding.synthetic.plant",),
            ),
        ),
        (
            C.ZoneDemandSource(
                "source.synthetic.visual",
                C.ZoneDemandSourceMode.PHOTO_AI_DERIVED,
                plant_group_ids=("synthetic_groundcover",),
                structured_visual_assessment_ids=("assessment.synthetic",),
            ),
        ),
        (
            C.IrrigationDeliveryLink(
                "link.synthetic.unresolved",
                "synthetic_groundcover",
                C.DeliveryLinkStatus.UNRESOLVED,
            ),
        ),
    )

    payload = profile.to_dict()
    assert payload["identity"]["property_id"] == "property.synthetic_other"
    assert payload["demand_sources"][0]["mode"] == "photo_ai_derived"
    assert "photo" not in payload
    with pytest.raises(FrozenInstanceError):
        profile.display_name = "Changed"


def test_commissioning_cross_references_and_authority_fail_closed() -> None:
    plant = _plant("plant", "Plant", None, M.EstablishmentState.UNKNOWN)
    with pytest.raises(ValueError, match="unknown current plant group"):
        C.CommissionedZoneProfile(
            1,
            C.CanonicalZoneIdentity("property.example", "zone.invalid", 1, 9),
            "Invalid",
            _landscape(9, (plant,)),
            (_details("plant"),),
            (
                C.ZoneDemandSource(
                    "source.invalid",
                    C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
                    ("missing",),
                ),
            ),
            (),
        )
    with pytest.raises(ValueError, match="advisory only"):
        C.DeliveryCompatibilityAssessment(
            C.DeliveryCompatibilityState.DOCUMENTED,
            (),
            execution_authorized=True,
        )
