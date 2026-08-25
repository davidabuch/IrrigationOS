"""Guided capture of explicit baseline environmental reference evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from ..quantitative_water_balance import canonical_weather_balance_evidence
from ..weather import ObservationWindow, WeatherQualityStatus
from .admission import (
    CommissioningAssessment,
    CommissioningPurpose,
    PurposeReadinessState,
)
from .baseline_scaling import select_exact_observation_window
from .commissioning import (
    BaselineEnvironmentalReference,
    BaselineReferenceSource,
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    SerializableCommissioningModel,
)
from .models import Confidence

BASELINE_REFERENCE_CAPTURE_SCHEMA_VERSION = 1
BASELINE_REFERENCE_CAPTURE_POLICY_VERSION = "1.0.0"
SUPPORTED_REFERENCE_PERIOD_HOURS = (24, 48)


class BaselineReferenceCaptureStatus(StrEnum):
    """Terminal non-authorizing result of one guided capture request."""

    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CaptureBaselineReferenceRequest(SerializableCommissioningModel):
    """Explicit user intent to capture a representative dry reference period."""

    identity: CanonicalZoneIdentity
    expected_baseline_runtime_seconds: int
    period_hours: int
    representative_dry_condition_confirmed: bool
    replace_existing_reference_confirmed: bool
    captured_at: datetime

    def __post_init__(self) -> None:
        if self.expected_baseline_runtime_seconds <= 0:
            raise ValueError("expected baseline runtime must be positive")
        if self.period_hours not in SUPPORTED_REFERENCE_PERIOD_HOURS:
            raise ValueError("unsupported baseline reference period")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BaselineReferenceCaptureResult(SerializableCommissioningModel):
    """Immutable proposed reference; persistence remains a separate transaction."""

    identity: CanonicalZoneIdentity
    status: BaselineReferenceCaptureStatus
    proposed_reference: BaselineEnvironmentalReference | None
    baseline_runtime_seconds: int | None
    observed_precipitation_mm: float | None
    observed_mean_air_temperature_celsius: float | None
    confidence: float
    blocker_codes: tuple[str, ...]
    advisory_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    schema_version: int = BASELINE_REFERENCE_CAPTURE_SCHEMA_VERSION
    policy_version: str = BASELINE_REFERENCE_CAPTURE_POLICY_VERSION
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != BASELINE_REFERENCE_CAPTURE_SCHEMA_VERSION:
            raise ValueError("unsupported baseline reference capture schema")
        if self.policy_version != BASELINE_REFERENCE_CAPTURE_POLICY_VERSION:
            raise ValueError("unsupported baseline reference capture policy")
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("baseline reference capture cannot authorize execution")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        for values in (self.blocker_codes, self.advisory_codes, self.reason_codes):
            if values != tuple(sorted(set(values))):
                raise ValueError("capture codes must be unique and deterministic")
        if self.status is BaselineReferenceCaptureStatus.READY:
            if self.proposed_reference is None or self.blocker_codes:
                raise ValueError("ready capture requires unblocked reference evidence")
        elif self.proposed_reference is not None:
            raise ValueError("blocked capture cannot propose a reference")


def capture_baseline_environmental_reference(
    profile: CommissionedZoneProfile,
    commissioning: CommissioningAssessment,
    request: CaptureBaselineReferenceRequest,
    *,
    observations: ObservationWindow | None,
) -> BaselineReferenceCaptureResult:
    """Capture exact normalized evidence without deriving ET0 from temperature."""
    blockers: set[str] = set()
    advisories: set[str] = set()
    reasons: set[str] = {"calibration_evidence_only_no_execution_authority"}
    if request.identity != profile.identity:
        raise ValueError("capture request identity does not match commissioned zone")
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
    if (
        baseline is not None
        and baseline.runtime_seconds != request.expected_baseline_runtime_seconds
    ):
        blockers.add("baseline_runtime_changed")
    if not request.representative_dry_condition_confirmed:
        blockers.add("representative_dry_condition_not_confirmed")
    if (
        baseline is not None
        and baseline.environmental_reference is not None
        and not request.replace_existing_reference_confirmed
    ):
        blockers.add("reference_replacement_not_confirmed")

    selected = select_exact_observation_window(observations, request.period_hours)
    if observations is None:
        blockers.add("environmental_observations_unavailable")
    elif selected is None:
        blockers.add("reference_period_incomplete")
    elif request.captured_at < selected.ends_at:
        blockers.add("environmental_observation_from_future")
    elif request.captured_at - selected.ends_at > timedelta(hours=6):
        blockers.add("environmental_observations_stale")

    et0, rain, _forecast, evidence = canonical_weather_balance_evidence(selected, None)
    temperatures: list[float] = []
    fact_confidences: list[float] = []
    sources: set[str] = set()
    quality = "good"
    if selected is not None:
        for observation in selected.observations:
            facts = (
                observation.facts.reference_evapotranspiration_mm,
                observation.facts.precipitation_mm,
                observation.facts.air_temperature_celsius,
            )
            if any(
                not fact.is_known
                or not isinstance(fact.value, int | float)
                or isinstance(fact.value, bool)
                or fact.quality.status
                not in {WeatherQualityStatus.GOOD, WeatherQualityStatus.ESTIMATED}
                for fact in facts
            ):
                blockers.add("environmental_reference_facts_incomplete")
                continue
            temperature = observation.facts.air_temperature_celsius
            temperature_value = temperature.value
            if not isinstance(temperature_value, int | float) or isinstance(
                temperature_value, bool
            ):
                blockers.add("environmental_reference_facts_incomplete")
                continue
            temperatures.append(float(temperature_value))
            fact_confidences.extend(fact.confidence for fact in facts)
            sources.update(fact.provenance.source for fact in facts)
            if any(fact.quality.status is WeatherQualityStatus.ESTIMATED for fact in facts):
                quality = "estimated"
    confidence = min(fact_confidences, default=0.0)
    if confidence < 0.6:
        blockers.add("environmental_reference_confidence_insufficient")
    et0_value = None if et0 is None else et0.scalar
    rain_value = None if rain is None else rain.scalar
    if et0_value is None or et0_value <= 0:
        blockers.add("reference_et0_invalid")
    if rain_value is None:
        blockers.add("reference_precipitation_unavailable")
    elif rain_value != 0:
        blockers.add("rainy_period_not_valid_dry_reference")
    if selected is not None and len(temperatures) != request.period_hours:
        blockers.add("reference_temperature_incomplete")

    proposed: BaselineEnvironmentalReference | None = None
    mean_temperature = (
        None if not temperatures else sum(temperatures) / len(temperatures)
    )
    if not blockers and et0_value is not None and mean_temperature is not None:
        proposed = BaselineEnvironmentalReference(
            reference_et0_mm=et0_value,
            period_hours=request.period_hours,
            observed_at=selected.ends_at if selected is not None else request.captured_at,
            source=";".join(sorted(sources)),
            confidence=_qualitative_confidence(confidence),
            observed_air_temperature_celsius=mean_temperature,
            quality=quality,
            capture_method=BaselineReferenceSource.OBSERVED_ENVIRONMENT_CAPTURE,
            captured_at=request.captured_at,
            evidence_ids=tuple(sorted(item.evidence_id for item in evidence)),
        )
        reasons.add("dry_reference_captured_from_normalized_environment")
        if baseline is not None and baseline.environmental_reference is not None:
            advisories.add("existing_reference_will_be_preserved_in_history")
    return BaselineReferenceCaptureResult(
        identity=profile.identity,
        status=(
            BaselineReferenceCaptureStatus.READY
            if proposed is not None
            else BaselineReferenceCaptureStatus.BLOCKED
        ),
        proposed_reference=proposed,
        baseline_runtime_seconds=None if baseline is None else baseline.runtime_seconds,
        observed_precipitation_mm=rain_value,
        observed_mean_air_temperature_celsius=mean_temperature,
        confidence=confidence,
        blocker_codes=tuple(sorted(blockers)),
        advisory_codes=tuple(sorted(advisories)),
        reason_codes=tuple(sorted(reasons)),
    )


def apply_baseline_reference_capture(
    profile: CommissionedZoneProfile,
    result: BaselineReferenceCaptureResult,
) -> CommissionedZoneProfile:
    """Apply one successful capture while retaining prior reference provenance."""
    if result.identity != profile.identity:
        raise ValueError("capture result identity does not match commissioned zone")
    if (
        result.status is not BaselineReferenceCaptureStatus.READY
        or result.proposed_reference is None
    ):
        raise ValueError("only a ready baseline reference capture may be applied")
    updated_sources = []
    matched = 0
    for source in profile.demand_sources:
        baseline = source.calibrated_baseline
        if baseline is None:
            updated_sources.append(source)
            continue
        matched += 1
        if (
            baseline.environmental_reference is not None
            and _same_source_reference(
                baseline.environmental_reference, result.proposed_reference
            )
        ):
            updated_sources.append(source)
            continue
        history = baseline.reference_history
        if baseline.environmental_reference is not None:
            history = (*history, baseline.environmental_reference)
        updated_sources.append(
            replace(
                source,
                calibrated_baseline=replace(
                    baseline,
                    environmental_reference=result.proposed_reference,
                    reference_history=history,
                ),
            )
        )
    if matched != 1:
        raise ValueError("capture requires exactly one calibrated baseline")
    return replace(
        profile,
        demand_sources=tuple(updated_sources),
        execution_authorized=False,
        live_control_authorized=False,
    )


def _same_source_reference(
    first: BaselineEnvironmentalReference,
    second: BaselineEnvironmentalReference,
) -> bool:
    """Ignore only the later capture action when source evidence is identical."""
    return (
        first.reference_et0_mm == second.reference_et0_mm
        and first.period_hours == second.period_hours
        and first.observed_at == second.observed_at
        and first.source == second.source
        and first.confidence is second.confidence
        and first.observed_air_temperature_celsius
        == second.observed_air_temperature_celsius
        and first.quality == second.quality
        and first.capture_method is second.capture_method
        and first.evidence_ids == second.evidence_ids
    )


def _qualitative_confidence(confidence: float) -> Confidence:
    if confidence >= 0.8:
        return Confidence.HIGH
    if confidence >= 0.6:
        return Confidence.MODERATE
    return Confidence.LOW
