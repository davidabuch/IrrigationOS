from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

C = load_integration_module("landscape_intelligence.commissioning")
M = load_integration_module("landscape_intelligence.models")
ONBOARDING = load_integration_module("landscape_intelligence.onboarding")
P = load_integration_module("landscape_intelligence.persistence")
Z = load_integration_module("landscape_intelligence.zone1")

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _manual(
    plant_group_id: str = "podocarpus",
    common_name: str = "Podocarpus",
    botanical_name: str | None = "Podocarpus spp.",
    establishment: object = M.EstablishmentState.ESTABLISHING,
) -> Any:
    return ONBOARDING.ManualPlantOnboardingInput(
        plant_group_id=plant_group_id,
        common_name=common_name,
        botanical_name=botanical_name,
        establishment_state=establishment,
        observed_at=NOW,
        planted_at=NOW - timedelta(days=365),
        source_container_gallons=5,
        current_height_meters=1.8288,
    )


def _manual_zone(
    *,
    property_id: str = "property.primary",
    zone_id: str = "zone.2",
    controller_slot: int | None = 1,
    area_slot: int = 2,
) -> Any:
    return ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity(
                property_id, zone_id, controller_slot, area_slot
            ),
            "Podocarpus screen",
            C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
            NOW,
            manual_plants=(_manual(),),
        )
    )


def test_manual_zone_two_maps_user_confirmed_facts_without_zone_code() -> None:
    zone = _manual_zone()
    detail = zone.plant_details[0]

    assert zone.identity.to_dict() == {
        "property_id": "property.primary",
        "zone_id": "zone.2",
        "controller_slot": 1,
        "area_slot": 2,
    }
    assert detail.source is C.CommissioningEvidenceSource.USER_CONFIRMED
    assert detail.confidence is M.Confidence.HIGH
    assert detail.source_container_gallons == 5
    assert detail.current_height_meters == pytest.approx(1.8288)
    assert zone.delivery_links[0].status is C.DeliveryLinkStatus.UNRESOLVED
    assert zone.execution_authorized is False


def test_unrelated_property_baseline_requires_no_plant_or_weather_scaling() -> None:
    baseline = C.UserCalibratedBaseline(
        720,
        (75 - 32) * 5 / 9,
        0,
        "dry day with no recent rain",
        NOW,
        M.Confidence.HIGH,
    )
    zone = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.other", "zone.baseline", None, 1),
            "Other property baseline",
            C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
            NOW,
            calibrated_baseline=baseline,
        )
    )

    assert zone.landscape_profile.plant_groups == ()
    assert zone.demand_sources[0].calibrated_baseline == baseline
    assert zone.landscape_profile.hydrozone_type is M.HydrozoneType.UNRESOLVED
    assert "scale" not in zone.to_dict()


def test_approved_visual_findings_persist_references_without_raw_images() -> None:
    finding = ONBOARDING.ApprovedVisualPlantFinding(
        "plant.visual",
        "assessment.approved",
        ("evidence.photo.1",),
        "Synthetic shrub",
        None,
        M.Confidence.MODERATE,
        M.EstablishmentState.UNKNOWN,
        NOW,
        visible_irrigation_method="microjet",
    )
    zone = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.other", "zone.visual", None, 2),
            "Visual zone",
            C.ZoneDemandSourceMode.PHOTO_AI_DERIVED,
            NOW,
            visual_findings=(finding,),
        )
    )

    payload = zone.to_dict()
    assert payload["demand_sources"][0]["structured_visual_assessment_ids"] == [
        "assessment.approved"
    ]
    assert payload["plant_details"][0]["structured_evidence_ids"] == [
        "evidence.photo.1"
    ]
    assert b"raw-image" not in repr(payload).encode()
    with pytest.raises(ValueError, match="evidence_ids"):
        ONBOARDING.ApprovedVisualPlantFinding(
            "plant.visual",
            "assessment.approved",
            (b"raw-image",),
            "Synthetic shrub",
            None,
            M.Confidence.MODERATE,
            M.EstablishmentState.UNKNOWN,
            NOW,
        )


def test_hybrid_identity_conflict_preserves_both_candidates_and_blocks_authority() -> None:
    manual = _manual("plant.primary", "Citrus", "Citrus spp.")
    visual = ONBOARDING.ApprovedVisualPlantFinding(
        "plant.primary",
        "assessment.hybrid",
        ("evidence.hybrid.1",),
        "Hass avocado",
        "Persea americana Hass",
        M.Confidence.MODERATE,
        M.EstablishmentState.ESTABLISHING,
        NOW,
    )
    zone = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.primary", "zone.hybrid", 1, 3),
            "Hybrid conflict",
            C.ZoneDemandSourceMode.HYBRID,
            NOW,
            manual_plants=(manual,),
            visual_findings=(visual,),
        )
    )

    assert zone.landscape_profile.plant_groups[0].common_name == "Citrus"
    assert len(zone.conflicts) == 1
    candidates = zone.conflicts[0].candidates
    assert tuple(candidate.value for candidate in candidates) == (
        "Citrus spp.",
        "Persea americana Hass",
    )
    assert tuple(candidate.source for candidate in candidates) == (
        C.CommissioningEvidenceSource.USER_CONFIRMED,
        C.CommissioningEvidenceSource.AI_INFERRED,
    )
    assert zone.conflicts[0].unresolved is True
    assert zone.execution_authorized is False
    assert zone.live_control_authorized is False


