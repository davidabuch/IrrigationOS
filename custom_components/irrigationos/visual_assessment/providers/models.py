"""Provider-neutral request, response, capability, and error models."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..models import PhotoEvidence, VisualLandscapeAssessment

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CONTEXT_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ProviderCapability(StrEnum):
    """Capabilities that a visual-assessment provider may advertise."""

    IMAGE_ANALYSIS = "image_analysis"
    MULTI_IMAGE_ANALYSIS = "multi_image_analysis"
    STRUCTURED_OUTPUT = "structured_output"
    FOLLOW_UP_QUESTIONS = "follow_up_questions"
    PLANT_IDENTIFICATION = "plant_identification"
    IRRIGATION_HARDWARE_IDENTIFICATION = "irrigation_hardware_identification"
    SOIL_VISUAL_ASSESSMENT = "soil_visual_assessment"
    HEALTH_DIAGNOSTICS = "health_diagnostics"


class ProviderErrorCategory(StrEnum):
    """Stable categories for safe provider error translation."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    CONTENT_UNAVAILABLE = "content_unavailable"
    CONTENT_REJECTED = "content_rejected"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK = "network"
    INVALID_RESPONSE = "invalid_response"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INTERNAL = "internal"


class VisualAssessmentPurpose(StrEnum):
    """Reason for requesting provider analysis."""

    INITIAL_LANDSCAPE_SETUP = "initial_landscape_setup"
    HARDWARE_IDENTIFICATION = "hardware_identification"
    SOIL_ASSESSMENT = "soil_assessment"
    PLANT_HEALTH_DIAGNOSTIC = "plant_health_diagnostic"
    FOLLOW_UP_ASSESSMENT = "follow_up_assessment"


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _serialize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, tuple | list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError("raw bytes are not permitted in provider models")
    return value


class SerializableProviderModel:
    """Mixin for deterministic provider-boundary serialization."""

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic plain-dictionary representation."""
        value = _serialize(self)
        if not isinstance(value, dict):
            raise TypeError("provider model did not serialize to a dictionary")
        return value


@dataclass(frozen=True, slots=True)
class ProviderDescriptor(SerializableProviderModel):
    """Stable description of a configured assessment provider."""

    provider_id: str
    display_name: str
    capabilities: tuple[ProviderCapability, ...]
    supports_cloud_processing: bool
    model_reference: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("provider_id", self.provider_id)
        _validate_text("display_name", self.display_name)
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("capabilities must not contain duplicates")
        if self.model_reference is not None:
            _validate_text("model_reference", self.model_reference)


@dataclass(frozen=True, slots=True)
class ProviderRetryPolicy(SerializableProviderModel):
    """Bounded retry policy applied outside the domain assessment models."""

    maximum_attempts: int = 2
    initial_delay_seconds: float = 1.0
    maximum_delay_seconds: float = 8.0
    multiplier: float = 2.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.maximum_attempts, bool)
            or not isinstance(self.maximum_attempts, int)
            or not 1 <= self.maximum_attempts <= 5
        ):
            raise ValueError("maximum_attempts must be between 1 and 5")

        for name, value in (
            ("initial_delay_seconds", self.initial_delay_seconds),
            ("maximum_delay_seconds", self.maximum_delay_seconds),
            ("multiplier", self.multiplier),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number")

        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError(
                "maximum_delay_seconds cannot be less than initial_delay_seconds"
            )
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least 1")


@dataclass(frozen=True, slots=True)
class AssessmentContextValue(SerializableProviderModel):
    """One provider-neutral contextual fact supplied with an assessment request."""

    key: str
    value: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not _CONTEXT_KEY_PATTERN.fullmatch(self.key):
            raise ValueError("context key must use stable lower_snake_case")
        _validate_text("value", self.value)
        _validate_text("source", self.source)


@dataclass(frozen=True, slots=True)
class VisualAssessmentRequest(SerializableProviderModel):
    """Validated request supplied to a visual-assessment provider."""

    request_id: str
    session_id: str
    area_id: str
    purpose: VisualAssessmentPurpose
    requested_at: datetime
    photo_evidence: tuple[PhotoEvidence, ...]
    required_capabilities: tuple[ProviderCapability, ...]
    context: tuple[AssessmentContextValue, ...] = ()
    locale: str = "en-US"

    def __post_init__(self) -> None:
        _validate_identifier("request_id", self.request_id)
        _validate_identifier("session_id", self.session_id)
        _validate_identifier("area_id", self.area_id)
        _validate_timestamp("requested_at", self.requested_at)
        _validate_text("locale", self.locale)

        if not self.photo_evidence:
            raise ValueError("visual assessment requests require photo evidence")

        if any(photo.area_id != self.area_id for photo in self.photo_evidence):
            raise ValueError("all photo evidence must belong to the request area")

        evidence_ids = [photo.evidence_id for photo in self.photo_evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("photo evidence IDs must not contain duplicates")

        if len(self.required_capabilities) != len(set(self.required_capabilities)):
            raise ValueError("required_capabilities must not contain duplicates")

        context_keys = [item.key for item in self.context]
        if len(context_keys) != len(set(context_keys)):
            raise ValueError("context keys must not contain duplicates")


@dataclass(frozen=True, slots=True)
class VisualAssessmentProviderResult(SerializableProviderModel):
    """Validated result returned by a provider adapter."""

    request_id: str
    provider_id: str
    received_at: datetime
    assessment: VisualLandscapeAssessment
    provider_request_id: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("request_id", self.request_id)
        _validate_identifier("provider_id", self.provider_id)
        _validate_timestamp("received_at", self.received_at)

        if self.provider_request_id is not None:
            _validate_identifier("provider_request_id", self.provider_request_id)

        for warning in self.warnings:
            _validate_text("warning", warning)


@dataclass(frozen=True, slots=True)
class ProviderFailure(SerializableProviderModel):
    """Safe structured provider failure suitable for UI and diagnostics."""

    category: ProviderErrorCategory
    message: str
    retryable: bool
    occurred_at: datetime
    provider_id: str | None = None
    request_id: str | None = None
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        _validate_text("message", self.message)
        _validate_timestamp("occurred_at", self.occurred_at)

        if self.provider_id is not None:
            _validate_identifier("provider_id", self.provider_id)
        if self.request_id is not None:
            _validate_identifier("request_id", self.request_id)

        if self.retry_after_seconds is not None:
            value = self.retry_after_seconds
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    "retry_after_seconds must be a positive finite number"
                )
            if not self.retryable:
                raise ValueError(
                    "retry_after_seconds is only valid for retryable failures"
                )
