"""Deterministic commissioning completeness and evidence-admission policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .commissioning import (
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    CommissioningEvidenceSource,
    DeliveryLinkStatus,
    SerializableCommissioningModel,
    ZoneDemandSourceMode,
)
from .models import Confidence, EstablishmentState, IrrigationRole

COMMISSIONING_ASSESSMENT_SCHEMA_VERSION = 1
COMMISSIONING_ADMISSION_POLICY_VERSION = "1.0.0"


class CommissioningPurpose(StrEnum):
    """Downstream purposes evaluated independently by commissioning policy."""

    LANDSCAPE_UNDERSTANDING = "landscape_understanding"
    PLANT_DEMAND_ESTIMATION = "plant_demand_estimation"
    BASELINE_ENVIRONMENTAL_SCALING = "baseline_environmental_scaling"
    DELIVERY_QUANTIFICATION = "delivery_quantification"
    WATER_BALANCE = "water_balance"
    ADVISORY_ONLY = "advisory_only"


class PurposeReadinessState(StrEnum):
    """Whether commissioning evidence is fit to enter one purpose."""

    NOT_READY = "not_ready"
    READY = "ready"


class CommissioningAssessmentStatus(StrEnum):
    """Overall usefulness of current commissioning evidence, never authority."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ADVISORY_ONLY = "advisory_only"
    PURPOSE_READY = "purpose_ready"


class EvidenceAdmissionDecision(StrEnum):
    """Explicit policy result for one immutable evidence item."""

    ADMITTED = "admitted"
    WITHHELD = "withheld"


class CommissioningEvidenceKind(StrEnum):
    """Stable kinds of commissioning evidence understood by this policy."""

    PLANT_IDENTITY = "plant_identity"
    ESTABLISHMENT_STATE = "establishment_state"
    PLANT_MEASUREMENT = "plant_measurement"
    STRUCTURED_VISUAL_FINDING = "structured_visual_finding"
    CALIBRATED_BASELINE = "calibrated_baseline"
    DELIVERY_LINK = "delivery_link"


class FollowUpPriority(StrEnum):
    """Relative importance of one structured request for information."""

    REQUIRED = "required"
    RECOMMENDED = "recommended"


@dataclass(frozen=True, slots=True)
class CommissioningEvidenceAdmission(SerializableCommissioningModel):
    """Admission result preserving source, confidence, and evidence references."""

    evidence_id: str
    kind: CommissioningEvidenceKind
    decision: EvidenceAdmissionDecision
    source: CommissioningEvidenceSource
    confidence: Confidence
    plant_group_id: str | None
    evidence_reference_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.decision is EvidenceAdmissionDecision.ADMITTED and not self.reason_codes:
            raise ValueError("admitted evidence requires an explanation")
        _require_sorted_unique("reason_codes", self.reason_codes)
        if self.evidence_reference_ids != tuple(sorted(self.evidence_reference_ids)):
            raise ValueError("evidence references must use deterministic ordering")


@dataclass(frozen=True, slots=True)
class CommissioningPurposeReadiness(SerializableCommissioningModel):
    """Purpose-specific readiness derived only from commissioning evidence."""

    purpose: CommissioningPurpose
    state: PurposeReadinessState
    blocker_codes: tuple[str, ...]
    advisory_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sorted_unique("blocker_codes", self.blocker_codes)
        _require_sorted_unique("advisory_codes", self.advisory_codes)
        if self.state is PurposeReadinessState.READY and self.blocker_codes:
            raise ValueError("ready purpose cannot retain blockers")


@dataclass(frozen=True, slots=True)
class CommissioningFollowUpRequirement(SerializableCommissioningModel):
    """Structured next information request suitable for deterministic UI."""

    code: str
    priority: FollowUpPriority
    purposes: tuple[CommissioningPurpose, ...]
    plant_group_id: str | None
    prompt: str


