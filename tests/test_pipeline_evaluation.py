"""Tests for synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module
from tests.test_execution import execution_request

controllers = load_integration_module("controllers")
execution = load_integration_module("execution")
landscape = load_integration_module("landscape")
pipeline = load_integration_module("pipeline")
pipeline_runtime = load_integration_module("pipeline.runtime_monitoring")
scientific_inputs = load_integration_module("scientific_inputs")


def snapshot(*, configured: bool = True) -> Any:
    now = datetime(2026, 8, 6, 6, 0, tzinfo=UTC)
    area = controllers.IrrigationArea(
        area_id="area-1",
        controller_id="controller-1",
        slot_number=1,
        name="Zone 1",
        enabled=True,
        configured=configured,
        state=controllers.IrrigationAreaState.IDLE,
    )
    controller = controllers.IrrigationController(
        controller_id="controller-1",
        binding=controllers.VendorBinding(provider="rachio", native_id="native-1"),
        name="Controller",
        availability=controllers.ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=1,
        watering_observation_quality=controllers.ObservationQuality.CONFIRMED,
        capabilities=controllers.ControllerCapabilities(),
        areas=(area,),
    )
    return controllers.ControllerRegistrySnapshot(
        provider="rachio",
        account_id="account",
        account_name=None,
        controllers=(controller,),
        observation=controllers.ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=5),
            source="polling",
            quality=controllers.ObservationQuality.CONFIRMED,
        ),
    )


def profile(
    *, complete: bool = True, configured_context: bool = False
) -> Any:
    source = landscape.ProfileValueSource.USER
    unknown = landscape.ProfileValueSource.UNKNOWN
    return landscape.LandscapeProfile(
        schema_version=1,
        areas=(
            landscape.IrrigationAreaProfile(
                area_id="area-1",
                display_name=landscape.ProfileValue("Zone 1", source, 100),
                plant_type=landscape.ProfileValue(
                    landscape.PlantType.TREE if complete else landscape.PlantType.UNKNOWN,
                    source if complete else unknown,
                    100 if complete else 0,
                ),
                plant_description=landscape.ProfileValue(
                    "Bermudagrass" if configured_context else None,
                    source if configured_context else unknown,
                    100 if configured_context else 0,
                ),
                irrigation_method=landscape.ProfileValue(
                    landscape.IrrigationMethod.DRIP,
                    source,
                    100,
                ),
                sun_exposure=landscape.ProfileValue(
                    landscape.SunExposure.FULL_SUN,
                    source,
                    100,
                ),
                slope_percent=landscape.ProfileValue(0.0, source, 100),
                soil_texture=landscape.ProfileValue(
                    landscape.SoilTexture.LOAM,
                    source,
                    100,
                ),
                soil_description=landscape.ProfileValue(None, unknown, 0),
                root_depth_inches=landscape.ProfileValue(24.0, source, 100),
                application_rate_inches_per_hour=landscape.ProfileValue(
                    0.5, source, 100
                ),
                distribution_efficiency=landscape.ProfileValue(0.9, source, 100),
                establishment_stage=landscape.ProfileValue(
                    landscape.EstablishmentStage.ESTABLISHED
                    if configured_context
                    else landscape.EstablishmentStage.UNKNOWN,
                    source if configured_context else unknown,
                    100 if configured_context else 0,
                ),
            ),
        ),
    )



def inputs_snapshot(*, ready: bool = True, area_count: int = 1) -> Any:
    weather = (
        scientific_inputs.WeatherInputSnapshot(
            entity_id="weather.forecast_home",
            observed_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
            condition="sunny",
            temperature_celsius=25.0,
            relative_humidity_percent=40.0,
            pressure_hpa=None,
            wind_speed_meters_per_second=None,
            wind_bearing_degrees=None,
            attribution=None,
            known_fact_count=3,
        )
        if ready
        else None
    )
    area_knowledge = tuple(
        scientific_inputs.AreaKnowledgeInput(
            area_id=f"area-{index + 1}",
            requested_identity="Bermudagrass",
            selected_profile_id="pk.species.cynodon_dactylon" if ready else None,
            resolution_confidence=1.0 if ready else 0.0,
            blocker_codes=() if ready else ("plant_knowledge_profile_unresolved",),
        )
        for index in range(area_count)
    )
    return scientific_inputs.ScientificInputSnapshot(
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
        status=(
            scientific_inputs.ScientificInputStatus.READY
            if ready
            else scientific_inputs.ScientificInputStatus.BLOCKED
        ),
        weather=weather,
        area_knowledge=area_knowledge,
        blocker_codes=() if ready else ("weather_entity_unavailable",),
    )

def test_pipeline_snapshot_is_immutable_and_synchronized() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    result = pipeline.build_pipeline_evaluation(
        snapshot(), profile(), inputs_snapshot(), evaluated_at=evaluated_at
    )

    assert result.evaluated_at == evaluated_at
    assert result.observation_snapshot.provider == "rachio"
    assert result.complete_profile_count == 1
    assert result.current_stage is pipeline.PipelineStage.WATER_REQUIREMENT
    assert result.stage(pipeline.PipelineStage.OBSERVATIONS).status is (
        pipeline.PipelineStageStatus.READY
    )
    assert "establishment_stage_not_configured" in result.blocker_codes


def test_incomplete_landscape_is_reported_without_inventing_science() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        inputs_snapshot(ready=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    knowledge = result.stage(pipeline.PipelineStage.KNOWLEDGE)
    assert result.status is pipeline.PipelineEvaluationStatus.PARTIAL
    assert knowledge.status is pipeline.PipelineStageStatus.PARTIAL
    assert "incomplete_landscape_profiles" in knowledge.blocker_codes


def test_no_configured_areas_blocks_pipeline() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(configured=False),
        landscape.LandscapeProfile(schema_version=1, areas=()),
        inputs_snapshot(ready=False, area_count=0),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert result.status is pipeline.PipelineEvaluationStatus.BLOCKED
    assert result.current_stage is pipeline.PipelineStage.KNOWLEDGE
    assert "no_configured_areas" in result.blocker_codes


def test_water_requirement_executes_with_configured_context() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 28, "humidity": 40},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    water = result.stage(pipeline.PipelineStage.WATER_REQUIREMENT)
    assert water.status is pipeline.PipelineStageStatus.PARTIAL
    assert len(result.water_requirements) == 1
    assessment = result.water_requirements[0].assessment
    assert assessment is not None
    assert assessment.value == 0.6
    assert result.water_requirements[0].season.value == "summer"
    assert result.current_stage is pipeline.PipelineStage.WATER_REQUIREMENT


def test_plant_stress_executes_from_current_environmental_context() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert result.environmental_report is not None
    signal_types = {signal.signal_type.value for signal in result.environmental_report.signals}
    assert {"heat_exposure", "freeze_potential", "wind_exposure"} <= signal_types
    assert len(result.plant_stress) == 1
    stress = result.plant_stress[0].assessment
    assert stress is not None
    assert {item.dimension.value for item in stress.dimensions} == {
        "freeze", "heat", "water_deficit"
    }
    assert result.stage(pipeline.PipelineStage.STRESS).status in {
        pipeline.PipelineStageStatus.PARTIAL,
        pipeline.PipelineStageStatus.BLOCKED,
    }
    assert any(
        code.startswith("stress_water_deficit_")
        for code in result.plant_stress[0].blocker_codes
    )


def test_plant_health_preserves_direct_evidence_boundary() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert len(result.plant_health) == 1
    health = result.plant_health[0].assessment
    assert health is not None
    assert health.status.value == "insufficient_direct_evidence"
    assert health.classification.value == "unknown"
    assert health.aggregate_stress_assessment_id == result.plant_stress[0].assessment.assessment_id
    assert result.stage(pipeline.PipelineStage.HEALTH).status is (
        pipeline.PipelineStageStatus.BLOCKED
    )
    assert "plant_health_direct_evidence_required" in result.stage(
        pipeline.PipelineStage.HEALTH
    ).blocker_codes


def test_recommendations_adapt_existing_engine_and_preserve_provenance() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert len(result.recommendations) == 1
    recommendation_result = result.recommendations[0]
    assessment = recommendation_result.assessment
    assert assessment is not None
    assert assessment.status.value == "partial"
    health_assessment = result.plant_health[0].assessment
    stress_assessment = result.plant_stress[0].assessment
    water_assessment = result.water_requirements[0].assessment
    assert health_assessment is not None
    assert stress_assessment is not None
    assert water_assessment is not None
    assert assessment.plant_health_assessment_id == health_assessment.assessment_id
    assert assessment.aggregate_stress_assessment_id == stress_assessment.assessment_id
    assert assessment.water_requirement_assessment_id == water_assessment.assessment_id
    categories = {item.category.value for item in assessment.recommendations}
    assert "inspect" in categories
    for recommendation in assessment.recommendations:
        flags = {item.value for item in recommendation.safety_flags}
        assert "advisory_only" in flags
        assert "no_automatic_execution" in flags
    recommendation_stage = result.stage(pipeline.PipelineStage.RECOMMENDATIONS)
    assert recommendation_stage.status is pipeline.PipelineStageStatus.PARTIAL
    assert "plant_health_direct_evidence_required" in recommendation_stage.blocker_codes
    assert "recommendation_evidence_partial" in recommendation_stage.blocker_codes
    assert result.stage(pipeline.PipelineStage.PLANNING).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )


def test_recommendations_do_not_invent_missing_upstream_assessments() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        inputs_snapshot(ready=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert len(result.recommendations) == 1
    assert result.recommendations[0].assessment is None
    assert result.stage(pipeline.PipelineStage.RECOMMENDATIONS).status is (
        pipeline.PipelineStageStatus.BLOCKED
    )
    assert "recommendations_unavailable" in result.stage(
        pipeline.PipelineStage.RECOMMENDATIONS
    ).blocker_codes


def test_planning_adapts_existing_engine_without_inventing_directives() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert len(result.planning) == 1
    plan = result.planning[0].plan
    recommendation = result.recommendations[0].assessment
    assert plan is not None
    assert recommendation is not None
    assert plan.recommendation_assessment_id == recommendation.assessment_id
    by_recommendation = {action.recommendation_id: action for action in plan.actions}
    for item in recommendation.recommendations:
        action = by_recommendation[item.recommendation_id]
        assert action.supporting_assessment_ids == item.supporting_assessment_ids
        assert action.target_id is None
        assert action.quantity is None
        assert action.runtime_seconds is None
        assert "no_automatic_execution" in action.safety_constraints
        assert action.disposition.value in {"manual_only", "blocked"}
    planning_stage = result.stage(pipeline.PipelineStage.PLANNING)
    assert planning_stage.status is pipeline.PipelineStageStatus.PARTIAL
    assert result.stage(pipeline.PipelineStage.SCHEDULING).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )


def test_planning_does_not_invent_missing_recommendation_assessment() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        inputs_snapshot(ready=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert len(result.planning) == 1
    assert result.planning[0].plan is None
    planning_stage = result.stage(pipeline.PipelineStage.PLANNING)
    assert planning_stage.status is pipeline.PipelineStageStatus.BLOCKED
    assert "planning_unavailable" in planning_stage.blocker_codes


def test_scheduling_adapts_existing_engine_without_inventing_windows() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert len(result.scheduling) == 1
    schedule = result.scheduling[0].schedule
    plan = result.planning[0].plan
    assert schedule is not None
    assert plan is not None
    assert schedule.plan_id == plan.plan_id
    assert schedule.status.value == "partial"
    by_plan_action = {item.plan_action_id: item for item in schedule.actions}
    for action in plan.actions:
        scheduled = by_plan_action[action.action_id]
        assert scheduled.source_action == action
        assert scheduled.starts_at is None
        assert scheduled.ends_at is None
        assert scheduled.window_id is None
        assert scheduled.disposition.value in {"manual_only", "blocked"}
    assert result.stage(pipeline.PipelineStage.SCHEDULING).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )
    assert result.stage(pipeline.PipelineStage.EXECUTION).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )


def test_scheduling_does_not_invent_missing_plan() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        inputs_snapshot(ready=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert len(result.scheduling) == 1
    assert result.scheduling[0].schedule is None
    scheduling_stage = result.stage(pipeline.PipelineStage.SCHEDULING)
    assert scheduling_stage.status is pipeline.PipelineStageStatus.BLOCKED
    assert "scheduling_unavailable" in scheduling_stage.blocker_codes


def test_execution_adapts_existing_engine_without_hardware_control() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert len(result.execution) == 1
    execution_plan = result.execution[0].execution_plan
    schedule = result.scheduling[0].schedule
    assert execution_plan is not None
    assert schedule is not None
    assert execution_plan.source_schedule == schedule
    assert execution_plan.schedule_id == schedule.schedule_id
    assert execution_plan.status.value == "no_commands"
    assert execution_plan.commands == ()
    assert result.stage(pipeline.PipelineStage.EXECUTION).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )
    assert result.stage(pipeline.PipelineStage.RUNTIME_MONITORING).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )


def test_execution_does_not_invent_missing_schedule() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        inputs_snapshot(ready=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert len(result.execution) == 1
    assert result.execution[0].execution_plan is None
    execution_stage = result.stage(pipeline.PipelineStage.EXECUTION)
    assert execution_stage.status is pipeline.PipelineStageStatus.BLOCKED
    assert "execution_unavailable" in execution_stage.blocker_codes

def test_runtime_monitoring_adapts_existing_engine_without_live_outcomes() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    configured_profile = profile(configured_context=True)
    normalized = scientific_inputs.build_scientific_input_snapshot(
        landscape=configured_profile,
        weather_entities=((
            "weather.home",
            "sunny",
            {"temperature": 38, "humidity": 40, "wind_speed": 8, "wind_speed_unit": "m/s"},
            evaluated_at,
        ),),
        evaluated_at=evaluated_at,
        country_code="US",
        latitude=34.0,
        elevation_meters=100.0,
    )
    result = pipeline.build_pipeline_evaluation(
        snapshot(), configured_profile, normalized, evaluated_at=evaluated_at
    )

    assert len(result.runtime_monitoring) == 1
    runtime_result = result.runtime_monitoring[0]
    report = runtime_result.report
    execution_plan = result.execution[0].execution_plan
    assert report is not None
    assert execution_plan is not None
    assert report.source_execution_plan == execution_plan
    assert report.execution_plan_id == execution_plan.execution_plan_id
    assert report.status.value == "no_execution"
    assert report.expected_command_count == 0
    assert report.acknowledged_command_count == 0
    assert report.unresolved_command_count == 0
    assert result.stage(pipeline.PipelineStage.RUNTIME_MONITORING).status is (
        pipeline.PipelineStageStatus.PARTIAL
    )
    assert "runtime_no_execution" in runtime_result.blocker_codes


def test_runtime_monitoring_does_not_invent_missing_execution_plan() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        inputs_snapshot(ready=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert len(result.runtime_monitoring) == 1
    assert result.runtime_monitoring[0].report is None
    runtime_stage = result.stage(pipeline.PipelineStage.RUNTIME_MONITORING)
    assert runtime_stage.status is pipeline.PipelineStageStatus.BLOCKED
    assert "runtime_monitoring_unavailable" in runtime_stage.blocker_codes

def test_runtime_monitoring_refuses_to_invent_results_for_runnable_commands() -> None:
    execution_plan = execution.build_execution_plan(execution_request())
    assert execution_plan.status.value == "ready"
    evaluations = pipeline_runtime.build_area_runtime_reports(
        (
            pipeline.AreaExecutionEvaluation(
                area_id="area-1",
                execution_plan=execution_plan,
            ),
        ),
        snapshot(),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert len(evaluations) == 1
    assert evaluations[0].report is None
    assert "runtime_command_results_unavailable" in evaluations[0].blocker_codes
