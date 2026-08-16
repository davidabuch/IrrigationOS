"""Immutable canonical production-recommendation contracts."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..production_targets import ProductionTarget

PRODUCTION_RECOMMENDATION_SCHEMA_VERSION = 1
PRODUCTION_RECOMMENDATION_POLICY_VERSION = "1.0.0"


class ProductionRecommendationState(StrEnum):
    """Truthful outcome for one current production recommendation."""

    NOT_AVAILABLE = "not_available"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_IRRIGATION_RECOMMENDED = "no_irrigation_recommended"
    IRRIGATION_RECOMMENDED = "irrigation_recommended"
    MIXED = "mixed"


class ScientificNeedState(StrEnum):
    """Scientific irrigation need, independent of execution feasibility."""

    UNAVAILABLE = "unavailable"
    NOT_INDICATED = "not_indicated"
    INDICATED = "indicated"


class DeliveryReadinessState(StrEnum):
    """Whether evidence can support a quantitative delivery contract."""

    UNAVAILABLE = "unavailable"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"


class RecommendationEvidenceKind(StrEnum):
    """Privacy-safe evidence categories included in a recommendation."""

    CONTROLLER_OBSERVATION = "controller_observation"
    LANDSCAPE_PROFILE = "landscape_profile"
    PLANT_KNOWLEDGE = "plant_knowledge"
    PLANT_WATER_REQUIREMENT = "plant_water_requirement"
    PLANT_STRESS = "plant_stress"
    PLANT_HEALTH = "plant_health"
    WEATHER_OBSERVATION = "weather_observation"


@dataclass(frozen=True, slots=True)
class RecommendationQuantity:
    """A scalar or bounded range without silently collapsing evidence."""

    unit: str
    scalar: float | None = None
    minimum: float | None = None
    typical: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not self.unit.strip():
            raise ValueError("quantity unit must not be blank")
        values = (self.scalar, self.minimum, self.typical, self.maximum)
        if any(value is not None and (not isfinite(value) or value < 0) for value in values):
            raise ValueError("quantity values must be finite and non-negative")
        range_present = self.minimum is not None or self.maximum is not None
        if (self.scalar is None) == (not range_present):
            raise ValueError("quantity must contain exactly one scalar or range")
        if range_present:
            if self.minimum is None or self.maximum is None:
                raise ValueError("quantity ranges require minimum and maximum")
            if self.minimum > self.maximum:
                raise ValueError("quantity minimum must not exceed maximum")
            if self.typical is not None and not self.minimum <= self.typical <= self.maximum:
                raise ValueError("quantity typical must be within its range")
        elif self.typical is not None:
            raise ValueError("scalar quantities cannot contain a typical value")


@dataclass(frozen=True, slots=True)
class RecommendationSchedulingWindow:
    """A supported future start/end window, never an execution instruction."""

    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        _aware("starts_at", self.starts_at)
        _aware("ends_at", self.ends_at)
        if self.ends_at <= self.starts_at:
            raise ValueError("scheduling window must end after it starts")


@dataclass(frozen=True, slots=True)
class ProductionRecommendationEvidence:
    """One privacy-safe reference to immutable upstream evidence."""

    kind: RecommendationEvidenceKind
    status: str
    observed_at: datetime | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RecommendationEvidenceKind):
            raise ValueError("evidence kind must be canonical")
        if not self.status.strip():
            raise ValueError("evidence status must not be blank")
        if self.observed_at is not None:
            _aware("observed_at", self.observed_at)
        if self.confidence is not None and (
            not isfinite(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("evidence confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ProductionAreaRecommendation:
    """One canonical recommendation for one selected production target."""

    target: ProductionTarget
    state: ProductionRecommendationState
    scientific_need: ScientificNeedState
    delivery_readiness: DeliveryReadinessState
    irrigation_depth: RecommendationQuantity | None
    estimated_runtime_seconds: RecommendationQuantity | None
    scheduling_window: RecommendationSchedulingWindow | None
    evidence: tuple[ProductionRecommendationEvidence, ...]
    confidence: float
    completeness: float
    reason_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    execution_blocker_codes: tuple[str, ...]
    calculated_at: datetime
    valid_until: datetime
    schema_version: int = PRODUCTION_RECOMMENDATION_SCHEMA_VERSION
    policy_version: str = PRODUCTION_RECOMMENDATION_POLICY_VERSION
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.target, ProductionTarget):
            raise ValueError("target must be canonical")
        _aware("calculated_at", self.calculated_at)
        _aware("valid_until", self.valid_until)
        if self.valid_until <= self.calculated_at:
            raise ValueError("valid_until must be after calculated_at")
        for name, value in (("confidence", self.confidence), ("completeness", self.completeness)):
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name, values in (
            ("reason_codes", self.reason_codes),
            ("blocker_codes", self.blocker_codes),
            ("execution_blocker_codes", self.execution_blocker_codes),
        ):
            _sorted_unique(name, values)
        if tuple(item.kind.value for item in self.evidence) != tuple(
            sorted({item.kind.value for item in self.evidence})
        ):
            raise ValueError("evidence must use deterministic unique ordering")
        if self.execution_authorized:
            raise ValueError("production recommendations never authorize execution")
        if self.state is ProductionRecommendationState.INSUFFICIENT_EVIDENCE and any(
            value is not None
            for value in (
                self.irrigation_depth,
                self.estimated_runtime_seconds,
                self.scheduling_window,
            )
        ):
            raise ValueError("insufficient evidence cannot contain invented delivery output")

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic plain data suitable for entities and audit history."""

        return _serialize(self)


@dataclass(frozen=True, slots=True)
class ProductionRecommendationSnapshot:
    """Coordinator-owned current recommendations; never persisted as authority."""

    state: ProductionRecommendationState
    calculated_at: datetime | None
    recommendations: tuple[ProductionAreaRecommendation, ...]
    reason_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    schema_version: int = PRODUCTION_RECOMMENDATION_SCHEMA_VERSION
    policy_version: str = PRODUCTION_RECOMMENDATION_POLICY_VERSION
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if self.calculated_at is not None:
            _aware("calculated_at", self.calculated_at)
        targets = tuple(item.target for item in self.recommendations)
        if targets != tuple(sorted(set(targets))):
            raise ValueError("recommendations must use deterministic unique targets")
        _sorted_unique("reason_codes", self.reason_codes)
        _sorted_unique("blocker_codes", self.blocker_codes)
        if self.execution_authorized:
            raise ValueError("production recommendation snapshots never authorize execution")
        if self.state is ProductionRecommendationState.NOT_AVAILABLE and (
            self.calculated_at is not None or self.recommendations
        ):
            raise ValueError("not_available snapshots cannot contain stale recommendations")

    @classmethod
    def not_available(cls) -> ProductionRecommendationSnapshot:
        """Return the fail-closed startup/reload state."""

        return cls(
            state=ProductionRecommendationState.NOT_AVAILABLE,
            calculated_at=None,
            recommendations=(),
            reason_codes=("fresh_recomputation_required",),
            blocker_codes=("recommendation_not_evaluated",),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic plain data without internal or provider identifiers."""

        return _serialize(self)


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _sorted_unique(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must use deterministic unique tuple ordering")
    if any(not value or not value.replace("_", "").isalnum() for value in values):
        raise ValueError(f"{name} must contain lower_snake_case values")


def _serialize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value