@dataclass(frozen=True, slots=True)
class CommissioningConfidenceSummary(SerializableCommissioningModel):
    """Bounded summary of admitted and withheld evidence quality."""

    admitted_high_count: int
    admitted_moderate_count: int
    admitted_low_count: int
    withheld_count: int
    admitted_sources: tuple[CommissioningEvidenceSource, ...]

    def __post_init__(self) -> None:
        counts = (
            self.admitted_high_count,
            self.admitted_moderate_count,
            self.admitted_low_count,
            self.withheld_count,
        )
        if any(isinstance(value, bool) or value < 0 for value in counts):
            raise ValueError("confidence counts must be non-negative integers")
        if self.admitted_sources != tuple(sorted(set(self.admitted_sources), key=str)):
            raise ValueError("admitted sources must be unique and deterministic")


@dataclass(frozen=True, slots=True)
class CommissioningAssessment(SerializableCommissioningModel):
    """Immutable purpose-specific commissioning assessment."""

    identity: CanonicalZoneIdentity
    status: CommissioningAssessmentStatus
    purpose_readiness: tuple[CommissioningPurposeReadiness, ...]
    admitted_evidence: tuple[CommissioningEvidenceAdmission, ...]
    unresolved_evidence: tuple[CommissioningEvidenceAdmission, ...]
    blocker_codes: tuple[str, ...]
    advisory_codes: tuple[str, ...]
    follow_up_requirements: tuple[CommissioningFollowUpRequirement, ...]
    confidence_summary: CommissioningConfidenceSummary
    schema_version: int = COMMISSIONING_ASSESSMENT_SCHEMA_VERSION
    policy_version: str = COMMISSIONING_ADMISSION_POLICY_VERSION
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != COMMISSIONING_ASSESSMENT_SCHEMA_VERSION:
            raise ValueError("unsupported commissioning assessment schema")
        if self.policy_version != COMMISSIONING_ADMISSION_POLICY_VERSION:
            raise ValueError("unsupported commissioning admission policy")
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("commissioning assessment cannot authorize execution")
        if tuple(item.purpose for item in self.purpose_readiness) != _PURPOSE_ORDER:
            raise ValueError("purpose readiness must use canonical deterministic ordering")
        _require_sorted_unique("blocker_codes", self.blocker_codes)
        _require_sorted_unique("advisory_codes", self.advisory_codes)
        evidence = (*self.admitted_evidence, *self.unresolved_evidence)
        evidence_ids = tuple(item.evidence_id for item in evidence)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("commissioning evidence IDs must be unique")
        if tuple(item.evidence_id for item in self.admitted_evidence) != tuple(
            sorted(item.evidence_id for item in self.admitted_evidence)
        ):
            raise ValueError("admitted evidence must use deterministic ordering")
        if tuple(item.evidence_id for item in self.unresolved_evidence) != tuple(
            sorted(item.evidence_id for item in self.unresolved_evidence)
        ):
            raise ValueError("unresolved evidence must use deterministic ordering")
        if any(
            item.decision is not EvidenceAdmissionDecision.ADMITTED
            for item in self.admitted_evidence
        ) or any(
            item.decision is not EvidenceAdmissionDecision.WITHHELD
            for item in self.unresolved_evidence
        ):
            raise ValueError("evidence collections must match admission decisions")
        followup_keys = tuple(
            (item.code, item.plant_group_id or "")
            for item in self.follow_up_requirements
        )
        if followup_keys != tuple(sorted(set(followup_keys))):
            raise ValueError("follow-up requirements must be unique and deterministic")

    def readiness_for(self, purpose: CommissioningPurpose) -> CommissioningPurposeReadiness:
        """Return the deterministic result for one required purpose."""
        return next(item for item in self.purpose_readiness if item.purpose is purpose)


_PURPOSE_ORDER = tuple(CommissioningPurpose)
_UNKNOWN_IDENTITIES = frozenset({"unknown", "unresolved", "unidentified", "unknown plant"})


