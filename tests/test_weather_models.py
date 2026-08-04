"""Behavioral tests for the canonical Environmental Weather Domain."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

MODULE = load_integration_module("weather.models")
CurrentWeatherObservation = MODULE.CurrentWeatherObservation
DailyWeatherForecast = MODULE.DailyWeatherForecast
EnvironmentalWeatherFacts = MODULE.EnvironmentalWeatherFacts
ForecastWindow = MODULE.ForecastWindow
HistoricalWeatherObservation = MODULE.HistoricalWeatherObservation
HourlyWeatherForecast = MODULE.HourlyWeatherForecast
ObservationWindow = MODULE.ObservationWindow
WeatherCondition = MODULE.WeatherCondition
WeatherFact = MODULE.WeatherFact
WeatherProvenance = MODULE.WeatherProvenance
WeatherQualityMetadata = MODULE.WeatherQualityMetadata
WeatherQualityStatus = MODULE.WeatherQualityStatus
WeatherSourceType = MODULE.WeatherSourceType
WeatherVerificationStatus = MODULE.WeatherVerificationStatus

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
NEXT_HOUR = NOW + timedelta(hours=1)
TWO_HOURS = NOW + timedelta(hours=2)
NEXT_DAY = NOW + timedelta(days=1)


def quality(
    status: Any = WeatherQualityStatus.GOOD,
    *,
    reason: str | None = None,
) -> Any:
    """Build quality metadata for tests."""
    return WeatherQualityMetadata(
        status=status,
        flags=("quality_controlled",) if status is not WeatherQualityStatus.UNAVAILABLE else (),
        sample_count=1 if status is not WeatherQualityStatus.UNAVAILABLE else None,
        reason=reason,
    )


def fact(
    value: object,
    *,
    observed_at: datetime = NOW,
    confidence: float = 0.9,
    source_type: Any = WeatherSourceType.STATION,
    quality_status: Any = WeatherQualityStatus.GOOD,
    verification: Any = WeatherVerificationStatus.PROVIDER_VALIDATED,
) -> Any:
    """Build a canonical known weather fact."""
    return WeatherFact(
        value=value,
        confidence=confidence,
        provenance=WeatherProvenance(
            source="canonical-test-source",
            source_type=source_type,
            source_reference="source-record-1",
        ),
        verification_status=verification,
        observed_at=observed_at,
        quality=quality(
            quality_status,
            reason=(
                "marked unavailable"
                if quality_status is WeatherQualityStatus.UNAVAILABLE
                else None
            ),
        ),
    )


def unknown(*, observed_at: datetime = NOW) -> Any:
    """Build an explicitly unavailable weather fact."""
    return WeatherFact(
        value=None,
        confidence=0,
        provenance=WeatherProvenance(
            source="canonical-test-source",
            source_type=WeatherSourceType.OTHER,
        ),
        verification_status=WeatherVerificationStatus.UNVERIFIED,
        observed_at=observed_at,
        quality=quality(WeatherQualityStatus.UNAVAILABLE, reason="not supplied"),
    )


def weather_facts(timestamp: datetime = NOW, **changes: object) -> Any:
    """Build the complete canonical fact set at one applicability timestamp."""
    values: dict[str, object] = {
        "air_temperature_celsius": fact(24.5, observed_at=timestamp),
        "relative_humidity_percent": fact(48.0, observed_at=timestamp),
        "dew_point_celsius": fact(12.5, observed_at=timestamp),
        "wind_speed_meters_per_second": fact(3.2, observed_at=timestamp),
        "wind_gust_meters_per_second": fact(5.8, observed_at=timestamp),
        "wind_direction_degrees": fact(245.0, observed_at=timestamp),
        "precipitation_mm": fact(0.0, observed_at=timestamp),
        "snowfall_mm": fact(0.0, observed_at=timestamp),
        "precipitation_probability_percent": fact(
            10.0, observed_at=timestamp, source_type=WeatherSourceType.FORECAST
        ),
        "rain_rate_mm_per_hour": fact(0.0, observed_at=timestamp),
        "cloud_cover_percent": fact(20.0, observed_at=timestamp),
        "solar_radiation_watts_per_square_meter": fact(720.0, observed_at=timestamp),
        "uv_index": fact(6.0, observed_at=timestamp),
        "barometric_pressure_hpa": fact(1012.4, observed_at=timestamp),
        "visibility_meters": fact(16000.0, observed_at=timestamp),
        "condition": fact(WeatherCondition.MOSTLY_CLEAR, observed_at=timestamp),
        "sunrise": fact(
            timestamp.replace(hour=6),
            observed_at=timestamp,
        ),
        "sunset": fact(
            timestamp.replace(hour=19),
            observed_at=timestamp,
        ),
        "reference_evapotranspiration_mm": fact(
            4.8,
            observed_at=timestamp,
            source_type=WeatherSourceType.FORECAST,
        ),
    }
    values.update(changes)
    return EnvironmentalWeatherFacts(**values)


def current_observation(**changes: object) -> Any:
    """Build a current observation."""
    values: dict[str, object] = {
        "observation_id": "current-1",
        "location_id": "property-1",
        "observed_at": NOW,
        "received_at": NOW + timedelta(seconds=30),
        "facts": weather_facts(),
    }
    values.update(changes)
    return CurrentWeatherObservation(**values)


def historical_observation(
    timestamp: datetime = NOW,
    *,
    observation_id: str = "history-1",
    location_id: str = "property-1",
) -> Any:
    """Build a historical point observation."""
    return HistoricalWeatherObservation(
        observation_id=observation_id,
        location_id=location_id,
        observed_at=timestamp,
        received_at=timestamp + timedelta(seconds=30),
        facts=weather_facts(timestamp),
    )


def hourly_forecast(
    valid_from: datetime = NEXT_HOUR,
    *,
    forecast_id: str = "hourly-1",
    location_id: str = "property-1",
    duration: timedelta = timedelta(hours=1),
) -> Any:
    """Build an hourly forecast period."""
    return HourlyWeatherForecast(
        forecast_id=forecast_id,
        location_id=location_id,
        issued_at=NOW,
        valid_from=valid_from,
        valid_until=valid_from + duration,
        facts=weather_facts(valid_from),
    )


def daily_forecast(
    valid_from: datetime = NEXT_DAY,
    *,
    forecast_id: str = "daily-1",
    location_id: str = "property-1",
) -> Any:
    """Build a daily forecast period."""
    return DailyWeatherForecast(
        forecast_id=forecast_id,
        location_id=location_id,
        local_date=valid_from.date(),
        issued_at=NOW,
        valid_from=valid_from,
        valid_until=valid_from + timedelta(days=1),
        facts=weather_facts(valid_from),
        minimum_air_temperature_celsius=fact(16.0, observed_at=valid_from),
        maximum_air_temperature_celsius=fact(29.0, observed_at=valid_from),
    )


def test_current_observation_serializes_deterministically() -> None:
    """Canonical observations produce stable plain dictionaries."""
    observation = current_observation()

    first = observation.to_dict()
    second = observation.to_dict()

    assert first == second
    assert first["observation_id"] == "current-1"
    assert first["observed_at"] == "2026-08-03T12:00:00+00:00"
    assert first["facts"]["air_temperature_celsius"]["value"] == 24.5
    assert first["facts"]["condition"]["value"] == "mostly_clear"
    assert first["facts"]["air_temperature_celsius"]["quality"]["status"] == "good"
    assert isinstance(first["facts"]["air_temperature_celsius"]["quality"]["flags"], list)


def test_models_are_frozen_and_slotted() -> None:
    """Weather records cannot be mutated or extended in place."""
    observation = current_observation()
    with pytest.raises(FrozenInstanceError):
        observation.__setattr__("location_id", "other")
    with pytest.raises((AttributeError, TypeError)):
        observation.__setattr__("unexpected", "value")


def test_weather_fact_preserves_all_required_metadata() -> None:
    """Each weather value retains confidence, source, verification, time, and quality."""
    temperature = weather_facts().air_temperature_celsius
    assert temperature.confidence == 0.9
    assert temperature.provenance.source == "canonical-test-source"
    assert temperature.verification_status is WeatherVerificationStatus.PROVIDER_VALIDATED
    assert temperature.observed_at == NOW
    assert temperature.quality.status is WeatherQualityStatus.GOOD


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("inf"), float("nan")])
def test_weather_fact_rejects_invalid_confidence(confidence: float) -> None:
    """Confidence is a finite normalized fraction."""
    with pytest.raises(ValueError, match="confidence"):
        fact(20.0, confidence=confidence)


def test_unknown_and_known_quality_states_are_consistent() -> None:
    """Unavailable quality and unknown values cannot contradict one another."""
    assert unknown().is_known is False
    with pytest.raises(ValueError, match="zero confidence"):
        WeatherFact(
            value=None,
            confidence=0.5,
            provenance=WeatherProvenance(
                source="test", source_type=WeatherSourceType.OTHER
            ),
            verification_status=WeatherVerificationStatus.UNVERIFIED,
            observed_at=NOW,
            quality=quality(WeatherQualityStatus.UNAVAILABLE, reason="missing"),
        )
    with pytest.raises(ValueError, match="require unavailable quality"):
        WeatherFact(
            value=None,
            confidence=0,
            provenance=WeatherProvenance(
                source="test", source_type=WeatherSourceType.OTHER
            ),
            verification_status=WeatherVerificationStatus.UNVERIFIED,
            observed_at=NOW,
            quality=quality(),
        )
    with pytest.raises(ValueError, match="cannot have unavailable quality"):
        fact(
            20.0,
            confidence=0.5,
            quality_status=WeatherQualityStatus.UNAVAILABLE,
        )


def test_unavailable_quality_requires_a_reason() -> None:
    """Missing weather carries an actionable safe reason."""
    with pytest.raises(ValueError, match="requires a reason"):
        quality(WeatherQualityStatus.UNAVAILABLE)


def test_quality_flags_are_unique_and_sample_count_is_positive() -> None:
    """Quality metadata rejects ambiguous duplication and impossible counts."""
    with pytest.raises(ValueError, match="duplicates"):
        WeatherQualityMetadata(
            status=WeatherQualityStatus.GOOD,
            flags=("checked", "checked"),
        )
    with pytest.raises(ValueError, match="positive integer"):
        WeatherQualityMetadata(
            status=WeatherQualityStatus.GOOD,
            sample_count=0,
        )


def test_weather_fact_rejects_raw_payloads_and_naive_timestamps() -> None:
    """Provider payloads, bytes, and ambiguous times stay outside the domain."""
    with pytest.raises(TypeError, match="plain scalar"):
        fact({"provider": "payload"})
    with pytest.raises(TypeError, match="raw bytes"):
        fact(b"raw response")
    with pytest.raises(ValueError, match="timezone-aware"):
        fact(20.0, observed_at=datetime(2026, 8, 3, 12, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        fact(datetime(2026, 8, 3, 6, 0))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("air_temperature_celsius", 71.0, "at most 70"),
        ("relative_humidity_percent", 101.0, "at most 100"),
        ("wind_speed_meters_per_second", -0.1, "at least 0"),
        ("precipitation_mm", -0.1, "at least 0"),
        ("snowfall_mm", -0.1, "at least 0"),
        ("precipitation_probability_percent", 101.0, "at most 100"),
        ("rain_rate_mm_per_hour", -0.1, "at least 0"),
        ("cloud_cover_percent", 101.0, "at most 100"),
        ("solar_radiation_watts_per_square_meter", -1.0, "at least 0"),
        ("uv_index", -0.1, "at least 0"),
        ("barometric_pressure_hpa", -1.0, "at least 0"),
        ("visibility_meters", -1.0, "at least 0"),
        ("reference_evapotranspiration_mm", -0.1, "at least 0"),
    ],
)
def test_environmental_weather_values_enforce_physical_bounds(
    field_name: str,
    value: float,
    message: str,
) -> None:
    """Impossible environmental values fail at construction."""
    with pytest.raises(ValueError, match=message):
        weather_facts(**{field_name: fact(value)})


@pytest.mark.parametrize("direction", [-0.1, 360.0])
def test_wind_direction_uses_half_open_degree_range(direction: float) -> None:
    """Canonical bearings are normalized to zero inclusive and 360 exclusive."""
    with pytest.raises(ValueError, match=r"at least 0|less than 360"):
        weather_facts(wind_direction_degrees=fact(direction))


def test_sunrise_must_precede_sunset_when_both_are_known() -> None:
    """Astronomical timestamps retain a valid order without being calculated."""
    with pytest.raises(ValueError, match="sunset must follow sunrise"):
        weather_facts(
            sunrise=fact(NOW.replace(hour=19)),
            sunset=fact(NOW.replace(hour=6)),
        )


def test_condition_and_astronomical_facts_require_canonical_types() -> None:
    """Condition and solar-event facts reject strings masquerading as canonical values."""
    with pytest.raises(ValueError, match="canonical WeatherCondition"):
        weather_facts(condition=fact("sunny"))
    with pytest.raises(ValueError, match="timezone-aware datetime"):
        weather_facts(sunrise=fact("06:00"))


def test_unknown_weather_fields_remain_explicit() -> None:
    """Missing values are not silently converted to zero."""
    facts = weather_facts(snowfall_mm=unknown(), uv_index=unknown())
    assert facts.snowfall_mm.value is None
    assert facts.uv_index.quality.status is WeatherQualityStatus.UNAVAILABLE


def test_current_observation_requires_matching_fact_timestamps() -> None:
    """All facts in a point record apply to its canonical observation time."""
    mismatched = weather_facts(
        air_temperature_celsius=fact(24.5, observed_at=NEXT_HOUR)
    )
    with pytest.raises(ValueError, match="timestamp must match"):
        current_observation(facts=mismatched)


def test_observation_receipt_cannot_precede_observation() -> None:
    """Observation ingestion chronology is unambiguous."""
    with pytest.raises(ValueError, match="cannot precede"):
        current_observation(received_at=NOW - timedelta(seconds=1))


def test_current_and_historical_records_are_distinct_canonical_types() -> None:
    """Current and historical observations cannot be silently interchanged."""
    current = current_observation()
    historical = historical_observation()
    assert type(current).__name__ == "CurrentWeatherObservation"
    assert type(historical).__name__ == "HistoricalWeatherObservation"
    assert current.observed_at == historical.observed_at


def test_hourly_forecast_is_bounded_and_serializable() -> None:
    """Hourly forecasts retain issue time, validity, and fact applicability."""
    forecast = hourly_forecast()
    serialized = forecast.to_dict()
    assert forecast.valid_until - forecast.valid_from == timedelta(hours=1)
    assert serialized["valid_from"] == "2026-08-03T13:00:00+00:00"
    assert serialized["facts"]["air_temperature_celsius"]["observed_at"] == (
        "2026-08-03T13:00:00+00:00"
    )


def test_forecast_period_and_fact_timestamps_are_validated() -> None:
    """Forecast periods cannot be inverted or detached from their facts."""
    forecast = hourly_forecast()
    with pytest.raises(ValueError, match="must follow"):
        replace(forecast, valid_until=forecast.valid_from)
    with pytest.raises(ValueError, match="cannot follow"):
        replace(forecast, issued_at=forecast.valid_until + timedelta(seconds=1))
    with pytest.raises(ValueError, match="timestamp must match"):
        replace(forecast, facts=weather_facts(NOW))


def test_daily_forecast_preserves_date_and_temperature_extremes() -> None:
    """Daily forecasts retain local date and separately sourced minimum and maximum."""
    forecast = daily_forecast()
    serialized = forecast.to_dict()
    assert serialized["local_date"] == "2026-08-04"
    assert serialized["minimum_air_temperature_celsius"]["value"] == 16.0
    assert serialized["maximum_air_temperature_celsius"]["value"] == 29.0


def test_daily_temperature_extremes_are_ordered_and_timestamped() -> None:
    """Daily minimum and maximum facts remain physically and temporally consistent."""
    forecast = daily_forecast()
    with pytest.raises(ValueError, match="cannot exceed"):
        replace(
            forecast,
            minimum_air_temperature_celsius=fact(30.0, observed_at=NEXT_DAY),
            maximum_air_temperature_celsius=fact(20.0, observed_at=NEXT_DAY),
        )
    with pytest.raises(ValueError, match="timestamp must match"):
        replace(
            forecast,
            minimum_air_temperature_celsius=fact(16.0, observed_at=NOW),
        )
    with pytest.raises(ValueError, match="local_date must be a date"):
        replace(forecast, local_date=NOW)
    with pytest.raises(ValueError, match="must match valid_from"):
        replace(forecast, local_date=date(2026, 8, 5))


def test_observation_window_accepts_ordered_history() -> None:
    """A historical window contains ordered unique observations for one location."""
    first = historical_observation()
    second = historical_observation(NEXT_HOUR, observation_id="history-2")
    window = ObservationWindow(
        window_id="observation-window-1",
        location_id="property-1",
        starts_at=NOW,
        ends_at=TWO_HOURS,
        observations=(first, second),
    )
    assert tuple(item.observation_id for item in window.observations) == (
        "history-1",
        "history-2",
    )


def test_observation_window_rejects_empty_or_invalid_membership() -> None:
    """Observation windows reject missing, foreign, unordered, and out-of-range records."""
    with pytest.raises(ValueError, match="at least one"):
        ObservationWindow(
            window_id="observation-window-empty",
            location_id="property-1",
            starts_at=NOW,
            ends_at=NEXT_HOUR,
            observations=(),
        )
    foreign = historical_observation(location_id="property-2")
    with pytest.raises(ValueError, match="window location"):
        ObservationWindow(
            window_id="observation-window-foreign",
            location_id="property-1",
            starts_at=NOW,
            ends_at=NEXT_HOUR,
            observations=(foreign,),
        )
    first = historical_observation()
    second = historical_observation(NEXT_HOUR, observation_id="history-2")
    with pytest.raises(ValueError, match="chronological order"):
        ObservationWindow(
            window_id="observation-window-unordered",
            location_id="property-1",
            starts_at=NOW,
            ends_at=TWO_HOURS,
            observations=(second, first),
        )
    with pytest.raises(ValueError, match="within"):
        ObservationWindow(
            window_id="observation-window-outside",
            location_id="property-1",
            starts_at=NOW,
            ends_at=NEXT_HOUR,
            observations=(second,),
        )


def test_observation_window_rejects_duplicate_ids_and_timestamps() -> None:
    """Window identity and temporal coordinates are unambiguous."""
    first = historical_observation()
    duplicate_id = historical_observation(NEXT_HOUR, observation_id="history-1")
    with pytest.raises(ValueError, match="duplicate identifiers"):
        ObservationWindow(
            window_id="observation-window-duplicate-id",
            location_id="property-1",
            starts_at=NOW,
            ends_at=TWO_HOURS,
            observations=(first, duplicate_id),
        )
    duplicate_time = historical_observation(NOW, observation_id="history-2")
    with pytest.raises(ValueError, match="timestamps must not contain duplicates"):
        ObservationWindow(
            window_id="observation-window-duplicate-time",
            location_id="property-1",
            starts_at=NOW,
            ends_at=TWO_HOURS,
            observations=(first, duplicate_time),
        )


def test_forecast_window_accepts_hourly_and_daily_resolutions() -> None:
    """Different forecast granularities may cover the same bounded horizon."""
    first_hour = hourly_forecast()
    second_hour = hourly_forecast(TWO_HOURS, forecast_id="hourly-2")
    day = daily_forecast()
    window = ForecastWindow(
        window_id="forecast-window-1",
        location_id="property-1",
        generated_at=NOW,
        starts_at=NOW,
        ends_at=NEXT_DAY + timedelta(days=1),
        hourly_forecasts=(first_hour, second_hour),
        daily_forecasts=(day,),
    )
    assert len(window.hourly_forecasts) == 2
    assert len(window.daily_forecasts) == 1


def test_forecast_window_requires_forecasts_and_valid_bounds() -> None:
    """An empty or inverted forecast window is not a canonical forecast."""
    with pytest.raises(ValueError, match="at least one"):
        ForecastWindow(
            window_id="forecast-window-empty",
            location_id="property-1",
            generated_at=NOW,
            starts_at=NOW,
            ends_at=NEXT_HOUR,
        )
    with pytest.raises(ValueError, match="must follow"):
        ForecastWindow(
            window_id="forecast-window-invalid",
            location_id="property-1",
            generated_at=NOW,
            starts_at=NOW,
            ends_at=NOW,
            hourly_forecasts=(hourly_forecast(),),
        )


def test_forecast_window_rejects_overlap_order_location_and_containment_errors() -> None:
    """Same-resolution forecast periods form a clean chronological sequence."""
    first = hourly_forecast(duration=timedelta(hours=2))
    overlapping = hourly_forecast(TWO_HOURS, forecast_id="hourly-2")
    with pytest.raises(ValueError, match="must not overlap"):
        ForecastWindow(
            window_id="forecast-window-overlap",
            location_id="property-1",
            generated_at=NOW,
            starts_at=NOW,
            ends_at=NEXT_DAY,
            hourly_forecasts=(first, overlapping),
        )
    later = hourly_forecast(TWO_HOURS, forecast_id="hourly-2")
    earlier = hourly_forecast(NEXT_HOUR)
    with pytest.raises(ValueError, match="chronological order"):
        ForecastWindow(
            window_id="forecast-window-order",
            location_id="property-1",
            generated_at=NOW,
            starts_at=NOW,
            ends_at=NEXT_DAY,
            hourly_forecasts=(later, earlier),
        )
    foreign = hourly_forecast(location_id="property-2")
    with pytest.raises(ValueError, match="window location"):
        ForecastWindow(
            window_id="forecast-window-location",
            location_id="property-1",
            generated_at=NOW,
            starts_at=NOW,
            ends_at=NEXT_DAY,
            hourly_forecasts=(foreign,),
        )
    outside = hourly_forecast(NEXT_DAY)
    with pytest.raises(ValueError, match="within"):
        ForecastWindow(
            window_id="forecast-window-outside",
            location_id="property-1",
            generated_at=NOW,
            starts_at=NOW,
            ends_at=NEXT_DAY,
            hourly_forecasts=(outside,),
        )


def test_stable_identifiers_reject_mutable_location_names() -> None:
    """Canonical identity cannot be derived from a mutable display name."""
    with pytest.raises(ValueError, match="stable identifier"):
        current_observation(location_id="Back Yard Weather")


def test_enum_values_are_stable_canonical_vocabulary() -> None:
    """Condition, quality, source, and verification values serialize predictably."""
    assert WeatherCondition.THUNDERSTORM.value == "thunderstorm"
    assert WeatherCondition.UNKNOWN.value == "unknown"
    assert WeatherQualityStatus.ESTIMATED.value == "estimated"
    assert WeatherSourceType.REANALYSIS.value == "reanalysis"
    assert WeatherVerificationStatus.SENSOR_VERIFIED.value == "sensor_verified"


def test_domain_has_no_provider_planning_intelligence_or_execution_surface() -> None:
    """Environmental records expose representation only."""
    observation = current_observation()
    forbidden = (
        "fetch",
        "refresh",
        "calculate_runoff",
        "calculate_effective_rainfall",
        "calculate_water_deficit",
        "detect_santa_ana",
        "detect_marine_layer",
        "detect_heat_wave",
        "recommend_irrigation",
        "start",
        "stop",
        "schedule",
        "execute",
    )
    for name in forbidden:
        assert not hasattr(observation, name)
