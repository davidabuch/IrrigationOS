"""Behavioral tests for deterministic advisory recommendations."""

from dataclasses import replace
from typing import Any

from tests.helpers import load_integration_module
from tests.test_plant_health import evidence
from tests.test_plant_health import request as health_request
from tests.test_plant_stress_models import aggregate
from tests.test_plant_stress_models import dimension as base_dimension
from tests.test_plant_water_requirement_models import assessment as water_assessment

RECOMMENDATIONS = load_integration_module("recommendations")
HEALTH = load_integration_module("plant_health")
STRESS = load_integration_module("plant_stress")


def healthy_assessment() -> Any:
    return HEALTH.assess_plant_health(
        health_request(
            evidence(
                "evidence-1",
                HEALTH.PlantHealthIndicator.VIGOR,
                HEALTH.PlantHealthSeverity.NONE,
            ),
            evidence(
                "evidence-2",
                HEALTH.PlantHealthIndicator.RECOVERY,
                HEALTH.PlantHealthSeverity.MILD,
            ),
        )
    )


def recommendation_request(
    *,
    health: Any | None = None,
    stress: Any | None = None,
    minimum_confidence: float = 0.5,
) -> Any:
    health_value = healthy_assessment() if health is None else health
    stress_value = aggregate() if stress is None else stress
    return RECOMMENDATIONS.RecommendationRequest(
        request_id="recommendation-request-1",
        plant_health=health_value,
        aggregate_stress=stress_value,
        water_requirement=water_assessment(),
        policy=RECOMMENDATIONS.RecommendationPolicy(
            policy_id="recommendation-policy",
            policy_version="1.0.0",
            minimum_confidence=minimum_confidence,
        ),
        created_at=health_value.created_at,
    )


def dimension_assessment(dimension: Any, risk: Any) -> Any:
    current = base_dimension()
    return replace(
        current,
        assessment_id=f"assessment-{dimension.value}",
        dimension=dimension,
        risk=risk,
        selected_profile_id="pk.profile.acacia_example",
        environmental_report_id="report-1",
        water_requirement_assessment_id=(
            "water-assessment-1"
            if dimension is STRESS.PlantStressDimension.WATER_DEFICIT
            else None
        ),
    )


def aggregate_with_risk(dimension: Any, risk: Any) -> Any:
    dimensions = [
        dimension_assessment(
            STRESS.PlantStressDimension.FREEZE,
            STRESS.PlantStressRiskClassification.LOW,
        ),
        dimension_assessment(
            STRESS.PlantStressDimension.HEAT,
            STRESS.PlantStressRiskClassification.LOW,
        ),
        dimension_assessment(
            STRESS.PlantStressDimension.WATER_DEFICIT,
            STRESS.PlantStressRiskClassification.LOW,
        ),
    ]
    for index, current in enumerate(dimensions):
        if current.dimension is dimension:
            dimensions[index] = dimension_assessment(dimension, risk)
    return replace(
        aggregate(),
        dimensions=tuple(sorted(dimensions, key=lambda item: item.dimension.value)),
        overall_risk=risk,
    )


def categories(assessment: Any) -> tuple[Any, ...]:
    return tuple(item.category for item in assessment.recommendations)


def test_healthy_plant_without_high_stress_returns_no_action() -> None:
    current = RECOMMENDATIONS.assess_recommendations(recommendation_request())
    assert current.status is RECOMMENDATIONS.RecommendationStatus.AVAILABLE
    assert categories(current) == (RECOMMENDATIONS.RecommendationCategory.NO_ACTION,)


def test_insufficient_health_evidence_recommends_inspection() -> None:
    health = HEALTH.assess_plant_health(health_request())
    current = RECOMMENDATIONS.assess_recommendations(
        recommendation_request(health=health)
    )
    assert current.status is RECOMMENDATIONS.RecommendationStatus.PARTIAL
    assert RECOMMENDATIONS.RecommendationCategory.INSPECT in categories(current)


def test_critical_health_recommends_urgent_expert_review() -> None:
    health = HEALTH.assess_plant_health(
        health_request(
            evidence(
                "evidence-1",
                HEALTH.PlantHealthIndicator.TISSUE_DAMAGE,
                HEALTH.PlantHealthSeverity.CRITICAL,
            )
        )
    )
    current = RECOMMENDATIONS.assess_recommendations(
        recommendation_request(health=health)
    )
    recommendation = current.recommendations[0]
    assert recommendation.category is RECOMMENDATIONS.RecommendationCategory.SEEK_EXPERT_REVIEW
    assert recommendation.priority is RECOMMENDATIONS.RecommendationPriority.URGENT


def test_high_water_deficit_risk_recommends_irrigation_review() -> None:
    stress = aggregate_with_risk(
        STRESS.PlantStressDimension.WATER_DEFICIT,
        STRESS.PlantStressRiskClassification.HIGH,
    )
    current = RECOMMENDATIONS.assess_recommendations(
        recommendation_request(stress=stress)
    )
    assert RECOMMENDATIONS.RecommendationCategory.ADJUST_IRRIGATION in categories(current)


def test_very_high_heat_and_freeze_risks_produce_independent_recommendations() -> None:
    heat = dimension_assessment(
        STRESS.PlantStressDimension.HEAT,
        STRESS.PlantStressRiskClassification.VERY_HIGH,
    )
    freeze = dimension_assessment(
        STRESS.PlantStressDimension.FREEZE,
        STRESS.PlantStressRiskClassification.VERY_HIGH,
    )
    water = dimension_assessment(
        STRESS.PlantStressDimension.WATER_DEFICIT,
        STRESS.PlantStressRiskClassification.LOW,
    )
    stress = replace(
        aggregate(),
        dimensions=tuple(sorted((freeze, heat, water), key=lambda item: item.dimension.value)),
        overall_risk=STRESS.PlantStressRiskClassification.VERY_HIGH,
    )
    current = RECOMMENDATIONS.assess_recommendations(
        recommendation_request(stress=stress)
    )
    assert RECOMMENDATIONS.RecommendationCategory.PROTECT_FROM_FREEZE in categories(current)
    assert RECOMMENDATIONS.RecommendationCategory.PROTECT_FROM_HEAT in categories(current)


def test_outputs_are_advisory_only_and_serialize_deterministically() -> None:
    current = RECOMMENDATIONS.assess_recommendations(recommendation_request())
    recommendation = current.recommendations[0]
    assert RECOMMENDATIONS.RecommendationSafetyFlag.ADVISORY_ONLY in recommendation.safety_flags
    assert (
        RECOMMENDATIONS.RecommendationSafetyFlag.NO_AUTOMATIC_EXECUTION
        in recommendation.safety_flags
    )
    assert current.to_dict() == current.to_dict()


def test_request_rejects_untyped_upstream_assessments() -> None:
    current = recommendation_request()
    try:
        replace(current, plant_health={})
    except ValueError as error:
        assert "PlantHealthAssessment" in str(error)
    else:  # pragma: no cover
        raise AssertionError("invalid plant health input was accepted")
