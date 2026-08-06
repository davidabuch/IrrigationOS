"""Tests for synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers")
landscape = load_integration_module("landscape")
pipeline = load_integration_module("pipeline")
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


def profile(*, complete: bool = True) -> Any:
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
                plant_description=landscape.ProfileValue(None, unknown, 0),
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
    assert "plant_water_context_not_configured" in result.blocker_codes


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
