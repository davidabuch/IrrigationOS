"""Pure advisory environmental scaling for user-calibrated baselines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite

from ..quantitative_water_balance import (
    EffectivePrecipitationPolicy,
    ForecastAdjustmentPolicy,
    ForecastPrecipitationEvidence,
    WaterBalanceEvidence,
    WaterQuantity,
    apply_effective_precipitation_policy,
    canonical_weather_balance_evidence,
)
from ..weather import ForecastWindow, ObservationWindow
from .admission import (
    CommissioningAssessment,
    CommissioningPurpose,
    PurposeReadinessState,
)
from .commissioning import (
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    SerializableCommissioningModel,
)
from .models import Confidence

BASELINE_SCALING_SCHEMA_VERSION = 1
BASELINE_SCALING_ALGORITHM_VERSION = "1.0.0"
BASELINE_SCALING_POLICY_VERSION = "1.0.0"


class BaselineScalingStatus(StrEnum):
    """Fail-closed advisory scaling outcome."""

    READY = "ready"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    STALE_ENVIRONMENTAL_DATA = "stale_environmental_data"
    PRECIPITATION_HOLD = "precipitation_hold"
    FORECAST_HOLD = "forecast_hold"
    SCALING_WITHHELD = "scaling_withheld"


@dataclass(frozen=True, slots=True)
class BaselineScalingPolicy(SerializableCommissioningModel):
    """Versioned product-safety envelope around an ET0 demand ratio."""

    minimum_scaling_factor: float = 0.5
    maximum_scaling_factor: float = 1.5
    maximum_observation_age_hours: int = 6
    minimum_evidence_confidence: float = 0.6
    policy_version: str = BASELINE_SCALING_POLICY_VERSION

    def __post_init__(self) -> None:
        values = (self.minimum_scaling_factor, self.maximum_scaling_factor)
        if any(not isfinite(value) or value < 0 for value in values):
            raise ValueError("scaling bounds must be finite and non-negative")
        if self.minimum_scaling_factor > self.maximum_scaling_factor:
            raise ValueError("minimum scaling factor cannot exceed maximum")
        if self.maximum_observation_age_hours < 1:
            raise ValueError("maximum observation age must be positive")
        if not 0 <= self.minimum_evidence_confidence <= 1:
            raise ValueError("minimum evidence confidence must be between zero and one")
        if self.policy_version != BASELINE_SCALING_POLICY_VERSION:
            raise ValueError("unsupported baseline scaling policy")


@dataclass(frozen=True, slots=True)
class BaselineEnvironmentalScalingAssessment(SerializableCommissioningModel):
    """Immutable scientific comparison that never grants execution authority."""

    identity: CanonicalZoneIdentity
    status: BaselineScalingStatus
    baseline_runtime_seconds: int | None
    reference_temperature_celsius: float | None
    reference_et0_mm: float | None
    reference_period_hours: int | None
    current_et0_mm: float | None
    observed_precipitation_mm: float | None
    effective_observed_precipitation_mm: float | None
    forecast_precipitation_mm: float | None
    effective_forecast_precipitation_mm: float | None
    raw_demand_ratio: float | None
    scaling_factor: float | None
    advisory_runtime_seconds: float | None
    observation_ends_at: datetime | None
    generated_at: datetime
    confidence: float
    evidence: tuple[WaterBalanceEvidence, ...]
    blocker_codes: tuple[str, ...]
    advisory_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    schema_version: int = BASELINE_SCALING_SCHEMA_VERSION
    algorithm_version: str = BASELINE_SCALING_ALGORITHM_VERSION
    policy_version: str = BASELINE_SCALING_POLICY_VERSION
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != BASELINE_SCALING_SCHEMA_VERSION:
            raise ValueError("unsupported baseline scaling assessment schema")
        if self.algorithm_version != BASELINE_SCALING_ALGORITHM_VERSION:
            raise ValueError("unsupported baseline scaling algorithm")
        if self.policy_version != BASELINE_SCALING_POLICY_VERSION:
            raise ValueError("unsupported baseline scaling policy")
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("baseline scaling cannot authorize execution")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        for values in (self.blocker_codes, self.advisory_codes, self.reason_codes):
            if values != tuple(sorted(set(values))):
                raise ValueError("assessment codes must be unique and deterministic")


def assess_baseline_environmental_scaling(
    profile: CommissionedZoneProfile,
    commissioning: CommissioningAssessment,
    *,
    observations: ObservationWindow | None,
    forecast: ForecastWindow | None,
    generated_at: datetime,
    effective_precipitation_policy: EffectivePrecipitationPolicy | None = None,
    scaling_policy: BaselineScalingPolicy | None = None,
    forecast_policy: ForecastAdjustmentPolicy | None = None,
) -> BaselineEnvironmentalScalingAssessment:
    """Compare normalized current ET0 with explicit reference ET0 evidence."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    scaling_policy = scaling_policy or BaselineScalingPolicy()
    forecast_policy = forecast_policy or ForecastAdjustmentPolicy()
    blockers: set[str] = set()
    advisories: set[str] = set()
    reasons: set[str] = set()
    readiness = commissioning.readiness_for(
        CommissioningPurpose.BASELINE_ENVIRONMENTAL_SCALING
    )
    if readiness.state is not PurposeReadinessState.READY:
        blockers.add("baseline_not_admissible")
    baselines = tuple(
        source.calibrated_baseline
        for source in profile.demand_sources
        if source.calibrated_baseline is not None
    )
    baseline = baselines[0] if len(baselines) == 1 else None
    if not baselines:
        blockers.add("calibrated_baseline_missing")
    elif len(baselines) > 1:
        blockers.add("calibrated_baseline_ambiguous")
    reference = None if baseline is None else baseline.environmental_reference
    if reference is None:
        blockers.add("reference_et0_unavailable")
    elif reference.confidence is Confidence.LOW:
        blockers.add("reference_et0_confidence_insufficient")
    if baseline is not None and baseline.reference_recent_precipitation_mm != 0:
        blockers.add("reference_condition_not_dry")

    selected = select_exact_observation_window(
        observations, reference.period_hours if reference else 0
    )
    if observations is None:
        blockers.add("current_environmental_evidence_unavailable")
    elif selected is None:
        blockers.add("current_environmental_window_incomplete")
    elif generated_at - selected.ends_at > timedelta(
        hours=scaling_policy.maximum_observation_age_hours
    ):
        blockers.add("current_environmental_evidence_stale")

    current_et, observed_rain, _unused_forecast, current_evidence = (
        canonical_weather_balance_evidence(selected, None)
    )
    _unused_et, _unused_rain, forecast_evidence, forecast_evidence_items = (
        canonical_weather_balance_evidence(None, forecast)
    )
    evidence = tuple(
        sorted((*current_evidence, *forecast_evidence_items), key=lambda item: item.evidence_id)
    )
    if current_et is None:
        blockers.add("current_reference_et0_unavailable")
    if observed_rain is None:
        blockers.add("observed_precipitation_unavailable")
    evidence_confidence = min(
        (item.confidence for item in current_evidence), default=0.0
    )
    if current_evidence and evidence_confidence < scaling_policy.minimum_evidence_confidence:
        blockers.add("current_environmental_confidence_insufficient")

    effective_rain = apply_effective_precipitation_policy(
        observed_rain, effective_precipitation_policy
    )
    if observed_rain is not None and _quantity(observed_rain) > 0 and effective_rain is None:
        blockers.add("effective_precipitation_policy_unavailable")
    effective_forecast = apply_effective_precipitation_policy(
        None if forecast_evidence is None else forecast_evidence.precipitation_mm,
        effective_precipitation_policy,
    )
    raw_ratio: float | None = None
    scaling_factor: float | None = None
    runtime: float | None = None
    status = BaselineScalingStatus.INSUFFICIENT_EVIDENCE
    if not blockers and baseline is not None and reference is not None:
        current_et_value = _quantity(current_et)
        effective_rain_value = _quantity(effective_rain)
        net_demand = max(0.0, current_et_value - effective_rain_value)
        raw_ratio = net_demand / reference.reference_et0_mm
        scaling_factor = min(
            scaling_policy.maximum_scaling_factor,
            max(scaling_policy.minimum_scaling_factor, raw_ratio),
        )
        runtime = round(baseline.runtime_seconds * scaling_factor, 3)
        if net_demand == 0 and _quantity(observed_rain) > 0:
            status = BaselineScalingStatus.PRECIPITATION_HOLD
            scaling_factor = 0.0
            runtime = 0.0
            reasons.add("observed_effective_precipitation_holds_advisory_irrigation")
        elif _forecast_qualifies(
            forecast_evidence, effective_forecast, generated_at, forecast_policy
        ):
            status = BaselineScalingStatus.FORECAST_HOLD
            runtime = None
            reasons.add("qualifying_forecast_precipitation_holds_advisory_irrigation")
        else:
            status = BaselineScalingStatus.READY
            reasons.add("current_et0_compared_with_explicit_reference_et0")
            if raw_ratio != scaling_factor:
                advisories.add("environmental_scaling_bounded_by_policy")
            if forecast_evidence is not None:
                advisories.add("forecast_precipitation_did_not_qualify_for_hold")
    elif "current_environmental_evidence_stale" in blockers:
        status = BaselineScalingStatus.STALE_ENVIRONMENTAL_DATA
    elif baseline is not None and readiness.state is PurposeReadinessState.READY:
        status = BaselineScalingStatus.SCALING_WITHHELD
    reasons.add("advisory_only_no_execution_authority")
    reference_confidence = (
        0.0 if reference is None else _confidence_value(reference.confidence)
    )
    return BaselineEnvironmentalScalingAssessment(
        identity=profile.identity,
        status=status,
        baseline_runtime_seconds=None if baseline is None else baseline.runtime_seconds,
        reference_temperature_celsius=(
            None if baseline is None else baseline.reference_air_temperature_celsius
        ),
        reference_et0_mm=None if reference is None else reference.reference_et0_mm,
        reference_period_hours=None if reference is None else reference.period_hours,
        current_et0_mm=None if current_et is None else _quantity(current_et),
        observed_precipitation_mm=(
            None if observed_rain is None else _quantity(observed_rain)
        ),
        effective_observed_precipitation_mm=(
            None if effective_rain is None else _quantity(effective_rain)
        ),
        forecast_precipitation_mm=(
            None if forecast_evidence is None else _quantity(forecast_evidence.precipitation_mm)
        ),
        effective_forecast_precipitation_mm=(
            None if effective_forecast is None else _quantity(effective_forecast)
        ),
        raw_demand_ratio=raw_ratio,
        scaling_factor=scaling_factor,
        advisory_runtime_seconds=runtime,
        observation_ends_at=None if selected is None else selected.ends_at,
        generated_at=generated_at,
        confidence=min(reference_confidence, evidence_confidence),
        evidence=evidence,
        blocker_codes=tuple(sorted(blockers)),
        advisory_codes=tuple(sorted(advisories)),
        reason_codes=tuple(sorted(reasons)),
    )


