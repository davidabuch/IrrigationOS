"""Deterministic heat, freeze, wind, rain, and forecast-reliability signals."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from math import isfinite
from typing import Any

from ..weather.models import (
    DailyWeatherForecast,
    ForecastWindow,
    HistoricalWeatherObservation,
    HourlyWeatherForecast,
    ObservationWindow,
    WeatherFact,
    WeatherQualityStatus,
)
from .models import (
    EnvironmentalAnalysisWindow,
    EnvironmentalConfidence,
    EnvironmentalEvidenceReference,
    EnvironmentalEvidenceType,
    EnvironmentalExplanation,
    EnvironmentalSignal,
    EnvironmentalSignalClassification,
    EnvironmentalSignalType,
    EnvironmentalThreshold,
)

SIGNAL_ALGORITHM_VERSION = "environment-signals-v1"
SIGNAL_CONFIDENCE_POLICY_VERSION = "weather-signal-confidence-v1"


@dataclass(frozen=True, slots=True)
class EnvironmentalSignalPolicy:
    """Explicit thresholds for deterministic environmental exposure signals."""

    policy_id: str = "environment-signals-default"
    policy_version: str = "1.0.0"
    heat_low_celsius: float = 30.0
    heat_moderate_celsius: float = 35.0
    heat_high_celsius: float = 40.0
    heat_extreme_celsius: float = 45.0
    freeze_low_celsius: float = 4.0
    freeze_moderate_celsius: float = 0.0
    freeze_high_celsius: float = -3.0
    freeze_extreme_celsius: float = -7.0
    wind_low_mps: float = 6.0
    wind_moderate_mps: float = 10.0
    wind_high_mps: float = 15.0
    wind_extreme_mps: float = 22.0
    gust_low_mps: float = 10.0
    gust_moderate_mps: float = 15.0
    gust_high_mps: float = 22.0
    gust_extreme_mps: float = 30.0
    rain_low_mm: float = 5.0
    rain_moderate_mm: float = 15.0
    rain_high_mm: float = 30.0
    rain_extreme_mm: float = 60.0
    rain_rate_low_mm_per_hour: float = 5.0
    rain_rate_moderate_mm_per_hour: float = 15.0
    rain_rate_high_mm_per_hour: float = 30.0
    rain_rate_extreme_mm_per_hour: float = 50.0
    reliability_available_completeness: float = 0.85
    reliability_available_confidence: float = 0.75
    reliability_degraded_completeness: float = 0.50
    reliability_degraded_confidence: float = 0.45

    def __post_init__(self) -> None:
        groups = (
            (
                self.heat_low_celsius,
                self.heat_moderate_celsius,
                self.heat_high_celsius,
                self.heat_extreme_celsius,
            ),
            (
                self.wind_low_mps,
                self.wind_moderate_mps,
                self.wind_high_mps,
                self.wind_extreme_mps,
            ),
            (
                self.gust_low_mps,
                self.gust_moderate_mps,
                self.gust_high_mps,
                self.gust_extreme_mps,
            ),
            (
                self.rain_low_mm,
                self.rain_moderate_mm,
                self.rain_high_mm,
                self.rain_extreme_mm,
            ),
            (
                self.rain_rate_low_mm_per_hour,
                self.rain_rate_moderate_mm_per_hour,
                self.rain_rate_high_mm_per_hour,
                self.rain_rate_extreme_mm_per_hour,
            ),
        )
        for group in groups:
            if any(isinstance(value, bool) or not isfinite(value) for value in group):
                raise ValueError("signal thresholds must be finite numbers")
            if tuple(sorted(group)) != group or len(set(group)) != len(group):
                raise ValueError("signal thresholds must be strictly increasing")
        freeze = (
            self.freeze_extreme_celsius,
            self.freeze_high_celsius,
            self.freeze_moderate_celsius,
            self.freeze_low_celsius,
        )
        if tuple(sorted(freeze)) != freeze or len(set(freeze)) != len(freeze):
            raise ValueError("freeze thresholds must be strictly increasing")
        reliability = (
            self.reliability_degraded_completeness,
            self.reliability_degraded_confidence,
            self.reliability_available_completeness,
            self.reliability_available_confidence,
        )
        if any(not 0 <= value <= 1 for value in reliability):
            raise ValueError("reliability thresholds must be between 0 and 1")
        if self.reliability_degraded_completeness > self.reliability_available_completeness:
            raise ValueError("degraded completeness cannot exceed available completeness")
        if self.reliability_degraded_confidence > self.reliability_available_confidence:
            raise ValueError("degraded confidence cannot exceed available confidence")


@dataclass(frozen=True, slots=True)
class EnvironmentalSignalAnalysis:
    """Environmental exposure signals and their evidence for one analysis window."""

    analysis_window: EnvironmentalAnalysisWindow
    created_at: datetime
    policy_id: str
    policy_version: str
    evidence: tuple[EnvironmentalEvidenceReference, ...]
    signals: tuple[EnvironmentalSignal, ...]


def _classification_up(
    value: float | None,
    thresholds: tuple[float, float, float, float],
) -> EnvironmentalSignalClassification:
    if value is None:
        return EnvironmentalSignalClassification.UNAVAILABLE
    low, moderate, high, extreme = thresholds
    if value >= extreme:
        return EnvironmentalSignalClassification.EXTREME
    if value >= high:
        return EnvironmentalSignalClassification.HIGH
    if value >= moderate:
        return EnvironmentalSignalClassification.MODERATE
    if value >= low:
        return EnvironmentalSignalClassification.LOW
    return EnvironmentalSignalClassification.NONE


def _classification_down(
    value: float | None,
    thresholds: tuple[float, float, float, float],
) -> EnvironmentalSignalClassification:
    if value is None:
        return EnvironmentalSignalClassification.UNAVAILABLE
    low, moderate, high, extreme = thresholds
    if value <= extreme:
        return EnvironmentalSignalClassification.EXTREME
    if value <= high:
        return EnvironmentalSignalClassification.HIGH
    if value <= moderate:
        return EnvironmentalSignalClassification.MODERATE
    if value <= low:
        return EnvironmentalSignalClassification.LOW
    return EnvironmentalSignalClassification.NONE


def _more_severe(
    first: EnvironmentalSignalClassification,
    second: EnvironmentalSignalClassification,
) -> EnvironmentalSignalClassification:
    """Return the more severe known exposure classification."""
    severity = {
        EnvironmentalSignalClassification.NONE: 0,
        EnvironmentalSignalClassification.LOW: 1,
        EnvironmentalSignalClassification.MODERATE: 2,
        EnvironmentalSignalClassification.HIGH: 3,
        EnvironmentalSignalClassification.EXTREME: 4,
    }
    known = tuple(item for item in (first, second) if item in severity)
    if not known:
        return EnvironmentalSignalClassification.UNAVAILABLE
    return max(known, key=severity.__getitem__)


def _known_values(facts: tuple[WeatherFact[float], ...]) -> tuple[float, ...]:
    return tuple(fact.value for fact in facts if fact.value is not None and fact.is_known)


def _confidence(facts: tuple[WeatherFact[Any], ...]) -> EnvironmentalConfidence:
    known = tuple(fact for fact in facts if fact.is_known and fact.value is not None)
    required = len(facts)
    statuses = tuple(fact.quality.status for fact in facts)
    return EnvironmentalConfidence(
        completeness=len(known) / required if required else 0.0,
        average_confidence=(
            sum(fact.confidence for fact in known) / len(known) if known else 0.0
        ),
        known_fact_count=len(known),
        required_fact_count=required,
        good_quality_count=sum(status is WeatherQualityStatus.GOOD for status in statuses),
        estimated_quality_count=sum(
            status is WeatherQualityStatus.ESTIMATED for status in statuses
        ),
        suspect_quality_count=sum(
            status is WeatherQualityStatus.SUSPECT for status in statuses
        ),
        unavailable_quality_count=sum(
            status is WeatherQualityStatus.UNAVAILABLE for status in statuses
        ),
        confidence_policy_version=SIGNAL_CONFIDENCE_POLICY_VERSION,
    )


def _thresholds(
    policy: EnvironmentalSignalPolicy,
    names: tuple[str, ...],
) -> tuple[EnvironmentalThreshold, ...]:
    descriptions = {
        "heat_low_celsius": "Low heat-exposure threshold",
        "heat_moderate_celsius": "Moderate heat-exposure threshold",
        "heat_high_celsius": "High heat-exposure threshold",
        "heat_extreme_celsius": "Extreme heat-exposure threshold",
        "freeze_low_celsius": "Low freeze-potential threshold",
        "freeze_moderate_celsius": "Moderate freeze-potential threshold",
        "freeze_high_celsius": "High freeze-potential threshold",
        "freeze_extreme_celsius": "Extreme freeze-potential threshold",
        "wind_low_mps": "Low sustained-wind threshold",
        "wind_moderate_mps": "Moderate sustained-wind threshold",
        "wind_high_mps": "High sustained-wind threshold",
        "wind_extreme_mps": "Extreme sustained-wind threshold",
        "gust_low_mps": "Low wind-gust threshold",
        "gust_moderate_mps": "Moderate wind-gust threshold",
        "gust_high_mps": "High wind-gust threshold",
        "gust_extreme_mps": "Extreme wind-gust threshold",
        "rain_low_mm": "Low accumulated-rain threshold",
        "rain_moderate_mm": "Moderate accumulated-rain threshold",
        "rain_high_mm": "High accumulated-rain threshold",
        "rain_extreme_mm": "Extreme accumulated-rain threshold",
        "rain_rate_low_mm_per_hour": "Low rain-rate threshold",
        "rain_rate_moderate_mm_per_hour": "Moderate rain-rate threshold",
        "rain_rate_high_mm_per_hour": "High rain-rate threshold",
        "rain_rate_extreme_mm_per_hour": "Extreme rain-rate threshold",
        "reliability_available_completeness": "Available forecast completeness threshold",
        "reliability_available_confidence": "Available forecast confidence threshold",
        "reliability_degraded_completeness": "Degraded forecast completeness threshold",
        "reliability_degraded_confidence": "Degraded forecast confidence threshold",
    }
    units = {
        "heat": "celsius",
        "freeze": "celsius",
        "wind": "m/s",
        "gust": "m/s",
        "rain_rate": "mm/hour",
        "rain": "mm",
        "reliability": "fraction",
    }
    result = []
    for name in names:
        prefix = next(key for key in units if name.startswith(key))
        result.append(
            EnvironmentalThreshold(
                name=name,
                value=float(getattr(policy, name)),
                unit=units[prefix],
                description=descriptions[name],
            )
        )
    return tuple(result)


def _evidence(
    records: tuple[
        HistoricalWeatherObservation | HourlyWeatherForecast | DailyWeatherForecast,
        ...,
    ],
    fact_paths: tuple[str, ...],
) -> tuple[EnvironmentalEvidenceReference, ...]:
    result = []
    for record in records:
        if isinstance(record, HistoricalWeatherObservation):
            record_id = record.observation_id
            evidence_type = (
                EnvironmentalEvidenceType.HISTORICAL_OBSERVATION
            )
        elif isinstance(record, HourlyWeatherForecast):
            record_id = record.forecast_id
            evidence_type = EnvironmentalEvidenceType.HOURLY_FORECAST
        else:
            record_id = record.forecast_id
            evidence_type = EnvironmentalEvidenceType.DAILY_FORECAST
        for path in fact_paths:
            suffix = path.replace(".", "-").replace("_", "-")
            result.append(
                EnvironmentalEvidenceReference(
                    evidence_id=f"evidence-{record_id}-{suffix}",
                    location_id=record.location_id,
                    evidence_type=evidence_type,
                    record_id=record_id,
                    fact_path=path,
                )
            )
    return tuple(result)


def _signal(
    *,
    signal_id: str,
    location_id: str,
    signal_type: EnvironmentalSignalType,
    classification: EnvironmentalSignalClassification,
    starts_at: datetime,
    ends_at: datetime,
    created_at: datetime,
    policy: EnvironmentalSignalPolicy,
    confidence: EnvironmentalConfidence,
    evidence: tuple[EnvironmentalEvidenceReference, ...],
    thresholds: tuple[EnvironmentalThreshold, ...],
    summary: str,
    detail: str,
    reason_code: str,
) -> EnvironmentalSignal:
    return EnvironmentalSignal(
        signal_id=signal_id,
        location_id=location_id,
        signal_type=signal_type,
        classification=classification,
        analysis_starts_at=starts_at,
        analysis_ends_at=ends_at,
        created_at=created_at,
        algorithm_version=SIGNAL_ALGORITHM_VERSION,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        confidence=confidence,
        explanation=EnvironmentalExplanation(
            reason_codes=(reason_code,),
            summary=summary,
            detail=detail,
        ),
        evidence_ids=tuple(item.evidence_id for item in evidence),
        threshold_values=thresholds,
    )


def _forecast_facts(
    forecasts: tuple[HourlyWeatherForecast, ...] | tuple[DailyWeatherForecast, ...],
) -> tuple[WeatherFact[Any], ...]:
    result: list[WeatherFact[Any]] = []
    for forecast in forecasts:
        result.extend(getattr(forecast.facts, item.name) for item in fields(forecast.facts))
        if isinstance(forecast, DailyWeatherForecast):
            result.extend(
                (
                    forecast.minimum_air_temperature_celsius,
                    forecast.maximum_air_temperature_celsius,
                )
            )
    return tuple(result)


def analyze_environmental_signals(
    *,
    created_at: datetime,
    observation_window: ObservationWindow | None = None,
    forecast_window: ForecastWindow | None = None,
    policy: EnvironmentalSignalPolicy | None = None,
) -> EnvironmentalSignalAnalysis:
    """Derive conservative exposure and forecast-reliability signals."""
    if observation_window is None and forecast_window is None:
        raise ValueError("environmental signal analysis requires weather inputs")
    active_policy = policy or EnvironmentalSignalPolicy()
    if observation_window is not None:
        location_id = observation_window.location_id
    else:
        assert forecast_window is not None
        location_id = forecast_window.location_id
    if (
        observation_window is not None
        and forecast_window is not None
        and observation_window.location_id != forecast_window.location_id
    ):
        raise ValueError("observation and forecast windows must share one location")
    starts = [window.starts_at for window in (observation_window, forecast_window) if window]
    ends = [window.ends_at for window in (observation_window, forecast_window) if window]
    starts_at = min(starts)
    ends_at = max(ends)
    if created_at < ends_at:
        raise ValueError("created_at cannot precede the analysis period end")

    observations = observation_window.observations if observation_window else ()
    hourly = forecast_window.hourly_forecasts if forecast_window else ()
    daily = forecast_window.daily_forecasts if forecast_window else ()
    forecast_records = hourly + daily
    all_records = observations + forecast_records
    observation_ids = tuple(item.observation_id for item in observations)
    forecast_ids = tuple(item.forecast_id for item in forecast_records)
    analysis_window = EnvironmentalAnalysisWindow(
        window_id=f"environment-signals-{location_id}",
        location_id=location_id,
        starts_at=starts_at,
        ends_at=ends_at,
        observation_ids=observation_ids,
        forecast_ids=forecast_ids,
    )

    signals: list[EnvironmentalSignal] = []
    evidence: list[EnvironmentalEvidenceReference] = []

    temperatures = tuple(item.facts.air_temperature_celsius for item in all_records)
    heat_evidence = _evidence(all_records, ("facts.air_temperature_celsius",))
    evidence.extend(heat_evidence)
    temperature_values = _known_values(temperatures)
    maximum_temperature = max(temperature_values) if temperature_values else None
    heat_class = _classification_up(
        maximum_temperature,
        (
            active_policy.heat_low_celsius,
            active_policy.heat_moderate_celsius,
            active_policy.heat_high_celsius,
            active_policy.heat_extreme_celsius,
        ),
    )
    signals.append(
        _signal(
            signal_id=f"signal-{location_id}-heat",
            location_id=location_id,
            signal_type=EnvironmentalSignalType.HEAT_EXPOSURE,
            classification=heat_class,
            starts_at=starts_at,
            ends_at=ends_at,
            created_at=created_at,
            policy=active_policy,
            confidence=_confidence(temperatures),
            evidence=heat_evidence,
            thresholds=_thresholds(
                active_policy,
                (
                    "heat_low_celsius",
                    "heat_moderate_celsius",
                    "heat_high_celsius",
                    "heat_extreme_celsius",
                ),
            ),
            reason_code=f"heat_exposure_{heat_class.value}",
            summary=f"Environmental heat exposure is {heat_class.value}.",
            detail=(
                "Maximum known air temperature is unavailable."
                if maximum_temperature is None
                else f"Maximum known air temperature is {maximum_temperature:.1f} C."
            ),
        )
    )

    minimum_facts: tuple[WeatherFact[float], ...] = tuple(
        item.minimum_air_temperature_celsius for item in daily
    )
    freeze_facts = temperatures + minimum_facts
    freeze_paths = ("facts.air_temperature_celsius",)
    freeze_evidence = _evidence(all_records, freeze_paths)
    if daily:
        freeze_evidence += _evidence(daily, ("minimum_air_temperature_celsius",))
    evidence.extend(freeze_evidence)
    freeze_values = _known_values(freeze_facts)
    minimum_temperature = min(freeze_values) if freeze_values else None
    freeze_class = _classification_down(
        minimum_temperature,
        (
            active_policy.freeze_low_celsius,
            active_policy.freeze_moderate_celsius,
            active_policy.freeze_high_celsius,
            active_policy.freeze_extreme_celsius,
        ),
    )
    signals.append(
        _signal(
            signal_id=f"signal-{location_id}-freeze",
            location_id=location_id,
            signal_type=EnvironmentalSignalType.FREEZE_POTENTIAL,
            classification=freeze_class,
            starts_at=starts_at,
            ends_at=ends_at,
            created_at=created_at,
            policy=active_policy,
            confidence=_confidence(freeze_facts),
            evidence=freeze_evidence,
            thresholds=_thresholds(
                active_policy,
                (
                    "freeze_low_celsius",
                    "freeze_moderate_celsius",
                    "freeze_high_celsius",
                    "freeze_extreme_celsius",
                ),
            ),
            reason_code=f"freeze_potential_{freeze_class.value}",
            summary=f"Environmental freeze potential is {freeze_class.value}.",
            detail=(
                "Minimum known air temperature is unavailable."
                if minimum_temperature is None
                else f"Minimum known air temperature is {minimum_temperature:.1f} C."
            ),
        )
    )

    wind_facts = tuple(item.facts.wind_speed_meters_per_second for item in all_records)
    gust_facts = tuple(item.facts.wind_gust_meters_per_second for item in all_records)
    wind_evidence = _evidence(
        all_records,
        (
            "facts.wind_speed_meters_per_second",
            "facts.wind_gust_meters_per_second",
        ),
    )
    evidence.extend(wind_evidence)
    max_wind = max(_known_values(wind_facts), default=None)
    max_gust = max(_known_values(gust_facts), default=None)
    wind_class = _more_severe(
        _classification_up(
            max_wind,
            (
                active_policy.wind_low_mps,
                active_policy.wind_moderate_mps,
                active_policy.wind_high_mps,
                active_policy.wind_extreme_mps,
            ),
        ),
        _classification_up(
            max_gust,
            (
                active_policy.gust_low_mps,
                active_policy.gust_moderate_mps,
                active_policy.gust_high_mps,
                active_policy.gust_extreme_mps,
            ),
        ),
    )
    signals.append(
        _signal(
            signal_id=f"signal-{location_id}-wind",
            location_id=location_id,
            signal_type=EnvironmentalSignalType.WIND_EXPOSURE,
            classification=wind_class,
            starts_at=starts_at,
            ends_at=ends_at,
            created_at=created_at,
            policy=active_policy,
            confidence=_confidence(wind_facts + gust_facts),
            evidence=wind_evidence,
            thresholds=_thresholds(
                active_policy,
                (
                    "wind_low_mps",
                    "wind_moderate_mps",
                    "wind_high_mps",
                    "wind_extreme_mps",
                    "gust_low_mps",
                    "gust_moderate_mps",
                    "gust_high_mps",
                    "gust_extreme_mps",
                ),
            ),
            reason_code=f"wind_exposure_{wind_class.value}",
            summary=f"Environmental wind exposure is {wind_class.value}.",
            detail=f"Maximum sustained wind is {max_wind}; maximum gust is {max_gust} m/s.",
        )
    )

    rain_facts = tuple(item.facts.precipitation_mm for item in all_records)
    rain_rate_facts = tuple(item.facts.rain_rate_mm_per_hour for item in all_records)
    rain_evidence = _evidence(
        all_records,
        ("facts.precipitation_mm", "facts.rain_rate_mm_per_hour"),
    )
    evidence.extend(rain_evidence)
    rain_values = _known_values(rain_facts)
    rain_total = sum(rain_values) if len(rain_values) == len(rain_facts) and rain_facts else None
    max_rate = max(_known_values(rain_rate_facts), default=None)
    rain_class = _more_severe(
        _classification_up(
            rain_total,
            (
                active_policy.rain_low_mm,
                active_policy.rain_moderate_mm,
                active_policy.rain_high_mm,
                active_policy.rain_extreme_mm,
            ),
        ),
        _classification_up(
            max_rate,
            (
                active_policy.rain_rate_low_mm_per_hour,
                active_policy.rain_rate_moderate_mm_per_hour,
                active_policy.rain_rate_high_mm_per_hour,
                active_policy.rain_rate_extreme_mm_per_hour,
            ),
        ),
    )
    signals.append(
        _signal(
            signal_id=f"signal-{location_id}-heavy-rain",
            location_id=location_id,
            signal_type=EnvironmentalSignalType.HEAVY_RAIN_POTENTIAL,
            classification=rain_class,
            starts_at=starts_at,
            ends_at=ends_at,
            created_at=created_at,
            policy=active_policy,
            confidence=_confidence(rain_facts + rain_rate_facts),
            evidence=rain_evidence,
            thresholds=_thresholds(
                active_policy,
                (
                    "rain_low_mm",
                    "rain_moderate_mm",
                    "rain_high_mm",
                    "rain_extreme_mm",
                    "rain_rate_low_mm_per_hour",
                    "rain_rate_moderate_mm_per_hour",
                    "rain_rate_high_mm_per_hour",
                    "rain_rate_extreme_mm_per_hour",
                ),
            ),
            reason_code=f"heavy_rain_potential_{rain_class.value}",
            summary=f"Environmental heavy-rain potential is {rain_class.value}.",
            detail=(
                f"Known precipitation total is {rain_total}; "
                f"maximum rain rate is {max_rate} mm/hour."
            ),
        )
    )

    if forecast_records:
        forecast_facts = _forecast_facts(hourly) + _forecast_facts(daily)
        forecast_confidence = _confidence(forecast_facts)
        if (
            forecast_confidence.completeness
            >= active_policy.reliability_available_completeness
            and forecast_confidence.average_confidence
            >= active_policy.reliability_available_confidence
            and forecast_confidence.suspect_quality_count == 0
        ):
            reliability = EnvironmentalSignalClassification.AVAILABLE
        elif (
            forecast_confidence.completeness
            >= active_policy.reliability_degraded_completeness
            and forecast_confidence.average_confidence
            >= active_policy.reliability_degraded_confidence
        ):
            reliability = EnvironmentalSignalClassification.DEGRADED
        else:
            reliability = EnvironmentalSignalClassification.UNAVAILABLE
        reliability_evidence = _evidence(
            forecast_records,
            ("facts.air_temperature_celsius",),
        )
        evidence.extend(reliability_evidence)
        signals.append(
            _signal(
                signal_id=f"signal-{location_id}-forecast-reliability",
                location_id=location_id,
                signal_type=EnvironmentalSignalType.FORECAST_RELIABILITY,
                classification=reliability,
                starts_at=starts_at,
                ends_at=ends_at,
                created_at=created_at,
                policy=active_policy,
                confidence=forecast_confidence,
                evidence=reliability_evidence,
                thresholds=_thresholds(
                    active_policy,
                    (
                        "reliability_available_completeness",
                        "reliability_available_confidence",
                        "reliability_degraded_completeness",
                        "reliability_degraded_confidence",
                    ),
                ),
                reason_code=f"forecast_reliability_{reliability.value}",
                summary=f"Forecast reliability is {reliability.value}.",
                detail=(
                    f"Forecast completeness is {forecast_confidence.completeness:.2f}; "
                    f"average confidence is {forecast_confidence.average_confidence:.2f}."
                ),
            )
        )

    unique_evidence = tuple(dict.fromkeys(item.evidence_id for item in evidence))
    evidence_by_id = {item.evidence_id: item for item in evidence}
    return EnvironmentalSignalAnalysis(
        analysis_window=analysis_window,
        created_at=created_at,
        policy_id=active_policy.policy_id,
        policy_version=active_policy.policy_version,
        evidence=tuple(evidence_by_id[item] for item in unique_evidence),
        signals=tuple(signals),
    )
