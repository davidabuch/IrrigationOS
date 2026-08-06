"""Behavioral tests for deterministic freeze stress-risk assessment."""

from dataclasses import replace
from typing import Any

from tests.helpers import load_integration_module
from tests.test_environment_models import report, signal
from tests.test_plant_stress_models import request

PK = load_integration_module("plant_knowledge")
ENV = load_integration_module("environment.models")
STRESS = load_integration_module("plant_stress")


def minimum_temperature_claim(value: float = -3.9, confidence: float = 0.9) -> Any:
    """Build one approved effective minimum-temperature claim."""
    return PK.EffectivePlantKnowledgeClaim(
        claim_id="pk.claim.example.minimum_temperature_celsius",
        field_path="environment.minimum_temperature_celsius",
        value=value,
        unit=PK.KnowledgeUnit.CELSIUS,
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


def freeze_request(
    *,
    minimum_claim: Any = None,
    classification: Any = None,
    signal_completeness: float = 1.0,
) -> Any:
    """Build a valid request with minimum temperature and freeze potential."""
    base = request()
    knowledge = replace(
        base.knowledge_resolution,
        effective_claims=tuple(
            sorted(
                (
                    *base.knowledge_resolution.effective_claims,
                    minimum_claim or minimum_temperature_claim(),
                ),
                key=lambda claim: claim.field_path,
            )
        ),
    )
    freeze = signal(
        signal_type=ENV.EnvironmentalSignalType.FREEZE_POTENTIAL,
        classification=classification or ENV.EnvironmentalSignalClassification.HIGH,
        confidence=replace(
            signal().confidence,
            completeness=signal_completeness,
            known_fact_count=4 if signal_completeness == 1.0 else 3,
            unavailable_quality_count=0 if signal_completeness == 1.0 else 1,
            good_quality_count=3 if signal_completeness == 1.0 else 2,
        ),
    )
    return replace(
        base,
        knowledge_resolution=knowledge,
        environmental_report=report(signals=(freeze,)),
        policy=replace(
            base.policy,
            enabled_dimensions=(STRESS.PlantStressDimension.FREEZE,),
        ),
    )


def test_available_freeze_assessment_is_deterministic_and_preserves_provenance() -> None:
    current = STRESS.assess_freeze_stress(freeze_request())
    dimension = current.dimensions[0]
    assert dimension.status is STRESS.PlantStressRiskStatus.AVAILABLE
    assert dimension.risk is STRESS.PlantStressRiskClassification.MODERATE
    assert dimension.plant_knowledge_claim_ids == (
        "pk.claim.example.minimum_temperature_celsius",
    )
    assert dimension.environmental_signal_ids == ("signal-1",)
    assert dimension.water_requirement_assessment_id is None
    assert current.to_dict() == current.to_dict()


def test_freeze_matrix_combines_potential_and_hardiness() -> None:
    tender = STRESS.assess_freeze_stress(
        freeze_request(
            minimum_claim=minimum_temperature_claim(7.0),
            classification=ENV.EnvironmentalSignalClassification.HIGH,
        )
    )
    hardy = STRESS.assess_freeze_stress(
        freeze_request(
            minimum_claim=minimum_temperature_claim(-15.0),
            classification=ENV.EnvironmentalSignalClassification.HIGH,
        )
    )
    assert tender.dimensions[0].risk is STRESS.PlantStressRiskClassification.VERY_HIGH
    assert hardy.dimensions[0].risk is STRESS.PlantStressRiskClassification.LOW


def test_missing_minimum_temperature_returns_typed_non_success() -> None:
    base = request()
    current = STRESS.assess_freeze_stress(
        replace(
            base,
            policy=replace(base.policy, enabled_dimensions=(STRESS.PlantStressDimension.FREEZE,)),
        )
    )
    assert (
        current.dimensions[0].status
        is STRESS.PlantStressRiskStatus.INSUFFICIENT_PLANT_KNOWLEDGE
    )
    assert current.dimensions[0].risk is STRESS.PlantStressRiskClassification.UNKNOWN


def test_missing_freeze_signal_returns_typed_non_success() -> None:
    current_request = freeze_request()
    heat = signal(
        signal_type=ENV.EnvironmentalSignalType.HEAT_EXPOSURE,
        classification=ENV.EnvironmentalSignalClassification.HIGH,
    )
    current = STRESS.assess_freeze_stress(
        replace(current_request, environmental_report=report(signals=(heat,)))
    )
    assert (
        current.dimensions[0].status
        is STRESS.PlantStressRiskStatus.INSUFFICIENT_ENVIRONMENTAL_EVIDENCE
    )


def test_conflicting_minimum_temperature_returns_conflicting_evidence() -> None:
    conflicting = replace(minimum_temperature_claim(), conflict_unresolved=True)
    current = STRESS.assess_freeze_stress(freeze_request(minimum_claim=conflicting))
    assert current.dimensions[0].status is STRESS.PlantStressRiskStatus.CONFLICTING_EVIDENCE


def test_incomplete_freeze_evidence_is_partial_or_unavailable_by_policy() -> None:
    partial_request = freeze_request(signal_completeness=0.75)
    partial = STRESS.assess_freeze_stress(partial_request)
    strict = STRESS.assess_freeze_stress(
        replace(
            partial_request,
            policy=replace(
                partial_request.policy,
                partial_evidence_behavior=STRESS.PartialEvidenceBehavior.REQUIRE_COMPLETE,
            ),
        )
    )
    assert partial.dimensions[0].status is STRESS.PlantStressRiskStatus.PARTIAL
    assert strict.dimensions[0].status is STRESS.PlantStressRiskStatus.UNAVAILABLE


def test_optional_highest_available_freeze_aggregation_is_explicit() -> None:
    current_request = freeze_request()
    current = STRESS.assess_freeze_stress(
        replace(
            current_request,
            policy=replace(
                current_request.policy,
                overall_risk_aggregation=STRESS.OverallRiskAggregation.HIGHEST_AVAILABLE,
            ),
        )
    )
    assert current.overall_risk is current.dimensions[0].risk
