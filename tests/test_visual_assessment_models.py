"""Behavioral tests for the Visual Landscape Intelligence domain."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

MODULE = load_integration_module("visual_assessment.models")
AdjustmentKind = MODULE.AdjustmentKind
AreaUnit = MODULE.AreaUnit
BaselineAdjustment = MODULE.BaselineAdjustment
DetectedIrrigationHardware = MODULE.DetectedIrrigationHardware
DetectedPlant = MODULE.DetectedPlant
DiagnosisHypothesis = MODULE.DiagnosisHypothesis
EstablishmentStage = MODULE.EstablishmentStage
GuidedTest = MODULE.GuidedTest
GuidedTestState = MODULE.GuidedTestState
GuidedTestType = MODULE.GuidedTestType
HardwareQuantityMode = MODULE.HardwareQuantityMode
InferenceMetadata = MODULE.InferenceMetadata
IrrigationHardwareType = MODULE.IrrigationHardwareType
MeasurementType = MODULE.MeasurementType
PhotoEvidence = MODULE.PhotoEvidence
PhotoEvidenceType = MODULE.PhotoEvidenceType
PhotoSource = MODULE.PhotoSource
PlantCategory = MODULE.PlantCategory
PlantQuantityMode = MODULE.PlantQuantityMode
PrivacyClassification = MODULE.PrivacyClassification
Provenance = MODULE.Provenance
RecommendedAction = MODULE.RecommendedAction
RecommendedActionType = MODULE.RecommendedActionType
RetentionPolicy = MODULE.RetentionPolicy
SoilAssessment = MODULE.SoilAssessment
SoilClass = MODULE.SoilClass
TemporaryAdjustment = MODULE.TemporaryAdjustment
Uncertainty = MODULE.Uncertainty
UncertaintyKind = MODULE.UncertaintyKind
UserMeasurement = MODULE.UserMeasurement
VerificationStatus = MODULE.VerificationStatus
VisualAssessmentSession = MODULE.VisualAssessmentSession
VisualAssessmentSessionState = MODULE.VisualAssessmentSessionState
VisualLandscapeAssessment = MODULE.VisualLandscapeAssessment

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)


def inference(
    confidence: float = 0.8,
    verification_status: Any = VerificationStatus.UNVERIFIED,
) -> Any:
    """Build common inference metadata for tests."""
    return InferenceMetadata(
        confidence=confidence,
        provenance=Provenance(source="visual_model", detail="provider-neutral-analysis"),
        verification_status=verification_status,
        assessed_at=NOW,
    )


def photo() -> Any:
    """Build safe photo evidence for tests."""
    return PhotoEvidence(
        evidence_id="evidence-1",
        area_id="area-1",
        evidence_type=PhotoEvidenceType.AREA_OVERVIEW,
        captured_at=NOW,
        source=PhotoSource.USER_CAPTURE,
        privacy_classification=PrivacyClassification.PRIVATE,
        retention_policy=RetentionPolicy.CONFIGURABLE_DURATION,
        content_reference="photo-store:asset-42",
        retention_days=30,
        user_note="Overview from the south edge",
    )


def session() -> Any:
    """Build an active assessment session for tests."""
    return VisualAssessmentSession(
        session_id="session-1",
        area_id="area-1",
        state=VisualAssessmentSessionState.READY_FOR_REVIEW,
        created_at=NOW,
        updated_at=LATER,
        evidence_ids=("evidence-1",),
    )


def tree(**changes: object) -> Any:
    """Build a count-based tree finding."""
    values: dict[str, object] = {
        "plant_id": "plant-tree",
        "area_id": "area-1",
        "category": PlantCategory.TREE,
        "quantity_mode": PlantQuantityMode.COUNT,
        "quantity": 2,
        "establishment_stage": EstablishmentStage.MATURE,
        "metadata": inference(),
        "evidence_ids": ("evidence-1",),
        "likely_common_name": "Olive tree",
        "age_estimate_months": 120,
        "canopy_size_meters": 3.5,
    }
    values.update(changes)
    return DetectedPlant(**values)


def test_valid_aggregate_has_deterministic_plain_serialization() -> None:
    """A complete assessment serializes predictably without provider payload types."""
    evidence = photo()
    plant = tree()
    hardware = DetectedIrrigationHardware(
        hardware_id="hardware-1",
        area_id="area-1",
        hardware_type=IrrigationHardwareType.DRIP_EMITTER,
        quantity_mode=HardwareQuantityMode.COUNT,
        quantity=4,
        metadata=inference(0.75),
        evidence_ids=(evidence.evidence_id,),
        guided_verification_required=True,
        flow_liters_per_hour=7.6,
    )
    soil = SoilAssessment(
        area_id="area-1",
        assessed_at=NOW,
        visual_class=SoilClass.CLAY_LOAM,
        visual_metadata=inference(0.6),
        drainage_observations=("Some surface pooling is visible",),
    )
    uncertainty = Uncertainty(
        uncertainty_id="uncertainty-1",
        kind=UncertaintyKind.REQUIRES_MEASUREMENT,
        description="Emitter flow cannot be established from a still photo",
        metadata=inference(0.9),
        evidence_ids=(evidence.evidence_id,),
        resolvable_by_test_id="test-1",
    )
    guided_test = GuidedTest(
        test_id="test-1",
        area_id="area-1",
        test_type=GuidedTestType.EMITTER_MEASURED_VOLUME,
        why_it_matters="Measured output validates the inferred emitter flow",
        instructions=("Place a marked cup below one emitter", "Collect water for 60 seconds"),
        requested_unit="milliliters",
        expected_measurement_type=MeasurementType.VOLUME,
        state=GuidedTestState.REQUESTED,
        safety_note="Keep electrical equipment dry",
        timer_duration_seconds=60,
    )
    hypothesis = DiagnosisHypothesis(
        hypothesis_id="hypothesis-1",
        likely_cause="Restricted emitter flow",
        metadata=inference(0.55),
        supporting_evidence_ids=(evidence.evidence_id,),
        contradicting_evidence_ids=(),
        alternative_causes=("Root-zone compaction",),
        recommended_next_diagnostic_step="Measure emitter volume",
    )
    action = RecommendedAction(
        action_id="action-1",
        area_id="area-1",
        action_type=RecommendedActionType.RUN_GUIDED_TEST,
        rationale="Confirm actual output before proposing an adjustment",
        metadata=inference(0.85),
        related_hypothesis_ids=(hypothesis.hypothesis_id,),
        guided_test_id=guided_test.test_id,
    )
    assessment = VisualLandscapeAssessment(
        assessment_id="assessment-1",
        session=session(),
        assessed_at=LATER,
        photo_evidence=(evidence,),
        plants=(plant,),
        irrigation_hardware=(hardware,),
        soil=soil,
        uncertainties=(uncertainty,),
        guided_tests=(guided_test,),
        hypotheses=(hypothesis,),
        recommended_actions=(action,),
    )

    first = assessment.to_dict()
    second = assessment.to_dict()

    assert first == second
    assert first["session"]["state"] == "ready_for_review"
    assert first["assessed_at"] == "2026-08-03T13:00:00+00:00"
    assert first["plants"][0]["quantity_mode"] == "count"
    assert first["photo_evidence"][0]["content_reference"] == "photo-store:asset-42"
    assert isinstance(first["plants"], list)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("inf"), float("nan")])
def test_confidence_must_be_finite_and_bounded(confidence: float) -> None:
    """Confidence is always a normalized finite fraction."""
    with pytest.raises(ValueError, match="confidence"):
        inference(confidence)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"quantity": 0}, "positive"),
        ({"quantity": 1.5}, "whole number"),
        (
            {"quantity_mode": PlantQuantityMode.PERCENTAGE, "quantity": 101},
            "cannot exceed 100",
        ),
        (
            {"quantity_mode": PlantQuantityMode.AREA, "quantity": 25},
            "requires area_unit",
        ),
    ],
)
def test_invalid_plant_quantities_are_rejected(
    changes: dict[str, object], message: str
) -> None:
    """Quantity semantics reject impossible or ambiguous values."""
    with pytest.raises(ValueError, match=message):
        tree(**changes)


def test_count_trees_coexist_with_area_based_shrubs() -> None:
    """Counts and areas remain independent rather than forced into one percentage total."""
    shrubs = tree(
        plant_id="plant-shrubs",
        category=PlantCategory.SHRUB,
        quantity_mode=PlantQuantityMode.AREA,
        quantity=160,
        area_unit=AreaUnit.SQUARE_FEET,
    )
    assessment = VisualLandscapeAssessment(
        assessment_id="assessment-mixed-plants",
        session=session(),
        assessed_at=LATER,
        photo_evidence=(photo(),),
        plants=(tree(), shrubs),
    )

    assert assessment.plants[0].quantity == 2
    assert assessment.plants[1].quantity == 160
    assert assessment.plants[1].area_unit is AreaUnit.SQUARE_FEET


def test_mixed_hardware_percentages_are_supported() -> None:
    """An area can retain multiple estimated hardware shares."""
    hardware = tuple(
        DetectedIrrigationHardware(
            hardware_id=f"hardware-{index}",
            area_id="area-1",
            hardware_type=hardware_type,
            quantity_mode=HardwareQuantityMode.SHARE_PERCENTAGE,
            quantity=share,
            metadata=inference(),
            evidence_ids=("evidence-1",),
            guided_verification_required=True,
        )
        for index, (hardware_type, share) in enumerate(
            ((IrrigationHardwareType.SPRAY, 70), (IrrigationHardwareType.ROTOR, 30)),
            start=1,
        )
    )
    assessment = VisualLandscapeAssessment(
        assessment_id="assessment-mixed-hardware",
        session=session(),
        assessed_at=LATER,
        photo_evidence=(photo(),),
        irrigation_hardware=hardware,
    )

    assert sum(item.quantity for item in assessment.irrigation_hardware) == 100


def test_guided_test_lifecycle_is_immutable_and_requires_measurement() -> None:
    """Completing a test returns a new validated state with measured evidence."""
    requested = GuidedTest(
        test_id="test-1",
        area_id="area-1",
        test_type=GuidedTestType.INFILTRATION,
        why_it_matters="Measured infiltration can resolve the soil-class conflict",
        instructions=("Apply a measured depth of water", "Record absorption time"),
        requested_unit="seconds",
        expected_measurement_type=MeasurementType.DURATION,
        state=GuidedTestState.REQUESTED,
        safety_note="Stop if water begins to run off the test area",
        timer_duration_seconds=300,
    )

    completed = requested.complete(measurement_ids=("measurement-1",), completed_at=LATER)

    assert requested.state is GuidedTestState.REQUESTED
    assert completed.state is GuidedTestState.COMPLETED
    assert completed.measurement_ids == ("measurement-1",)
    with pytest.raises(ValueError, match="require a measurement"):
        GuidedTest(
            test_id="test-invalid",
            area_id="area-1",
            test_type=GuidedTestType.INFILTRATION,
            why_it_matters="Resolve uncertainty",
            instructions=("Measure infiltration",),
            requested_unit="seconds",
            expected_measurement_type=MeasurementType.DURATION,
            state=GuidedTestState.COMPLETED,
            safety_note="Avoid slippery surfaces",
            completed_at=LATER,
        )


def temporary_adjustment(**changes: object) -> Any:
    """Build a safe temporary proposal for tests."""
    values: dict[str, object] = {
        "adjustment_id": "temporary-1",
        "area_id": "area-1",
        "kind": AdjustmentKind.PERCENTAGE,
        "change": 10,
        "safety_minimum": -20,
        "safety_maximum": 20,
        "reason": "Short observation period suggests mild under-watering",
        "metadata": inference(0.65),
        "event_count_limit": 2,
    }
    values.update(changes)
    return TemporaryAdjustment(**values)


def test_temporary_adjustments_are_bounded_proposals() -> None:
    """Temporary proposals require a limit and cannot escape safety bounds."""
    assert temporary_adjustment().proposal_only is True
    with pytest.raises(ValueError, match="within safety bounds"):
        temporary_adjustment(change=30)
    with pytest.raises(ValueError, match="time bounds or an event-count limit"):
        temporary_adjustment(event_count_limit=None)
    with pytest.raises(ValueError, match="proposals only"):
        temporary_adjustment(proposal_only=False)


def test_temporary_adjustment_accepts_ordered_time_bounds() -> None:
    """A temporary proposal may use an explicit start and end instead of event count."""
    adjustment = temporary_adjustment(
        event_count_limit=None,
        starts_at=NOW,
        ends_at=LATER,
    )
    assert adjustment.ends_at == LATER
    with pytest.raises(ValueError, match="must follow"):
        temporary_adjustment(event_count_limit=None, starts_at=LATER, ends_at=NOW)


def test_baseline_adjustment_always_requires_explicit_approval() -> None:
    """Persistent proposals cannot bypass user approval."""
    adjustment = BaselineAdjustment(
        adjustment_id="baseline-1",
        area_id="area-1",
        field_name="soil_class",
        old_value="loam",
        proposed_value="clay_loam",
        rationale="User infiltration measurement contradicts the old baseline",
        metadata=inference(0.9),
    )
    assert adjustment.requires_explicit_approval is True
    with pytest.raises(ValueError, match="explicit approval"):
        BaselineAdjustment(
            adjustment_id="baseline-2",
            area_id="area-1",
            field_name="soil_class",
            old_value="loam",
            proposed_value="clay_loam",
            rationale="Proposed correction",
            metadata=inference(),
            requires_explicit_approval=False,
        )


def test_user_confirmation_overrides_inference_without_destroying_history() -> None:
    """Effective values prefer user truth while retaining source assessments."""
    soil = SoilAssessment(
        area_id="area-1",
        assessed_at=NOW,
        visual_class=SoilClass.SANDY_LOAM,
        visual_metadata=inference(0.55),
        dataset_suggested_class=SoilClass.LOAM,
        dataset_metadata=InferenceMetadata(
            confidence=0.7,
            provenance=Provenance(source="soil_dataset"),
            verification_status=VerificationStatus.UNVERIFIED,
            assessed_at=NOW,
        ),
        user_confirmed_class=SoilClass.CLAY_LOAM,
        user_confirmation_provenance=Provenance(source="user_infiltration_test"),
        user_confirmed_at=LATER,
    )

    assert soil.effective_class is SoilClass.CLAY_LOAM
    assert soil.has_class_conflict is True
    assert soil.visual_class is SoilClass.SANDY_LOAM
    assert soil.dataset_suggested_class is SoilClass.LOAM
    serialized = soil.to_dict()
    assert serialized["visual_class"] == "sandy_loam"
    assert serialized["user_confirmed_class"] == "clay_loam"


def test_user_corrected_plant_value_wins_and_preserves_inference() -> None:
    """Plant corrections use the same user-first resolution rule."""
    plant = tree(
        metadata=inference(0.7, VerificationStatus.USER_CORRECTED),
        category=PlantCategory.TREE,
        likely_common_name="Olive tree",
        user_confirmed_category=PlantCategory.SHRUB,
        user_confirmed_common_name="Toyon",
    )
    assert plant.effective_category is PlantCategory.SHRUB
    assert plant.effective_common_name == "Toyon"
    assert plant.category is PlantCategory.TREE
    assert plant.likely_common_name == "Olive tree"


@pytest.mark.parametrize(
    "reference",
    [b"raw image", bytearray(b"raw image"), "data:image/png;base64,abc"],
)
def test_photo_evidence_rejects_embedded_image_data(reference: object) -> None:
    """Photo records contain opaque references, never image content."""
    with pytest.raises((TypeError, ValueError), match=r"raw bytes|embed image data"):
        PhotoEvidence(
            evidence_id="evidence-unsafe",
            area_id="area-1",
            evidence_type=PhotoEvidenceType.DIAGNOSTIC,
            captured_at=NOW,
            source=PhotoSource.USER_SELECTED,
            privacy_classification=PrivacyClassification.SENSITIVE,
            retention_policy=RetentionPolicy.SESSION,
            content_reference=reference,
        )


def test_models_are_immutable() -> None:
    """Assessment state cannot be mutated in place."""
    current = session()
    with pytest.raises(FrozenInstanceError):
        current.__setattr__("state", VisualAssessmentSessionState.CONFIRMED)


def test_session_lifecycle_rejects_invalid_transitions_and_naive_timestamps() -> None:
    """Session transitions are explicit and timestamps are unambiguous."""
    created = VisualAssessmentSession(
        session_id="session-new",
        area_id="area-1",
        state=VisualAssessmentSessionState.CREATED,
        created_at=NOW,
        updated_at=NOW,
    )
    collecting = created.transition(
        VisualAssessmentSessionState.COLLECTING_EVIDENCE,
        updated_at=LATER,
    )
    assert collecting.state is VisualAssessmentSessionState.COLLECTING_EVIDENCE
    with pytest.raises(ValueError, match="invalid session transition"):
        created.transition(VisualAssessmentSessionState.CONFIRMED, updated_at=LATER)
    with pytest.raises(ValueError, match="timezone-aware"):
        VisualAssessmentSession(
            session_id="session-naive",
            area_id="area-1",
            state=VisualAssessmentSessionState.CREATED,
            created_at=datetime(2026, 8, 3, 12, 0),
            updated_at=NOW,
        )


def test_invalid_identifiers_are_rejected() -> None:
    """Stable identifiers cannot be derived from mutable display-name strings."""
    with pytest.raises(ValueError, match="stable identifier"):
        VisualAssessmentSession(
            session_id="Front Yard Session",
            area_id="area-1",
            state=VisualAssessmentSessionState.CREATED,
            created_at=NOW,
            updated_at=NOW,
        )


def test_enum_values_are_stable_public_vocabulary() -> None:
    """Critical lifecycle, test, hardware, and action values remain explicit."""
    assert [state.value for state in VisualAssessmentSessionState] == [
        "created",
        "collecting_evidence",
        "awaiting_user_input",
        "ready_for_review",
        "confirmed",
        "superseded",
        "failed",
    ]
    assert GuidedTestType.EMITTER_DRIP_COUNT.value == "emitter_drip_count"
    assert IrrigationHardwareType.SUBSURFACE_DRIP.value == "subsurface_drip"
    assert RecommendedActionType.PROPOSE_BASELINE_ADJUSTMENT.value == (
        "propose_baseline_adjustment"
    )


def test_user_measurement_and_soil_conflict_are_serializable() -> None:
    """Measured results can contradict visual soil evidence without erasing it."""
    measurement = UserMeasurement(
        measurement_id="measurement-1",
        area_id="area-1",
        measurement_type=MeasurementType.DURATION,
        value=540,
        unit="seconds",
        observed_at=LATER,
        provenance=Provenance(source="user_guided_test"),
        guided_test_id="test-1",
    )
    soil = SoilAssessment(
        area_id="area-1",
        assessed_at=NOW,
        visual_class=SoilClass.SAND,
        visual_metadata=inference(0.5),
        user_confirmed_class=SoilClass.CLAY,
        user_confirmation_provenance=Provenance(source="user_guided_test"),
        user_confirmed_at=LATER,
        infiltration_observations=(measurement,),
    )

    assert soil.has_class_conflict
    assert soil.to_dict()["infiltration_observations"][0]["value"] == 540
