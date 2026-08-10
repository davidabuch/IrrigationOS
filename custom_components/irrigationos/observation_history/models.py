"""Immutable provider-neutral watering-session evidence models."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..controllers import ObservationQuality

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class WateringSessionState(StrEnum):
    """Lifecycle state of one observed watering session."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class WateringObservationSource(StrEnum):
    """How canonical watering state became available to the recorder."""

    POLLING = "polling"
    REALTIME_REFRESH = "realtime_refresh"
    RESTART_RECONCILIATION = "restart_reconciliation"
    MIXED = "mixed"


class WateringTimestampPrecision(StrEnum):
    """Conservative precision of observed session boundaries."""

    POLLING_WINDOW = "polling_window"
    EVENT_BOUNDED = "event_bounded"
    RECONSTRUCTED = "reconstructed"


class WateringAttribution(StrEnum):
    """Conservative ownership vocabulary for observed watering."""

    EXTERNAL_UNKNOWN = "external_unknown"
    PROVIDER_SCHEDULE = "provider_schedule"
    MANUAL = "manual"
    IRRIGATIONOS = "irrigationos"


class AttributionEvidenceCode(StrEnum):
    """Stable reasons supporting or limiting watering attribution."""

    NO_EXPLICIT_PROVIDER_EVIDENCE = "no_explicit_provider_evidence"
    REALTIME_EVENT_NOT_OWNERSHIP_EVIDENCE = "realtime_event_not_ownership_evidence"
    POLLING_BOUNDARY_INEXACT = "polling_boundary_inexact"
    OBSERVATION_GAP = "observation_gap"
    RECONSTRUCTED_AFTER_RESTART = "reconstructed_after_restart"


class WateringSessionEventType(StrEnum):
    """Events emitted by deterministic session reconciliation."""

    SESSION_STARTED = "session_started"
    SESSION_UPDATED = "session_updated"
    SESSION_CLOSED = "session_closed"
    SESSION_RECONCILED = "session_reconciled"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_utc(name: str, value: datetime) -> None:
    offset = value.utcoffset() if isinstance(value, datetime) else None
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or offset is None
        or offset.total_seconds() != 0
    ):
        raise ValueError(f"{name} must be a timezone-aware UTC datetime")


