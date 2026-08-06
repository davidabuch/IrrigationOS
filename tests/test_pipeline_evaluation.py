"""Tests for synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers")
landscape = load_integration_module("landscape")
pipeline = load_integration_module("pipeline")


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


def test_pipeline_snapshot_is_immutable_and_synchronized() -> None:
    evaluated_at = datetime(2026, 8, 6, 6, 5, tzinfo=UTC)
    result = pipeline.build_pipeline_evaluation(
        snapshot(), profile(), evaluated_at=evaluated_at
    )

    assert result.evaluated_at == evaluated_at
    assert result.observation_snapshot.provider == "rachio"
    assert result.complete_profile_count == 1
    assert result.current_stage is pipeline.PipelineStage.WATER_REQUIREMENT
    assert result.stage(pipeline.PipelineStage.OBSERVATIONS).status is (
        pipeline.PipelineStageStatus.READY
    )
    assert "scientific_inputs_not_integrated" in result.blocker_codes


def test_incomplete_landscape_is_reported_without_inventing_science() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(),
        profile(complete=False),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    knowledge = result.stage(pipeline.PipelineStage.KNOWLEDGE)
    assert result.status is pipeline.PipelineEvaluationStatus.PARTIAL
    assert knowledge.status is pipeline.PipelineStageStatus.PARTIAL
    assert knowledge.blocker_codes == ("incomplete_landscape_profiles",)


def test_no_configured_areas_blocks_pipeline() -> None:
    result = pipeline.build_pipeline_evaluation(
        snapshot(configured=False),
        landscape.LandscapeProfile(schema_version=1, areas=()),
        evaluated_at=datetime(2026, 8, 6, 6, 5, tzinfo=UTC),
    )

    assert result.status is pipeline.PipelineEvaluationStatus.BLOCKED
    assert result.current_stage is pipeline.PipelineStage.KNOWLEDGE
    assert "no_configured_areas" in result.blocker_codes
