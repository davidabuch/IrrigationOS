"""Conversational commissioning foundation tests."""

from datetime import UTC, datetime
from typing import Any

from tests.helpers import load_integration_module

L = load_integration_module("landscape_intelligence")
W = load_integration_module("water_delivery")
P = load_integration_module("water_delivery.persistence")

ApprovedVisualDeliveryFinding = L.ApprovedVisualDeliveryFinding
ApprovedVisualPlantFinding = L.ApprovedVisualPlantFinding
CanonicalZoneIdentity = L.CanonicalZoneIdentity
Confidence = L.Confidence
ConversationalCommissioningIntake = L.ConversationalCommissioningIntake
DeliverySharing = L.DeliverySharing
EstablishmentState = L.EstablishmentState
EvidenceMateriality = L.EvidenceMateriality
GenericDeliveryReference = L.GenericDeliveryReference
SimpleDeliveryDescription = L.SimpleDeliveryDescription
SimplePlantDescription = L.SimplePlantDescription
build_conversational_commissioning_proposal = L.build_conversational_commissioning_proposal
DeliveryEvidenceLevel = W.DeliveryEvidenceLevel
DeliveryComponentCalibrationRequest = W.DeliveryComponentCalibrationRequest
MeasurementUnit = W.MeasurementUnit
SprayPattern = W.SprayPattern
WaterDeliveryType = W.WaterDeliveryType
calibrate_delivery_component = W.calibrate_delivery_component

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
IDENTITY = CanonicalZoneIdentity("property.synthetic", "front.planter", 2, 7)


def _plant() -> Any:
    return SimplePlantDescription(
        "Podocarpus",
        NOW,
        planted_at=datetime(2025, 8, 25, tzinfo=UTC),
        source_container_gallons=5,
        current_height_meters=1.8288,
        establishment_state=EstablishmentState.ESTABLISHING,
    )


def _delivery(reference_id: str = "reference.microjet.blue.medium") -> Any:
    return SimpleDeliveryDescription(
        WaterDeliveryType.MICROJET,
        NOW,
        emitter_class="blue",
        throw_min_meters=0.9144,
        throw_max_meters=1.2192,
        spray_pattern=SprayPattern.PART_CIRCLE,
        arc_degrees=180,
        sharing=DeliverySharing.SHARED,
        plants_per_emitter=2,
        generic_reference_id=reference_id,
    )


def _reference(low: float = 20, high: float = 24) -> Any:
    return GenericDeliveryReference(
        "reference.microjet.blue.medium",
        WaterDeliveryType.MICROJET,
        "blue 3-4 ft microjet",
        0.9,
        1.25,
        low,
        high,
        source="documented_provider_neutral_reference",
    )


def test_simple_podocarpus_maps_to_canonical_models_without_false_precision() -> None:
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY,
            "Front planter",
            "One two-sided blue microjet serves two Podocarpus.",
            NOW,
            _plant(),
            _delivery(),
        ),
        generic_references=(_reference(),),
    )
    plant = result.zone_profile.landscape_profile.plant_groups[0]
    component = result.delivery_profile.components[0]
    assert plant.common_name == "Podocarpus"
    assert plant.plant_group_id == "front.planter.plant.podocarpus"
    assert result.zone_profile.delivery_links[0].dedicated_delivery is False
    assert component.nominal_flow_liters_per_hour.value is None
    assert component.measured_flow_liters_per_hour.value is None
    assert component.approximate_flow_range is not None
    assert component.approximate_flow_range.minimum_liters_per_hour == 20
    assert component.approximate_flow_range.maximum_liters_per_hour == 24
    assert component.emitter_class == "blue"
    assert component.plants_per_emitter == 2
    assert result.flow_materiality is EvidenceMateriality.SUFFICIENT_FOR_CURRENT_DECISION
    assert not result.execution_authorized
    assert not result.live_control_authorized


def test_generic_color_without_catalog_reference_does_not_fabricate_flow() -> None:
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY, "Front", "Blue microjet", NOW, _plant(), _delivery()
        )
    )
    component = result.delivery_profile.components[0]
    assert component.approximate_flow_range is None
    assert result.flow_materiality is EvidenceMateriality.ADDITIONAL_EVIDENCE_REQUIRED


