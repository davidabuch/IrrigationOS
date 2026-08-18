"""Read-only weather evidence ingestion from Home Assistant and Open-Meteo."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from homeassistant.core import HomeAssistant

from .models import (
    EnvironmentalWeatherFacts,
    ForecastWindow,
    HistoricalWeatherObservation,
    HourlyWeatherForecast,
    ObservationWindow,
    WeatherCondition,
    WeatherFact,
    WeatherProvenance,
    WeatherQualityMetadata,
    WeatherQualityStatus,
    WeatherSourceType,
    WeatherVerificationStatus,
)

OPEN_METEO_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
OPEN_METEO_HOURLY = "precipitation,et0_fao_evapotranspiration"
OPEN_METEO_REFRESH_INTERVAL = timedelta(minutes=30)
OPEN_METEO_MAX_CACHE_AGE = timedelta(hours=2)
HA_FORECAST_REFRESH_INTERVAL = timedelta(minutes=30)
HA_FORECAST_MAX_CACHE_AGE = timedelta(hours=2)
HA_FORECAST_TIMEOUT_SECONDS = 10
HISTORY_HOURS = 48
FORECAST_HOURS = 48


def _unknown(at: datetime, source: str, source_type: WeatherSourceType) -> WeatherFact[Any]:
    return WeatherFact(
        value=None,
        confidence=0,
        provenance=WeatherProvenance(source=source, source_type=source_type),
        verification_status=WeatherVerificationStatus.UNVERIFIED,
        observed_at=at,
        quality=WeatherQualityMetadata(
            status=WeatherQualityStatus.UNAVAILABLE, reason="source_field_unavailable"
        ),
    )


def _fact(
    value: Any,
    at: datetime,
    source: str,
    source_type: WeatherSourceType,
    *,
    confidence: float,
    quality: WeatherQualityStatus = WeatherQualityStatus.GOOD,
) -> WeatherFact[Any]:
    if value is None:
        return _unknown(at, source, source_type)
    return WeatherFact(
        value=value,
        confidence=confidence,
        provenance=WeatherProvenance(source=source, source_type=source_type),
        verification_status=WeatherVerificationStatus.PROVIDER_VALIDATED,
        observed_at=at,
        quality=WeatherQualityMetadata(status=quality),
    )


def _facts(
    at: datetime,
    source: str,
    source_type: WeatherSourceType,
    values: Mapping[str, Any],
    *,
    confidence: float,
    quality: WeatherQualityStatus = WeatherQualityStatus.GOOD,
) -> EnvironmentalWeatherFacts:
    def unknown() -> WeatherFact[Any]:
        return _unknown(at, source, source_type)

    def fact(key: str) -> WeatherFact[Any]:
        return _fact(
            values.get(key),
            at,
            source,
            source_type,
            confidence=confidence,
            quality=quality,
        )

    return EnvironmentalWeatherFacts(
        air_temperature_celsius=fact("temperature_c"),
        relative_humidity_percent=fact("humidity"),
        dew_point_celsius=unknown(),
        wind_speed_meters_per_second=fact("wind_mps"),
        wind_gust_meters_per_second=unknown(),
        wind_direction_degrees=fact("wind_direction"),
        precipitation_mm=fact("precipitation_mm"),
        snowfall_mm=unknown(),
        precipitation_probability_percent=fact("precipitation_probability"),
        rain_rate_mm_per_hour=unknown(),
        cloud_cover_percent=fact("cloud_cover"),
        solar_radiation_watts_per_square_meter=unknown(),
        uv_index=fact("uv_index"),
        barometric_pressure_hpa=unknown(),
        visibility_meters=unknown(),
        condition=fact("condition"),
        sunrise=unknown(),
        sunset=unknown(),
        reference_evapotranspiration_mm=fact("et0_mm"),
    )


def _condition(value: object) -> WeatherCondition | None:
    text = str(value or "").lower().replace("-", "")
    return {
        "sunny": WeatherCondition.CLEAR,
        "clearnight": WeatherCondition.CLEAR,
        "partlycloudy": WeatherCondition.PARTLY_CLOUDY,
        "cloudy": WeatherCondition.CLOUDY,
        "fog": WeatherCondition.FOG,
        "rainy": WeatherCondition.RAIN,
        "pouring": WeatherCondition.HEAVY_RAIN,
        "lightningrainy": WeatherCondition.THUNDERSTORM,
        "snowy": WeatherCondition.SNOW,
        "snowyrainy": WeatherCondition.SLEET,
        "hail": WeatherCondition.HAIL,
        "windy": WeatherCondition.WINDY,
    }.get(text)


def _temperature_c(value: object, unit: str | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if unit in {"°F", "F", "fahrenheit"}:
        return (float(value) - 32) * 5 / 9
    if unit in {"°C", "C", "celsius"}:
        return float(value)
    return None


def _wind_mps(value: object, unit: str | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    factors = {
        "mph": 0.44704,
        "km/h": 1 / 3.6,
        "m/s": 1.0,
        "kn": 0.514444,
        "kt": 0.514444,
    }
    factor = factors.get(unit or "")
    return None if factor is None else float(value) * factor


def build_ha_hourly_forecast(
    *, entity_id: str, issued_at: datetime, records: Sequence[Mapping[str, Any]],
    temperature_unit: str | None, wind_speed_unit: str | None, precipitation_unit: str | None,
    now: datetime,
) -> ForecastWindow | None:
    """Normalize HA hourly forecast records into the canonical weather domain."""
    parsed: list[tuple[datetime, Mapping[str, Any]]] = []
    for item in records:
        raw = item.get("datetime")
        if not isinstance(raw, str):
            continue
        try:
            at = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        if now <= at < now + timedelta(hours=FORECAST_HOURS):
            parsed.append((at, item))
    parsed.sort(key=lambda item: item[0])
    if not parsed:
        return None
    forecasts = []
    for index, (at, item) in enumerate(parsed):
        until = (
            parsed[index + 1][0]
            if index + 1 < len(parsed)
            else min(at + timedelta(hours=1), now + timedelta(hours=FORECAST_HOURS))
        )
        precip = item.get("precipitation")
        precipitation_mm = None
        if isinstance(precip, int | float) and not isinstance(precip, bool):
            if precipitation_unit == "in":
                precipitation_mm = float(precip) * 25.4
            elif precipitation_unit == "mm":
                precipitation_mm = float(precip)
        values = {
            "temperature_c": _temperature_c(item.get("temperature"), temperature_unit),
            "humidity": item.get("humidity"),
            "precipitation_mm": precipitation_mm,
            "precipitation_probability": item.get("precipitation_probability"),
            "cloud_cover": item.get("cloud_coverage"),
            "wind_mps": _wind_mps(item.get("wind_speed"), wind_speed_unit),
            "wind_direction": item.get("wind_bearing"),
            "uv_index": item.get("uv_index"),
            "condition": _condition(item.get("condition")),
        }
        identity = f"{entity_id}|{issued_at.isoformat()}|{at.isoformat()}"
        digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
        forecasts.append(HourlyWeatherForecast(
            forecast_id=f"ha.forecast.{digest}", location_id="home", issued_at=issued_at,
            valid_from=at, valid_until=until,
            facts=_facts(at, entity_id, WeatherSourceType.FORECAST, values, confidence=0.8),
        ))
    return ForecastWindow(
        window_id=(
            "ha.window."
            + hashlib.sha256((entity_id + issued_at.isoformat()).encode()).hexdigest()[:20]
        ),
        location_id="home", generated_at=issued_at,
        starts_at=forecasts[0].valid_from, ends_at=forecasts[-1].valid_until,
        hourly_forecasts=tuple(forecasts),
    )


def build_open_meteo_observations(
    payload: Mapping[str, Any], *, now: datetime
) -> ObservationWindow | None:
    """Normalize completed Open-Meteo hourly precipitation and ET0 intervals."""
    hourly = payload.get("hourly")
    if not isinstance(hourly, Mapping):
        return None
    times = hourly.get("time")
    rain = hourly.get("precipitation")
    et0 = hourly.get("et0_fao_evapotranspiration")
    if not isinstance(times, list) or not isinstance(rain, list) or not isinstance(et0, list):
        return None
    if not (len(times) == len(rain) == len(et0)):
        return None
    start = now - timedelta(hours=HISTORY_HOURS)
    observations = []
    for raw_time, rain_value, et_value in zip(times, rain, et0, strict=False):
        if not isinstance(raw_time, str):
            continue
        try:
            parsed_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            interval_end = (
                parsed_time.replace(tzinfo=UTC)
                if parsed_time.tzinfo is None
                else parsed_time.astimezone(UTC)
            )
        except ValueError:
            continue
        observed_at = interval_end - timedelta(hours=1)
        if interval_end > now or not start <= observed_at < now:
            continue
        values = {
            "precipitation_mm": (
                rain_value
                if isinstance(rain_value, int | float) and not isinstance(rain_value, bool)
                else None
            ),
            "et0_mm": (
                et_value
                if isinstance(et_value, int | float) and not isinstance(et_value, bool)
                else None
            ),
        }
        digest = hashlib.sha256(observed_at.isoformat().encode()).hexdigest()[:20]
        observations.append(HistoricalWeatherObservation(
            observation_id=f"openmeteo.observation.{digest}", location_id="home",
            observed_at=observed_at, received_at=now,
            facts=_facts(
                observed_at, "open-meteo-historical-forecast", WeatherSourceType.FORECAST,
                values, confidence=0.7, quality=WeatherQualityStatus.ESTIMATED,
            ),
        ))
    if not observations:
        return None
    return ObservationWindow(
        window_id=(
            "openmeteo.window."
            + hashlib.sha256(
                (observations[0].observed_at.isoformat() + now.isoformat()).encode()
            ).hexdigest()[:20]
        ),
        location_id="home",
        starts_at=observations[0].observed_at,
        ends_at=observations[-1].observed_at + timedelta(hours=1),
        observations=tuple(observations),
    )


class WeatherEvidenceManager:
    """Fetch bounded read-only weather evidence without affecting HA health."""

    def __init__(self, hass: HomeAssistant, session: ClientSession) -> None:
        self._hass = hass
        self._session = session
        self.observations: ObservationWindow | None = None
        self.forecast: ForecastWindow | None = None
        self.last_error: str | None = None
        self.last_refresh_at: datetime | None = None
        self._last_open_meteo_success_at: datetime | None = None
        self._last_ha_forecast_refresh_at: datetime | None = None
        self._last_ha_forecast_source_updated: datetime | None = None

    async def async_refresh(self, now: datetime) -> None:
        """Refresh evidence; failures fail closed to no new evidence."""
        self.last_refresh_at = now
        errors: list[str] = []
        should_refresh_open_meteo = (
            self._last_open_meteo_success_at is None
            or now - self._last_open_meteo_success_at >= OPEN_METEO_REFRESH_INTERVAL
        )
        if should_refresh_open_meteo:
            try:
                refreshed = await self._async_open_meteo(now)
                if refreshed is not None:
                    self.observations = refreshed
                    self._last_open_meteo_success_at = now
                else:
                    errors.append("open_meteo_evidence_unavailable")
            except Exception:
                errors.append("open_meteo_unavailable")
        if (
            self._last_open_meteo_success_at is None
            or now - self._last_open_meteo_success_at > OPEN_METEO_MAX_CACHE_AGE
        ):
            self.observations = None
        weather_state = self._single_weather_state()
        source_updated = (
            None
            if weather_state is None
            else weather_state.last_updated.astimezone(UTC)
        )
        should_refresh_ha = (
            self.forecast is None
            or self._last_ha_forecast_refresh_at is None
            or now - self._last_ha_forecast_refresh_at >= HA_FORECAST_REFRESH_INTERVAL
            or source_updated != self._last_ha_forecast_source_updated
        )
        if should_refresh_ha:
            try:
                refreshed_forecast = await self._async_ha_forecast(
                    now, weather_state=weather_state
                )
                self._last_ha_forecast_refresh_at = now
                if refreshed_forecast is not None:
                    self.forecast = refreshed_forecast
                    self._last_ha_forecast_source_updated = source_updated
                else:
                    errors.append("ha_forecast_unavailable")
            except Exception:
                self._last_ha_forecast_refresh_at = now
                errors.append("ha_forecast_unavailable")
        if (
            self.forecast is not None
            and now - self.forecast.generated_at > HA_FORECAST_MAX_CACHE_AGE
        ):
            self.forecast = None
        self.last_error = ";".join(errors) or None

    async def _async_open_meteo(self, now: datetime) -> ObservationWindow | None:
        params: dict[str, str | float] = {
            "latitude": float(self._hass.config.latitude),
            "longitude": float(self._hass.config.longitude),
            "hourly": OPEN_METEO_HOURLY,
            "start_date": (now - timedelta(days=2)).date().isoformat(),
            "end_date": now.date().isoformat(),
            "timezone": "UTC",
            "precipitation_unit": "mm",
        }
        timeout = ClientTimeout(total=10)
        async with self._session.get(
            OPEN_METEO_URL, params=params, timeout=timeout
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        if not isinstance(payload, Mapping):
            return None
        return build_open_meteo_observations(payload, now=now)

    def _single_weather_state(self) -> Any | None:
        states = [
            state
            for entity_id in self._hass.states.async_entity_ids("weather")
            if (state := self._hass.states.get(entity_id)) is not None
            and state.state not in {"unknown", "unavailable"}
        ]
        return states[0] if len(states) == 1 else None

    async def _async_ha_forecast(
        self, now: datetime, *, weather_state: Any | None = None
    ) -> ForecastWindow | None:
        state = weather_state or self._single_weather_state()
        if state is None:
            return None
        async with asyncio.timeout(HA_FORECAST_TIMEOUT_SECONDS):
            response = await self._hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly"},
                target={"entity_id": state.entity_id},
                blocking=True,
                return_response=True,
            )
        if not isinstance(response, Mapping):
            return None
        entity_response = response.get(state.entity_id)
        if not isinstance(entity_response, Mapping):
            return None
        raw_forecast = entity_response.get("forecast")
        if not isinstance(raw_forecast, list):
            return None
        records = tuple(item for item in raw_forecast if isinstance(item, Mapping))
        if len(records) != len(raw_forecast):
            return None
        return build_ha_hourly_forecast(
            entity_id=state.entity_id, issued_at=state.last_updated.astimezone(UTC),
            records=records,
            temperature_unit=state.attributes.get("temperature_unit"),
            wind_speed_unit=state.attributes.get("wind_speed_unit"),
            precipitation_unit=state.attributes.get("precipitation_unit"), now=now,
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "last_refresh_at": (
                None if self.last_refresh_at is None else self.last_refresh_at.isoformat()
            ),
            "last_error": self.last_error,
            "observation_count": (
                0 if self.observations is None else len(self.observations.observations)
            ),
            "forecast_count": 0 if self.forecast is None else len(self.forecast.hourly_forecasts),
            "open_meteo_enabled": True,
            "open_meteo_evidence_class": "estimated_historical_forecast",
            "open_meteo_last_success_at": (
                None if self._last_open_meteo_success_at is None
                else self._last_open_meteo_success_at.isoformat()
            ),
            "ha_forecast_preferred": True,
            "ha_forecast_last_refresh_at": (
                None
                if self._last_ha_forecast_refresh_at is None
                else self._last_ha_forecast_refresh_at.isoformat()
            ),
            "ha_forecast_source_updated": (
                None
                if self._last_ha_forecast_source_updated is None
                else self._last_ha_forecast_source_updated.isoformat()
            ),
            "execution_authorized": False,
        }
