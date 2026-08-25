from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

A = load_integration_module("landscape_intelligence.admission")
C = load_integration_module("landscape_intelligence.commissioning")
E = load_integration_module("landscape_intelligence.editing")
M = load_integration_module("landscape_intelligence.models")
ONBOARDING = load_integration_module("landscape_intelligence.onboarding")
P = load_integration_module("landscape_intelligence.persistence")
Z = load_integration_module("landscape_intelligence.zone1")

NOW = datetime(2026, 8, 24, 18, 0, tzinfo=UTC)


def _manual(
    plant_id: str,
    name: str,
    *,
    botanical_name: str | None = None,
    state: Any = M.EstablishmentState.ESTABLISHED,
    planted_at: datetime | None = None,
    container: float | None = None,
    height: float | None = None,
) -> Any:
    return ONBOARDING.ManualPlantOnboardingInput(
        plant_id,
        name,
        botanical_name,
        state,
        NOW,
        planted_at=planted_at,
        source_container_gallons=container,
        current_height_meters=height,
    )


def _profile(
    *,
    zone_id: str = "zone.synthetic",
    mode: Any = C.ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
    manual: tuple[Any, ...] = (),
    visual: tuple[Any, ...] = (),
    baseline: Any = None,
    links: tuple[Any, ...] = (),
    area_slot: int = 6,
) -> Any:
    return ONBOARDING.map_zone_onboarding(
        ONBOARDING.ZoneOnboardingRequest(
            C.CanonicalZoneIdentity("property.synthetic", zone_id, 1, area_slot),
            "Synthetic zone",
            mode,
            NOW,
            manual_plants=manual,
            visual_findings=visual,
            calibrated_baseline=baseline,
            delivery_links=links,
        )
    )


def _state(assessment: Any, purpose: Any) -> Any:
    return assessment.readiness_for(purpose).state


def test_manual_podocarpus_is_plant_ready_but_requests_delivery() -> None:
    profile = _profile(
        manual=(
            _manual(
                "plant.podocarpus",
                "Podocarpus",
                botanical_name="Podocarpus spp.",
                state=M.EstablishmentState.ESTABLISHING,
                planted_at=NOW - timedelta(days=365),
                container=5,
                height=1.8288,
            ),
        )
    )

    result = A.assess_commissioning(profile)

    assert (
        _state(result, A.CommissioningPurpose.LANDSCAPE_UNDERSTANDING)
        is A.PurposeReadinessState.READY
    )
    assert (
        _state(result, A.CommissioningPurpose.PLANT_DEMAND_ESTIMATION)
        is A.PurposeReadinessState.READY
    )
    assert (
        _state(result, A.CommissioningPurpose.DELIVERY_QUANTIFICATION)
        is A.PurposeReadinessState.NOT_READY
    )
    assert "document_irrigation_delivery" in {item.code for item in result.follow_up_requirements}
    assert all(
        item.kind is not A.CommissioningEvidenceKind.DELIVERY_LINK
        for item in result.unresolved_evidence
    )
    assert result.execution_authorized is False
    assert result.live_control_authorized is False


def test_new_avocado_admits_establishment_and_requests_delivery_review() -> None:
    profile = _profile(
        manual=(
            _manual(
                "plant.avocado",
                "Hass avocado",
                botanical_name="Persea americana Hass",
                state=M.EstablishmentState.NEWLY_PLANTED,
                planted_at=NOW - timedelta(days=7),
                container=5,
                height=1.2192,
            ),
        )
    )

    result = A.assess_commissioning(profile)

    assert any(
        item.kind is A.CommissioningEvidenceKind.ESTABLISHMENT_STATE
        and item.decision is A.EvidenceAdmissionDecision.ADMITTED
        for item in result.admitted_evidence
    )
    assert "establishment_delivery_review_required" in result.advisory_codes
    assert "confirm_establishment_delivery" in {item.code for item in result.follow_up_requirements}


