from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

C = load_integration_module("landscape_intelligence.commissioning")
E = load_integration_module("landscape_intelligence.editing")
M = load_integration_module("landscape_intelligence.models")
ONBOARDING = load_integration_module("landscape_intelligence.onboarding")
P = load_integration_module("landscape_intelligence.persistence")
Z = load_integration_module("landscape_intelligence.zone1")

NOW = datetime(2026, 8, 24, 18, 0, tzinfo=UTC)


def _manual(
    plant_id: str,
    common_name: str,
    *,
    botanical_name: str | None = None,
    state: Any = M.EstablishmentState.ESTABLISHED,
    observed_at: datetime = NOW,
    planted_at: datetime | None = None,
    container: float | None = None,
    height: float | None = None,
) -> Any:
    return ONBOARDING.ManualPlantOnboardingInput(
        plant_group_id=plant_id,
        common_name=common_name,
        botanical_name=botanical_name,
        establishment_state=state,
        observed_at=observed_at,
        planted_at=planted_at,
        source_container_gallons=container,
        current_height_meters=height,
    )


def _zone(
    *,
    property_id: str = "property.example",
    zone_id: str = "zone.front",
    area_slot: int = 2,
) -> Any:
    return ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity(property_id, zone_id, 1, area_slot),
            "Front planter",
            C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
            NOW,
            manual_plants=(
                _manual(
                    f"{zone_id}.plant.1",
                    "Podocarpus",
                    botanical_name="Podocarpus spp.",
                ),
            ),
        )
    )


def _add(
    profile: Any,
    plant: Any,
    event_id: str,
    when: datetime,
) -> Any:
    return E.add_plant_group(
        profile,
        ONBOARDING.PlantAdditionInput(event_id, plant, when),
    )


def test_multi_plant_zone_review_is_generic_deterministic_and_bounded() -> None:
    profile = _zone()
    profile = _add(
        profile,
        _manual(
            "zone.front.plant.2",
            "Hass avocado",
            botanical_name="Persea americana Hass",
            state=M.EstablishmentState.NEWLY_PLANTED,
            planted_at=NOW - timedelta(days=7),
            container=5,
            height=1.2192,
        ),
        "event.front.avocado.add",
        NOW + timedelta(minutes=1),
    )
    profile = _add(
        profile,
        _manual("zone.front.plant.3", "Established ornamental shrubs"),
        "event.front.shrubs.add",
        NOW + timedelta(minutes=2),
    )

    review = E.build_commissioning_review(profile)

    assert tuple(
        item.plant_group.plant_group_id for item in review.plants
    ) == (
        "zone.front.plant.1",
        "zone.front.plant.2",
        "zone.front.plant.3",
    )
    assert review.identity.property_id == "property.example"
    assert len(review.recent_landscape_events) == 2
    assert "establishment_delivery_information_required" in {
        advisory.code for advisory in review.advisories
    }
    assert review.execution_authorized is False
    assert review.live_control_authorized is False


def test_add_and_edit_podocarpus_preserves_prior_snapshot() -> None:
    profile = _zone()
    edited = E.edit_plant_group(
        profile,
        E.PlantEditInput(
            "event.front.podocarpus.update",
            _manual(
                "zone.front.plant.1",
                "Podocarpus",
                botanical_name="Podocarpus spp.",
                state=M.EstablishmentState.ESTABLISHING,
                observed_at=NOW + timedelta(days=365),
                planted_at=NOW,
                container=5,
                height=1.8288,
            ),
            NOW + timedelta(days=365),
        ),
    )

    assert edited.plant_details[0].source_container_gallons == 5
    assert edited.plant_details[0].current_height_meters == 1.8288
    assert edited.plant_details[0].planted_at == NOW
    assert edited.landscape_events[-1].event_type is C.LandscapeEventType.PLANT_GROUP_UPDATED
    assert (
        edited.landscape_events[-1].plant_snapshot.commissioning_details
        == profile.plant_details[0]
    )


