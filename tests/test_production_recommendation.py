"""Behavioral tests for the canonical production-recommendation contract."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import load_integration_module
from tests.test_pipeline_evaluation import inputs_snapshot, profile, snapshot

controllers = load_integration_module("controllers")
pipeline = load_integration_module("pipeline")
production = load_integration_module("production_recommendation")
water_balance = load_integration_module("quantitative_water_balance")


def _evaluation() -> Any:
    observed = snapshot()
    controller = observed.controllers[0]
    area = replace(
        controller.areas[0],
        binding=controllers.VendorBinding("rachio", "provider-zone-secret"),
    )
    observed = replace(observed, controllers=(replace(controller, areas=(area,)),))
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    return pipeline.build_pipeline_evaluation(
        observed,
        profile(),
        inputs_snapshot(ready=False),
        evaluated_at=evaluated_at,
    )


def test_insufficient_evidence_never_invents_depth_runtime_or_schedule() -> None:
    result = production.build_production_recommendations(_evaluation())
    assert result.state is production.ProductionRecommendationState.INSUFFICIENT_EVIDENCE
    assert len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert recommendation.target.to_dict() == {"controller_slot": 1, "area_slot": 1}
    assert recommendation.scientific_need is production.ScientificNeedState.UNAVAILABLE
    assert recommendation.delivery_readiness is production.DeliveryReadinessState.INCOMPLETE
    assert recommendation.irrigation_depth is None
    assert recommendation.estimated_runtime_seconds is None
    assert recommendation.scheduling_window is None
    assert recommendation.execution_authorized is False
    assert "plant_profile_unresolved" in recommendation.blocker_codes
    assert "target_irrigation_depth_unavailable" in recommendation.blocker_codes
    assert "provider-zone-secret" not in repr(result.to_dict())


def test_restart_state_requires_fresh_recomputation_and_is_not_authority() -> None:
    result = production.ProductionRecommendationSnapshot.not_available()
    assert result.state is production.ProductionRecommendationState.NOT_AVAILABLE
    assert result.calculated_at is None
    assert result.recommendations == ()
    assert result.execution_authorized is False


def test_serialization_is_deterministic_and_models_are_immutable() -> None:
    first = production.build_production_recommendations(_evaluation())
    second = production.build_production_recommendations(_evaluation())
    assert first == second
    assert first.to_dict() == second.to_dict()
    with pytest.raises(FrozenInstanceError):
        first.recommendations[0].confidence = 1.0


def test_quantity_preserves_scalar_and_range_shapes() -> None:
    scalar = production.RecommendationQuantity(unit="millimeters", scalar=2.5)
    bounded = production.RecommendationQuantity(
        unit="millimeters", minimum=1.0, typical=2.0, maximum=3.0
    )
    assert scalar.scalar == 2.5
    assert bounded.minimum == 1.0
    with pytest.raises(ValueError):
        production.RecommendationQuantity(
            unit="millimeters", scalar=2.0, minimum=1.0, maximum=3.0
        )


def test_stale_weather_is_not_refreshed_by_a_new_pipeline_evaluation() -> None:
    evaluation = _evaluation()
    weather = replace(
        inputs_snapshot().weather,
        observed_at=evaluation.evaluated_at - timedelta(hours=3),
    )
    stale_inputs = replace(evaluation.scientific_inputs, weather=weather)
    stale_evaluation = replace(evaluation, scientific_inputs=stale_inputs)
    result = production.build_production_recommendations(stale_evaluation)
    assert "weather_observation_stale" in result.recommendations[0].blocker_codes


def test_package_has_no_physical_operation_or_provider_transport_imports() -> None:
    root = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "irrigationos"
        / "production_recommendation"
    )
    imports: set[str] = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
    forbidden = (
        "first_live_delivery",
        "supervised_operation",
        "unattended_canary",
        "adapters.rachio",
    )
    assert not any(name in imported for imported in imports for name in forbidden)


def test_quantitative_deficit_changes_scientific_need_but_never_authority() -> None:
    evaluation = _evaluation()
    target = load_integration_module("production_targets").ProductionTarget(1, 1)
    balance = water_balance.calculate_production_area_water_balance(
        water_balance.ProductionAreaWaterBalanceRequest(
            target=target,
            window_start=evaluation.evaluated_at - timedelta(days=1),
            window_end=evaluation.evaluated_at,
            calculated_at=evaluation.evaluated_at,
            reference_et_mm=water_balance.WaterQuantity.millimeters(10),
            plant_factor=water_balance.RatioQuantity(scalar=0.5),
            observed_precipitation_mm=water_balance.WaterQuantity.millimeters(0),
            quantified_irrigation_credit_mm=water_balance.WaterQuantity.millimeters(0),
            unquantified_irrigation_session_ids=(),
            effective_precipitation_policy=water_balance.EffectivePrecipitationPolicy(
                policy_id="water.effective.test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            forecast=None,
            opening_balance_state=water_balance.OpeningBalanceState.RECONSTRUCTED,
            opening_deficit_mm=water_balance.WaterQuantity.millimeters(0),
            root_zone_available_water_mm=water_balance.WaterQuantity.millimeters(10),
            allowable_depletion_fraction=water_balance.RatioQuantity(scalar=0.4),
        )
    )
    balances = water_balance.WaterBalanceSnapshot(
        state=water_balance.WaterBalanceState.AVAILABLE,
        calculated_at=evaluation.evaluated_at,
        balances=(balance,),
        reason_codes=("actual_water_balance_calculated",),
        blocker_codes=(),
    )

    result = production.build_production_recommendations(
        evaluation, water_balances=balances
    )
    recommendation = result.recommendations[0]
    assert recommendation.scientific_need.value == "indicated"
    assert recommendation.irrigation_depth.scalar == 5
    assert "target_irrigation_depth_unavailable" not in recommendation.blocker_codes
    assert recommendation.estimated_runtime_seconds is None
    assert recommendation.scheduling_window is None
    assert recommendation.execution_authorized is False


def test_positive_deficit_below_trigger_does_not_recommend_irrigation() -> None:
    evaluation = _evaluation()
    target = load_integration_module("production_targets").ProductionTarget(1, 1)
    balance = water_balance.calculate_production_area_water_balance(
        water_balance.ProductionAreaWaterBalanceRequest(
            target=target,
            window_start=evaluation.evaluated_at - timedelta(days=1),
            window_end=evaluation.evaluated_at,
            calculated_at=evaluation.evaluated_at,
            reference_et_mm=water_balance.WaterQuantity.millimeters(3),
            plant_factor=water_balance.RatioQuantity(scalar=1),
            observed_precipitation_mm=water_balance.WaterQuantity.millimeters(0),
            quantified_irrigation_credit_mm=water_balance.WaterQuantity.millimeters(0),
            unquantified_irrigation_session_ids=(),
            effective_precipitation_policy=None,
            forecast=None,
            opening_balance_state=water_balance.OpeningBalanceState.RECONSTRUCTED,
            opening_deficit_mm=water_balance.WaterQuantity.millimeters(0),
            root_zone_available_water_mm=water_balance.WaterQuantity.millimeters(20),
            allowable_depletion_fraction=water_balance.RatioQuantity(scalar=0.4),
        )
    )
    balances = water_balance.WaterBalanceSnapshot(
        state=water_balance.WaterBalanceState.AVAILABLE,
        calculated_at=evaluation.evaluated_at,
        balances=(balance,),
        reason_codes=("actual_water_balance_calculated",),
        blocker_codes=(),
    )

    recommendation = production.build_production_recommendations(
        evaluation, water_balances=balances
    ).recommendations[0]

    assert recommendation.state is (
        production.ProductionRecommendationState.NO_IRRIGATION_RECOMMENDED
    )
    assert recommendation.scientific_need is production.ScientificNeedState.NOT_INDICATED
    assert recommendation.irrigation_depth is None
    assert recommendation.estimated_runtime_seconds is None
    assert recommendation.execution_authorized is False
