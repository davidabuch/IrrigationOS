"""Adapt normalized Home Assistant weather into Environmental Intelligence."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..environment import (
    ENVIRONMENTAL_INTELLIGENCE_SCHEMA_VERSION,
    SIGNAL_ALGORITHM_VERSION,
    SIGNAL_CONFIDENCE_POLICY_VERSION,
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
    EnvironmentalSignalPolicy,
    EnvironmentalSignalType,
)
from ..scientific_inputs import ScientificInputSnapshot

_LOCATION_ID = "property"
_RECORD_ID = "ha.current_weather"


def build_environmental_report(
    scientific_inputs: ScientificInputSnapshot,
    *,
    evaluated_at: datetime,
) -> EnvironmentalIntelligenceReport | None:
    """Build conservative current-condition environmental signals from HA weather."""
    weather = scientific_inputs.weather
    if weather is None:
        return None

    policy = EnvironmentalSignalPolicy()
    starts_at = evaluated_at - timedelta(seconds=1)
    window = EnvironmentalAnalysisWindow(
        window_id="environment.current",
        location_id=_LOCATION_ID,
        starts_at=starts_at,
        ends_at=evaluated_at,
        observation_ids=(_RECORD_ID,),
    )
    evidence: list[EnvironmentalEvidenceReference] = []
    signals: list[EnvironmentalSignal] = []

    if weather.temperature_celsius is not None:
        temperature_evidence = EnvironmentalEvidenceReference(
            evidence_id="evidence.ha.current_temperature",
            location_id=_LOCATION_ID,
            evidence_type=EnvironmentalEvidenceType.CURRENT_OBSERVATION,
            record_id=_RECORD_ID,
            fact_path="temperature_celsius",
        )
        evidence.append(temperature_evidence)
        confidence = _confidence(known=1, required=1)
        heat = _classification_up(
            weather.temperature_celsius,
            (
                policy.heat_low_celsius,
                policy.heat_moderate_celsius,
                policy.heat_high_celsius,
                policy.heat_extreme_celsius,
            ),
        )
        freeze = _classification_down(
            weather.temperature_celsius,
            (
                policy.freeze_low_celsius,
                policy.freeze_moderate_celsius,
                policy.freeze_high_celsius,
                policy.freeze_extreme_celsius,
            ),
        )
        signals.extend(
            (
                _signal(
                    "signal.property.heat",
                    EnvironmentalSignalType.HEAT_EXPOSURE,
                    heat,
                    confidence,
                    (temperature_evidence.evidence_id,),
                    starts_at,
                    evaluated_at,
                    policy,
                ),
                _signal(
                    "signal.property.freeze",
                    EnvironmentalSignalType.FREEZE_POTENTIAL,
                    freeze,
                    confidence,
                    (temperature_evidence.evidence_id,),
                    starts_at,
                    evaluated_at,
                    policy,
                ),
            )
        )

    if weather.wind_speed_meters_per_second is not None:
        wind_evidence = EnvironmentalEvidenceReference(
            evidence_id="evidence.ha.current_wind",
            location_id=_LOCATION_ID,
            evidence_type=EnvironmentalEvidenceType.CURRENT_OBSERVATION,
            record_id=_RECORD_ID,
            fact_path="wind_speed_meters_per_second",
        )
        evidence.append(wind_evidence)
        wind = _classification_up(
            weather.wind_speed_meters_per_second,
            (
                policy.wind_low_mps,
                policy.wind_moderate_mps,
                policy.wind_high_mps,
                policy.wind_extreme_mps,
            ),
        )
        signals.append(
            _signal(
                "signal.property.wind",
                EnvironmentalSignalType.WIND_EXPOSURE,
                wind,
                _confidence(known=1, required=1),
                (wind_evidence.evidence_id,),
                starts_at,
                evaluated_at,
                policy,
            )
        )

    if not signals:
        return None

    return EnvironmentalIntelligenceReport(
        report_id="environment.report.current",
        schema_version=ENVIRONMENTAL_INTELLIGENCE_SCHEMA_VERSION,
        analysis_window=window,
        created_at=evaluated_at,
        algorithm_suite_version=SIGNAL_ALGORITHM_VERSION,
        provenance=EnvironmentalProvenance(
            source="Home Assistant weather entity",
            provenance_type=EnvironmentalProvenanceType.DETERMINISTIC_ENGINE,
            source_reference=weather.entity_id,
        ),
        confidence=_confidence(known=len(evidence), required=len(evidence)),
        evidence=tuple(evidence),
        signals=tuple(signals),
    )


def _classification_up(
    value: float,
    thresholds: tuple[float, float, float, float],
) -> EnvironmentalSignalClassification:
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
    value: float,
    thresholds: tuple[float, float, float, float],
) -> EnvironmentalSignalClassification:
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


def _confidence(*, known: int, required: int) -> EnvironmentalConfidence:
    return EnvironmentalConfidence(
        completeness=known / required if required else 0.0,
        average_confidence=1.0 if known else 0.0,
        known_fact_count=known,
        required_fact_count=required,
        good_quality_count=known,
        estimated_quality_count=0,
        suspect_quality_count=0,
        unavailable_quality_count=required - known,
        confidence_policy_version=SIGNAL_CONFIDENCE_POLICY_VERSION,
    )


def _signal(
    signal_id: str,
    signal_type: EnvironmentalSignalType,
    classification: EnvironmentalSignalClassification,
    confidence: EnvironmentalConfidence,
    evidence_ids: tuple[str, ...],
    starts_at: datetime,
    ends_at: datetime,
    policy: EnvironmentalSignalPolicy,
) -> EnvironmentalSignal:
    return EnvironmentalSignal(
        signal_id=signal_id,
        location_id=_LOCATION_ID,
        signal_type=signal_type,
        classification=classification,
        analysis_starts_at=starts_at,
        analysis_ends_at=ends_at,
        created_at=ends_at,
        algorithm_version=SIGNAL_ALGORITHM_VERSION,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        confidence=confidence,
        explanation=EnvironmentalExplanation(
            reason_codes=(f"current_{signal_type.value}_{classification.value}",),
            summary=(
                f"Current-condition {signal_type.value.replace('_', ' ')} is "
                f"{classification.value}."
            ),
        ),
        evidence_ids=evidence_ids,
    )
