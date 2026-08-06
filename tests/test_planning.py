"""Behavioral tests for the deterministic Planning Engine."""
from dataclasses import replace
from typing import Any, cast

from tests.helpers import load_integration_module
from tests.test_recommendations import aggregate_with_risk, recommendation_request

PLANNING = load_integration_module("planning")
RECOMMENDATIONS = load_integration_module("recommendations")
STRESS = load_integration_module("plant_stress")


def recommendation_assessment(*, water_deficit: bool = False) -> Any:
    request = recommendation_request(
        stress=(
            aggregate_with_risk(
                STRESS.PlantStressDimension.WATER_DEFICIT,
                STRESS.PlantStressRiskClassification.HIGH,
            )
            if water_deficit
            else None
        )
    )
    return RECOMMENDATIONS.assess_recommendations(request)


def planning_request(
    *,
    assessment: Any | None = None,
    directives: tuple[Any, ...] = (),
) -> Any:
    current = recommendation_assessment() if assessment is None else assessment
    return PLANNING.PlanningRequest(
        request_id="planning-request-1",
        recommendations=current,
        directives=directives,
        policy=PLANNING.PlanningPolicy(
            policy_id="planning-policy",
            policy_version="1.0.0",
        ),
        created_at=current.created_at,
    )


def irrigation_recommendation(assessment: Any) -> Any:
    return next(
        item for item in assessment.recommendations
        if item.category is RECOMMENDATIONS.RecommendationCategory.ADJUST_IRRIGATION
    )


def test_no_action_becomes_manual_machine_readable_plan_action() -> None:
    plan = PLANNING.build_irrigation_plan(planning_request())
    assert plan.status is PLANNING.PlanStatus.PARTIAL
    assert plan.actions[0].action_type is PLANNING.PlanActionType.NO_ACTION
    assert plan.actions[0].disposition is PLANNING.PlanExecutionDisposition.MANUAL_ONLY


def test_irrigation_without_directive_is_not_executable() -> None:
    assessment = recommendation_assessment(water_deficit=True)
    plan = PLANNING.build_irrigation_plan(planning_request(assessment=assessment))
    action = next(
        item
        for item in plan.actions
        if item.action_type is PLANNING.PlanActionType.IRRIGATE
    )
    assert action.disposition is PLANNING.PlanExecutionDisposition.BLOCKED
    assert action.blocking_reasons == (
        "missing calculated runtime",
        "missing irrigation quantity",
        "missing planning directive",
        "missing target",
    ) or action.blocking_reasons == (
        "missing irrigation quantity",
        "missing planning directive",
        "missing target",
    )
    assert any("missing target" in issue for issue in plan.unresolved_issues)


def test_quantitative_directive_is_preserved_without_recalculation() -> None:
    assessment = recommendation_assessment(water_deficit=True)
    recommendation = irrigation_recommendation(assessment)
    directive = PLANNING.PlanningDirective(
        recommendation_id=recommendation.recommendation_id,
        target_id="zone-7",
        quantity=12.5,
        quantity_unit=PLANNING.PlanQuantityUnit.MILLIMETERS,
        runtime_seconds=1800,
        cycle_count=3,
        soak_seconds=900,
    )
    plan = PLANNING.build_irrigation_plan(
        planning_request(assessment=assessment, directives=(directive,))
    )
    action = next(
        item
        for item in plan.actions
        if item.action_type is PLANNING.PlanActionType.IRRIGATE
    )
    assert action.target_id == "zone-7"
    assert action.quantity == 12.5
    assert action.runtime_seconds == 1800
    assert action.cycle_count == 3
    assert action.soak_seconds == 900


def test_complete_irrigation_action_remains_manual_only() -> None:
    assessment = recommendation_assessment(water_deficit=True)
    recommendation = irrigation_recommendation(assessment)
    directive = PLANNING.PlanningDirective(
        recommendation_id=recommendation.recommendation_id,
        target_id="zone-7",
        quantity=12.5,
        quantity_unit=PLANNING.PlanQuantityUnit.MILLIMETERS,
        runtime_seconds=1800,
    )
    plan = PLANNING.build_irrigation_plan(
        planning_request(assessment=assessment, directives=(directive,))
    )
    action = next(
        item
        for item in plan.actions
        if item.action_type is PLANNING.PlanActionType.IRRIGATE
    )
    assert action.blocking_reasons == ()
    assert action.disposition is PLANNING.PlanExecutionDisposition.MANUAL_ONLY
    assert "no_automatic_execution" in action.safety_constraints


def test_unknown_directive_is_reported_and_does_not_create_action() -> None:
    directive = PLANNING.PlanningDirective(
        recommendation_id="recommendation:unknown",
        target_id="zone-1",
    )
    plan = PLANNING.build_irrigation_plan(planning_request(directives=(directive,)))
    assert len(plan.actions) == 1
    assert (
        "directive references unknown recommendation recommendation:unknown"
        in plan.unresolved_issues
    )


def test_actions_preserve_recommendation_provenance() -> None:
    assessment = recommendation_assessment(water_deficit=True)
    plan = PLANNING.build_irrigation_plan(planning_request(assessment=assessment))
    by_id = {item.recommendation_id: item for item in plan.actions}
    for recommendation in assessment.recommendations:
        assert (
            by_id[recommendation.recommendation_id].supporting_assessment_ids
            == recommendation.supporting_assessment_ids
        )


def test_plan_serialization_is_deterministic() -> None:
    plan = PLANNING.build_irrigation_plan(planning_request())
    assert plan.to_dict() == plan.to_dict()
    assert plan.to_dict()["recommendation_assessment_id"].startswith(
        "recommendation-assessment"
    )


def test_models_are_immutable() -> None:
    plan = PLANNING.build_irrigation_plan(planning_request())
    try:
        cast(Any, plan).status = PLANNING.PlanStatus.READY
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("planning model was mutable")


def test_request_rejects_untyped_recommendation_assessment() -> None:
    request = planning_request()
    try:
        replace(request, recommendations={})
    except ValueError as error:
        assert "RecommendationAssessment" in str(error)
    else:
        raise AssertionError("invalid recommendation input was accepted")


def test_directive_requires_quantity_unit() -> None:
    try:
        PLANNING.PlanningDirective(
            recommendation_id="recommendation-1",
            target_id="zone-1",
            quantity=1.0,
        )
    except ValueError as error:
        assert "quantity_unit" in str(error)
    else:
        raise AssertionError("quantity without unit was accepted")


def test_single_cycle_rejects_soak_time() -> None:
    try:
        PLANNING.PlanningDirective(
            recommendation_id="recommendation-1",
            target_id="zone-1",
            soak_seconds=60,
        )
    except ValueError as error:
        assert "multiple cycles" in str(error)
    else:
        raise AssertionError("single-cycle soak was accepted")


def test_directives_require_deterministic_ordering() -> None:
    first = PLANNING.PlanningDirective("recommendation-b", "zone-2")
    second = PLANNING.PlanningDirective("recommendation-a", "zone-1")
    try:
        planning_request(directives=(first, second))
    except ValueError as error:
        assert "deterministic" in str(error)
    else:
        raise AssertionError("unordered directives were accepted")