def test_baseline_only_does_not_require_plant_identity() -> None:
    baseline = C.UserCalibratedBaseline(
        12 * 60,
        (75 - 32) * 5 / 9,
        0,
        "dry day with no recent rain",
        NOW,
        M.Confidence.HIGH,
    )
    profile = _profile(
        zone_id="zone.baseline",
        mode=C.ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
        baseline=baseline,
    )

    result = A.assess_commissioning(profile)

    assert (
        _state(result, A.CommissioningPurpose.BASELINE_ENVIRONMENTAL_SCALING)
        is A.PurposeReadinessState.READY
    )
    assert (
        _state(result, A.CommissioningPurpose.PLANT_DEMAND_ESTIMATION)
        is A.PurposeReadinessState.NOT_READY
    )
    assert "confirm_plant_identity" not in {item.code for item in result.follow_up_requirements}
    assert "baseline_mode_ready_for_environmental_scaling" in result.advisory_codes


def test_approved_high_confidence_visual_identity_is_admitted() -> None:
    visual = ONBOARDING.ApprovedVisualPlantFinding(
        "plant.visual",
        "assessment.visual.1",
        ("evidence.visual.1",),
        "Likely citrus",
        "Citrus syntheticus",
        M.Confidence.HIGH,
        M.EstablishmentState.ESTABLISHED,
        NOW,
    )
    profile = _profile(
        zone_id="zone.visual",
        mode=C.ZoneDemandSourceMode.PHOTO_AI_DERIVED,
        visual=(visual,),
    )

    result = A.assess_commissioning(profile)

    identity = next(
        item
        for item in result.admitted_evidence
        if item.kind is A.CommissioningEvidenceKind.PLANT_IDENTITY
    )
    assert identity.source is C.CommissioningEvidenceSource.AI_INFERRED
    assert identity.confidence is M.Confidence.HIGH
    assert identity.evidence_reference_ids == ("evidence.visual.1",)
    assert (
        _state(result, A.CommissioningPurpose.PLANT_DEMAND_ESTIMATION)
        is A.PurposeReadinessState.READY
    )


def test_unresolved_conflict_withholds_identity_until_human_resolution() -> None:
    manual = _manual("plant.primary", "Citrus", botanical_name="Citrus spp.")
    visual = ONBOARDING.ApprovedVisualPlantFinding(
        "plant.primary",
        "assessment.hybrid",
        ("evidence.visual.hybrid",),
        "Avocado",
        "Persea americana",
        M.Confidence.MODERATE,
        M.EstablishmentState.ESTABLISHED,
        NOW,
    )
    profile = _profile(
        zone_id="zone.hybrid",
        mode=C.ZoneDemandSourceMode.HYBRID,
        manual=(manual,),
        visual=(visual,),
    )

    unresolved = A.assess_commissioning(profile)

    assert "commissioning_conflict_unresolved" in unresolved.blocker_codes
    assert (
        _state(unresolved, A.CommissioningPurpose.PLANT_DEMAND_ESTIMATION)
        is A.PurposeReadinessState.NOT_READY
    )
    assert any(
        item.kind is A.CommissioningEvidenceKind.PLANT_IDENTITY
        for item in unresolved.unresolved_evidence
    )
    assert any(
        item.evidence_reference_ids == ("evidence.visual.hybrid",)
        and item.source is C.CommissioningEvidenceSource.AI_INFERRED
        for item in unresolved.unresolved_evidence
    )
    assert any(
        item.kind is A.CommissioningEvidenceKind.ESTABLISHMENT_STATE
        for item in unresolved.admitted_evidence
    )

    resolved_profile = E.resolve_identity_conflict(
        profile,
        E.ConflictResolutionInput(
            "resolution.hybrid.identity",
            "event.hybrid.identity",
            profile.conflicts[0].conflict_id,
            "Citrus",
            "Citrus spp.",
            NOW + timedelta(minutes=1),
        ),
    )
    resolved = A.assess_commissioning(resolved_profile)

    assert "commissioning_conflict_unresolved" not in resolved.blocker_codes
    assert (
        _state(resolved, A.CommissioningPurpose.PLANT_DEMAND_ESTIMATION)
        is A.PurposeReadinessState.READY
    )
    assert resolved_profile.conflicts == profile.conflicts
    assert resolved_profile.conflict_resolutions


