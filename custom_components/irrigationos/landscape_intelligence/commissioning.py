"""Generic, advisory zone-commissioning contracts.

These models normalize manual, calibrated-baseline, and future structured visual
inputs without granting scheduling or execution authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from .models import (
    Confidence,
    EstablishmentState,
    IrrigationRole,
    LandscapeIntelligenceProfile,
    PlantGroup,
)

ZONE_COMMISSIONING_SCHEMA_VERSION = 2
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ZoneDemandSourceMode(StrEnum):
    """How a zone's normalized demand evidence was commissioned."""

    PHOTO_AI_DERIVED = "photo_ai_derived"
    USER_CALIBRATED_BASELINE = "user_calibrated_baseline"
    MANUAL_PLANT_PROFILE = "manual_plant_profile"
    HYBRID = "hybrid"


class CommissioningEvidenceSource(StrEnum):
    """Source of a normalized commissioning fact."""

    USER_CONFIRMED = "user_confirmed"
    HUMAN_REVIEWED_PHOTO = "human_reviewed_photo"
    AI_INFERRED = "ai_inferred"
    IMPORTED = "imported"


class DeliveryLinkStatus(StrEnum):
    """Evidence state for a plant-to-delivery relationship."""

    UNRESOLVED = "unresolved"
    DOCUMENTED = "documented"
    REVIEW_REQUIRED = "review_required"


class LandscapeEventType(StrEnum):
    """Immutable landscape-change event types."""

    PLANT_GROUP_ADDED = "plant_group_added"
    PLANT_GROUP_REMOVED = "plant_group_removed"


