"""Behavioral tests for the Environmental Intelligence foundation."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

MODULE = load_integration_module("environment.models")

SCHEMA_VERSION = MODULE.ENVIRONMENTAL_INTELLIGENCE_SCHEMA_VERSION
EnvironmentalAnalysisWindow = MODULE.EnvironmentalAnalysisWindow
EnvironmentalConfidence = MODULE.EnvironmentalConfidence
EnvironmentalEvidenceReference = MODULE.EnvironmentalEvidenceReference
EnvironmentalEvidenceType = MODULE.EnvironmentalEvidenceType
EnvironmentalExplanation = MODULE.EnvironmentalExplanation
EnvironmentalIntelligenceReport = MODULE.EnvironmentalIntelligenceReport
EnvironmentalProvenance = MODULE.EnvironmentalProvenance
EnvironmentalProvenanceType = MODULE.EnvironmentalProvenanceType
EnvironmentalSignal = MODULE.EnvironmentalSignal
EnvironmentalSignalClassification = MODULE.EnvironmentalSignalClassification
EnvironmentalSignalType = MODULE.EnvironmentalSignalType
EnvironmentalThreshold = MODULE.EnvironmentalThreshold
EnvironmentalThresholdPolicy = MODULE.EnvironmentalThresholdPolicy

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
END = NOW + timedelta(hours=24)
CREATED = END + timedelta(minutes=1)


def confidence(**changes: object) -> Any:
    """Build a valid confidence summary."""
    values: dict[str, object] = {
        "completeness": 0.75,
        "average_confidence": 0.8,
        "known_fact_count": 3,
        "required_fact_count": 4,
        "good_quality_count": 2,
        "estimated_quality_count": 1,
        "suspect_quality_count": 0,
        "unavailable_quality_count": 1,
        "confidence_policy_version": "confidence-v1",
    }
    values.update(changes)
    return EnvironmentalConfidence(**values)


def window(**changes: object) -> Any:
    """Build a valid analysis window."""
    values: dict[str, object] = {
        "window_id": "window-1",
        "location_id": "property-1",
        "starts_at": NOW,
        "ends_at": END,
        "observation_ids": ("observation-1",),
        "forecast_ids": ("forecast-1",),
    }
    values.update(changes)
    return EnvironmentalAnalysisWindow(**values)


def evidence(**changes: object) -> Any:
    """Build a valid evidence reference."""
    values: dict[str, object] = {
        "evidence_id": "evidence-1",
        "location_id": "property-1",
        "evidence_type": EnvironmentalEvidenceType.HISTORICAL_OBSERVATION,
        "record_id": "observation-1",
        "fact_path": "facts.reference_evapotranspiration_mm",
    }
    values.update(changes)
    return EnvironmentalEvidenceReference(**values)


def threshold(**changes: object) -> Any:
    """Build a named threshold."""
    values: dict[str, object] = {
        "name": "strong_drying_mm",
        "value": 5.0,
        "unit": "mm",
        "description": "Minimum atmospheric deficit for strong drying",
    }
    values.update(changes)
    return EnvironmentalThreshold(**values)


def signal(**changes: object) -> Any:
    """Build an explainable environmental signal."""
    values: dict[str, object] = {
        "signal_id": "signal-1",
        "location_id": "property-1",
        "signal_type": EnvironmentalSignalType.DRYING_TREND,
        "classification": EnvironmentalSignalClassification.STRONGLY_DRYING,
        "analysis_starts_at": NOW,
        "analysis_ends_at": END,
        "created_at": CREATED,
        "algorithm_version": "drying-v1",
        "policy_id": "drying-policy",
        "policy_version": "1.0",
        "confidence": confidence(),
        "explanation": EnvironmentalExplanation(
            reason_codes=("observed_et0_exceeds_precipitation",),
            summary="Strong atmospheric drying during the analysis period.",
        ),
        "evidence_ids": ("evidence-1",),
        "threshold_values": (threshold(),),
    }
    values.update(changes)
    return EnvironmentalSignal(**values)


def report(**changes: object) -> Any:
    """Build a valid Environmental Intelligence report."""
    values: dict[str, object] = {
        "report_id": "report-1",
        "schema_version": SCHEMA_VERSION,
        "analysis_window": window(),
        "created_at": CREATED,
        "algorithm_suite_version": "environment-suite-v1",
        "provenance": EnvironmentalProvenance(
            source="irrigationos_environment_engine",
            provenance_type=EnvironmentalProvenanceType.DETERMINISTIC_ENGINE,
        ),
        "confidence": confidence(),
        "evidence": (evidence(),),
        "signals": (signal(),),
    }
    values.update(changes)
    return EnvironmentalIntelligenceReport(**values)


def test_report_serializes_deterministically() -> None:
    """Reports produce stable persistence- and audit-safe dictionaries."""
    current = report()
    first = current.to_dict()
    second = current.to_dict()
    assert first == second
    assert first["schema_version"] == 1
    assert first["signals"][0]["signal_type"] == "drying_trend"
    assert first["signals"][0]["classification"] == "strongly_drying"
    assert first["created_at"] == "2026-08-04T12:01:00+00:00"


def test_models_are_frozen_and_slotted() -> None:
    """Environmental conclusions cannot be mutated in place."""
    current = report()
    with pytest.raises(FrozenInstanceError):
        current.__setattr__("report_id", "changed")
    with pytest.raises((AttributeError, TypeError)):
        current.__setattr__("unexpected", "value")


def test_analysis_window_requires_inputs_and_valid_time() -> None:
    """Analysis windows are bounded and evidence-bearing."""
    with pytest.raises(ValueError, match="must follow"):
        window(ends_at=NOW)
    with pytest.raises(ValueError, match="requires observation or forecast"):
        window(observation_ids=(), forecast_ids=())
    with pytest.raises(ValueError, match="duplicate"):
        window(observation_ids=("observation-1", "observation-1"))


def test_confidence_keeps_completeness_and_quality_consistent() -> None:
    """Confidence summaries cannot contradict their fact counts."""
    with pytest.raises(ValueError, match="completeness must match"):
        confidence(completeness=1.0)
    with pytest.raises(ValueError, match="quality counts"):
        confidence(good_quality_count=3)
    with pytest.raises(ValueError, match="cannot exceed"):
        confidence(known_fact_count=5)


def test_threshold_policy_requires_explicit_unique_values() -> None:
    """Policies reject hidden or duplicate threshold definitions."""
    policy = EnvironmentalThresholdPolicy(
        policy_id="drying-policy",
        policy_version="1.0",
        description="Atmospheric drying thresholds",
        thresholds=(threshold(),),
    )
    assert policy.thresholds[0].unit == "mm"
    with pytest.raises(ValueError, match="at least one"):
        replace(policy, thresholds=())
    with pytest.raises(ValueError, match="duplicates"):
        replace(policy, thresholds=(threshold(), threshold()))


def test_threshold_values_must_be_finite_and_named() -> None:
    """Thresholds use canonical names, units, and finite numbers."""
    with pytest.raises(ValueError, match="lower_snake_case"):
        threshold(name="Strong Drying")
    with pytest.raises(ValueError, match="finite"):
        threshold(value=float("inf"))
    with pytest.raises(ValueError, match="canonical"):
        threshold(unit="millimeters of rain")


def test_explanation_requires_stable_reason_codes() -> None:
    """Reason codes remain machine-readable and unique."""
    with pytest.raises(ValueError, match="at least one"):
        EnvironmentalExplanation(reason_codes=(), summary="Missing reason")
    with pytest.raises(ValueError, match="lower_snake_case"):
        EnvironmentalExplanation(reason_codes=("Bad Reason",), summary="Invalid")
    with pytest.raises(ValueError, match="duplicates"):
        EnvironmentalExplanation(
            reason_codes=("drying", "drying"), summary="Duplicate"
        )


def test_signal_requires_evidence_and_matching_chronology() -> None:
    """Signals remain evidence-linked and temporally coherent."""
    with pytest.raises(ValueError, match="requires evidence"):
        signal(evidence_ids=())
    with pytest.raises(ValueError, match="must follow"):
        signal(analysis_ends_at=NOW)
    with pytest.raises(ValueError, match="cannot precede"):
        signal(created_at=END - timedelta(seconds=1))


def test_report_rejects_wrong_location_and_external_records() -> None:
    """Reports cannot silently include unrelated weather evidence."""
    with pytest.raises(ValueError, match="analysis location"):
        report(evidence=(evidence(location_id="property-2"),))
    with pytest.raises(ValueError, match="outside the analysis window"):
        report(evidence=(evidence(record_id="observation-missing"),))
    with pytest.raises(ValueError, match="analysis location"):
        report(signals=(signal(location_id="property-2"),))


def test_report_rejects_dangling_signal_evidence() -> None:
    """Every signal evidence reference must exist in the report."""
    with pytest.raises(ValueError, match="unknown evidence"):
        report(signals=(signal(evidence_ids=("evidence-missing",)),))


def test_signal_period_must_match_report_window() -> None:
    """A report cannot aggregate signals from another analysis period."""
    with pytest.raises(ValueError, match="period must match"):
        report(
            signals=(
                signal(analysis_starts_at=NOW + timedelta(hours=1)),
            )
        )


def test_schema_and_enum_values_are_stable() -> None:
    """Critical serialized vocabulary remains explicit."""
    assert EnvironmentalSignalType.HEAT_EXPOSURE.value == "heat_exposure"
    assert EnvironmentalSignalClassification.UNAVAILABLE.value == "unavailable"
    assert EnvironmentalEvidenceType.HOURLY_FORECAST.value == "hourly_forecast"
    with pytest.raises(ValueError, match="unsupported"):
        report(schema_version=2)


def test_report_has_no_irrigation_command_surface() -> None:
    """The foundation remains descriptive and advisory only."""
    current = report()
    for name in (
        "start",
        "stop",
        "run",
        "schedule",
        "irrigate",
        "execute",
        "set_duration",
        "set_rain_delay",
        "adjust_controller",
    ):
        assert not hasattr(current, name)
