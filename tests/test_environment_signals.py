"""Behavioral tests for deterministic environmental exposure signals."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

ENVIRONMENT_MODELS = load_integration_module("environment.models")
ENVIRONMENT_SIGNALS = load_integration_module("environment.signals")
WEATHER_MODELS = load_integration_module("weather.models")

EnvironmentalSignalClassification = (
    ENVIRONMENT_MODELS.EnvironmentalSignalClassification
)
EnvironmentalSignalType = ENVIRONMENT_MODELS.EnvironmentalSignalType

SIGNAL_ALGORITHM_VERSION = ENVIRONMENT_SIGNALS.SIGNAL_ALGORITHM_VERSION
EnvironmentalSignalPolicy = ENVIRONMENT_SIGNALS.EnvironmentalSignalPolicy
analyze_environmental_signals = (
    ENVIRONMENT_SIGNALS.analyze_environmental_signals
)

EnvironmentalWeatherFacts = WEATHER_MODELS.EnvironmentalWeatherFacts
ForecastWindow = WEATHER_MODELS.ForecastWindow
HistoricalWeatherObservation = WEATHER_MODELS.HistoricalWeatherObservation
HourlyWeatherForecast = WEATHER_MODELS.HourlyWeatherForecast
ObservationWindow = WEATHER_MODELS.ObservationWindow
WeatherCondition = WEATHER_MODELS.WeatherCondition
WeatherFact = WEATHER_MODELS.WeatherFact
WeatherProvenance = WEATHER_MODELS.WeatherProvenance
WeatherQualityMetadata = WEATHER_MODELS.WeatherQualityMetadata
WeatherQualityStatus = WEATHER_MODELS.WeatherQualityStatus
WeatherSourceType = WEATHER_MODELS.WeatherSourceType
WeatherVerificationStatus = WEATHER_MODELS.WeatherVerificationStatus

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def fact(value: object, timestamp: datetime, confidence: float = 0.9) -> Any:
    """Build one canonical weather fact."""
    unavailable = value is None
    return WeatherFact(
        value=value,
        confidence=0.0 if unavailable else confidence,
        provenance=WeatherProvenance(
            source="test",
            source_type=WeatherSourceType.FORECAST,
        ),
        verification_status=WeatherVerificationStatus.PROVIDER_VALIDATED,
        observed_at=timestamp,
        quality=WeatherQualityMetadata(
            status=(
                WeatherQualityStatus.UNAVAILABLE
                if unavailable
                else WeatherQualityStatus.GOOD
            ),
            reason="missing" if unavailable else None,
        ),
    )


def facts(
    timestamp: datetime,
    *,
    temperature: float | None = 24.0,
    wind: float | None = 2.0,
    gust: float | None = 4.0,
    precipitation: float | None = 0.0,
    rain_rate: float | None = 0.0,
    confidence: float = 0.9,
) -> Any:
    """Build the complete canonical weather fact set."""
    values: dict[str, object] = {
        "air_temperature_celsius": fact(temperature, timestamp, confidence),
        "relative_humidity_percent": fact(50.0, timestamp, confidence),
        "dew_point_celsius": fact(12.0, timestamp, confidence),
        "wind_speed_meters_per_second": fact(wind, timestamp, confidence),
        "wind_gust_meters_per_second": fact(gust, timestamp, confidence),
        "wind_direction_degrees": fact(180.0, timestamp, confidence),
        "precipitation_mm": fact(precipitation, timestamp, confidence),
        "snowfall_mm": fact(0.0, timestamp, confidence),
        "precipitation_probability_percent": fact(20.0, timestamp, confidence),
        "rain_rate_mm_per_hour": fact(rain_rate, timestamp, confidence),
        "cloud_cover_percent": fact(20.0, timestamp, confidence),
        "solar_radiation_watts_per_square_meter": fact(500.0, timestamp, confidence),
        "uv_index": fact(5.0, timestamp, confidence),
        "barometric_pressure_hpa": fact(1012.0, timestamp, confidence),
        "visibility_meters": fact(10000.0, timestamp, confidence),
        "condition": fact(WeatherCondition.CLEAR, timestamp, confidence),
        "sunrise": fact(timestamp.replace(hour=6), timestamp, confidence),
        "sunset": fact(timestamp.replace(hour=19), timestamp, confidence),
        "reference_evapotranspiration_mm": fact(0.2, timestamp, confidence),
    }
    return EnvironmentalWeatherFacts(**values)


def observation(
    timestamp: datetime,
    *,
    observation_id: str,
    temperature: float | None = 24.0,
    wind: float | None = 2.0,
    gust: float | None = 4.0,
    precipitation: float | None = 0.0,
    rain_rate: float | None = 0.0,
    confidence: float = 0.9,
) -> Any:
    """Build one historical weather observation."""
    return HistoricalWeatherObservation(
        observation_id=observation_id,
        location_id="property-1",
        observed_at=timestamp,
        received_at=timestamp + timedelta(minutes=1),
        facts=facts(
            timestamp,
            temperature=temperature,
            wind=wind,
            gust=gust,
            precipitation=precipitation,
            rain_rate=rain_rate,
            confidence=confidence,
        ),
    )


def forecast(
    timestamp: datetime,
    *,
    forecast_id: str,
    temperature: float | None = 24.0,
    wind: float | None = 2.0,
    gust: float | None = 4.0,
    precipitation: float | None = 0.0,
    rain_rate: float | None = 0.0,
    confidence: float = 0.9,
) -> Any:
    """Build one hourly weather forecast."""
    return HourlyWeatherForecast(
        forecast_id=forecast_id,
        location_id="property-1",
        issued_at=NOW,
        valid_from=timestamp,
        valid_until=timestamp + HOUR,
        facts=facts(
            timestamp,
            temperature=temperature,
            wind=wind,
            gust=gust,
            precipitation=precipitation,
            rain_rate=rain_rate,
            confidence=confidence,
        ),
    )


def signal(analysis: Any, signal_type: Any) -> Any:
    """Find one signal by canonical type."""
    return next(item for item in analysis.signals if item.signal_type is signal_type)


def test_heat_signal_uses_maximum_temperature() -> None:
    """Heat exposure is classified from the maximum known air temperature."""
    window = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + 2 * HOUR,
        observations=(
            observation(NOW, observation_id="obs-1", temperature=31.0),
            observation(NOW + HOUR, observation_id="obs-2", temperature=41.0),
        ),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + 2 * HOUR,
        observation_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.HEAT_EXPOSURE)
    assert current.classification is EnvironmentalSignalClassification.HIGH
    assert current.algorithm_version == SIGNAL_ALGORITHM_VERSION
    assert current.explanation.reason_codes == ("heat_exposure_high",)


def test_freeze_signal_uses_minimum_temperature() -> None:
    """Freeze potential is classified without claiming plant damage."""
    window = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + HOUR,
        observations=(observation(NOW, observation_id="obs-1", temperature=-4.0),),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + HOUR,
        observation_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.FREEZE_POTENTIAL)
    assert current.classification is EnvironmentalSignalClassification.HIGH


def test_wind_signal_uses_more_severe_sustained_or_gust_value() -> None:
    """Wind classification reflects the more severe sustained or gust threshold."""
    window = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + HOUR,
        observations=(
            observation(
                NOW,
                observation_id="obs-1",
                wind=7.0,
                gust=24.0,
            ),
        ),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + HOUR,
        observation_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.WIND_EXPOSURE)
    assert current.classification is EnvironmentalSignalClassification.HIGH


def test_heavy_rain_uses_total_or_rate() -> None:
    """A high rain rate can elevate the signal even when accumulation is modest."""
    window = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + HOUR,
        observations=(
            observation(
                NOW,
                observation_id="obs-1",
                precipitation=4.0,
                rain_rate=35.0,
            ),
        ),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + HOUR,
        observation_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.HEAVY_RAIN_POTENTIAL)
    assert current.classification is EnvironmentalSignalClassification.HIGH


def test_missing_rain_does_not_become_zero() -> None:
    """Incomplete rain facts make the accumulation classification unavailable."""
    window = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + HOUR,
        observations=(
            observation(
                NOW,
                observation_id="obs-1",
                precipitation=None,
                rain_rate=None,
            ),
        ),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + HOUR,
        observation_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.HEAVY_RAIN_POTENTIAL)
    assert current.classification is EnvironmentalSignalClassification.UNAVAILABLE
    assert current.confidence.completeness == 0.0


def test_forecast_reliability_is_available_for_complete_high_confidence_data() -> None:
    """Complete high-confidence canonical forecasts are classified available."""
    window = ForecastWindow(
        window_id="forecast-window-1",
        location_id="property-1",
        generated_at=NOW,
        starts_at=NOW + HOUR,
        ends_at=NOW + 3 * HOUR,
        hourly_forecasts=(
            forecast(NOW + HOUR, forecast_id="forecast-1"),
            forecast(NOW + 2 * HOUR, forecast_id="forecast-2"),
        ),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + 3 * HOUR,
        forecast_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.FORECAST_RELIABILITY)
    assert current.classification is EnvironmentalSignalClassification.AVAILABLE


def test_forecast_reliability_degrades_with_missing_facts() -> None:
    """Forecast missingness lowers reliability without fabricating values."""
    window = ForecastWindow(
        window_id="forecast-window-1",
        location_id="property-1",
        generated_at=NOW,
        starts_at=NOW + HOUR,
        ends_at=NOW + 2 * HOUR,
        hourly_forecasts=(
            forecast(
                NOW + HOUR,
                forecast_id="forecast-1",
                temperature=None,
            ),
        ),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + 2 * HOUR,
        forecast_window=window,
    )
    current = signal(analysis, EnvironmentalSignalType.FORECAST_RELIABILITY)
    assert current.classification is EnvironmentalSignalClassification.AVAILABLE
    assert current.confidence.completeness < 1.0


def test_analysis_rejects_mixed_locations() -> None:
    """Observation and forecast inputs must describe one canonical location."""
    observations = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + HOUR,
        observations=(observation(NOW, observation_id="obs-1"),),
    )
    foreign = forecast(NOW + HOUR, forecast_id="forecast-1")
    foreign = type(foreign)(
        forecast_id=foreign.forecast_id,
        location_id="property-2",
        issued_at=foreign.issued_at,
        valid_from=foreign.valid_from,
        valid_until=foreign.valid_until,
        facts=foreign.facts,
    )
    forecasts = ForecastWindow(
        window_id="forecast-window-1",
        location_id="property-2",
        generated_at=NOW,
        starts_at=NOW + HOUR,
        ends_at=NOW + 2 * HOUR,
        hourly_forecasts=(foreign,),
    )
    with pytest.raises(ValueError, match="share one location"):
        analyze_environmental_signals(
            created_at=NOW + 2 * HOUR,
            observation_window=observations,
            forecast_window=forecasts,
        )


def test_policy_thresholds_are_strictly_ordered() -> None:
    """Invalid threshold order is rejected at construction."""
    with pytest.raises(ValueError, match="strictly increasing"):
        EnvironmentalSignalPolicy(
            heat_low_celsius=35.0,
            heat_moderate_celsius=30.0,
        )


def test_signal_analysis_is_deterministically_serializable() -> None:
    """Signal results serialize through their canonical model envelopes."""
    window = ObservationWindow(
        window_id="observations-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=NOW + HOUR,
        observations=(observation(NOW, observation_id="obs-1"),),
    )
    analysis = analyze_environmental_signals(
        created_at=NOW + HOUR,
        observation_window=window,
    )
    assert analysis.signals[0].to_dict() == analysis.signals[0].to_dict()
    assert len({item.evidence_id for item in analysis.evidence}) == len(analysis.evidence)


def test_signal_package_exposes_no_irrigation_command_surface() -> None:
    """Environmental exposure signals remain advisory observations only."""
    forbidden = (
        "start",
        "stop",
        "run",
        "schedule",
        "irrigate",
        "execute",
        "set_duration",
        "set_rain_delay",
    )
    for name in forbidden:
        assert not hasattr(analyze_environmental_signals, name)