def test_removed_historical_plant_does_not_enter_current_assessment() -> None:
    profile = _profile(
        manual=(_manual("plant.olive", "Olive", botanical_name="Syntheticus oldii"),)
    )
    changed = ONBOARDING.map_landscape_changes(
        profile,
        removals=(
            ONBOARDING.PlantRemovalInput(
                "event.olive.remove", "plant.olive", NOW + timedelta(days=1)
            ),
        ),
        additions=(
            ONBOARDING.PlantAdditionInput(
                "event.avocado.add",
                _manual(
                    "plant.avocado",
                    "Hass avocado",
                    botanical_name="Syntheticus newii",
                    state=M.EstablishmentState.NEWLY_PLANTED,
                ),
                NOW + timedelta(days=1),
            ),
        ),
    )

    result = A.assess_commissioning(changed)

    assert changed.landscape_events[0].plant_snapshot.plant_group.common_name == "Olive"
    assert all(item.plant_group_id != "plant.olive" for item in result.admitted_evidence)
    assert all(item.plant_group_id != "plant.olive" for item in result.unresolved_evidence)


def test_documented_delivery_is_admitted_without_claiming_hydraulics() -> None:
    profile = _profile(
        manual=(_manual("plant.primary", "Synthetic plant"),),
        links=(
            C.IrrigationDeliveryLink(
                "link.synthetic",
                "plant.primary",
                C.DeliveryLinkStatus.DOCUMENTED,
                "delivery.synthetic",
                ("component.synthetic.1",),
                True,
            ),
        ),
    )

    result = A.assess_commissioning(profile)

    assert (
        _state(result, A.CommissioningPurpose.DELIVERY_QUANTIFICATION)
        is A.PurposeReadinessState.READY
    )
    assert _state(result, A.CommissioningPurpose.WATER_BALANCE) is A.PurposeReadinessState.READY
    assert "delivery_profile_requires_downstream_validation" in result.advisory_codes
    payload = result.to_dict()
    assert "flow_rate" not in repr(payload)
    assert "runtime" not in repr(payload)
    assert result.execution_authorized is False


def test_assessment_is_deterministic_and_zone_one_remains_compatible() -> None:
    zone1 = Z.build_zone_1_commissioning_profile(NOW)

    first = A.assess_commissioning(zone1)
    second = A.assess_commissioning(zone1)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.blocker_codes == tuple(sorted(first.blocker_codes))
    assert first.advisory_codes == tuple(sorted(first.advisory_codes))
    assert tuple(item.evidence_id for item in first.admitted_evidence) == tuple(
        sorted(item.evidence_id for item in first.admitted_evidence)
    )
    assert tuple(item.purpose for item in first.purpose_readiness) == tuple(A.CommissioningPurpose)
    assert first.schema_version == 1
    assert zone1.to_landscape_intelligence_profile() == Z.build_zone_1_landscape_intelligence(NOW)


def test_derived_assessment_needs_no_persistence_schema_change() -> None:
    zone1 = Z.build_zone_1_commissioning_profile(NOW)
    profile = _profile(manual=(_manual("plant.synthetic", "Synthetic plant"),))
    before = A.assess_commissioning(profile)
    restored = P.restore_store_payload(
        P.build_store_payload(
            (profile, zone1),
            (),
            legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
        ),
        fallback_zone1=zone1,
    )
    restored_profile = next(
        item for item in restored.zones if item.identity.zone_id == "zone.synthetic"
    )

    assert P.COMMISSIONING_STORE_SCHEMA_VERSION == 3
    assert A.assess_commissioning(restored_profile) == before
    assert "commissioning_assessment" not in P.build_store_payload(
        (profile, zone1),
        (),
        legacy_zone1=zone1.to_landscape_intelligence_profile().to_dict(),
    )
