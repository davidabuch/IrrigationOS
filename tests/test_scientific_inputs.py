"""Tests for deterministic Home Assistant scientific-input normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tests.helpers import load_integration_module

landscape = load_integration_module("landscape")
inputs = load_integration_module("scientific_inputs")


def profile(*, plant_description: str = "Bermudagrass") -> Any:
    source = landscape.ProfileValueSource.USER
    return landscape.LandscapeProfile(
        schema_version=1,
        areas=(
            landscape.IrrigationAreaProfile(
                area_id="area-1",
                display_name=landscape.ProfileValue("Lawn", source, 100),
                plant_type=landscape.ProfileValue(
                    landscape.PlantType.TURF_WARM_SEASON, source, 100
                ),
                plant_description=landscape.ProfileValue(
                    plant_description, source, 100
                ),
                irrigation_method=landscape.ProfileValue(
                    landscape.IrrigationMethod.SPRAY, source, 100
                ),
                sun_exposure=landscape.ProfileValue(
                    landscape.SunExposure.FULL_SUN, source, 100
                ),
                slope_percent=landscape.ProfileValue(0.0, source, 100),
                soil_texture=landscape.ProfileValue(
                    landscape.SoilTexture.LOAM, source, 100
                ),
                soil_description=landscape.ProfileValue("Loam", source, 100),
                root_depth_inches=landscape.ProfileValue(8.0, source, 100),
                application_rate_inches_per_hour=landscape.ProfileValue(
                    1.5, source, 100
                ),
                distribution_efficiency=landscape.ProfileValue(0.8, source, 100),
            ),
        ),
    )


def test_single_weather_entity_and_curated_knowledge_are_normalized() -> None:
    evaluated_at = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    result = inputs.build_scientific_input_snapshot(
        landscape=profile(),
        weather_entities=(
            (
                "weather.forecast_home",
                "sunny",
                {
                    "temperature": 86,
                    "temperature_unit": "°F",
                    "humidity": 35,
                    "pressure": 29.92,
                    "pressure_unit": "inHg",
                    "wind_speed": 10,
                    "wind_speed_unit": "mph",
                    "wind_bearing": 270,
                },
            ),
        ),
        evaluated_at=evaluated_at,
    )

    assert result.status is inputs.ScientificInputStatus.READY
    assert result.weather is not None
    assert round(result.weather.temperature_celsius, 2) == 30.0
    assert round(result.weather.wind_speed_meters_per_second, 3) == 4.47
    assert result.area_knowledge[0].selected_profile_id == "pk.species.cynodon_dactylon"


def test_multiple_weather_entities_are_not_guessed() -> None:
    evaluated_at = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    result = inputs.build_scientific_input_snapshot(
        landscape=profile(),
        weather_entities=(
            ("weather.one", "sunny", {"temperature": 25, "humidity": 40}),
            ("weather.two", "cloudy", {"temperature": 24, "humidity": 50}),
        ),
        evaluated_at=evaluated_at,
    )

    assert result.status is inputs.ScientificInputStatus.BLOCKED
    assert result.weather is None
    assert "multiple_weather_entities_require_selection" in result.blocker_codes


def test_unresolved_plant_identity_is_reported() -> None:
    result = inputs.build_scientific_input_snapshot(
        landscape=profile(plant_description="Unlisted specimen"),
        weather_entities=(
            ("weather.forecast_home", "sunny", {"temperature": 25, "humidity": 40}),
        ),
        evaluated_at=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
    )

    assert result.status is inputs.ScientificInputStatus.PARTIAL
    assert result.area_knowledge[0].selected_profile_id is None
    assert "plant_knowledge_profile_unresolved" in result.blocker_codes
