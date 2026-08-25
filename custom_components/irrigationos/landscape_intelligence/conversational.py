"""Pure conversational commissioning fusion into canonical IrrigationOS models."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from ..water_delivery import (
    ApproximateFlowRange,
    DeliveryComponentCalibrationRequest,
    DeliveryEvidenceLevel,
    DeliveryFact,
    DeliveryProvenance,
    FlowBasis,
    SprayPattern,
    WaterDeliveryProfile,
    WaterDeliveryType,
    calibrate_delivery_component,
)
from .commissioning import (
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    CommissioningConflictCandidate,
    CommissioningEvidenceConflict,
    CommissioningEvidenceSource,
    DeliveryLinkStatus,
    IrrigationDeliveryLink,
    ZoneDemandSourceMode,
)
from .models import Confidence, EstablishmentState, IrrigationRole
from .onboarding import (
    ApprovedVisualPlantFinding,
    ManualPlantOnboardingInput,
    ZoneOnboardingRequest,
    map_zone_onboarding,
)

CONVERSATIONAL_COMMISSIONING_POLICY_VERSION = "1.0.0"
_NON_ID = re.compile(r"[^a-z0-9]+")


class CommissioningExperienceLevel(StrEnum):
    """Progressive-disclosure mode; both modes write identical canonical models."""

    SIMPLE = "simple"
    ADVANCED = "advanced"


class DeliverySharing(StrEnum):
    """Plain-language delivery relationship."""

    DEDICATED = "dedicated"
    SHARED = "shared"
    UNKNOWN = "unknown"


class EvidenceMateriality(StrEnum):
    """Whether more precision is useful for the current advisory decision."""

    SUFFICIENT_FOR_CURRENT_DECISION = "sufficient_for_current_decision"
    OPTIONAL_PRECISION_IMPROVEMENT = "optional_precision_improvement"
    ADDITIONAL_EVIDENCE_REQUIRED = "additional_evidence_required"


class FollowUpImportance(StrEnum):
    """Stable question priority."""

    REQUIRED = "required"
    HIGH = "high"
    OPTIONAL = "optional"


@dataclass(frozen=True, slots=True)
class GenericDeliveryReference:
    """Documented provider-neutral range supplied by a reference catalog."""

    reference_id: str
    delivery_type: WaterDeliveryType
    emitter_class: str
    throw_min_meters: float
    throw_max_meters: float
    flow_min_liters_per_hour: float | None = None
    flow_max_liters_per_hour: float | None = None
    source: str = "generic_reference_catalog"
    confidence: float = 0.45

    def __post_init__(self) -> None:
        if self.throw_min_meters <= 0 or self.throw_max_meters < self.throw_min_meters:
            raise ValueError("generic reference throw range is invalid")
        paired = (self.flow_min_liters_per_hour is None) == (
            self.flow_max_liters_per_hour is None
        )
        if not paired:
            raise ValueError("generic flow range requires both bounds")
        if self.flow_min_liters_per_hour is not None and (
            self.flow_min_liters_per_hour <= 0
            or self.flow_max_liters_per_hour is None
            or self.flow_max_liters_per_hour < self.flow_min_liters_per_hour
        ):
            raise ValueError("generic reference flow range is invalid")
        if not 0 <= self.confidence <= 1:
            raise ValueError("generic reference confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SimplePlantDescription:
    """Plain-language plant facts without internal identifiers."""

    common_name: str
    observed_at: datetime
    botanical_name: str | None = None
    planted_at: datetime | None = None
    source_container_gallons: float | None = None
    current_height_meters: float | None = None
    establishment_state: EstablishmentState = EstablishmentState.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.common_name, str) or not self.common_name.strip():
            raise ValueError("common_name must not be blank")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        for name, value in (
            ("source_container_gallons", self.source_container_gallons),
            ("current_height_meters", self.current_height_meters),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class SimpleDeliveryDescription:
    """Observable delivery facts a non-expert can reasonably provide."""

    delivery_type: WaterDeliveryType
    observed_at: datetime
    emitter_class: str | None = None
    throw_min_meters: float | None = None
    throw_max_meters: float | None = None
    spray_pattern: SprayPattern = SprayPattern.UNKNOWN
    arc_degrees: float | None = None
    sharing: DeliverySharing = DeliverySharing.UNKNOWN
    plants_per_emitter: int | None = None
    emitter_count: int | None = None
    generic_reference_id: str | None = None

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.throw_min_meters is not None and self.throw_min_meters <= 0:
            raise ValueError("throw_min_meters must be positive")
        if (
            self.throw_max_meters is not None
            and (
                self.throw_min_meters is None
                or self.throw_max_meters < self.throw_min_meters
            )
        ):
            raise ValueError("throw range is incomplete or reversed")
        if self.arc_degrees is not None and not 0 < self.arc_degrees <= 360:
            raise ValueError("arc_degrees must be between 0 and 360")
        for name, value in (
            ("plants_per_emitter", self.plants_per_emitter),
            ("emitter_count", self.emitter_count),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class ApprovedVisualDeliveryFinding:
    """Human-approved provider-neutral visual delivery evidence; never image bytes."""

    assessment_id: str
    evidence_ids: tuple[str, ...]
    delivery_type: WaterDeliveryType
    confidence: Confidence
    approved_at: datetime
    spray_pattern: SprayPattern = SprayPattern.UNKNOWN
    arc_degrees: float | None = None
    throw_meters: float | None = None
    apparent_shared_delivery: bool | None = None

    def __post_init__(self) -> None:
        if not self.assessment_id.strip() or not self.evidence_ids:
            raise ValueError("approved visual findings require assessment and evidence IDs")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("visual evidence IDs must be unique")
        if self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")
        if self.arc_degrees is not None and not 0 < self.arc_degrees <= 360:
            raise ValueError("arc_degrees must be between 0 and 360")
        if self.throw_meters is not None and self.throw_meters <= 0:
            raise ValueError("throw_meters must be positive")


@dataclass(frozen=True, slots=True)
class ConversationalCommissioningIntake:
    """Immutable provider-neutral simple intake; raw photos are excluded."""

    identity: CanonicalZoneIdentity
    display_name: str
    description: str
    observed_at: datetime
    plant: SimplePlantDescription | None = None
    delivery: SimpleDeliveryDescription | None = None
    visual_plant: ApprovedVisualPlantFinding | None = None
    visual_delivery: ApprovedVisualDeliveryFinding | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("conversational description must not be blank")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CommissioningFollowUpQuestion:
    """One deterministic high-value question, separate from canonical evidence."""

    code: str
    question: str
    reason: str
    importance: FollowUpImportance
    evidence_gap: str
    plant_group_id: str | None = None
    component_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationalCommissioningProposal:
    """Reviewable candidate canonical update; persistence remains an explicit step."""

    zone_profile: CommissionedZoneProfile
    delivery_profile: WaterDeliveryProfile | None
    summary: tuple[str, ...]
    follow_up_questions: tuple[CommissioningFollowUpQuestion, ...]
    flow_materiality: EvidenceMateriality
    policy_version: str = CONVERSATIONAL_COMMISSIONING_POLICY_VERSION
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("conversational commissioning is evidence-only")

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic review data without raw provider payloads."""
        return {
            "zone_profile": self.zone_profile.to_dict(),
            "delivery_profile": (
                None if self.delivery_profile is None else self.delivery_profile.to_dict()
            ),
            "summary": list(self.summary),
            "follow_up_questions": [
                {
                    "code": item.code,
                    "question": item.question,
                    "reason": item.reason,
                    "importance": item.importance.value,
                    "evidence_gap": item.evidence_gap,
                    "plant_group_id": item.plant_group_id,
                    "component_id": item.component_id,
                }
                for item in self.follow_up_questions
            ],
            "flow_materiality": self.flow_materiality.value,
            "policy_version": self.policy_version,
            "execution_authorized": False,
            "live_control_authorized": False,
        }


