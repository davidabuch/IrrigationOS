"""Behavioral tests for deterministic environmental water and drying analysis."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

WEATHER = load_integration_module("weather.models")
ENGINE = load_integration_module("environment.engine")

EnvironmentalWeatherFacts = WEATHER.EnvironmentalWeatherFacts
ForecastWindow = WEATHER.ForecastWindow
HistoricalWeatherObservation = WEATHER.HistoricalWeatherObservation
HourlyWeatherForecast = WEATHER.HourlyWeatherForecast
ObservationWindow = WEATHER.ObservationWindow
WeatherCondition = WEATHER.WeatherCondition
WeatherFact = WEATHER.WeatherFact
WeatherProvenance = WEATHER.WeatherProvenance
WeatherQualityMetadata = WEATHER.WeatherQualityMetadata
WeatherQualityStatus = WEATHER.WeatherQualityStatus
WeatherSourceType = WEATHER.WeatherSourceType
WeatherVerificationStatus = WEATHER.WeatherVerificationStatus

DryingClassification = ENGINE.DryingClassification
EnvironmentalCalculationPolicy = ENGINE.EnvironmentalCalculationPolicy
analyze_water_and_drying = ENGINE.analyze_water_and_drying

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def fact(value: object, timestamp: datetime, confidence: float = 0.9) -> Any:
    return WeatherFact(
        value=value,
        confidence=confidence,
        provenance=WeatherProvenance(
            source="test",
            source_type=WeatherSourceType.STATION,
        ),
        verification_status=WeatherVerificationStatus.PROVIDER_VALIDATED,
        observed_at=timestamp,
        quality=WeatherQualityMetadata(status=WeatherQualityStatus.GOOD),
    )


def unknown(timestamp: datetime) -> Any:
    return WeatherFact(
        value=None,
        confidence=0,
        provenance=WeatherProvenance(
            source="test",
            source_type=WeatherSourceType.OTHER,
        ),
        verification_status=WeatherVerificationStatus.UNVERIFIED,
        observed_at=timestamp,
        quality=WeatherQualityMetadata(
            status=WeatherQualityStatus.UNAVAILABLE,
            reason="missing",
        ),
    )


def facts(timestamp: datetime, precipitation: Any, et0: Any) -> Any:
    values = {
        "air_temperature_celsius": fact(25.0, timestamp),
        "relative_humidity_percent": fact(50.0, timestamp),
        "dew_point_celsius": fact(12.0, timestamp),
        "wind_speed_meters_per_second": fact(2.0, timestamp),
        "wind_gust_meters_per_second": fact(3.0, timestamp),
        "wind_direction_degrees": fact(180.0, timestamp),
        "precipitation_mm": precipitation,
        "snowfall_mm": fact(0.0, timestamp),
        "precipitation_probability_percent": fact(10.0, timestamp),
        "rain_rate_mm_per_hour": fact(0.0, timestamp),
        "cloud_cover_percent": fact(20.0, timestamp),
        "solar_radiation_watts_per_square_meter": fact(500.0, timestamp),
        "uv_index": fact(5.0, timestamp),
        "barometric_pressure_hpa": fact(1012.0, timestamp),
        "visibility_meters": fact(10000.0, timestamp),
        "condition": fact(WeatherCondition.CLEAR, timestamp),
        "sunrise": fact(timestamp.replace(hour=6), timestamp),
        "sunset": fact(timestamp.replace(hour=19), timestamp),
        "reference_evapotranspiration_mm": et0,
    }
    return EnvironmentalWeatherFacts(**values)


def observation(timestamp: datetime, record_id: str, precipitation: Any, et0: Any) -> Any:
    return HistoricalWeatherObservation(
        observation_id=record_id,
        location_id="property-1",
        observed_at=timestamp,
        received_at=timestamp + timedelta(seconds=10),
        facts=facts(timestamp, precipitation, et0),
    )


def forecast(timestamp: datetime, record_id: str, precipitation: Any, et0: Any) -> Any:
    return HourlyWeatherForecast(
        forecast_id=record_id,
        location_id="property-1",
        issued_at=NOW,
        valid_from=timestamp,
        valid_until=timestamp + timedelta(hours=1),
        facts=facts(timestamp, precipitation, et0),
    )


def test_observed_totals_balance_and_drying_are_deterministic() -> None:
    first = observation(NOW, "obs-1", fact(0.0, NOW), fact(2.0, NOW))
    later = NOW + timedelta(hours=1)
    second = observation(later, "obs-2", fact(1.0, later), fact(2.0, later))
    window = ObservationWindow(
        window_id="obs-window",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=2),
        observations=(first, second),
    )

    analysis = analyze_water_and_drying(
        report_id="report-1",
        created_at=NOW + timedelta(hours=2),
        observation_window=window,
    )

    assert analysis.observed is not None
    assert analysis.observed.precipitation.total_mm == 1.0
    assert analysis.observed.reference_evapotranspiration.total_mm == 4.0
    assert analysis.observed.balance_mm == -3.0
    assert analysis.observed.classification is DryingClassification.WETTING
    assert analysis.report.to_dict() == analysis.report.to_dict()


def test_missing_precipitation_never_becomes_zero() -> None:
    item = observation(NOW, "obs-1", unknown(NOW), fact(2.0, NOW))
    window = ObservationWindow(
        window_id="obs-window",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        observations=(item,),
    )
    analysis = analyze_water_and_drying(
        report_id="report-1",
        created_at=NOW + timedelta(hours=1),
        observation_window=window,
    )
    assert analysis.observed is not None
    assert analysis.observed.precipitation.total_mm is None
    assert analysis.observed.balance_mm is None
    assert analysis.observed.classification is DryingClassification.UNAVAILABLE


def test_forecast_totals_are_separate_from_observed_totals() -> None:
    first_time = NOW + timedelta(hours=1)
    second_time = NOW + timedelta(hours=2)
    first = forecast(first_time, "fc-1", fact(2.0, first_time), fact(0.5, first_time))
    second = forecast(second_time, "fc-2", fact(1.0, second_time), fact(0.5, second_time))
    window = ForecastWindow(
        window_id="fc-window",
        location_id="property-1",
        generated_at=NOW,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=3),
        hourly_forecasts=(first, second),
    )
    analysis = analyze_water_and_drying(
        report_id="report-1",
        created_at=NOW + timedelta(hours=3),
        forecast_window=window,
    )
    assert analysis.observed is None
    assert analysis.forecast is not None
    assert analysis.forecast.precipitation.total_mm == 3.0
    assert analysis.forecast.reference_evapotranspiration.total_mm == 1.0
    assert analysis.forecast.balance_mm == 2.0
    assert analysis.forecast.classification is DryingClassification.DRYING


@pytest.mark.parametrize(
    ("balance", "classification"),
    [
        (-5.0, DryingClassification.STRONGLY_WETTING),
        (-1.0, DryingClassification.WETTING),
        (1.0, DryingClassification.BALANCED),
        (5.0, DryingClassification.DRYING),
        (5.01, DryingClassification.STRONGLY_DRYING),
    ],
)
def test_policy_threshold_boundaries(balance: float, classification: Any) -> None:
    assert EnvironmentalCalculationPolicy().classify(balance) is classification


def test_policy_thresholds_must_be_strictly_increasing() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        EnvironmentalCalculationPolicy(
            strongly_wetting_maximum_mm=-1,
            wetting_maximum_mm=-1,
        )


def test_location_mismatch_is_rejected() -> None:
    item = observation(NOW, "obs-1", fact(0.0, NOW), fact(1.0, NOW))
    observation_window = ObservationWindow(
        window_id="obs-window",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        observations=(item,),
    )
    forecast_time = NOW + timedelta(hours=1)
    fc = forecast(forecast_time, "fc-1", fact(0.0, forecast_time), fact(1.0, forecast_time))
    fc = HourlyWeatherForecast(
        forecast_id=fc.forecast_id,
        location_id="property-2",
        issued_at=fc.issued_at,
        valid_from=fc.valid_from,
        valid_until=fc.valid_until,
        facts=fc.facts,
    )
    forecast_window = ForecastWindow(
        window_id="fc-window",
        location_id="property-2",
        generated_at=NOW,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=2),
        hourly_forecasts=(fc,),
    )
    with pytest.raises(ValueError, match="share one location"):
        analyze_water_and_drying(
            report_id="report-1",
            created_at=NOW + timedelta(hours=2),
            observation_window=observation_window,
            forecast_window=forecast_window,
        )


def test_engine_has_no_irrigation_command_surface() -> None:
    for name in ("start", "stop", "run", "schedule", "execute", "irrigate"):
        assert not hasattr(ENGINE, name)
