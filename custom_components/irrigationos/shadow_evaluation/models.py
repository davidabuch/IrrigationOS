"""Canonical contracts for observation-only shadow evaluations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, cast

SHADOW_EVALUATION_SCHEMA_VERSION = 2


class ShadowEvaluationReason(StrEnum):
    """Why a decision-significant shadow evaluation was considered."""

    NIGHTLY = "nightly"
    WATERING_COMPLETED = "watering_completed"
    PROFILE_CHANGE = "profile_change"
    SCIENTIFIC_INPUT_CHANGE = "scientific_input_change"
    OBSERVATION_CHANGE = "observation_change"
    CONFIDENCE_CHANGE = "confidence_change"
    DECISION_CHANGE = "decision_change"
    STARTUP_STALE_OR_MISSING = "startup_stale_or_missing"


@dataclass(frozen=True, slots=True)
class ShadowEvaluationRecord:
    """Immutable point-in-time evidence of what IrrigationOS believed."""

    schema_version: int
    evaluation_id: str
    reason: ShadowEvaluationReason
    timestamp_utc: datetime
    timestamp_local: datetime
    integration_version: str
    pipeline_algorithm_version: str
    decision_fingerprint: str
    payload: dict[str, Any]


SENSITIVE_KEYS = {
    "account_id",
    "native_id",
    "binding",
    "serial_number",
    "latitude",
    "longitude",
}
VOLATILE_SEMANTIC_KEYS = {"evaluated_at", "observed_at", "generated_at", "created_at"}


def jsonable(value: Any) -> Any:
    """Convert canonical contracts to safe JSON-compatible values."""
    if is_dataclass(value):
        return jsonable(asdict(cast(Any, value)))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(k): jsonable(v)
            for k, v in value.items()
            if str(k) not in SENSITIVE_KEYS
        }
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value


def semantic_value(value: Any) -> Any:
    """Remove volatile identities/timestamps before decision fingerprinting."""
    value = jsonable(value)
    if isinstance(value, dict):
        return {
            k: semantic_value(v)
            for k, v in value.items()
            if k not in VOLATILE_SEMANTIC_KEYS and not k.endswith("_id")
        }
    if isinstance(value, list):
        return [semantic_value(v) for v in value]
    return value
