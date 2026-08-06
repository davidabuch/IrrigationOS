"""Behavioral tests for deterministic aggregate plant stress assessment."""

from dataclasses import replace
from typing import Any

import pytest

from tests.helpers import load_integration_module
from tests.test_plant_stress_models import dimension, request

STRESS = load_integration_module("plant_stress")


def aggregate_request(*, highest: bool = True) -> Any:
    base = request()
    return replace(
        base,
        policy=replace(
            base.policy,
            enabled_dimensions=(
                STRESS.PlantStressDimension.FREEZE,
                STRESS.PlantStressDimension.HEAT,
                STRESS.PlantStressDimension.WATER_DEFICIT,
            ),
            overall_risk_aggregation=(
                STRESS.OverallRiskAggregation.HIGHEST_AVAILABLE
                if highest
                else STRESS.OverallRiskAggregation.NONE
            ),
        ),
    )


def assessment(
    current_request: Any,
    stress_dimension: Any,
    risk: Any,
    *,
    status: Any | None = None,
    confidence: float = 0.9,
) -> Any:
    current = dimension()
    return replace(
        current,
        assessment_id=f"assessment-{stress_dimension.value}",
        dimension=stress_dimension,
        status=status or STRESS.PlantStressRiskStatus.AVAILABLE,
        risk=risk,
        confidence=replace(current.confidence, confidence=confidence),
        selected_profile_id=current_request.selected_profile_id,
        policy_id=current_request.policy.policy_id,
        policy_version=current_request.policy.policy_version,
        environmental_report_id=current_request.environmental_report.report_id,
        water_requirement_assessment_id=(
            current_request.water_requirement_assessment.assessment_id
            if stress_dimension is STRESS.PlantStressDimension.WATER_DEFICIT
            else None
        ),
    )


def all_dimensions(current_request: Any) -> tuple[Any, Any, Any]:
    return (
        assessment(
            current_request,
            STRESS.PlantStressDimension.FREEZE,
            STRESS.PlantStressRiskClassification.LOW,
        ),
        assessment(
            current_request,
            STRESS.PlantStressDimension.HEAT,
            STRESS.PlantStressRiskClassification.HIGH,
        ),
        assessment(
            current_request,
            STRESS.PlantStressDimension.WATER_DEFICIT,
            STRESS.PlantStressRiskClassification.MODERATE,
        ),
    )


def test_highest_available_risk_is_selected_without_averaging() -> None:
    current_request = aggregate_request()
    current = STRESS.aggregate_plant_stress(current_request, all_dimensions(current_request))
    assert current.overall_status is STRESS.PlantStressRiskStatus.AVAILABLE
    assert current.overall_risk is STRESS.PlantStressRiskClassification.HIGH
    assert current.explanation.reason_codes == (
        "driven_by_heat",
        "highest_available_risk_selected",
        "independent_dimensions_preserved",
    )


def test_policy_can_withhold_overall_risk() -> None:
    current_request = aggregate_request(highest=False)
    current = STRESS.aggregate_plant_stress(current_request, all_dimensions(current_request))
    assert current.overall_risk is None
    assert "overall_risk_not_authorized" in current.explanation.reason_codes


def test_tied_driving_dimensions_are_all_explained() -> None:
    current_request = aggregate_request()
    dimensions = list(all_dimensions(current_request))
    dimensions[2] = replace(dimensions[2], risk=STRESS.PlantStressRiskClassification.HIGH)
    current = STRESS.aggregate_plant_stress(current_request, tuple(dimensions))
    assert "driven_by_heat" in current.explanation.reason_codes
    assert "driven_by_water_deficit" in current.explanation.reason_codes


def test_partial_dimension_makes_aggregate_partial_but_retains_highest_risk() -> None:
    current_request = aggregate_request()
    dimensions = list(all_dimensions(current_request))
    dimensions[0] = replace(
        dimensions[0],
        status=STRESS.PlantStressRiskStatus.INSUFFICIENT_ENVIRONMENTAL_EVIDENCE,
        risk=STRESS.PlantStressRiskClassification.UNKNOWN,
        unresolved_issues=("freeze evidence unavailable",),
    )
    current = STRESS.aggregate_plant_stress(current_request, tuple(dimensions))
    assert current.overall_status is STRESS.PlantStressRiskStatus.PARTIAL
    assert current.overall_risk is STRESS.PlantStressRiskClassification.HIGH
    assert current.unresolved_issues == ("freeze evidence unavailable",)


def test_aggregate_confidence_is_conservative_and_completeness_is_count_based() -> None:
    current_request = aggregate_request()
    dimensions = list(all_dimensions(current_request))
    dimensions[1] = replace(
        dimensions[1],
        confidence=STRESS.PlantStressRiskConfidence(
            confidence=0.6,
            completeness=0.5,
            known_required_input_count=1,
            required_input_count=2,
        ),
    )
    current = STRESS.aggregate_plant_stress(current_request, tuple(dimensions))
    assert current.confidence.confidence == 0.6
    assert current.confidence.known_required_input_count == 5
    assert current.confidence.required_input_count == 6
    assert current.confidence.completeness == 5 / 6


def test_dimensions_are_sorted_and_serialization_is_deterministic() -> None:
    current_request = aggregate_request()
    dimensions = tuple(reversed(all_dimensions(current_request)))
    current = STRESS.aggregate_plant_stress(current_request, dimensions)
    assert tuple(item.dimension.value for item in current.dimensions) == (
        "freeze",
        "heat",
        "water_deficit",
    )
    assert current.to_dict() == current.to_dict()


def test_missing_or_duplicate_dimensions_are_rejected() -> None:
    current_request = aggregate_request()
    dimensions = all_dimensions(current_request)
    with pytest.raises(ValueError, match="exactly match"):
        STRESS.aggregate_plant_stress(current_request, dimensions[:2])
    with pytest.raises(ValueError, match="duplicate"):
        STRESS.aggregate_plant_stress(
            current_request,
            (dimensions[0], dimensions[0], dimensions[2]),
        )
