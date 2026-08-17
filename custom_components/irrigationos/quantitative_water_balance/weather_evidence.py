"""Admit canonical weather-domain evidence into water-balance quantities."""

from __future__ import annotations

import hashlib

from ..weather import (
    DailyWeatherForecast,
    ForecastWindow,
    HourlyWeatherForecast,
    ObservationWindow,
    WeatherQualityStatus,
)
from .models import (
    ForecastPrecipitationEvidence,
    WaterBalanceEvidence,
    WaterBalanceEvidenceKind,
    WaterQuantity,
)


def canonical_weather_balance_evidence(
    observations: ObservationWindow | None,
    forecast: ForecastWindow | None,
) -> tuple[
    WaterQuantity | None,
    WaterQuantity | None,
    ForecastPrecipitationEvidence | None,
    tuple[WaterBalanceEvidence, ...],
]:
    """Extract ET0, observed rain, and forecast rain without estimation."""

    et_values: list[float] = []
    rain_values: list[float] = []
    evidence: list[WaterBalanceEvidence] = []
    if observations is not None:
        for item in observations.observations:
            et = item.facts.reference_evapotranspiration_mm
            rain = item.facts.precipitation_mm
            if (
                et.is_known
                and isinstance(et.value, int | float)
                and et.quality.status
                in {WeatherQualityStatus.GOOD, WeatherQualityStatus.ESTIMATED}
            ):
                et_values.append(float(et.value))
                evidence.append(
                    WaterBalanceEvidence(
                        evidence_id=f"weather.et.{item.observation_id}",
                        kind=WaterBalanceEvidenceKind.REFERENCE_ET,
                        source=et.provenance.source,
                        observed_at=et.observed_at,
                        confidence=et.confidence,
                        quality=et.quality.status.value,
                    )
                )
            if (
                rain.is_known
                and isinstance(rain.value, int | float)
                and rain.quality.status
                in {WeatherQualityStatus.GOOD, WeatherQualityStatus.ESTIMATED}
            ):
                rain_values.append(float(rain.value))
                evidence.append(
                    WaterBalanceEvidence(
                        evidence_id=f"weather.rain.{item.observation_id}",
                        kind=WaterBalanceEvidenceKind.OBSERVED_PRECIPITATION,
                        source=rain.provenance.source,
                        observed_at=rain.observed_at,
                        confidence=rain.confidence,
                        quality=rain.quality.status.value,
                    )
                )

    forecast_evidence = _forecast_evidence(forecast)
    if forecast_evidence is not None:
        evidence.append(
            WaterBalanceEvidence(
                evidence_id=f"weather.forecast.{forecast_evidence.forecast_id}",
                kind=WaterBalanceEvidenceKind.FORECAST_PRECIPITATION,
                source=forecast_evidence.source,
                observed_at=forecast_evidence.issued_at,
                confidence=forecast_evidence.confidence,
                quality=forecast_evidence.quality,
            )
        )
    return (
        WaterQuantity.millimeters(sum(et_values)) if et_values else None,
        WaterQuantity.millimeters(sum(rain_values)) if rain_values else None,
        forecast_evidence,
        tuple(sorted(evidence, key=lambda item: item.evidence_id)),
    )


def _forecast_evidence(
    window: ForecastWindow | None,
) -> ForecastPrecipitationEvidence | None:
    if window is None:
        return None
    records: tuple[HourlyWeatherForecast | DailyWeatherForecast, ...] = (
        window.hourly_forecasts or window.daily_forecasts
    )
    values: list[float] = []
    confidences: list[float] = []
    probabilities: list[float] = []
    sources: set[str] = set()
    quality = "good"
    for item in records:
        fact = item.facts.precipitation_mm
        if not fact.is_known or not isinstance(fact.value, int | float):
            return None
        if fact.quality.status not in {
            WeatherQualityStatus.GOOD,
            WeatherQualityStatus.ESTIMATED,
        }:
            return None
        values.append(float(fact.value))
        confidences.append(fact.confidence)
        sources.add(fact.provenance.source)
        if fact.quality.status is WeatherQualityStatus.ESTIMATED:
            quality = "estimated"
        probability = item.facts.precipitation_probability_percent
        if probability.is_known and isinstance(probability.value, int | float):
            probabilities.append(float(probability.value))
    if not values:
        return None
    probability_value = min(probabilities) if len(probabilities) == len(records) else None
    digest = hashlib.sha256(
        "|".join(item.forecast_id for item in records).encode()
    ).hexdigest()[:24]
    return ForecastPrecipitationEvidence(
        forecast_id=f"forecast.window.{digest}",
        issued_at=window.generated_at,
        window_start=window.starts_at,
        window_end=window.ends_at,
        precipitation_mm=WaterQuantity.millimeters(sum(values)),
        probability_percent=probability_value,
        confidence=min(confidences),
        quality=quality,
        source=";".join(sorted(sources)),
    )