def _require_sorted_unique(name: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must be unique and deterministically ordered")


def assess_commissioning(profile: CommissionedZoneProfile) -> CommissioningAssessment:
    """Assess evidence fitness without resolving science or granting authority."""
    resolved_conflicts = {item.conflict_id for item in profile.conflict_resolutions}
    unresolved_conflicts = tuple(
        item for item in profile.conflicts if item.conflict_id not in resolved_conflicts
    )
    conflicted_groups = {item.plant_group_id for item in unresolved_conflicts}
    details_by_group = {item.plant_group_id: item for item in profile.plant_details}
    links_by_group = {item.plant_group_id: item for item in profile.delivery_links}

    admitted: list[CommissioningEvidenceAdmission] = []
    withheld: list[CommissioningEvidenceAdmission] = []
    blockers: set[str] = set()
    advisories: set[str] = set()
    followups: dict[tuple[str, str | None], CommissioningFollowUpRequirement] = {}

    active_demand_groups = tuple(
        group
        for group in profile.landscape_profile.plant_groups
        if group.irrigation_role is not IrrigationRole.INCIDENTAL
    )
    identity_ready = bool(active_demand_groups)
    establishment_ready = bool(active_demand_groups)
    delivery_ready = bool(active_demand_groups)

    for conflict in unresolved_conflicts:
        for index, candidate in enumerate(conflict.candidates, start=1):
            withheld.append(
                CommissioningEvidenceAdmission(
                    evidence_id=f"{conflict.conflict_id}.candidate.{index}",
                    kind=CommissioningEvidenceKind.PLANT_IDENTITY,
                    decision=EvidenceAdmissionDecision.WITHHELD,
                    source=candidate.source,
                    confidence=candidate.confidence,
                    plant_group_id=conflict.plant_group_id,
                    evidence_reference_ids=tuple(sorted(candidate.evidence_ids)),
                    reason_codes=("commissioning_conflict_unresolved",),
                )
            )

    for group in profile.landscape_profile.plant_groups:
        details = details_by_group[group.plant_group_id]
        identity_is_unknown = group.common_name.strip().casefold() in _UNKNOWN_IDENTITIES
        source_admissible = _source_is_admissible(details.source, details.confidence)
        identity_admissible = (
            not identity_is_unknown
            and group.plant_group_id not in conflicted_groups
            and source_admissible
        )
        identity = CommissioningEvidenceAdmission(
            evidence_id=f"{group.plant_group_id}.identity",
            kind=CommissioningEvidenceKind.PLANT_IDENTITY,
            decision=(
                EvidenceAdmissionDecision.ADMITTED
                if identity_admissible
                else EvidenceAdmissionDecision.WITHHELD
            ),
            source=details.source,
            confidence=details.confidence,
            plant_group_id=group.plant_group_id,
            evidence_reference_ids=tuple(sorted(details.structured_evidence_ids)),
            reason_codes=_identity_reason_codes(
                conflict=group.plant_group_id in conflicted_groups,
                unknown=identity_is_unknown,
                source_admissible=source_admissible,
            ),
        )
        (admitted if identity_admissible else withheld).append(identity)

        if group.irrigation_role is not IrrigationRole.INCIDENTAL:
            if not identity_admissible:
                identity_ready = False
                code = (
                    "commissioning_conflict_unresolved"
                    if group.plant_group_id in conflicted_groups
                    else "plant_identity_unresolved"
                )
                blockers.add(code)
                _add_followup(
                    followups,
                    code="confirm_plant_identity",
                    plant_group_id=group.plant_group_id,
                    priority=FollowUpPriority.REQUIRED,
                    purposes=(
                        CommissioningPurpose.LANDSCAPE_UNDERSTANDING,
                        CommissioningPurpose.PLANT_DEMAND_ESTIMATION,
                    ),
                    prompt="Confirm the current plant identity for this plant group.",
                )

            establishment_admissible = (
                source_admissible
                and group.establishment_state is not EstablishmentState.UNKNOWN
            )
            establishment = CommissioningEvidenceAdmission(
                evidence_id=f"{group.plant_group_id}.establishment",
                kind=CommissioningEvidenceKind.ESTABLISHMENT_STATE,
                decision=(
                    EvidenceAdmissionDecision.ADMITTED
                    if establishment_admissible
                    else EvidenceAdmissionDecision.WITHHELD
                ),
                source=details.source,
                confidence=details.confidence,
                plant_group_id=group.plant_group_id,
                evidence_reference_ids=tuple(sorted(details.structured_evidence_ids)),
                reason_codes=(
                    ("establishment_state_admitted",)
                    if establishment_admissible
                    else ("establishment_state_unresolved",)
                ),
            )
            (admitted if establishment_admissible else withheld).append(establishment)
            if not establishment_admissible:
                establishment_ready = False
                blockers.add("establishment_state_unresolved")
                _add_followup(
                    followups,
                    code="confirm_establishment_state",
                    plant_group_id=group.plant_group_id,
                    priority=FollowUpPriority.RECOMMENDED,
                    purposes=(CommissioningPurpose.PLANT_DEMAND_ESTIMATION,),
                    prompt=(
                        "Confirm whether this plant group is newly planted, "
                        "establishing, or established."
                    ),
                )
            elif group.establishment_state is EstablishmentState.ESTABLISHED_OR_UNKNOWN:
                advisories.add("establishment_state_uncertain")

        measurement_values = (
            details.planted_at,
            details.source_container_gallons,
            details.current_height_meters,
        )
        if any(value is not None for value in measurement_values):
            measurements = CommissioningEvidenceAdmission(
                evidence_id=f"{group.plant_group_id}.measurements",
                kind=CommissioningEvidenceKind.PLANT_MEASUREMENT,
                decision=(
                    EvidenceAdmissionDecision.ADMITTED
                    if source_admissible
                    else EvidenceAdmissionDecision.WITHHELD
                ),
                source=details.source,
                confidence=details.confidence,
                plant_group_id=group.plant_group_id,
                evidence_reference_ids=tuple(sorted(details.structured_evidence_ids)),
                reason_codes=(
                    ("plant_measurements_preserved",)
                    if source_admissible
                    else ("plant_measurements_below_admission_policy",)
                ),
            )
            (admitted if source_admissible else withheld).append(measurements)

        if details.structured_evidence_ids:
            visual_admissible = _source_is_admissible(details.source, details.confidence)
            visual = CommissioningEvidenceAdmission(
                evidence_id=f"{group.plant_group_id}.structured_visual",
                kind=CommissioningEvidenceKind.STRUCTURED_VISUAL_FINDING,
                decision=(
                    EvidenceAdmissionDecision.ADMITTED
                    if visual_admissible
                    else EvidenceAdmissionDecision.WITHHELD
                ),
                source=details.source,
                confidence=details.confidence,
                plant_group_id=group.plant_group_id,
                evidence_reference_ids=tuple(sorted(details.structured_evidence_ids)),
                reason_codes=(
                    ("structured_visual_evidence_admitted",)
                    if visual_admissible
                    else ("structured_visual_evidence_below_policy",)
                ),
            )
            (admitted if visual_admissible else withheld).append(visual)
            if not visual_admissible:
                advisories.add("structured_visual_confirmation_required")
                _add_followup(
                    followups,
                    code="confirm_visual_plant_identity",
                    plant_group_id=group.plant_group_id,
                    priority=FollowUpPriority.REQUIRED,
                    purposes=(CommissioningPurpose.PLANT_DEMAND_ESTIMATION,),
                    prompt="Review and confirm the structured visual plant finding.",
                )

        if group.irrigation_role is IrrigationRole.INCIDENTAL:
            continue
        link = links_by_group.get(group.plant_group_id)
        link_admissible = link is not None and link.status is DeliveryLinkStatus.DOCUMENTED
        if link is not None and link.status is not DeliveryLinkStatus.UNRESOLVED:
            delivery = CommissioningEvidenceAdmission(
                evidence_id=f"{group.plant_group_id}.delivery",
                kind=CommissioningEvidenceKind.DELIVERY_LINK,
                decision=(
                    EvidenceAdmissionDecision.ADMITTED
                    if link_admissible
                    else EvidenceAdmissionDecision.WITHHELD
                ),
                source=(
                    CommissioningEvidenceSource.USER_CONFIRMED
                    if link_admissible
                    else details.source
                ),
                confidence=(Confidence.HIGH if link_admissible else details.confidence),
                plant_group_id=group.plant_group_id,
                evidence_reference_ids=tuple(
                    sorted((link.delivery_profile_id or "", *link.component_ids))
                ),
                reason_codes=(
                    ("delivery_link_admitted",)
                    if link_admissible
                    else ("irrigation_delivery_compatibility_review_required",)
                ),
            )
            (admitted if link_admissible else withheld).append(delivery)
        if not link_admissible:
            delivery_ready = False
            blocker = (
                "irrigation_delivery_information_required"
                if link is None or link.status is DeliveryLinkStatus.UNRESOLVED
                else "delivery_quantification_unavailable"
            )
            blockers.add(blocker)
            _add_followup(
                followups,
                code="document_irrigation_delivery",
                plant_group_id=group.plant_group_id,
                priority=FollowUpPriority.REQUIRED,
                purposes=(CommissioningPurpose.DELIVERY_QUANTIFICATION,),
                prompt=(
                    "Document the delivery profile and components that irrigate this plant group."
                ),
            )
            if group.establishment_state in {
                EstablishmentState.NEWLY_PLANTED,
                EstablishmentState.ESTABLISHING,
            }:
                advisories.add("establishment_delivery_review_required")
                _add_followup(
                    followups,
                    code="confirm_establishment_delivery",
                    plant_group_id=group.plant_group_id,
                    priority=FollowUpPriority.RECOMMENDED,
                    purposes=(
                        CommissioningPurpose.DELIVERY_QUANTIFICATION,
                        CommissioningPurpose.ADVISORY_ONLY,
                    ),
                    prompt=(
                        "Confirm whether dedicated delivery reaches this establishing plant group."
                    ),
                )
        else:
            advisories.add("delivery_profile_requires_downstream_validation")

    baseline_admitted = False
    for source in profile.demand_sources:
        baseline = source.calibrated_baseline
        if baseline is None:
            continue
        item_admitted = baseline.confidence in {Confidence.MODERATE, Confidence.HIGH}
        baseline_admitted = baseline_admitted or item_admitted
        evidence = CommissioningEvidenceAdmission(
            evidence_id=f"{source.source_id}.baseline",
            kind=CommissioningEvidenceKind.CALIBRATED_BASELINE,
            decision=(
                EvidenceAdmissionDecision.ADMITTED
                if item_admitted
                else EvidenceAdmissionDecision.WITHHELD
            ),
            source=CommissioningEvidenceSource.USER_CONFIRMED,
            confidence=baseline.confidence,
            plant_group_id=None,
            evidence_reference_ids=(source.source_id,),
            reason_codes=(
                ("calibrated_baseline_valid",)
                if item_admitted
                else ("calibrated_baseline_below_policy",)
            ),
        )
        (admitted if item_admitted else withheld).append(evidence)

    modes = {source.mode for source in profile.demand_sources}
    baseline_requested = bool(
        modes
        & {
            ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
            ZoneDemandSourceMode.HYBRID,
        }
    )
    if baseline_requested and not baseline_admitted:
        blockers.add("calibrated_baseline_missing")
        _add_followup(
            followups,
            code="provide_calibrated_baseline",
            plant_group_id=None,
            priority=FollowUpPriority.REQUIRED,
            purposes=(CommissioningPurpose.BASELINE_ENVIRONMENTAL_SCALING,),
            prompt="Provide or confirm the zone's runtime and reference dry-day conditions.",
        )

    landscape_ready = bool(profile.landscape_profile.plant_groups) and identity_ready
    plant_ready = identity_ready and establishment_ready and bool(active_demand_groups)
    water_balance_ready = plant_ready and delivery_ready
    if not plant_ready:
        blockers.add("plant_specific_demand_unavailable")
    if not water_balance_ready:
        blockers.add("water_balance_inputs_incomplete")
    if baseline_admitted:
        advisories.add("baseline_mode_ready_for_environmental_scaling")
    if plant_ready:
        advisories.add("commissioning_ready_for_factor_resolution")
    if water_balance_ready:
        advisories.add("external_water_balance_evidence_required")

    purpose_states = {
        CommissioningPurpose.LANDSCAPE_UNDERSTANDING: landscape_ready,
        CommissioningPurpose.PLANT_DEMAND_ESTIMATION: plant_ready,
        CommissioningPurpose.BASELINE_ENVIRONMENTAL_SCALING: baseline_admitted,
        CommissioningPurpose.DELIVERY_QUANTIFICATION: delivery_ready,
        CommissioningPurpose.WATER_BALANCE: water_balance_ready,
        CommissioningPurpose.ADVISORY_ONLY: bool(admitted or withheld),
    }
    readiness = tuple(
        _purpose_result(purpose, purpose_states[purpose], blockers, advisories)
        for purpose in _PURPOSE_ORDER
    )
    non_advisory_ready = any(
        item.state is PurposeReadinessState.READY
        for item in readiness
        if item.purpose is not CommissioningPurpose.ADVISORY_ONLY
    )
    status = (
        CommissioningAssessmentStatus.PURPOSE_READY
        if non_advisory_ready
        else CommissioningAssessmentStatus.ADVISORY_ONLY
        if purpose_states[CommissioningPurpose.ADVISORY_ONLY]
        else CommissioningAssessmentStatus.INSUFFICIENT_EVIDENCE
    )
    admitted_ordered = tuple(sorted(admitted, key=lambda item: item.evidence_id))
    withheld_ordered = tuple(sorted(withheld, key=lambda item: item.evidence_id))
    confidence_summary = CommissioningConfidenceSummary(
        admitted_high_count=sum(item.confidence is Confidence.HIGH for item in admitted_ordered),
        admitted_moderate_count=sum(
            item.confidence is Confidence.MODERATE for item in admitted_ordered
        ),
        admitted_low_count=sum(item.confidence is Confidence.LOW for item in admitted_ordered),
        withheld_count=len(withheld_ordered),
        admitted_sources=tuple(sorted({item.source for item in admitted_ordered}, key=str)),
    )
    return CommissioningAssessment(
        identity=profile.identity,
        status=status,
        purpose_readiness=readiness,
        admitted_evidence=admitted_ordered,
        unresolved_evidence=withheld_ordered,
        blocker_codes=tuple(sorted(blockers)),
        advisory_codes=tuple(sorted(advisories)),
        follow_up_requirements=tuple(
            sorted(followups.values(), key=lambda item: (item.code, item.plant_group_id or ""))
        ),
        confidence_summary=confidence_summary,
    )


def _source_is_admissible(source: CommissioningEvidenceSource, confidence: Confidence) -> bool:
    if source is CommissioningEvidenceSource.USER_CONFIRMED:
        return True
    if source is CommissioningEvidenceSource.HUMAN_REVIEWED_PHOTO:
        return confidence in {Confidence.MODERATE, Confidence.HIGH}
    if source is CommissioningEvidenceSource.AI_INFERRED:
        return confidence is Confidence.HIGH
    return False


def _identity_reason_codes(
    *, conflict: bool, unknown: bool, source_admissible: bool
) -> tuple[str, ...]:
    if conflict:
        return ("commissioning_conflict_unresolved",)
    if unknown:
        return ("plant_identity_unresolved",)
    if not source_admissible:
        return ("plant_identity_below_admission_policy",)
    return ("plant_identity_admitted",)


def _add_followup(
    items: dict[tuple[str, str | None], CommissioningFollowUpRequirement],
    *,
    code: str,
    plant_group_id: str | None,
    priority: FollowUpPriority,
    purposes: tuple[CommissioningPurpose, ...],
    prompt: str,
) -> None:
    items[(code, plant_group_id)] = CommissioningFollowUpRequirement(
        code=code,
        priority=priority,
        purposes=tuple(sorted(purposes, key=lambda item: _PURPOSE_ORDER.index(item))),
        plant_group_id=plant_group_id,
        prompt=prompt,
    )


def _purpose_result(
    purpose: CommissioningPurpose,
    ready: bool,
    blockers: set[str],
    advisories: set[str],
) -> CommissioningPurposeReadiness:
    relevant_blockers = {
        CommissioningPurpose.LANDSCAPE_UNDERSTANDING: {
            "commissioning_conflict_unresolved",
            "plant_identity_unresolved",
        },
        CommissioningPurpose.PLANT_DEMAND_ESTIMATION: {
            "commissioning_conflict_unresolved",
            "plant_identity_unresolved",
            "establishment_state_unresolved",
            "plant_specific_demand_unavailable",
        },
        CommissioningPurpose.BASELINE_ENVIRONMENTAL_SCALING: {
            "calibrated_baseline_missing",
        },
        CommissioningPurpose.DELIVERY_QUANTIFICATION: {
            "delivery_quantification_unavailable",
            "irrigation_delivery_information_required",
        },
        CommissioningPurpose.WATER_BALANCE: {
            "commissioning_conflict_unresolved",
            "plant_identity_unresolved",
            "establishment_state_unresolved",
            "irrigation_delivery_information_required",
            "delivery_quantification_unavailable",
            "water_balance_inputs_incomplete",
        },
        CommissioningPurpose.ADVISORY_ONLY: set(),
    }[purpose]
    relevant_advisories = {
        CommissioningPurpose.LANDSCAPE_UNDERSTANDING: {
            "establishment_state_uncertain",
        },
        CommissioningPurpose.PLANT_DEMAND_ESTIMATION: {
            "commissioning_ready_for_factor_resolution",
            "establishment_state_uncertain",
        },
        CommissioningPurpose.BASELINE_ENVIRONMENTAL_SCALING: {
            "baseline_mode_ready_for_environmental_scaling",
        },
        CommissioningPurpose.DELIVERY_QUANTIFICATION: {
            "establishment_delivery_review_required",
        },
        CommissioningPurpose.WATER_BALANCE: {
            "external_water_balance_evidence_required",
        },
        CommissioningPurpose.ADVISORY_ONLY: set(advisories),
    }[purpose]
    return CommissioningPurposeReadiness(
        purpose=purpose,
        state=PurposeReadinessState.READY if ready else PurposeReadinessState.NOT_READY,
        blocker_codes=tuple(sorted(blockers & relevant_blockers)),
        advisory_codes=tuple(sorted(advisories & relevant_advisories)),
    )


__all__ = [
    "COMMISSIONING_ADMISSION_POLICY_VERSION",
    "COMMISSIONING_ASSESSMENT_SCHEMA_VERSION",
    "CommissioningAssessment",
    "CommissioningAssessmentStatus",
    "CommissioningConfidenceSummary",
    "CommissioningEvidenceAdmission",
    "CommissioningEvidenceKind",
    "CommissioningFollowUpRequirement",
    "CommissioningPurpose",
    "CommissioningPurposeReadiness",
    "EvidenceAdmissionDecision",
    "FollowUpPriority",
    "PurposeReadinessState",
    "assess_commissioning",
]
