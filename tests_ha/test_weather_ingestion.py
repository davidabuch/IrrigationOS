"""Regression tests for v1.0.47 weather evidence ingestion."""

from datetime import UTC, datetime, timedelta

from custom_components.irrigationos.weather.ingestion import (
    build_ha_hourly_forecast,
    build_open_meteo_observations,
)

NOW = datetime(2026, 8, 18, 18, 30, tzinfo=UTC)


def test_ha_hourly_forecast_normalizes_live_provider_shape_and_units() -> None:
    issued = NOW - timedelta(minutes=15)
    result = build_ha_hourly_forecast(
        entity_id="weather.forecast_home",
        issued_at=issued,
        records=[
            {
                "datetime": "2026-08-18T19:00:00+00:00",
                "condition": "partlycloudy",
                "temperature": 88,
                "humidity": 42,
                "precipitation": 0.1,
                "cloud_coverage": 63.3,
                "wind_speed": 7.15,
                "wind_bearing": 194.3,
                "uv_index": 9.9,
            },
            {
                "datetime": "2026-08-18T20:00:00+00:00",
                "condition": "sunny",
                "temperature": 89,
                "humidity": 44,
                "precipitation": 0.0,
                "cloud_coverage": 10.0,
                "wind_speed": 6.0,
                "wind_bearing": 190.0,
                "uv_index": 8.0,
            },
        ],
        temperature_unit="°F",
        wind_speed_unit="mph",
        precipitation_unit="in",
        now=NOW,
    )
    assert result is not None
    assert result.generated_at == issued
    assert len(result.hourly_forecasts) == 2
    first = result.hourly_forecasts[0]
    assert first.facts.precipitation_mm.value == 2.54
    assert round(float(first.facts.air_temperature_celsius.value or 0), 3) == 31.111
    assert round(float(first.facts.wind_speed_meters_per_second.value or 0), 3) == 3.196
    assert first.facts.precipitation_probability_percent.value is None


def test_open_meteo_ingestion_admits_only_recent_completed_et0_and_rain() -> None:
    result = build_open_meteo_observations(
        {
            "hourly": {
                "time": [
                    "2026-08-18T17:00",
                    "2026-08-18T18:00",
                    "2026-08-18T19:00",
                ],
                "precipitation": [0.0, 1.2, 9.9],
                "et0_fao_evapotranspiration": [0.3, 0.4, 9.9],
            }
        },
        now=NOW,
    )
    assert result is not None
    assert [item.facts.precipitation_mm.value for item in result.observations] == [0.0, 1.2]
    assert [
        item.facts.reference_evapotranspiration_mm.value
        for item in result.observations
    ] == [0.3, 0.4]
    assert result.observations[0].observed_at == datetime(2026, 8, 18, 16, 0, tzinfo=UTC)
    assert result.ends_at == datetime(2026, 8, 18, 18, 0, tzinfo=UTC)


def test_ha_forecast_zero_precipitation_is_known_not_missing() -> None:
    result = build_ha_hourly_forecast(
        entity_id="weather.forecast_home",
        issued_at=NOW,
        records=[{"datetime": "2026-08-18T19:00:00+00:00", "precipitation": 0.0}],
        temperature_unit="°F",
        wind_speed_unit="mph",
        precipitation_unit="in",
        now=NOW,
    )
    assert result is not None
    assert result.hourly_forecasts[0].facts.precipitation_mm.value == 0.0
    assert result.hourly_forecasts[0].facts.precipitation_mm.is_known


def test_open_meteo_mismatched_hourly_arrays_fail_closed() -> None:
    result = build_open_meteo_observations(
        {
            "hourly": {
                "time": ["2026-08-18T17:00", "2026-08-18T18:00"],
                "precipitation": [0.0],
                "et0_fao_evapotranspiration": [0.3, 0.4],
            }
        },
        now=NOW,
    )
    assert result is None


def test_ha_forecast_unknown_units_fail_closed_instead_of_guessing() -> None:
    result = build_ha_hourly_forecast(
        entity_id="weather.forecast_home",
        issued_at=NOW,
        records=[
            {
                "datetime": "2026-08-18T19:00:00+00:00",
                "temperature": 88,
                "precipitation": 0.1,
                "wind_speed": 7.15,
            }
        ],
        temperature_unit="mystery",
        wind_speed_unit="mystery",
        precipitation_unit="mystery",
        now=NOW,
    )
    assert result is not None
    facts = result.hourly_forecasts[0].facts
    assert facts.air_temperature_celsius.value is None
    assert facts.wind_speed_meters_per_second.value is None
    assert facts.precipitation_mm.value is None