def test_noop_plant_edit_does_not_create_history_noise() -> None:
    profile = _zone()
    unchanged = E.edit_plant_group(
        profile,
        E.PlantEditInput(
            "event.front.noop",
            _manual(
                "zone.front.plant.1",
                "Podocarpus",
                botanical_name="Podocarpus spp.",
                observed_at=NOW + timedelta(minutes=5),
            ),
            NOW + timedelta(minutes=5),
        ),
    )

    assert unchanged is profile
    assert unchanged.landscape_events == ()


def test_landscape_replacement_retains_olive_and_activates_avocado() -> None:
    olive = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.other", "zone.replace", None, 4),
            "Replacement zone",
            C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
            NOW,
            manual_plants=(
                _manual("olive", "Olive", botanical_name="Syntheticus oldii"),
            ),
        )
    )
    avocado = _manual(
        "avocado",
        "Hass avocado",
        botanical_name="Syntheticus newii",
        state=M.EstablishmentState.NEWLY_PLANTED,
        observed_at=NOW + timedelta(days=7),
        planted_at=NOW + timedelta(days=1),
        container=5,
        height=1.2192,
    )
    changed = ONBOARDING.map_landscape_changes(
        olive,
        removals=(
            ONBOARDING.PlantRemovalInput(
                "event.olive.remove", "olive", NOW + timedelta(days=7)
            ),
        ),
        additions=(
            ONBOARDING.PlantAdditionInput(
                "event.avocado.add", avocado, NOW + timedelta(days=7)
            ),
        ),
    )

    assert changed.landscape_profile.plant_groups[0].plant_group_id == "avocado"
    assert tuple(
        event.plant_snapshot.plant_group.plant_group_id
        for event in changed.landscape_events
    ) == ("olive", "avocado")
    assert changed.delivery_links[0].status is C.DeliveryLinkStatus.UNRESOLVED
    assert E.build_commissioning_review(changed).advisories


def test_delivery_link_changes_from_unresolved_to_documented() -> None:
    profile = _zone()
    updated = E.update_delivery_link(
        profile,
        C.IrrigationDeliveryLink(
            "zone.front.plant.1.delivery",
            "zone.front.plant.1",
            C.DeliveryLinkStatus.DOCUMENTED,
            "delivery.front.microjet",
            ("component.front.1",),
            True,
        ),
    )

    assert updated.delivery_links[0].delivery_profile_id == "delivery.front.microjet"
    assert updated.delivery_links[0].component_ids == ("component.front.1",)
    assert "runtime" not in updated.to_dict()


def test_baseline_add_modify_remove_never_calculates_watering() -> None:
    profile = _zone()
    first = C.UserCalibratedBaseline(
        720,
        (75 - 32) * 5 / 9,
        0,
        "dry reference day",
        NOW,
        M.Confidence.HIGH,
    )
    added = E.set_calibrated_baseline(profile, first)
    modified = E.set_calibrated_baseline(
        added,
        C.UserCalibratedBaseline(
            840,
            (80 - 32) * 5 / 9,
            0,
            "updated dry reference day",
            NOW + timedelta(days=1),
            M.Confidence.HIGH,
        ),
    )
    removed = E.remove_calibrated_baseline(modified)

    assert E.build_commissioning_review(added).calibrated_baselines == (first,)
    assert E.build_commissioning_review(modified).calibrated_baselines[0].runtime_seconds == 840
    assert E.build_commissioning_review(removed).calibrated_baselines == ()
    assert removed.demand_sources[0].mode is C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE
    assert "calculated_runtime" not in modified.to_dict()