def test_landscape_remove_add_retains_history_and_missing_delivery_advisory() -> None:
    existing = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.primary", "zone.changed", 1, 4),
            "Changed zone",
            C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
            NOW - timedelta(days=30),
            manual_plants=(
                ONBOARDING.ManualPlantOnboardingInput(
                    "olive",
                    "Olive",
                    "Syntheticus oldii",
                    M.EstablishmentState.ESTABLISHED,
                    NOW - timedelta(days=30),
                ),
            ),
        )
    )
    avocado = ONBOARDING.ManualPlantOnboardingInput(
        "hass_avocado",
        "Hass avocado",
        "Syntheticus replacementii",
        M.EstablishmentState.NEWLY_PLANTED,
        NOW,
        planted_at=NOW - timedelta(days=7),
        source_container_gallons=5,
        current_height_meters=1.2192,
    )
    changed = ONBOARDING.map_landscape_changes(
        existing,
        removals=(ONBOARDING.PlantRemovalInput("event.olive.remove", "olive", NOW),),
        additions=(ONBOARDING.PlantAdditionInput("event.avocado.add", avocado, NOW),),
    )
    compatibility = C.assess_delivery_compatibility(changed)

    assert tuple(event.event_type for event in changed.landscape_events) == (
        C.LandscapeEventType.PLANT_GROUP_REMOVED,
        C.LandscapeEventType.PLANT_GROUP_ADDED,
    )
    snapshots = {
        event.plant_snapshot.plant_group.plant_group_id
        for event in changed.landscape_events
    }
    assert snapshots == {"olive", "hass_avocado"}
    assert changed.plant_details[0].source_container_gallons == 5
    assert changed.delivery_links[0].status is C.DeliveryLinkStatus.UNRESOLVED
    assert compatibility.state is C.DeliveryCompatibilityState.INSUFFICIENT_EVIDENCE


def test_schema_two_round_trip_and_deterministic_multi_property_order() -> None:
    zone1 = Z.build_zone_1_commissioning_profile(NOW)
    zone2 = _manual_zone()
    other = _manual_zone(
        property_id="property.aaa",
        zone_id="zone.remote",
        controller_slot=None,
        area_slot=9,
    )
    payload = P.build_store_payload(
        (zone2, zone1, other),
        (),
        legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
    )
    restored = P.restore_store_payload(payload, fallback_zone1=zone1)

    assert payload["commissioning_store_schema_version"] == 4
    assert tuple(
        (zone.identity.property_id, zone.identity.zone_id) for zone in restored.zones
    ) == (
        ("property.aaa", "zone.remote"),
        ("property.primary", "zone.1"),
        ("property.primary", "zone.2"),
    )
    rebuilt = P.build_store_payload(
        restored.zones,
        restored.deactivated_zones,
        legacy_zone1=restored.legacy_zone1,
    )
    assert rebuilt == payload


def test_two_properties_cannot_claim_the_same_installed_controller_area() -> None:
    zone1 = Z.build_zone_1_commissioning_profile(NOW)
    duplicate_binding = _manual_zone(
        property_id="property.other",
        zone_id="zone.other",
        controller_slot=1,
        area_slot=1,
    )

    with pytest.raises(ValueError, match="cannot bind multiple active zones"):
        P.build_store_payload(
            (zone1, duplicate_binding),
            (),
            legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
        )


def test_legacy_and_v1052_payloads_migrate_without_zone1_evidence_loss() -> None:
    zone1 = Z.build_zone_1_commissioning_profile(NOW)
    legacy_profile = zone1.to_landscape_intelligence_profile().to_dict()
    legacy = P.restore_store_payload(
        {"schema_version": 1, "zone_1": legacy_profile},
        fallback_zone1=zone1,
    )
    assert legacy.migration_required is True
    assert legacy.legacy_zone1 == legacy_profile
    assert legacy.zones == (zone1,)

    v1052_zone1 = deepcopy(zone1.to_dict())
    v1052_zone1["schema_version"] = 1
    v1052_zone1.pop("conflicts", None)
    v1052_zone2 = deepcopy(_manual_zone().to_dict())
    v1052_zone2["schema_version"] = 1
    v1052_zone2.pop("conflicts", None)
    v1052 = P.restore_store_payload(
        {
            "schema_version": 1,
            "zone_1": legacy_profile,
            "commissioned_zones": [v1052_zone1, v1052_zone2],
        },
        fallback_zone1=zone1,
    )
    assert v1052.migration_required is True
    assert v1052.zones[0].schema_version == C.ZONE_COMMISSIONING_SCHEMA_VERSION
    assert v1052.zones[0].conflicts == ()
    assert v1052.zones[0].landscape_profile == zone1.landscape_profile
    assert v1052.zones[1].identity.zone_id == "zone.2"
    assert v1052.zones[1].plant_details[0].source_container_gallons == 5

    v1053_zone = deepcopy(_manual_zone().to_dict())
    v1053_zone["schema_version"] = 2
    v1053_zone.pop("conflict_resolutions", None)
    v1053 = P.restore_store_payload(
        {
            "schema_version": 1,
            "commissioning_store_schema_version": 2,
            "zone_1": legacy_profile,
            "commissioned_zones": [v1053_zone],
        },
        fallback_zone1=zone1,
    )
    assert v1053.migration_required is True
    migrated_zone = next(
        zone for zone in v1053.zones if zone.identity.zone_id == "zone.2"
    )
    assert migrated_zone.schema_version == C.ZONE_COMMISSIONING_SCHEMA_VERSION
    assert migrated_zone.conflict_resolutions == ()