def select_exact_observation_window(
    observations: ObservationWindow | None, period_hours: int
) -> ObservationWindow | None:
    """Return the trailing exact contiguous hourly period used by scaling/capture."""
    if observations is None or period_hours < 1:
        return None
    starts_at = observations.ends_at - timedelta(hours=period_hours)
    records = tuple(
        item
        for item in observations.observations
        if starts_at <= item.observed_at < observations.ends_at
    )
    if len(records) != period_hours:
        return None
    if tuple(item.observed_at for item in records) != tuple(
        starts_at + timedelta(hours=index) for index in range(period_hours)
    ):
        return None
    return ObservationWindow(
        window_id=f"baseline.scaling.{observations.window_id}",
        location_id=observations.location_id,
        starts_at=starts_at,
        ends_at=observations.ends_at,
        observations=records,
    )


def _forecast_qualifies(
    forecast: ForecastPrecipitationEvidence | None,
    effective: WaterQuantity | None,
    generated_at: datetime,
    policy: ForecastAdjustmentPolicy,
) -> bool:
    if forecast is None or effective is None:
        return False
    return (
        forecast.issued_at <= generated_at < forecast.window_end
        and generated_at - forecast.issued_at
        <= timedelta(hours=policy.maximum_forecast_age_hours)
        and forecast.window_end - generated_at
        <= timedelta(hours=policy.maximum_horizon_hours)
        and forecast.confidence >= policy.minimum_source_confidence
        and forecast.quality in {"good", "estimated"}
        and _quantity(effective) >= policy.minimum_effective_precipitation_mm
    )


def _quantity(value: WaterQuantity | None) -> float:
    if value is None:
        return 0.0
    if value.scalar is None:
        raise ValueError("baseline scaling requires scalar weather quantities")
    return value.scalar


def _confidence_value(value: Confidence) -> float:
    return {Confidence.LOW: 0.3, Confidence.MODERATE: 0.7, Confidence.HIGH: 1.0}[value]