def _slug(value: str) -> str:
    slug = _NON_ID.sub("_", value.strip().casefold()).strip("_")
    return slug or "plant"


def _arc_pattern(value: float | None, pattern: SprayPattern) -> SprayPattern:
    if pattern is not SprayPattern.UNKNOWN:
        return pattern
    if value is None:
        return SprayPattern.UNKNOWN
    return SprayPattern.FULL_CIRCLE if value == 360 else SprayPattern.PART_CIRCLE


def _materiality(reference: GenericDeliveryReference | None) -> EvidenceMateriality:
    if reference is None or reference.flow_min_liters_per_hour is None:
        return EvidenceMateriality.ADDITIONAL_EVIDENCE_REQUIRED
    low = reference.flow_min_liters_per_hour
    high = reference.flow_max_liters_per_hour or low
    midpoint = (low + high) / 2
    if (high - low) / midpoint <= 0.25:
        return EvidenceMateriality.SUFFICIENT_FOR_CURRENT_DECISION
    return EvidenceMateriality.OPTIONAL_PRECISION_IMPROVEMENT


def build_conversational_commissioning_proposal(
    intake: ConversationalCommissioningIntake,
    *,
    generic_references: tuple[GenericDeliveryReference, ...] = (),
) -> ConversationalCommissioningProposal:
    """Fuse simple/manual/visual facts into existing canonical evidence models."""
    plant_name = (
        intake.plant.common_name
        if intake.plant is not None
        else intake.visual_plant.likely_common_name
        if intake.visual_plant is not None
        else "unknown"
    )
    plant_id = f"{intake.identity.zone_id}.plant.{_slug(plant_name)}"
    manual: tuple[ManualPlantOnboardingInput, ...] = ()
    if intake.plant is not None:
        manual = (
            ManualPlantOnboardingInput(
                plant_id,
                intake.plant.common_name,
                intake.plant.botanical_name,
                intake.plant.establishment_state,
                intake.plant.observed_at,
                intake.plant.planted_at,
                intake.plant.source_container_gallons,
                intake.plant.current_height_meters,
                IrrigationRole.PRIMARY_TARGET,
                intake.delivery is not None,
                intake.delivery is not None
                and intake.delivery.sharing is DeliverySharing.DEDICATED,
                None if intake.delivery is None else intake.delivery.delivery_type.value,
            ),
        )
    visual: tuple[ApprovedVisualPlantFinding, ...] = ()
    if intake.visual_plant is not None:
        visual = (replace(intake.visual_plant, plant_group_id=plant_id),)
    mode = (
        ZoneDemandSourceMode.HYBRID
        if manual and visual
        else ZoneDemandSourceMode.MANUAL_PLANT_PROFILE
        if manual
        else ZoneDemandSourceMode.PHOTO_AI_DERIVED
    )
    zone = map_zone_onboarding(
        ZoneOnboardingRequest(
            intake.identity,
            intake.display_name,
            mode,
            intake.observed_at,
            manual,
            visual,
        )
    )
    reference = next(
        (
            item
            for item in generic_references
            if intake.delivery is not None
            and item.reference_id == intake.delivery.generic_reference_id
        ),
        None,
    )
    delivery_profile: WaterDeliveryProfile | None = None
    flow_materiality = _materiality(reference)
    conflicts = list(zone.conflicts)
    questions: list[CommissioningFollowUpQuestion] = []
    summary = [f"Plant: {manual[0].common_name if manual else visual[0].likely_common_name}"]
    if intake.delivery is not None:
        component_id = (
            f"{intake.identity.zone_id}.component."
            f"{intake.delivery.delivery_type.value}.1"
        )
        count = intake.delivery.emitter_count or 1
        delivery_profile = calibrate_delivery_component(
            DeliveryComponentCalibrationRequest(
                profile_id=f"{intake.identity.zone_id}.delivery",
                area_id=intake.identity.zone_id,
                component_id=component_id,
                display_name=(
                    f"{intake.delivery.delivery_type.value.replace('_', ' ').title()} "
                    "delivery"
                ),
                delivery_type=intake.delivery.delivery_type,
                component_count=count,
                flow_evidence_level=DeliveryEvidenceLevel.UNKNOWN,
                observed_at=intake.delivery.observed_at,
                flow_basis=FlowBasis.PER_EMITTER,
                radius_meters=(
                    None
                    if intake.delivery.throw_min_meters is None
                    else (
                        intake.delivery.throw_min_meters
                        + (intake.delivery.throw_max_meters or intake.delivery.throw_min_meters)
                    )
                    / 2
                ),
            )
        )
        component = delivery_profile.components[0]
        approximate_range = None
        if reference is not None and reference.flow_min_liters_per_hour is not None:
            approximate_range = ApproximateFlowRange(
                reference.flow_min_liters_per_hour,
                reference.flow_max_liters_per_hour or reference.flow_min_liters_per_hour,
                reference.reference_id,
                reference.confidence,
                DeliveryProvenance(reference.source, reference.emitter_class),
                intake.delivery.observed_at,
            )
        resolved_pattern = _arc_pattern(
            intake.delivery.arc_degrees, intake.delivery.spray_pattern
        )
        component = replace(
            component,
            arc_degrees=DeliveryFact(
                intake.delivery.arc_degrees,
                0.6 if intake.delivery.arc_degrees is not None else 0.0,
                DeliveryProvenance("user_described_approximate_delivery"),
                intake.delivery.observed_at,
                DeliveryEvidenceLevel.USER_ESTIMATED,
            ),
            spray_pattern=DeliveryFact(
                resolved_pattern,
                0.0 if resolved_pattern is SprayPattern.UNKNOWN else 0.6,
                DeliveryProvenance("user_described_approximate_delivery"),
                intake.delivery.observed_at,
                DeliveryEvidenceLevel.USER_ESTIMATED,
            ),
            approximate_flow_range=approximate_range,
            emitter_class=intake.delivery.emitter_class,
            plants_per_emitter=intake.delivery.plants_per_emitter,
            visual_assessment_ids=(
                ()
                if intake.visual_delivery is None
                else (intake.visual_delivery.assessment_id,)
            ),
            visual_evidence_ids=(
                ()
                if intake.visual_delivery is None
                else intake.visual_delivery.evidence_ids
            ),
        )
        delivery_profile = replace(delivery_profile, components=(component,))
        link = IrrigationDeliveryLink(
            f"{plant_id}.delivery",
            plant_id,
            DeliveryLinkStatus.DOCUMENTED,
            delivery_profile.profile_id,
            (component_id,),
            intake.delivery.sharing is DeliverySharing.DEDICATED,
        )
        zone = replace(zone, delivery_links=(link,))
        summary.append(
            f"Delivery: {intake.delivery.delivery_type.value}; {intake.delivery.sharing.value}"
        )
        if intake.delivery.sharing is DeliverySharing.UNKNOWN:
            questions.append(
                CommissioningFollowUpQuestion(
                    "delivery_sharing_required",
                    "Does one emitter water one plant or several plants?",
                    "Sharing materially changes how delivery relates to plant demand.",
                    FollowUpImportance.HIGH,
                    "delivery.sharing",
                    plant_id,
                    component_id,
                )
            )
        if flow_materiality is EvidenceMateriality.OPTIONAL_PRECISION_IMPROVEMENT:
            questions.append(
                CommissioningFollowUpQuestion(
                    "measure_emitter_flow_optional",
                    "Would you like to measure this emitter's flow?",
                    "The generic range is wide enough that measurement could improve "
                    "a later estimate.",
                    FollowUpImportance.OPTIONAL,
                    "delivery.flow_precision",
                    plant_id,
                    component_id,
                )
            )
    else:
        questions.append(
            CommissioningFollowUpQuestion(
                "delivery_type_required",
                "How does water reach this plant group?",
                "Delivery information is needed before water can be quantified.",
                FollowUpImportance.HIGH,
                "delivery.type",
                plant_id,
            )
        )
    if intake.visual_delivery is not None and intake.delivery is not None:
        user_pattern = _arc_pattern(intake.delivery.arc_degrees, intake.delivery.spray_pattern)
        visual_pattern = _arc_pattern(
            intake.visual_delivery.arc_degrees, intake.visual_delivery.spray_pattern
        )
        if user_pattern is not visual_pattern:
            conflicts.append(
                CommissioningEvidenceConflict(
                    f"{plant_id}.conflict.delivery_pattern",
                    plant_id,
                    "delivery.spray_pattern",
                    (
                        CommissioningConflictCandidate(
                            CommissioningEvidenceSource.USER_CONFIRMED,
                            user_pattern.value,
                            Confidence.HIGH,
                        ),
                        CommissioningConflictCandidate(
                            CommissioningEvidenceSource.AI_INFERRED,
                            visual_pattern.value,
                            intake.visual_delivery.confidence,
                            intake.visual_delivery.evidence_ids,
                        ),
                    ),
                    "User-described and approved visual delivery patterns disagree.",
                )
            )
            questions.insert(
                0,
                CommissioningFollowUpQuestion(
                    "confirm_delivery_pattern",
                    "Is this emitter two-sided/part-circle or full-circle?",
                    "The user description and visual finding disagree.",
                    FollowUpImportance.REQUIRED,
                    "delivery.spray_pattern",
                    plant_id,
                ),
            )
    zone = replace(zone, conflicts=tuple(sorted(conflicts, key=lambda item: item.conflict_id)))
    questions.sort(key=lambda item: (list(FollowUpImportance).index(item.importance), item.code))
    return ConversationalCommissioningProposal(
        zone,
        delivery_profile,
        tuple(summary),
        tuple(questions),
        flow_materiality,
    )