def test_removing_only_baseline_leaves_explicit_unresolved_demand() -> None:
    baseline = C.UserCalibratedBaseline(
        720, 23.8888888889, 0, "dry reference", NOW, M.Confidence.HIGH
    )
    profile = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.other", "zone.baseline", None, 1),
            "Baseline only",
            C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
            NOW,
            calibrated_baseline=baseline,
        )
    )

    removed = E.remove_calibrated_baseline(profile)

    assert removed.demand_sources[0].mode is C.ZoneDemandSourceMode.UNRESOLVED
    assert removed.execution_authorized is False


def test_conflict_review_and_explicit_resolution_preserve_original_evidence() -> None:
    manual = _manual("plant.primary", "Citrus", botanical_name="Citrus spp.")
    visual = ONBOARDING.ApprovedVisualPlantFinding(
        "plant.primary",
        "assessment.hybrid",
        ("evidence.photo.1",),
        "Avocado",
        "Persea americana",
        M.Confidence.MODERATE,
        M.EstablishmentState.UNKNOWN,
        NOW,
    )
    profile = ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.other", "zone.hybrid", None, 3),
            "Hybrid zone",
            C.ZoneDemandSourceMode.HYBRID,
            NOW,
            manual_plants=(manual,),
            visual_findings=(visual,),
        )
    )
    before = E.build_commissioning_review(profile)
    resolved = E.resolve_identity_conflict(
        profile,
        E.ConflictResolutionInput(
            "resolution.hybrid.identity",
            "event.hybrid.correction",
            profile.conflicts[0].conflict_id,
            "Citrus",
            "Citrus spp.",
            NOW + timedelta(minutes=1),
            note="User inspected the plant directly.",
        ),
    )
    after = E.build_commissioning_review(resolved)

    assert tuple(candidate.value for candidate in before.unresolved_conflicts[0].candidates) == (
        "Citrus spp.",
        "Persea americana",
    )
    assert after.unresolved_conflicts == ()
    assert resolved.conflicts == profile.conflicts
    assert resolved.conflict_resolutions[0].selected_value == "Citrus spp."
    assert resolved.conflicts[0].candidates[1].evidence_ids == ("evidence.photo.1",)
    assert resolved.execution_authorized is False
    zone1 = Z.build_zone_1_commissioning_profile(NOW)
    restored = P.restore_store_payload(
        P.build_store_payload(
            (resolved, zone1),
            (),
            legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
        ),
        fallback_zone1=zone1,
    )
    restored_hybrid = next(
        zone for zone in restored.zones if zone.identity.zone_id == "zone.hybrid"
    )
    assert restored_hybrid.conflicts == resolved.conflicts
    assert restored_hybrid.conflict_resolutions == resolved.conflict_resolutions


def test_schema_three_round_trip_after_edits_and_zone_one_compatibility() -> None:
    zone1 = Z.build_zone_1_commissioning_profile(NOW)
    edited = _add(
        _zone(),
        _manual("zone.front.plant.2", "Synthetic companion"),
        "event.front.companion.add",
        NOW + timedelta(minutes=1),
    )
    payload = P.build_store_payload(
        (edited, zone1),
        (),
        legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
    )
    restored = P.restore_store_payload(payload, fallback_zone1=zone1)

    assert payload["commissioning_store_schema_version"] == 7
    assert restored.zones[0] == edited
    assert restored.zones[0].identity.zone_id == "zone.front"
    assert restored.zones[1].identity.zone_id == "zone.1"
    assert restored.legacy_zone1 == zone1.to_landscape_intelligence_profile().to_dict()


def test_unrelated_synthetic_property_uses_same_edit_engine() -> None:
    profile = _zone(
        property_id="property.synthetic_elsewhere",
        zone_id="zone.courtyard",
        area_slot=11,
    )
    updated = _add(
        profile,
        _manual("zone.courtyard.plant.2", "Synthetic groundcover"),
        "event.courtyard.groundcover.add",
        NOW + timedelta(minutes=1),
    )

    assert updated.identity.property_id == "property.synthetic_elsewhere"
    assert len(E.build_commissioning_review(updated).plants) == 2
    assert "zone1" not in repr(updated.to_dict()).casefold()
