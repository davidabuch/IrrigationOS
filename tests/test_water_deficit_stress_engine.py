"""Behavioral tests for deterministic water-deficit stress-risk assessment."""

from dataclasses import replace
from typing import Any

from tests.helpers import load_integration_module
from tests.test_environment_models import report, signal
from tests.test_plant_stress_models import request

PK = load_integration_module("plant_knowledge")
ENV = load_integration_module("environment.models")
STRESS = load_integration_module("plant_stress")


def sensitivity_claim(value: Any = None, confidence: float = 0.9) -> Any:
    """Build one complete approved effective sensitivity claim."""
    return PK.EffectivePlantKnowledgeClaim(
        claim_id="pk.claim.example.water_stress_sensitivity",
        field_path="water.water_stress_sensitivity",
        value=value or PK.WaterStressSensitivity.MODERATE,
        unit=None,
        originating_profile_id="pk.profile.examplegenus_ficticia",
        source_ids=("pk.source.primary",),
        review_state=PK.ReviewState.APPROVED,
        evidence_grade=PK.EvidenceGrade.MODERATE,
        confidence=confidence,
        regional_applicability=request().context.regional_applicability,
        intended_consumer_capabilities=(PK.ConsumerCapability.PLANT_HEALTH,),
        claim_version=1,
        inherited=False,
        conflict_unresolved=False,
    )


def stress_request(
    *,
    sensitivity: Any = None,
    classification: Any = None,
    water_factor: float = 0.5,
    signal_completeness: float = 0.75,
) -> Any:
    """Build a valid request with explicit susceptibility and drying evidence."""
    base = request()
    knowledge = replace(
        base.knowledge_resolution,
        effective_claims=tuple(
            sorted(
                (*base.knowledge_resolution.effective_claims, sensitivity or sensitivity_claim()),
                key=lambda claim: claim.field_path,
            )
        ),
    )
    drying = signal(
        classification=classification or ENV.EnvironmentalSignalClassification.DRYING,
        confidence=replace(
            signal().confidence,
            completeness=signal_completeness,
            known_fact_count=3 if signal_completeness == 0.75 else 4,
            unavailable_quality_count=1 if signal_completeness == 0.75 else 0,
            good_quality_count=2 if signal_completeness == 0.75 else 3,
        ),
    )
    environmental = report(signals=(drying,))
    water = replace(base.water_requirement_assessment, value=water_factor)
    return replace(
        base,
        knowledge_resolution=knowledge,
        environmental_report=environmental,
        water_requirement_assessment=water,
    )


def test_available_assessment_is_deterministic_and_preserves_provenance() -> None:
    current = STRESS.assess_water_deficit_stress(stress_request(signal_completeness=1.0))
    dimension = current.dimensions[0]
    assert dimension.status is STRESS.PlantStressRiskStatus.AVAILABLE
    assert dimension.risk is STRESS.PlantStressRiskClassification.MODERATE
    assert dimension.plant_knowledge_claim_ids == (
        "pk.claim.example.water_stress_sensitivity",
    )
    assert dimension.environmental_signal_ids == ("signal-1",)
    assert current.to_dict() == current.to_dict()


def test_risk_matrix_combines_drying_and_sensitivity() -> None:
    high = STRESS.assess_water_deficit_stress(
        stress_request(
            sensitivity=sensitivity_claim(PK.WaterStressSensitivity.HIGH),
            classification=ENV.EnvironmentalSignalClassification.STRONGLY_DRYING,
            signal_completeness=1.0,
        )
    )
    wet = STRESS.assess_water_deficit_stress(
        stress_request(
            sensitivity=sensitivity_claim(PK.WaterStressSensitivity.LOW),
            classification=ENV.EnvironmentalSignalClassification.STRONGLY_WETTING,
            signal_completeness=1.0,
        )
    )
    assert high.dimensions[0].risk is STRESS.PlantStressRiskClassification.VERY_HIGH
    assert wet.dimensions[0].risk is STRESS.PlantStressRiskClassification.NONE


def test_water_requirement_adjusts_one_category_without_becoming_recommendation() -> None:
    high_requirement = STRESS.assess_water_deficit_stress(
        stress_request(water_factor=0.8, signal_completeness=1.0)
    )
    low_requirement = STRESS.assess_water_deficit_stress(
        stress_request(water_factor=0.2, signal_completeness=1.0)
    )
    assert high_requirement.dimensions[0].risk is STRESS.PlantStressRiskClassification.HIGH
    assert low_requirement.dimensions[0].risk is STRESS.PlantStressRiskClassification.LOW
    assert "irrig" not in high_requirement.dimensions[0].explanation.summary.casefold()


def test_missing_sensitivity_returns_typed_non_success() -> None:
    current = STRESS.assess_water_deficit_stress(request())
    dimension = current.dimensions[0]
    assert dimension.status is STRESS.PlantStressRiskStatus.INSUFFICIENT_PLANT_KNOWLEDGE
    assert dimension.risk is STRESS.PlantStressRiskClassification.UNKNOWN


def test_missing_drying_signal_returns_typed_non_success() -> None:
    current_request = stress_request(signal_completeness=1.0)
    heat = signal(
        signal_type=ENV.EnvironmentalSignalType.HEAT_EXPOSURE,
        classification=ENV.EnvironmentalSignalClassification.HIGH,
    )
    current = STRESS.assess_water_deficit_stress(
        replace(current_request, environmental_report=report(signals=(heat,)))
    )
    assert (
        current.dimensions[0].status
        is STRESS.PlantStressRiskStatus.INSUFFICIENT_ENVIRONMENTAL_EVIDENCE
    )


def test_incomplete_evidence_is_partial_or_unavailable_by_policy() -> None:
    partial = STRESS.assess_water_deficit_stress(stress_request())
    strict_request = stress_request()
    strict_request = replace(
        strict_request,
        policy=replace(
            strict_request.policy,
            partial_evidence_behavior=STRESS.PartialEvidenceBehavior.REQUIRE_COMPLETE,
        ),
    )
    strict = STRESS.assess_water_deficit_stress(strict_request)
    assert partial.dimensions[0].status is STRESS.PlantStressRiskStatus.PARTIAL
    assert strict.dimensions[0].status is STRESS.PlantStressRiskStatus.UNAVAILABLE


def test_optional_highest_available_aggregation_is_explicit() -> None:
    current_request = stress_request(signal_completeness=1.0)
    current_request = replace(
        current_request,
        policy=replace(
            current_request.policy,
            overall_risk_aggregation=STRESS.OverallRiskAggregation.HIGHEST_AVAILABLE,
        ),
    )
    current = STRESS.assess_water_deficit_stress(current_request)
    assert current.overall_risk is current.dimensions[0].risk