class DeliveryCompatibilityState(StrEnum):
    """Advisory state; never an execution decision."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REVIEW_REQUIRED = "review_required"
    DOCUMENTED = "documented"


def _identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a stable identifier")


def _text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _timestamp(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _positive_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _unique_ids(name: str, values: tuple[str, ...]) -> None:
    for value in values:
        _identifier(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"unsupported commissioning type: {type(value).__name__}")


class SerializableCommissioningModel:
    """Deterministic plain-dictionary serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize without provider payloads or mutable mappings."""
        result = _serialize(self)
        if not isinstance(result, dict):  # pragma: no cover
            raise TypeError("commissioning model did not serialize to a dictionary")
        return result


@dataclass(frozen=True, slots=True)
class CommissioningConflictCandidate(SerializableCommissioningModel):
    """One preserved candidate value in unresolved commissioning evidence."""

    source: CommissioningEvidenceSource
    value: str
    confidence: Confidence
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text("value", self.value)
        _unique_ids("evidence_ids", self.evidence_ids)


@dataclass(frozen=True, slots=True)
class CommissioningEvidenceConflict(SerializableCommissioningModel):
    """Explicit unresolved evidence conflict retained for later review."""

    conflict_id: str
    plant_group_id: str
    field_path: str
    candidates: tuple[CommissioningConflictCandidate, ...]
    detail: str
    unresolved: bool = True

    def __post_init__(self) -> None:
        _identifier("conflict_id", self.conflict_id)
        _identifier("plant_group_id", self.plant_group_id)
        _identifier("field_path", self.field_path)
        _text("detail", self.detail)
        if len(self.candidates) < 2:
            raise ValueError("commissioning conflict requires at least two candidates")
        candidate_keys = tuple(
            (candidate.source, candidate.value.casefold()) for candidate in self.candidates
        )
        if len(candidate_keys) != len(set(candidate_keys)):
            raise ValueError("commissioning conflict candidates must be unique")
        if not self.unresolved:
            raise ValueError("conflict resolution policy is not implemented")


@dataclass(frozen=True, slots=True)
class CanonicalZoneIdentity(SerializableCommissioningModel):
    """Stable property and zone identity with an optional controller binding."""

    property_id: str
    zone_id: str
    controller_slot: int | None
    area_slot: int

    def __post_init__(self) -> None:
        _identifier("property_id", self.property_id)
        _identifier("zone_id", self.zone_id)
        for name, value in (("controller_slot", self.controller_slot),):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer when supplied")
        if (
            isinstance(self.area_slot, bool)
            or not isinstance(self.area_slot, int)
            or self.area_slot <= 0
        ):
            raise ValueError("area_slot must be a positive integer")


@dataclass(frozen=True, slots=True)
class PlantCommissioningDetails(SerializableCommissioningModel):
    """User- or assessment-supplied facts supplementing a canonical plant group."""

    plant_group_id: str
    source: CommissioningEvidenceSource
    confidence: Confidence
    observed_at: datetime
    planted_at: datetime | None = None
    source_container_gallons: float | None = None
    current_height_meters: float | None = None
    structured_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier("plant_group_id", self.plant_group_id)
        _timestamp("observed_at", self.observed_at)
        if self.planted_at is not None:
            _timestamp("planted_at", self.planted_at)
            if self.planted_at > self.observed_at:
                raise ValueError("planted_at cannot follow observed_at")
        for name, value in (
            ("source_container_gallons", self.source_container_gallons),
            ("current_height_meters", self.current_height_meters),
        ):
            if value is not None:
                _positive_number(name, value)
        _unique_ids("structured_evidence_ids", self.structured_evidence_ids)


@dataclass(frozen=True, slots=True)
class UserCalibratedBaseline(SerializableCommissioningModel):
    """User-confirmed reference runtime, not a weather-scaling algorithm."""

    runtime_seconds: int
    reference_air_temperature_celsius: float
    reference_recent_precipitation_mm: float
    reference_condition: str
    calibrated_at: datetime
    confidence: Confidence

    def __post_init__(self) -> None:
        if (
            isinstance(self.runtime_seconds, bool)
            or not isinstance(self.runtime_seconds, int)
            or self.runtime_seconds <= 0
        ):
            raise ValueError("runtime_seconds must be a positive integer")
        if (
            isinstance(self.reference_air_temperature_celsius, bool)
            or not isinstance(self.reference_air_temperature_celsius, int | float)
            or not isfinite(self.reference_air_temperature_celsius)
        ):
            raise ValueError("reference_air_temperature_celsius must be finite")
        if (
            isinstance(self.reference_recent_precipitation_mm, bool)
            or not isinstance(self.reference_recent_precipitation_mm, int | float)
            or not isfinite(self.reference_recent_precipitation_mm)
            or self.reference_recent_precipitation_mm < 0
        ):
            raise ValueError("reference_recent_precipitation_mm must be nonnegative")
        _text("reference_condition", self.reference_condition)
        _timestamp("calibrated_at", self.calibrated_at)


@dataclass(frozen=True, slots=True)
class ZoneDemandSource(SerializableCommissioningModel):
    """Normalized onboarding source consumed by downstream advisory engines."""

    source_id: str
    mode: ZoneDemandSourceMode
    plant_group_ids: tuple[str, ...] = ()
    structured_visual_assessment_ids: tuple[str, ...] = ()
    calibrated_baseline: UserCalibratedBaseline | None = None

    def __post_init__(self) -> None:
        _identifier("source_id", self.source_id)
        _unique_ids("plant_group_ids", self.plant_group_ids)
        _unique_ids(
            "structured_visual_assessment_ids", self.structured_visual_assessment_ids
        )
        has_plants = bool(self.plant_group_ids)
        has_visual = bool(self.structured_visual_assessment_ids)
        has_baseline = self.calibrated_baseline is not None
        if self.mode is ZoneDemandSourceMode.MANUAL_PLANT_PROFILE:
            if not has_plants or has_visual or has_baseline:
                raise ValueError("manual plant mode requires only plant-group references")
        elif self.mode is ZoneDemandSourceMode.PHOTO_AI_DERIVED:
            if not has_visual or has_baseline:
                raise ValueError("photo/AI mode requires structured assessment references")
        elif self.mode is ZoneDemandSourceMode.USER_CALIBRATED_BASELINE:
            if not has_baseline or has_plants or has_visual:
                raise ValueError("baseline mode requires only a calibrated baseline")
        elif sum((has_plants, has_visual, has_baseline)) < 2:
            raise ValueError("hybrid mode requires at least two evidence source kinds")


@dataclass(frozen=True, slots=True)
class IrrigationDeliveryLink(SerializableCommissioningModel):
    """Plant-group link to a separate canonical Water Delivery profile."""

    link_id: str
    plant_group_id: str
    status: DeliveryLinkStatus
    delivery_profile_id: str | None = None
    component_ids: tuple[str, ...] = ()
    dedicated_delivery: bool | None = None

    def __post_init__(self) -> None:
        _identifier("link_id", self.link_id)
        _identifier("plant_group_id", self.plant_group_id)
        _unique_ids("component_ids", self.component_ids)
        if self.status is DeliveryLinkStatus.UNRESOLVED:
            if self.delivery_profile_id is not None or self.component_ids:
                raise ValueError("unresolved delivery links cannot claim profile evidence")
            if self.dedicated_delivery is not None:
                raise ValueError("unresolved delivery links cannot claim dedicated delivery")
        elif self.delivery_profile_id is None:
            raise ValueError("documented delivery links require delivery_profile_id")
        else:
            _identifier("delivery_profile_id", self.delivery_profile_id)


@dataclass(frozen=True, slots=True)
class LandscapePlantSnapshot(SerializableCommissioningModel):
    """Plant state captured by an immutable landscape event."""

    plant_group: PlantGroup
    commissioning_details: PlantCommissioningDetails

    def __post_init__(self) -> None:
        if self.plant_group.plant_group_id != self.commissioning_details.plant_group_id:
            raise ValueError("snapshot plant and commissioning identities must match")


@dataclass(frozen=True, slots=True)
class LandscapeChangeEvent(SerializableCommissioningModel):
    """Immutable add/remove history; current state is derived explicitly by the profile."""

    event_id: str
    event_type: LandscapeEventType
    effective_at: datetime
    plant_snapshot: LandscapePlantSnapshot

    def __post_init__(self) -> None:
        _identifier("event_id", self.event_id)
        _timestamp("effective_at", self.effective_at)


@dataclass(frozen=True, slots=True)
class DeliveryAdvisory(SerializableCommissioningModel):
    """Privacy-safe design advisory with no command semantics."""

    code: str
    plant_group_id: str
    detail: str

    def __post_init__(self) -> None:
        _identifier("code", self.code)
        _identifier("plant_group_id", self.plant_group_id)
        _text("detail", self.detail)


@dataclass(frozen=True, slots=True)
class DeliveryCompatibilityAssessment(SerializableCommissioningModel):
    """Deterministic evidence assessment separate from scheduling and execution."""

    state: DeliveryCompatibilityState
    advisories: tuple[DeliveryAdvisory, ...]
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("delivery compatibility is advisory only")


@dataclass(frozen=True, slots=True)
class CommissionedZoneProfile(SerializableCommissioningModel):
    """Generic zone commissioning aggregate wrapping the v1 landscape profile."""

    schema_version: int
    identity: CanonicalZoneIdentity
    display_name: str
    landscape_profile: LandscapeIntelligenceProfile
    plant_details: tuple[PlantCommissioningDetails, ...]
    demand_sources: tuple[ZoneDemandSource, ...]
    delivery_links: tuple[IrrigationDeliveryLink, ...]
    landscape_events: tuple[LandscapeChangeEvent, ...] = ()
    conflicts: tuple[CommissioningEvidenceConflict, ...] = ()
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != ZONE_COMMISSIONING_SCHEMA_VERSION:
            raise ValueError("unsupported zone commissioning schema version")
        _text("display_name", self.display_name)
        if self.identity.area_slot != self.landscape_profile.area_slot:
            raise ValueError("canonical area slot must match landscape profile")
        current_ids = {item.plant_group_id for item in self.landscape_profile.plant_groups}
        detail_ids = tuple(item.plant_group_id for item in self.plant_details)
        if len(detail_ids) != len(set(detail_ids)):
            raise ValueError("plant_details must not contain duplicate plant groups")
        if set(detail_ids) != current_ids:
            raise ValueError("plant_details must exactly cover current plant groups")
        source_ids = tuple(item.source_id for item in self.demand_sources)
        link_ids = tuple(item.link_id for item in self.delivery_links)
        event_ids = tuple(item.event_id for item in self.landscape_events)
        conflict_ids = tuple(item.conflict_id for item in self.conflicts)
        for name, values in (
            ("demand source IDs", source_ids),
            ("delivery link IDs", link_ids),
            ("landscape event IDs", event_ids),
            ("commissioning conflict IDs", conflict_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        if not self.demand_sources:
            raise ValueError("commissioned zone requires at least one demand source")
        if any(
            group_id not in current_ids
            for source in self.demand_sources
            for group_id in source.plant_group_ids
        ):
            raise ValueError("demand source references an unknown current plant group")
        if any(link.plant_group_id not in current_ids for link in self.delivery_links):
            raise ValueError("delivery link references an unknown current plant group")
        if any(conflict.plant_group_id not in current_ids for conflict in self.conflicts):
            raise ValueError("commissioning conflict references an unknown current plant group")
        if len({link.plant_group_id for link in self.delivery_links}) != len(
            self.delivery_links
        ):
            raise ValueError("each current plant group may have at most one delivery link")
        previous_event_at: datetime | None = None
        for event in self.landscape_events:
            if previous_event_at is not None and event.effective_at < previous_event_at:
                raise ValueError("landscape events must be chronological")
            previous_event_at = event.effective_at
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("zone commissioning is advisory only")

    def to_landscape_intelligence_profile(self) -> LandscapeIntelligenceProfile:
        """Return the backward-compatible v1 profile consumed by existing engines."""
        return self.landscape_profile


@dataclass(frozen=True, slots=True)
class DeactivatedCommissionedZone(SerializableCommissioningModel):
    """Evidence-preserving tombstone for a deactivated commissioned zone."""

    profile: CommissionedZoneProfile
    deactivated_at: datetime
    reason: str

    def __post_init__(self) -> None:
        _timestamp("deactivated_at", self.deactivated_at)
        _text("reason", self.reason)


def assess_delivery_compatibility(
    profile: CommissionedZoneProfile,
) -> DeliveryCompatibilityAssessment:
    """Assess documentation gaps without inferring hardware performance."""
    links = {item.plant_group_id: item for item in profile.delivery_links}
    advisories: list[DeliveryAdvisory] = []
    for group in profile.landscape_profile.plant_groups:
        if group.irrigation_role is IrrigationRole.INCIDENTAL:
            continue
        link = links.get(group.plant_group_id)
        if link is None or link.status is DeliveryLinkStatus.UNRESOLVED:
            advisories.append(
                DeliveryAdvisory(
                    "irrigation_delivery_information_required",
                    group.plant_group_id,
                    "Document how this plant group receives irrigation before "
                    "assessing compatibility.",
                )
            )
            continue
        if link.status is DeliveryLinkStatus.REVIEW_REQUIRED:
            advisories.append(
                DeliveryAdvisory(
                    "irrigation_delivery_compatibility_review_required",
                    group.plant_group_id,
                    "The documented plant-to-delivery relationship requires review.",
                )
            )
        if (
            group.establishment_state
            in {EstablishmentState.NEWLY_PLANTED, EstablishmentState.ESTABLISHING}
            and link.dedicated_delivery is False
        ):
            advisories.append(
                DeliveryAdvisory(
                    "establishment_delivery_review_required",
                    group.plant_group_id,
                    "Review whether shared delivery can meet establishment needs without "
                    "overwatering other groups.",
                )
            )
    if any(item.code == "irrigation_delivery_information_required" for item in advisories):
        state = DeliveryCompatibilityState.INSUFFICIENT_EVIDENCE
    elif advisories:
        state = DeliveryCompatibilityState.REVIEW_REQUIRED
    else:
        state = DeliveryCompatibilityState.DOCUMENTED
    return DeliveryCompatibilityAssessment(state, tuple(advisories))
