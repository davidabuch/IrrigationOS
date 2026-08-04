"""Canonical Environmental Intelligence foundation models."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

ENVIRONMENTAL_INTELLIGENCE_SCHEMA_VERSION = 1
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_UNIT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_./%-]{0,31}$")


class EnvironmentalSignalType(StrEnum):
    """Stable categories of derived environmental conclusions."""

    ATMOSPHERIC_WATER_BALANCE = "atmospheric_water_balance"
    DRYING_TREND = "drying_trend"
    HEAT_EXPOSURE = "heat_exposure"
    FREEZE_POTENTIAL = "freeze_potential"
    WIND_EXPOSURE = "wind_exposure"
    HEAVY_RAIN_POTENTIAL = "heavy_rain_potential"
    FORECAST_RELIABILITY = "forecast_reliability"


class EnvironmentalSignalClassification(StrEnum):
    """Provider-neutral classifications available to future engines."""

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"
    STRONGLY_WETTING = "strongly_wetting"
    WETTING = "wetting"
    BALANCED = "balanced"
    DRYING = "drying"
    STRONGLY_DRYING = "strongly_drying"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class EnvironmentalEvidenceType(StrEnum):
    """Canonical source-record classes referenced by environmental reasoning."""

    CURRENT_OBSERVATION = "current_observation"
    HISTORICAL_OBSERVATION = "historical_observation"
    HOURLY_FORECAST = "hourly_forecast"
    DAILY_FORECAST = "daily_forecast"
    WEATHER_FACT = "weather_fact"


class EnvironmentalProvenanceType(StrEnum):
    """Origin class of an environmental report or signal."""

    DETERMINISTIC_ENGINE = "deterministic_engine"
    MANUAL_ASSESSMENT = "manual_assessment"
    IMPORTED = "imported"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_fraction(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def _validate_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_unique_ids(name: str, values: tuple[str, ...]) -> None:
    for value in values:
        _validate_identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate identifiers")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError("raw bytes are not permitted in environmental intelligence records")
    return value


class SerializableEnvironmentModel:
    """Mixin for deterministic plain-dictionary serialization."""

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic provider- and runtime-neutral data."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover - mixin contract
            raise TypeError("environment model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class EnvironmentalProvenance(SerializableEnvironmentModel):
    """Provider-neutral origin of an environmental conclusion."""

    source: str
    provenance_type: EnvironmentalProvenanceType
    source_reference: str | None = None

    def __post_init__(self) -> None:
        _validate_text("source", self.source)
        if not isinstance(self.provenance_type, EnvironmentalProvenanceType):
            raise ValueError("provenance_type must be canonical")
        if self.source_reference is not None:
            _validate_text("source_reference", self.source_reference)


@dataclass(frozen=True, slots=True)
class EnvironmentalAnalysisWindow(SerializableEnvironmentModel):
    """Bounded canonical weather-input window for one location."""

    window_id: str
    location_id: str
    starts_at: datetime
    ends_at: datetime
    observation_ids: tuple[str, ...] = ()
    forecast_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("window_id", self.window_id)
        _validate_identifier("location_id", self.location_id)
        _validate_timestamp("starts_at", self.starts_at)
        _validate_timestamp("ends_at", self.ends_at)
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must follow starts_at")
        _validate_unique_ids("observation_ids", self.observation_ids)
        _validate_unique_ids("forecast_ids", self.forecast_ids)
        if not self.observation_ids and not self.forecast_ids:
            raise ValueError("analysis window requires observation or forecast inputs")


@dataclass(frozen=True, slots=True)
class EnvironmentalEvidenceReference(SerializableEnvironmentModel):
    """Stable reference from a conclusion to canonical weather evidence."""

    evidence_id: str
    location_id: str
    evidence_type: EnvironmentalEvidenceType
    record_id: str
    fact_path: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("evidence_id", self.evidence_id)
        _validate_identifier("location_id", self.location_id)
        _validate_identifier("record_id", self.record_id)
        if not isinstance(self.evidence_type, EnvironmentalEvidenceType):
            raise ValueError("evidence_type must be canonical")
        if self.fact_path is not None:
            _validate_text("fact_path", self.fact_path)


@dataclass(frozen=True, slots=True)
class EnvironmentalThreshold(SerializableEnvironmentModel):
    """One named finite threshold with explicit canonical units."""

    name: str
    value: float
    unit: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _REASON_CODE_PATTERN.fullmatch(self.name):
            raise ValueError("threshold name must use stable lower_snake_case")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("threshold value must be a finite number")
        if not isfinite(self.value):
            raise ValueError("threshold value must be a finite number")
        if not isinstance(self.unit, str) or not _UNIT_PATTERN.fullmatch(self.unit):
            raise ValueError("threshold unit must be canonical")
        _validate_text("description", self.description)


@dataclass(frozen=True, slots=True)
class EnvironmentalThresholdPolicy(SerializableEnvironmentModel):
    """Versioned explicit thresholds for a future deterministic algorithm."""

    policy_id: str
    policy_version: str
    description: str
    thresholds: tuple[EnvironmentalThreshold, ...]

    def __post_init__(self) -> None:
        _validate_identifier("policy_id", self.policy_id)
        _validate_text("policy_version", self.policy_version)
        _validate_text("description", self.description)
        if not self.thresholds:
            raise ValueError("threshold policy requires at least one threshold")
        names = tuple(item.name for item in self.thresholds)
        if len(names) != len(set(names)):
            raise ValueError("threshold names must not contain duplicates")


@dataclass(frozen=True, slots=True)
class EnvironmentalExplanation(SerializableEnvironmentModel):
    """Human- and machine-readable explanation for a derived conclusion."""

    reason_codes: tuple[str, ...]
    summary: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("explanation requires at least one reason code")
        for reason_code in self.reason_codes:
            if not isinstance(reason_code, str) or not _REASON_CODE_PATTERN.fullmatch(
                reason_code
            ):
                raise ValueError("reason codes must use stable lower_snake_case")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason codes must not contain duplicates")
        _validate_text("summary", self.summary)
        if self.detail is not None:
            _validate_text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class EnvironmentalConfidence(SerializableEnvironmentModel):
    """Separate completeness, confidence, and source-quality summary."""

    completeness: float
    average_confidence: float
    known_fact_count: int
    required_fact_count: int
    good_quality_count: int
    estimated_quality_count: int
    suspect_quality_count: int
    unavailable_quality_count: int
    confidence_policy_version: str

    def __post_init__(self) -> None:
        _validate_fraction("completeness", self.completeness)
        _validate_fraction("average_confidence", self.average_confidence)
        for name, value in (
            ("known_fact_count", self.known_fact_count),
            ("required_fact_count", self.required_fact_count),
            ("good_quality_count", self.good_quality_count),
            ("estimated_quality_count", self.estimated_quality_count),
            ("suspect_quality_count", self.suspect_quality_count),
            ("unavailable_quality_count", self.unavailable_quality_count),
        ):
            _validate_non_negative_int(name, value)
        if self.known_fact_count > self.required_fact_count:
            raise ValueError("known_fact_count cannot exceed required_fact_count")
        expected_completeness = (
            self.known_fact_count / self.required_fact_count
            if self.required_fact_count
            else 0.0
        )
        if abs(self.completeness - expected_completeness) > 0.000001:
            raise ValueError("completeness must match known and required fact counts")
        quality_total = (
            self.good_quality_count
            + self.estimated_quality_count
            + self.suspect_quality_count
            + self.unavailable_quality_count
        )
        if quality_total != self.required_fact_count:
            raise ValueError("quality counts must equal required_fact_count")
        _validate_text("confidence_policy_version", self.confidence_policy_version)


@dataclass(frozen=True, slots=True)
class EnvironmentalSignal(SerializableEnvironmentModel):
    """Explainable, evidence-linked environmental conclusion envelope."""

    signal_id: str
    location_id: str
    signal_type: EnvironmentalSignalType
    classification: EnvironmentalSignalClassification
    analysis_starts_at: datetime
    analysis_ends_at: datetime
    created_at: datetime
    algorithm_version: str
    policy_id: str
    policy_version: str
    confidence: EnvironmentalConfidence
    explanation: EnvironmentalExplanation
    evidence_ids: tuple[str, ...]
    threshold_values: tuple[EnvironmentalThreshold, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("signal_id", self.signal_id)
        _validate_identifier("location_id", self.location_id)
        for name, value in (
            ("analysis_starts_at", self.analysis_starts_at),
            ("analysis_ends_at", self.analysis_ends_at),
            ("created_at", self.created_at),
        ):
            _validate_timestamp(name, value)
        if self.analysis_ends_at <= self.analysis_starts_at:
            raise ValueError("analysis_ends_at must follow analysis_starts_at")
        if self.created_at < self.analysis_ends_at:
            raise ValueError("created_at cannot precede analysis_ends_at")
        _validate_text("algorithm_version", self.algorithm_version)
        _validate_identifier("policy_id", self.policy_id)
        _validate_text("policy_version", self.policy_version)
        _validate_unique_ids("evidence_ids", self.evidence_ids)
        if not self.evidence_ids:
            raise ValueError("environmental signal requires evidence")
        threshold_names = tuple(item.name for item in self.threshold_values)
        if len(threshold_names) != len(set(threshold_names)):
            raise ValueError("signal threshold names must not contain duplicates")


@dataclass(frozen=True, slots=True)
class EnvironmentalIntelligenceReport(SerializableEnvironmentModel):
    """Canonical aggregate of environmental conclusions for one analysis window."""

    report_id: str
    schema_version: int
    analysis_window: EnvironmentalAnalysisWindow
    created_at: datetime
    algorithm_suite_version: str
    provenance: EnvironmentalProvenance
    confidence: EnvironmentalConfidence
    evidence: tuple[EnvironmentalEvidenceReference, ...]
    signals: tuple[EnvironmentalSignal, ...]

    def __post_init__(self) -> None:
        _validate_identifier("report_id", self.report_id)
        if self.schema_version != ENVIRONMENTAL_INTELLIGENCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported environmental intelligence schema version: {self.schema_version}"
            )
        _validate_timestamp("created_at", self.created_at)
        if self.created_at < self.analysis_window.ends_at:
            raise ValueError("report created_at cannot precede analysis window end")
        _validate_text("algorithm_suite_version", self.algorithm_suite_version)
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        signal_ids = tuple(item.signal_id for item in self.signals)
        _validate_unique_ids("evidence IDs", evidence_ids)
        _validate_unique_ids("signal IDs", signal_ids)
        if not self.signals:
            raise ValueError("environmental report requires at least one signal")
        if any(item.location_id != self.analysis_window.location_id for item in self.evidence):
            raise ValueError("all evidence must belong to the analysis location")
        if any(item.location_id != self.analysis_window.location_id for item in self.signals):
            raise ValueError("all signals must belong to the analysis location")
        allowed_record_ids = set(self.analysis_window.observation_ids) | set(
            self.analysis_window.forecast_ids
        )
        if any(item.record_id not in allowed_record_ids for item in self.evidence):
            raise ValueError("evidence references a record outside the analysis window")
        known_evidence = set(evidence_ids)
        for signal in self.signals:
            if (
                signal.analysis_starts_at != self.analysis_window.starts_at
                or signal.analysis_ends_at != self.analysis_window.ends_at
            ):
                raise ValueError(
                    "signal analysis period must match report analysis window"
                )
            if not set(signal.evidence_ids) <= known_evidence:
                raise ValueError("signal references unknown evidence")
