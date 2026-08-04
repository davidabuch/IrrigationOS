"""Deterministic environmental water and drying calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from ..weather.models import (
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
    EnvironmentalIntelligenceReport,
    EnvironmentalProvenance,
    EnvironmentalProvenanceType,
    EnvironmentalSignal,
    EnvironmentalSignalClassification,
    EnvironmentalSignalType,
    EnvironmentalThreshold,
)

ALGORITHM_SUITE_VERSION = "environment-water-drying-v1"
CONFIDENCE_POLICY_VERSION = "weather-fact-average-v1"


class DryingClassification(StrEnum):
    """Stable atmospheric wetting and drying classifications."""

    STRONGLY_WETTING = "strongly_wetting"
    WETTING = "wetting"
    BALANCED = "balanced"
    DRYING = "drying"
    STRONGLY_DRYING = "strongly_drying"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EnvironmentalCalculationPolicy:
    """Explicit thresholds for atmospheric wetting and drying classification."""

    policy_id: str = "environment-water-drying-default"
    policy_version: str = "1.0.0"
    strongly_wetting_maximum_mm: float = -5.0
    wetting_maximum_mm: float = -1.0
    balanced_maximum_mm: float = 1.0
    drying_maximum_mm: float = 5.0

    def __post_init__(self) -> None:
        values = (
            self.strongly_wetting_maximum_mm,
            self.wetting_maximum_mm,
            self.balanced_maximum_mm,
            self.drying_maximum_mm,
        )
        if any(isinstance(value, bool) or not isfinite(value) for value in values):
            raise ValueError("drying thresholds must be finite numbers")
        if tuple(sorted(values)) != values or len(set(values)) != len(values):
            raise ValueError("drying thresholds must be strictly increasing")

    def classify(self, atmospheric_balance_mm: float | None) -> DryingClassification:
        """Classify precipitation minus reference ET0."""
        if atmospheric_balance_mm is None:
            return DryingClassification.UNAVAILABLE
        if atmospheric_balance_mm <= self.strongly_wetting_maximum_mm:
            return DryingClassification.STRONGLY_WETTING
        if atmospheric_balance_mm <= self.wetting_maximum_mm:
            return DryingClassification.WETTING
        if atmospheric_balance_mm <= self.balanced_maximum_mm:
            return DryingClassification.BALANCED
        if atmospheric_balance_mm <= self.drying_maximum_mm:
            return DryingClassification.DRYING
        return DryingClassification.STRONGLY_DRYING


@dataclass(frozen=True, slots=True)
class EnvironmentalMetricSummary:
    """Completeness-aware total of one canonical weather metric."""

    total_mm: float | None
    known_count: int
    required_count: int
    missing_count: int
    average_confidence: float
    good_quality_count: int
    estimated_quality_count: int
    suspect_quality_count: int
    unavailable_quality_count: int

    @property
    def is_complete(self) -> bool:
        """Return whether every required source fact was known."""
        return self.required_count > 0 and self.missing_count == 0


@dataclass(frozen=True, slots=True)
class AtmosphericBalanceSummary:
    """Precipitation minus reference ET0, never a soil or plant balance."""

    precipitation: EnvironmentalMetricSummary
    reference_evapotranspiration: EnvironmentalMetricSummary
    balance_mm: float | None
    classification: DryingClassification


@dataclass(frozen=True, slots=True)
class WaterAndDryingAnalysis:
    """Detailed deterministic result plus the canonical report envelope."""

    observed: AtmosphericBalanceSummary | None
    forecast: AtmosphericBalanceSummary | None
    report: EnvironmentalIntelligenceReport


def _quality_counts(facts: tuple[WeatherFact[float], ...]) -> tuple[int, int, int, int]:
    good = sum(fact.quality.status is WeatherQualityStatus.GOOD for fact in facts)
    estimated = sum(
        fact.quality.status is WeatherQualityStatus.ESTIMATED for fact in facts
    )
    suspect = sum(fact.quality.status is WeatherQualityStatus.SUSPECT for fact in facts)
    unavailable = sum(
        fact.quality.status is WeatherQualityStatus.UNAVAILABLE for fact in facts
    )
    return good, estimated, suspect, unavailable


def _summarize_metric(facts: tuple[WeatherFact[float], ...]) -> EnvironmentalMetricSummary:
    known = tuple(
        fact
        for fact in facts
        if fact.is_known and fact.value is not None
    )
    known_values = tuple(
        fact.value
        for fact in known
        if fact.value is not None
    )
    missing_count = len(facts) - len(known)
    good, estimated, suspect, unavailable = _quality_counts(facts)
    total = (
        sum(known_values)
        if known_values and not missing_count
        else None
    )
    average_confidence = (
        sum(fact.confidence for fact in known) / len(known) if known else 0.0
    )
    return EnvironmentalMetricSummary(
        total_mm=total,
        known_count=len(known),
        required_count=len(facts),
        missing_count=missing_count,
        average_confidence=average_confidence,
        good_quality_count=good,
        estimated_quality_count=estimated,
        suspect_quality_count=suspect,
        unavailable_quality_count=unavailable,
    )


def _balance(
    precipitation: tuple[WeatherFact[float], ...],
    reference_et0: tuple[WeatherFact[float], ...],
    policy: EnvironmentalCalculationPolicy,
) -> AtmosphericBalanceSummary:
    precipitation_summary = _summarize_metric(precipitation)
    et0_summary = _summarize_metric(reference_et0)
    balance_mm = None
    if precipitation_summary.is_complete and et0_summary.is_complete:
        assert precipitation_summary.total_mm is not None
        assert et0_summary.total_mm is not None
        balance_mm = precipitation_summary.total_mm - et0_summary.total_mm
    return AtmosphericBalanceSummary(
        precipitation=precipitation_summary,
        reference_evapotranspiration=et0_summary,
        balance_mm=balance_mm,
        classification=policy.classify(balance_mm),
    )


def _confidence(
    precipitation: EnvironmentalMetricSummary,
    et0: EnvironmentalMetricSummary,
) -> EnvironmentalConfidence:
    required = precipitation.required_count + et0.required_count
    known = precipitation.known_count + et0.known_count
    weighted_confidence = (
        precipitation.average_confidence * precipitation.known_count
        + et0.average_confidence * et0.known_count
    )
    return EnvironmentalConfidence(
        completeness=known / required if required else 0.0,
        average_confidence=weighted_confidence / known if known else 0.0,
        known_fact_count=known,
        required_fact_count=required,
        good_quality_count=precipitation.good_quality_count + et0.good_quality_count,
        estimated_quality_count=(
            precipitation.estimated_quality_count + et0.estimated_quality_count
        ),
        suspect_quality_count=(
            precipitation.suspect_quality_count + et0.suspect_quality_count
        ),
        unavailable_quality_count=(
            precipitation.unavailable_quality_count + et0.unavailable_quality_count
        ),
        confidence_policy_version=CONFIDENCE_POLICY_VERSION,
    )


def _signal_classification(
    classification: DryingClassification,
) -> EnvironmentalSignalClassification:
    return EnvironmentalSignalClassification(classification.value)


def _evidence_for_observations(
    observations: tuple[HistoricalWeatherObservation, ...],
) -> tuple[EnvironmentalEvidenceReference, ...]:
    evidence: list[EnvironmentalEvidenceReference] = []
    for observation in observations:
        for suffix, fact_path in (
            ("precip", "facts.precipitation_mm"),
            ("et0", "facts.reference_evapotranspiration_mm"),
        ):
            evidence.append(
                EnvironmentalEvidenceReference(
                    evidence_id=f"evidence-{observation.observation_id}-{suffix}",
                    location_id=observation.location_id,
                    evidence_type=EnvironmentalEvidenceType.WEATHER_FACT,
                    record_id=observation.observation_id,
                    fact_path=fact_path,
                )
            )
    return tuple(evidence)


def _evidence_for_forecasts(
    forecasts: tuple[HourlyWeatherForecast, ...],
) -> tuple[EnvironmentalEvidenceReference, ...]:
    evidence: list[EnvironmentalEvidenceReference] = []
    for forecast in forecasts:
        for suffix, fact_path in (
            ("precip", "facts.precipitation_mm"),
            ("et0", "facts.reference_evapotranspiration_mm"),
        ):
            evidence.append(
                EnvironmentalEvidenceReference(
                    evidence_id=f"evidence-{forecast.forecast_id}-{suffix}",
                    location_id=forecast.location_id,
                    evidence_type=EnvironmentalEvidenceType.WEATHER_FACT,
                    record_id=forecast.forecast_id,
                    fact_path=fact_path,
                )
            )
    return tuple(evidence)


def _explanation(label: str, summary: AtmosphericBalanceSummary) -> EnvironmentalExplanation:
    if summary.balance_mm is None:
        return EnvironmentalExplanation(
            reason_codes=(f"{label}_atmospheric_balance_unavailable",),
            summary=f"{label.title()} atmospheric balance is unavailable.",
            detail=(
                "One or more precipitation or reference evapotranspiration facts "
                "were unavailable; missing values were not treated as zero."
            ),
        )
    return EnvironmentalExplanation(
        reason_codes=(f"{label}_{summary.classification.value}",),
        summary=(
            f"{label.title()} atmospheric balance is {summary.balance_mm:.2f} mm "
            f"({summary.classification.value.replace('_', ' ')})."
        ),
        detail=(
            f"Precipitation {summary.precipitation.total_mm:.2f} mm minus reference "
            f"ET0 {summary.reference_evapotranspiration.total_mm:.2f} mm. This is "
            "not a soil-water balance or plant-water-demand estimate."
        ),
    )


def analyze_water_and_drying(
    *,
    report_id: str,
    created_at: datetime,
    observation_window: ObservationWindow | None = None,
    forecast_window: ForecastWindow | None = None,
    policy: EnvironmentalCalculationPolicy | None = None,
) -> WaterAndDryingAnalysis:
    """Calculate conservative atmospheric water and drying summaries."""
    if observation_window is None and forecast_window is None:
        raise ValueError("analysis requires an observation or forecast window")
    policy = policy or EnvironmentalCalculationPolicy()

    locations = {
        window.location_id
        for window in (observation_window, forecast_window)
        if window is not None
    }
    if len(locations) != 1:
        raise ValueError("observation and forecast windows must share one location")
    location_id = next(iter(locations))

    starts = [window.starts_at for window in (observation_window, forecast_window) if window]
    ends = [window.ends_at for window in (observation_window, forecast_window) if window]
    analysis_window = EnvironmentalAnalysisWindow(
        window_id=f"analysis-{report_id}",
        location_id=location_id,
        starts_at=min(starts),
        ends_at=max(ends),
        observation_ids=(
            tuple(item.observation_id for item in observation_window.observations)
            if observation_window
            else ()
        ),
        forecast_ids=(
            tuple(item.forecast_id for item in forecast_window.hourly_forecasts)
            if forecast_window
            else ()
        ),
    )

    observed = None
    observed_evidence: tuple[EnvironmentalEvidenceReference, ...] = ()
    if observation_window:
        observations = observation_window.observations
        observed = _balance(
            tuple(item.facts.precipitation_mm for item in observations),
            tuple(item.facts.reference_evapotranspiration_mm for item in observations),
            policy,
        )
        observed_evidence = _evidence_for_observations(observations)

    forecast = None
    forecast_evidence: tuple[EnvironmentalEvidenceReference, ...] = ()
    if forecast_window:
        forecasts = forecast_window.hourly_forecasts
        if not forecasts:
            raise ValueError("water and drying analysis requires hourly forecasts")
        forecast = _balance(
            tuple(item.facts.precipitation_mm for item in forecasts),
            tuple(item.facts.reference_evapotranspiration_mm for item in forecasts),
            policy,
        )
        forecast_evidence = _evidence_for_forecasts(forecasts)

    evidence = (*observed_evidence, *forecast_evidence)
    signals: list[EnvironmentalSignal] = []
    thresholds = (
        EnvironmentalThreshold(
            name="strongly_wetting_maximum_mm",
            value=policy.strongly_wetting_maximum_mm,
            unit="mm",
            description="Maximum balance classified strongly wetting.",
        ),
        EnvironmentalThreshold(
            name="wetting_maximum_mm",
            value=policy.wetting_maximum_mm,
            unit="mm",
            description="Maximum balance classified wetting.",
        ),
        EnvironmentalThreshold(
            name="balanced_maximum_mm",
            value=policy.balanced_maximum_mm,
            unit="mm",
            description="Maximum balance classified balanced.",
        ),
        EnvironmentalThreshold(
            name="drying_maximum_mm",
            value=policy.drying_maximum_mm,
            unit="mm",
            description="Maximum balance classified drying.",
        ),
    )

    for label, summary, signal_evidence in (
        ("observed", observed, observed_evidence),
        ("forecast", forecast, forecast_evidence),
    ):
        if summary is None:
            continue
        signals.append(
            EnvironmentalSignal(
                signal_id=f"signal-{report_id}-{label}-drying",
                location_id=location_id,
                signal_type=EnvironmentalSignalType.DRYING_TREND,
                classification=_signal_classification(summary.classification),
                analysis_starts_at=analysis_window.starts_at,
                analysis_ends_at=analysis_window.ends_at,
                created_at=created_at,
                algorithm_version=ALGORITHM_SUITE_VERSION,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                confidence=_confidence(
                    summary.precipitation,
                    summary.reference_evapotranspiration,
                ),
                explanation=_explanation(label, summary),
                evidence_ids=tuple(item.evidence_id for item in signal_evidence),
                threshold_values=thresholds,
            )
        )

    all_precip = [summary.precipitation for summary in (observed, forecast) if summary]
    all_et0 = [summary.reference_evapotranspiration for summary in (observed, forecast) if summary]
    report_confidence = _confidence(
        EnvironmentalMetricSummary(
            total_mm=None,
            known_count=sum(item.known_count for item in all_precip),
            required_count=sum(item.required_count for item in all_precip),
            missing_count=sum(item.missing_count for item in all_precip),
            average_confidence=(
                sum(item.average_confidence * item.known_count for item in all_precip)
                / sum(item.known_count for item in all_precip)
                if sum(item.known_count for item in all_precip)
                else 0.0
            ),
            good_quality_count=sum(item.good_quality_count for item in all_precip),
            estimated_quality_count=sum(
                item.estimated_quality_count for item in all_precip
            ),
            suspect_quality_count=sum(item.suspect_quality_count for item in all_precip),
            unavailable_quality_count=sum(
                item.unavailable_quality_count for item in all_precip
            ),
        ),
        EnvironmentalMetricSummary(
            total_mm=None,
            known_count=sum(item.known_count for item in all_et0),
            required_count=sum(item.required_count for item in all_et0),
            missing_count=sum(item.missing_count for item in all_et0),
            average_confidence=(
                sum(item.average_confidence * item.known_count for item in all_et0)
                / sum(item.known_count for item in all_et0)
                if sum(item.known_count for item in all_et0)
                else 0.0
            ),
            good_quality_count=sum(item.good_quality_count for item in all_et0),
            estimated_quality_count=sum(item.estimated_quality_count for item in all_et0),
            suspect_quality_count=sum(item.suspect_quality_count for item in all_et0),
            unavailable_quality_count=sum(item.unavailable_quality_count for item in all_et0),
        ),
    )

    report = EnvironmentalIntelligenceReport(
        report_id=report_id,
        schema_version=1,
        analysis_window=analysis_window,
        created_at=created_at,
        algorithm_suite_version=ALGORITHM_SUITE_VERSION,
        provenance=EnvironmentalProvenance(
            source="environment.engine.analyze_water_and_drying",
            provenance_type=EnvironmentalProvenanceType.DETERMINISTIC_ENGINE,
            source_reference=policy.policy_version,
        ),
        confidence=report_confidence,
        evidence=evidence,
        signals=tuple(signals),
    )
    return WaterAndDryingAnalysis(observed=observed, forecast=forecast, report=report)
