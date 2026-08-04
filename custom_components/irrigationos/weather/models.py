"""Canonical, provider-neutral environmental weather domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import StrEnum
from itertools import pairwise
from math import isfinite
from typing import Any

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class WeatherVerificationStatus(StrEnum):
    """Verification state of an environmental weather fact."""

    UNVERIFIED = "unverified"
    PROVIDER_VALIDATED = "provider_validated"
    SENSOR_VERIFIED = "sensor_verified"
    USER_CONFIRMED = "user_confirmed"


class WeatherQualityStatus(StrEnum):
    """Quality classification supplied with a weather fact."""

    GOOD = "good"
    ESTIMATED = "estimated"
    SUSPECT = "suspect"
    UNAVAILABLE = "unavailable"


class WeatherSourceType(StrEnum):
    """Provider-neutral class of weather-data source."""

    STATION = "station"
    FORECAST = "forecast"
    REANALYSIS = "reanalysis"
    MANUAL = "manual"
    OTHER = "other"


class WeatherCondition(StrEnum):
    """Canonical observed or forecast weather conditions."""

    CLEAR = "clear"
    MOSTLY_CLEAR = "mostly_clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    FOG = "fog"
    DRIZZLE = "drizzle"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    THUNDERSTORM = "thunderstorm"
    SNOW = "snow"
    SLEET = "sleet"
    HAIL = "hail"
    WINDY = "windy"
    SMOKE = "smoke"
    DUST = "dust"
    UNKNOWN = "unknown"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_confidence(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("confidence must be between 0.0 and 1.0")


def _validate_number(
    name: str,
    value: int | float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    maximum_exclusive: bool = False,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None:
        if maximum_exclusive and value >= maximum:
            raise ValueError(f"{name} must be less than {maximum}")
        if not maximum_exclusive and value > maximum:
            raise ValueError(f"{name} must be at most {maximum}")


def _validate_unique_ids(name: str, values: tuple[str, ...]) -> None:
    for value in values:
        _validate_identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate identifiers")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError("raw bytes are not permitted in environmental weather records")
    return value


class SerializableWeatherModel:
    """Mixin for deterministic plain-dictionary serialization."""

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic provider- and runtime-neutral representation."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover - mixin contract
            raise TypeError("weather model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class WeatherProvenance(SerializableWeatherModel):
    """Provider-neutral origin of an environmental weather fact."""

    source: str
    source_type: WeatherSourceType
    source_reference: str | None = None
    method: str | None = None

    def __post_init__(self) -> None:
        _validate_text("source", self.source)
        if not isinstance(self.source_type, WeatherSourceType):
            raise ValueError("source_type must be a canonical WeatherSourceType")
        for name, value in (
            ("source_reference", self.source_reference),
            ("method", self.method),
        ):
            if value is not None:
                _validate_text(name, value)


@dataclass(frozen=True, slots=True)
class WeatherQualityMetadata(SerializableWeatherModel):
    """Quality classification and non-secret source quality flags."""

    status: WeatherQualityStatus
    flags: tuple[str, ...] = ()
    sample_count: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, WeatherQualityStatus):
            raise ValueError("status must be a canonical WeatherQualityStatus")
        for flag in self.flags:
            _validate_text("quality flag", flag)
        if len(self.flags) != len(set(self.flags)):
            raise ValueError("quality flags must not contain duplicates")
        if self.sample_count is not None:
            if isinstance(self.sample_count, bool) or not isinstance(self.sample_count, int):
                raise ValueError("sample_count must be a positive integer")
            if self.sample_count <= 0:
                raise ValueError("sample_count must be a positive integer")
        if self.reason is not None:
            _validate_text("reason", self.reason)
        if self.status is WeatherQualityStatus.UNAVAILABLE and self.reason is None:
            raise ValueError("unavailable quality requires a reason")


@dataclass(frozen=True, slots=True)
class WeatherFact[T](SerializableWeatherModel):
    """A weather value with confidence, provenance, verification, time, and quality."""

    value: T | None
    confidence: float
    provenance: WeatherProvenance
    verification_status: WeatherVerificationStatus
    observed_at: datetime
    quality: WeatherQualityMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.verification_status, WeatherVerificationStatus):
            raise ValueError(
                "verification_status must be a canonical WeatherVerificationStatus"
            )
        _validate_confidence(self.confidence)
        _validate_timestamp("observed_at", self.observed_at)
        is_unknown = self.value is None or (
            isinstance(self.value, StrEnum) and self.value.value == "unknown"
        )
        if is_unknown:
            if self.confidence != 0:
                raise ValueError("unknown weather facts must have zero confidence")
            if self.quality.status is not WeatherQualityStatus.UNAVAILABLE:
                raise ValueError("unknown weather facts require unavailable quality")
        elif self.quality.status is WeatherQualityStatus.UNAVAILABLE:
            raise ValueError("known weather facts cannot have unavailable quality")
        if isinstance(self.value, datetime):
            _validate_timestamp("weather fact value", self.value)
        elif isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("weather fact value must be finite")
        elif isinstance(self.value, bytes | bytearray | memoryview):
            raise TypeError("weather fact values cannot contain raw bytes")
        elif self.value is not None and not isinstance(
            self.value, StrEnum | str | bool | int | float
        ):
            raise TypeError("weather fact value must be a plain scalar, timestamp, or stable enum")

    @property
    def is_known(self) -> bool:
        """Return whether the fact contains an available canonical value."""
        if self.value is None:
            return False
        return not isinstance(self.value, StrEnum) or self.value.value != "unknown"


@dataclass(frozen=True, slots=True)
class EnvironmentalWeatherFacts(SerializableWeatherModel):
    """Canonical weather facts applicable to an observation or forecast period."""

    air_temperature_celsius: WeatherFact[float]
    relative_humidity_percent: WeatherFact[float]
    dew_point_celsius: WeatherFact[float]
    wind_speed_meters_per_second: WeatherFact[float]
    wind_gust_meters_per_second: WeatherFact[float]
    wind_direction_degrees: WeatherFact[float]
    precipitation_mm: WeatherFact[float]
    snowfall_mm: WeatherFact[float]
    precipitation_probability_percent: WeatherFact[float]
    rain_rate_mm_per_hour: WeatherFact[float]
    cloud_cover_percent: WeatherFact[float]
    solar_radiation_watts_per_square_meter: WeatherFact[float]
    uv_index: WeatherFact[float]
    barometric_pressure_hpa: WeatherFact[float]
    visibility_meters: WeatherFact[float]
    condition: WeatherFact[WeatherCondition]
    sunrise: WeatherFact[datetime]
    sunset: WeatherFact[datetime]
    reference_evapotranspiration_mm: WeatherFact[float]

    def __post_init__(self) -> None:
        for name, fact, minimum, maximum in (
            ("air_temperature_celsius", self.air_temperature_celsius, -120.0, 70.0),
            ("relative_humidity_percent", self.relative_humidity_percent, 0.0, 100.0),
            ("dew_point_celsius", self.dew_point_celsius, -120.0, 70.0),
            (
                "wind_speed_meters_per_second",
                self.wind_speed_meters_per_second,
                0.0,
                None,
            ),
            (
                "wind_gust_meters_per_second",
                self.wind_gust_meters_per_second,
                0.0,
                None,
            ),
            ("precipitation_mm", self.precipitation_mm, 0.0, None),
            ("snowfall_mm", self.snowfall_mm, 0.0, None),
            (
                "precipitation_probability_percent",
                self.precipitation_probability_percent,
                0.0,
                100.0,
            ),
            ("rain_rate_mm_per_hour", self.rain_rate_mm_per_hour, 0.0, None),
            ("cloud_cover_percent", self.cloud_cover_percent, 0.0, 100.0),
            (
                "solar_radiation_watts_per_square_meter",
                self.solar_radiation_watts_per_square_meter,
                0.0,
                None,
            ),
            ("uv_index", self.uv_index, 0.0, None),
            ("barometric_pressure_hpa", self.barometric_pressure_hpa, 0.0, None),
            ("visibility_meters", self.visibility_meters, 0.0, None),
            (
                "reference_evapotranspiration_mm",
                self.reference_evapotranspiration_mm,
                0.0,
                None,
            ),
        ):
            if fact.value is not None:
                _validate_number(name, fact.value, minimum=minimum, maximum=maximum)
        if self.wind_direction_degrees.value is not None:
            _validate_number(
                "wind_direction_degrees",
                self.wind_direction_degrees.value,
                minimum=0,
                maximum=360,
                maximum_exclusive=True,
            )
        if self.condition.value is not None and not isinstance(
            self.condition.value, WeatherCondition
        ):
            raise ValueError("condition must be a canonical WeatherCondition")
        sunrise = self.sunrise.value
        sunset = self.sunset.value
        if sunrise is not None and not isinstance(sunrise, datetime):
            raise ValueError("sunrise must be a timezone-aware datetime")
        if sunset is not None and not isinstance(sunset, datetime):
            raise ValueError("sunset must be a timezone-aware datetime")
        if sunrise is not None and sunset is not None and sunset <= sunrise:
            raise ValueError("sunset must follow sunrise")

    def validate_fact_timestamps(self, expected: datetime) -> None:
        """Validate that every fact applies at the enclosing record timestamp."""
        _validate_timestamp("expected fact timestamp", expected)
        for field in fields(self):
            fact = getattr(self, field.name)
            if fact.observed_at != expected:
                raise ValueError(
                    f"weather fact {field.name} timestamp must match its enclosing record"
                )


@dataclass(frozen=True, slots=True)
class CurrentWeatherObservation(SerializableWeatherModel):
    """Most recent point-in-time environmental observation for a location."""

    observation_id: str
    location_id: str
    observed_at: datetime
    received_at: datetime
    facts: EnvironmentalWeatherFacts

    def __post_init__(self) -> None:
        _validate_observation_record(
            self.observation_id,
            self.location_id,
            self.observed_at,
            self.received_at,
            self.facts,
        )


@dataclass(frozen=True, slots=True)
class HistoricalWeatherObservation(SerializableWeatherModel):
    """Immutable point-in-time environmental observation retained for a window."""

    observation_id: str
    location_id: str
    observed_at: datetime
    received_at: datetime
    facts: EnvironmentalWeatherFacts

    def __post_init__(self) -> None:
        _validate_observation_record(
            self.observation_id,
            self.location_id,
            self.observed_at,
            self.received_at,
            self.facts,
        )


def _validate_observation_record(
    observation_id: str,
    location_id: str,
    observed_at: datetime,
    received_at: datetime,
    facts: EnvironmentalWeatherFacts,
) -> None:
    _validate_identifier("observation_id", observation_id)
    _validate_identifier("location_id", location_id)
    _validate_timestamp("observed_at", observed_at)
    _validate_timestamp("received_at", received_at)
    if received_at < observed_at:
        raise ValueError("received_at cannot precede observed_at")
    facts.validate_fact_timestamps(observed_at)


@dataclass(frozen=True, slots=True)
class HourlyWeatherForecast(SerializableWeatherModel):
    """Environmental forecast for one bounded hourly period."""

    forecast_id: str
    location_id: str
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    facts: EnvironmentalWeatherFacts

    def __post_init__(self) -> None:
        _validate_forecast_record(
            self.forecast_id,
            self.location_id,
            self.issued_at,
            self.valid_from,
            self.valid_until,
            self.facts,
        )


@dataclass(frozen=True, slots=True)
class DailyWeatherForecast(SerializableWeatherModel):
    """Environmental forecast for one local calendar day."""

    forecast_id: str
    location_id: str
    local_date: date
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    facts: EnvironmentalWeatherFacts
    minimum_air_temperature_celsius: WeatherFact[float]
    maximum_air_temperature_celsius: WeatherFact[float]

    def __post_init__(self) -> None:
        _validate_forecast_record(
            self.forecast_id,
            self.location_id,
            self.issued_at,
            self.valid_from,
            self.valid_until,
            self.facts,
        )
        if not isinstance(self.local_date, date) or isinstance(self.local_date, datetime):
            raise ValueError("local_date must be a date")
        if self.local_date != self.valid_from.date():
            raise ValueError("local_date must match valid_from in its supplied timezone")
        for name, fact in (
            ("minimum_air_temperature_celsius", self.minimum_air_temperature_celsius),
            ("maximum_air_temperature_celsius", self.maximum_air_temperature_celsius),
        ):
            if fact.observed_at != self.valid_from:
                raise ValueError(f"{name} timestamp must match valid_from")
            if fact.value is not None:
                _validate_number(name, fact.value, minimum=-120, maximum=70)
        minimum = self.minimum_air_temperature_celsius.value
        maximum = self.maximum_air_temperature_celsius.value
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("minimum air temperature cannot exceed maximum air temperature")


def _validate_forecast_record(
    forecast_id: str,
    location_id: str,
    issued_at: datetime,
    valid_from: datetime,
    valid_until: datetime,
    facts: EnvironmentalWeatherFacts,
) -> None:
    _validate_identifier("forecast_id", forecast_id)
    _validate_identifier("location_id", location_id)
    for name, value in (
        ("issued_at", issued_at),
        ("valid_from", valid_from),
        ("valid_until", valid_until),
    ):
        _validate_timestamp(name, value)
    if valid_until <= valid_from:
        raise ValueError("valid_until must follow valid_from")
    if issued_at > valid_until:
        raise ValueError("issued_at cannot follow the forecast period")
    facts.validate_fact_timestamps(valid_from)


@dataclass(frozen=True, slots=True)
class ObservationWindow(SerializableWeatherModel):
    """Chronological historical observations for one location and bounded period."""

    window_id: str
    location_id: str
    starts_at: datetime
    ends_at: datetime
    observations: tuple[HistoricalWeatherObservation, ...]

    def __post_init__(self) -> None:
        _validate_identifier("window_id", self.window_id)
        _validate_identifier("location_id", self.location_id)
        _validate_window("observation window", self.starts_at, self.ends_at)
        if not self.observations:
            raise ValueError("observation window requires at least one observation")
        identifiers = tuple(item.observation_id for item in self.observations)
        _validate_unique_ids("observation_ids", identifiers)
        if any(item.location_id != self.location_id for item in self.observations):
            raise ValueError("all observations must belong to the window location")
        timestamps = tuple(item.observed_at for item in self.observations)
        if timestamps != tuple(sorted(timestamps)):
            raise ValueError("observations must be in chronological order")
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("observation timestamps must not contain duplicates")
        if any(not self.starts_at <= timestamp < self.ends_at for timestamp in timestamps):
            raise ValueError("observations must fall within the observation window")


@dataclass(frozen=True, slots=True)
class ForecastWindow(SerializableWeatherModel):
    """Hourly and daily forecasts for one location and bounded period."""

    window_id: str
    location_id: str
    generated_at: datetime
    starts_at: datetime
    ends_at: datetime
    hourly_forecasts: tuple[HourlyWeatherForecast, ...] = ()
    daily_forecasts: tuple[DailyWeatherForecast, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("window_id", self.window_id)
        _validate_identifier("location_id", self.location_id)
        _validate_timestamp("generated_at", self.generated_at)
        _validate_window("forecast window", self.starts_at, self.ends_at)
        if not self.hourly_forecasts and not self.daily_forecasts:
            raise ValueError("forecast window requires at least one forecast")
        if self.generated_at > self.ends_at:
            raise ValueError("generated_at cannot follow the forecast window")
        _validate_forecast_collection(
            "hourly forecasts",
            self.location_id,
            self.starts_at,
            self.ends_at,
            self.hourly_forecasts,
        )
        _validate_forecast_collection(
            "daily forecasts",
            self.location_id,
            self.starts_at,
            self.ends_at,
            self.daily_forecasts,
        )


def _validate_window(name: str, starts_at: datetime, ends_at: datetime) -> None:
    _validate_timestamp("starts_at", starts_at)
    _validate_timestamp("ends_at", ends_at)
    if ends_at <= starts_at:
        raise ValueError(f"{name} ends_at must follow starts_at")


def _validate_forecast_collection(
    name: str,
    location_id: str,
    starts_at: datetime,
    ends_at: datetime,
    forecasts: tuple[HourlyWeatherForecast, ...] | tuple[DailyWeatherForecast, ...],
) -> None:
    identifiers = tuple(item.forecast_id for item in forecasts)
    _validate_unique_ids("forecast_ids", identifiers)
    if any(item.location_id != location_id for item in forecasts):
        raise ValueError(f"all {name} must belong to the window location")
    valid_starts = tuple(item.valid_from for item in forecasts)
    if valid_starts != tuple(sorted(valid_starts)):
        raise ValueError(f"{name} must be in chronological order")
    if any(item.valid_from < starts_at or item.valid_until > ends_at for item in forecasts):
        raise ValueError(f"all {name} must fall within the forecast window")
    periods = tuple((item.valid_from, item.valid_until) for item in forecasts)
    for previous, current in pairwise(periods):
        if current[0] < previous[1]:
            raise ValueError(f"{name} must not overlap")