def test_wide_reference_only_suggests_optional_measurement() -> None:
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY, "Front", "Microjet", NOW, _plant(), _delivery()
        ),
        generic_references=(_reference(10, 30),),
    )
    assert result.flow_materiality is EvidenceMateriality.OPTIONAL_PRECISION_IMPROVEMENT
    assert [item.code for item in result.follow_up_questions] == [
        "measure_emitter_flow_optional"
    ]


def test_visual_delivery_conflict_is_preserved_and_question_ranked_first() -> None:
    visual = ApprovedVisualDeliveryFinding(
        "assessment.1",
        ("evidence.running.1",),
        WaterDeliveryType.MICROJET,
        Confidence.MODERATE,
        NOW,
        spray_pattern=SprayPattern.FULL_CIRCLE,
        arc_degrees=360,
    )
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY, "Front", "Two-sided emitter", NOW, _plant(), _delivery(), None, visual
        )
    )
    conflict = result.zone_profile.conflicts[0]
    assert conflict.field_path == "delivery.spray_pattern"
    assert tuple(item.value for item in conflict.candidates) == (
        "part_circle",
        "full_circle",
    )
    assert result.follow_up_questions[0].code == "confirm_delivery_pattern"


def test_manual_identity_wins_but_visual_conflict_remains_auditable() -> None:
    visual = ApprovedVisualPlantFinding(
        "ignored.by.fusion",
        "assessment.plant.1",
        ("evidence.photo.1",),
        "Avocado",
        "Persea americana",
        Confidence.MODERATE,
        EstablishmentState.ESTABLISHING,
        NOW,
    )
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY, "Front", "Podocarpus", NOW, _plant(), None, visual
        )
    )
    assert result.zone_profile.landscape_profile.plant_groups[0].common_name == "Podocarpus"
    assert result.zone_profile.conflicts[0].field_path == "plant.identity"


def test_approximate_range_persistence_round_trip_and_measured_precedence() -> None:
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY, "Front", "Microjet", NOW, _plant(), _delivery()
        ),
        generic_references=(_reference(),),
    )
    assert result.delivery_profile is not None
    restored = P.water_delivery_profile_from_dict(result.delivery_profile.to_dict())
    component = restored.components[0]
    assert component.approximate_flow_range == (
        result.delivery_profile.components[0].approximate_flow_range
    )
    assert component.preferred_flow_liters_per_hour is None
    assert component.approximate_flow_range is not None
    assert component.approximate_flow_range.provenance.source == (
        "documented_provider_neutral_reference"
    )
    assert component.nominal_flow_liters_per_hour.evidence_level is DeliveryEvidenceLevel.UNKNOWN


def test_measured_calibration_is_preferred_and_preserves_generic_evidence() -> None:
    result = build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            IDENTITY, "Front", "Microjet", NOW, _plant(), _delivery()
        ),
        generic_references=(_reference(),),
    )
    assert result.delivery_profile is not None
    prior = result.delivery_profile.components[0]
    measured = calibrate_delivery_component(
        DeliveryComponentCalibrationRequest(
            result.delivery_profile.profile_id,
            result.delivery_profile.area_id,
            prior.component_id,
            prior.display_name,
            prior.delivery_type,
            1,
            DeliveryEvidenceLevel.MEASURED,
            NOW,
            collected_volume=1,
            collected_volume_unit=MeasurementUnit.US_GALLONS,
            collection_duration_seconds=300,
        ),
        existing_profile=result.delivery_profile,
    )
    component = measured.components[0]
    assert component.preferred_flow_liters_per_hour == component.measured_flow_liters_per_hour.value
    assert component.approximate_flow_range == prior.approximate_flow_range
    assert component.emitter_class == "blue"
    assert component.plants_per_emitter == 2


def test_deterministic_serialization_and_no_raw_image_storage() -> None:
    intake = ConversationalCommissioningIntake(
        IDENTITY, "Front", "Photo shows a running microjet", NOW, _plant(), _delivery()
    )
    first = build_conversational_commissioning_proposal(
        intake, generic_references=(_reference(),)
    )
    second = build_conversational_commissioning_proposal(
        intake, generic_references=(_reference(),)
    )
    assert first.to_dict() == second.to_dict()
    serialized = str(first.to_dict())
    assert "data:image" not in serialized
    assert "execution_authorized': False" in serialized