def _validate_sorted_unique_reasons(values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ValueError("attribution_evidence must be an immutable tuple")
    if any(not isinstance(value, str) or not _REASON_PATTERN.fullmatch(value) for value in values):
        raise ValueError("attribution_evidence must contain stable reason codes")
    if values != tuple(sorted(set(values))):
        raise ValueError("attribution_evidence must be unique and deterministically ordered")


@dataclass(frozen=True, slots=True)
class WateringSession:
    """One immutable canonical watering-session evidence snapshot."""

    session_id: str
    controller_id: str
    area_id: str
    slot_number: int
    area_name: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    state: WateringSessionState
    observation_source: WateringObservationSource
    observation_quality: ObservationQuality
    timestamp_precision: WateringTimestampPrecision
    attribution: WateringAttribution
    attribution_confidence: float
    attribution_evidence: tuple[str, ...]
    reconstructed_after_restart: bool
    incomplete: bool
    first_observed_at: datetime
    last_observed_at: datetime

    def __post_init__(self) -> None:
        for identifier_name, identifier_value in (
            ("session_id", self.session_id),
            ("controller_id", self.controller_id),
            ("area_id", self.area_id),
        ):
            _validate_identifier(identifier_name, identifier_value)
        if isinstance(self.slot_number, bool) or not isinstance(self.slot_number, int):
            raise ValueError("slot_number must be a positive integer")
        if self.slot_number < 1:
            raise ValueError("slot_number must be a positive integer")
        if not isinstance(self.area_name, str) or not self.area_name.strip():
            raise ValueError("area_name must not be blank")
        for timestamp_name, timestamp_value in (
            ("started_at", self.started_at),
            ("first_observed_at", self.first_observed_at),
            ("last_observed_at", self.last_observed_at),
        ):
            _validate_utc(timestamp_name, timestamp_value)
        if self.ended_at is not None:
            _validate_utc("ended_at", self.ended_at)
        if self.first_observed_at < self.started_at:
            raise ValueError("first_observed_at cannot precede started_at")
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("last_observed_at cannot precede first_observed_at")
        if not isinstance(self.state, WateringSessionState):
            raise ValueError("state must be canonical")
        if not isinstance(self.observation_source, WateringObservationSource):
            raise ValueError("observation_source must be canonical")
        if not isinstance(self.observation_quality, ObservationQuality):
            raise ValueError("observation_quality must be canonical")
        if not isinstance(self.timestamp_precision, WateringTimestampPrecision):
            raise ValueError("timestamp_precision must be canonical")
        if not isinstance(self.attribution, WateringAttribution):
            raise ValueError("attribution must be canonical")
        if (
            isinstance(self.attribution_confidence, bool)
            or not isinstance(self.attribution_confidence, (int, float))
            or not isfinite(self.attribution_confidence)
            or not 0 <= self.attribution_confidence <= 1
        ):
            raise ValueError("attribution_confidence must be between 0.0 and 1.0")
        _validate_sorted_unique_reasons(self.attribution_evidence)
        if not isinstance(self.reconstructed_after_restart, bool):
            raise ValueError("reconstructed_after_restart must be a boolean")
        if not isinstance(self.incomplete, bool):
            raise ValueError("incomplete must be a boolean")
        if self.state is WateringSessionState.ACTIVE:
            if self.ended_at is not None or self.duration_seconds is not None:
                raise ValueError("active sessions cannot have an end or duration")
        else:
            if self.ended_at is None or self.duration_seconds is None:
                raise ValueError("inactive sessions require an end and duration")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at cannot precede started_at")
            expected = max(0, round((self.ended_at - self.started_at).total_seconds()))
            if self.duration_seconds != expected:
                raise ValueError("duration_seconds must match session boundaries")

    @property
    def active(self) -> bool:
        """Return whether the observed session remains active."""

        return self.state is WateringSessionState.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic persistence data."""

        return {
            "session_id": self.session_id,
            "controller_id": self.controller_id,
            "area_id": self.area_id,
            "slot_number": self.slot_number,
            "area_name": self.area_name,
            "started_at": self.started_at.isoformat(),
            "ended_at": None if self.ended_at is None else self.ended_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "state": self.state.value,
            "observation_source": self.observation_source.value,
            "observation_quality": self.observation_quality.value,
            "timestamp_precision": self.timestamp_precision.value,
            "attribution": self.attribution.value,
            "attribution_confidence": self.attribution_confidence,
            "attribution_evidence": list(self.attribution_evidence),
            "reconstructed_after_restart": self.reconstructed_after_restart,
            "incomplete": self.incomplete,
            "first_observed_at": self.first_observed_at.isoformat(),
            "last_observed_at": self.last_observed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, value: object) -> WateringSession:
        """Restore one validated session from persistence data."""

        if not isinstance(value, dict):
            raise ValueError("persisted watering session must be a mapping")
        ended = value.get("ended_at")
        evidence = value.get("attribution_evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise ValueError("persisted attribution evidence is invalid")
        return cls(
            session_id=str(value.get("session_id", "")),
            controller_id=str(value.get("controller_id", "")),
            area_id=str(value.get("area_id", "")),
            slot_number=_required_int(value.get("slot_number")),
            area_name=str(value.get("area_name", "")),
            started_at=_parse_utc(value.get("started_at")),
            ended_at=None if ended is None else _parse_utc(ended),
            duration_seconds=_optional_int(value.get("duration_seconds")),
            state=WateringSessionState(str(value.get("state", ""))),
            observation_source=WateringObservationSource(
                str(value.get("observation_source", ""))
            ),
            observation_quality=ObservationQuality(
                str(value.get("observation_quality", ""))
            ),
            timestamp_precision=WateringTimestampPrecision(
                str(value.get("timestamp_precision", ""))
            ),
            attribution=WateringAttribution(str(value.get("attribution", ""))),
            attribution_confidence=_required_float(value.get("attribution_confidence")),
            attribution_evidence=tuple(evidence),
            reconstructed_after_restart=_required_bool(
                value.get("reconstructed_after_restart", False)
            ),
            incomplete=_required_bool(value.get("incomplete", False)),
            first_observed_at=_parse_utc(value.get("first_observed_at")),
            last_observed_at=_parse_utc(value.get("last_observed_at")),
        )

    def reconstructed(self) -> WateringSession:
        """Return a restart-safe active-session representation."""

        evidence = tuple(
            sorted(
                {
                    *self.attribution_evidence,
                    AttributionEvidenceCode.RECONSTRUCTED_AFTER_RESTART.value,
                    AttributionEvidenceCode.OBSERVATION_GAP.value,
                }
            )
        )
        return replace(
            self,
            observation_source=WateringObservationSource.RESTART_RECONCILIATION,
            timestamp_precision=WateringTimestampPrecision.RECONSTRUCTED,
            attribution_evidence=evidence,
            reconstructed_after_restart=True,
            incomplete=True,
        )


@dataclass(frozen=True, slots=True)
class WateringSessionEvent:
    """One deterministic change emitted by session reconciliation."""

    event_type: WateringSessionEventType
    session: WateringSession
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, WateringSessionEventType):
            raise ValueError("event_type must be canonical")
        if not isinstance(self.session, WateringSession):
            raise ValueError("session must be canonical")
        _validate_utc("recorded_at", self.recorded_at)


def safe_session_summary(session: WateringSession) -> dict[str, Any]:
    """Return a vendor-ID-free operator and diagnostics summary."""

    return {
        "session_id": session.session_id,
        "slot_number": session.slot_number,
        "area_name": session.area_name,
        "started_at": session.started_at.isoformat(),
        "ended_at": None if session.ended_at is None else session.ended_at.isoformat(),
        "duration_seconds": session.duration_seconds,
        "state": session.state.value,
        "observation_source": session.observation_source.value,
        "observation_quality": session.observation_quality.value,
        "timestamp_precision": session.timestamp_precision.value,
        "attribution": session.attribution.value,
        "attribution_confidence": session.attribution_confidence,
        "attribution_evidence": list(session.attribution_evidence),
        "reconstructed_after_restart": session.reconstructed_after_restart,
        "incomplete": session.incomplete,
        "first_observed_at": session.first_observed_at.isoformat(),
        "last_observed_at": session.last_observed_at.isoformat(),
    }


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("persisted timestamp must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("persisted timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("persisted value must be an integer")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _required_int(value)


def _required_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("persisted value must be numeric")
    return float(value)


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("persisted value must be a boolean")
    return value
