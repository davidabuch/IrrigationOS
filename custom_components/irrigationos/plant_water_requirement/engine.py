"""Deterministic Plant Water Requirement assessment engine."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from math import isfinite
from typing import Any

from ..plant_knowledge import (
    CoastalApplicability,
    ConsumerCapability,
    EffectivePlantKnowledgeClaim,
    EvidenceGrade,
    InlandApplicability,
    KnowledgeRange,
    KnowledgeUnit,
    RegionalApplicability,
    RegionalScope,
    ReviewState,
    Season,
)
from .models import (
    PlantWaterRequirementAssessment,
    PlantWaterRequirementConfidence,
    PlantWaterRequirementExplanation,
    PlantWaterRequirementReasonCode,
    PlantWaterRequirementRequest,
    PlantWaterRequirementStatus,
    RangeHandling,
    RegionalApplicabilityResult,
)

_PLANT_FACTOR_PATH = "water.plant_factor"
_REQUIRED_INPUT_COUNT = 2

# Review states are a lifecycle threshold. Rejected and deprecated evidence is
# never admissible, including when either is mistakenly configured as a minimum.
_REVIEW_ADMISSION: dict[ReviewState, frozenset[ReviewState]] = {
    ReviewState.UNREVIEWED: frozenset(
        {ReviewState.UNREVIEWED, ReviewState.REVIEWED, ReviewState.APPROVED}
    ),
    ReviewState.REVIEWED: frozenset({ReviewState.REVIEWED, ReviewState.APPROVED}),
    ReviewState.APPROVED: frozenset({ReviewState.APPROVED}),
    ReviewState.REJECTED: frozenset(),
    ReviewState.DEPRECATED: frozenset(),
}

# Evidence grades are categories, not an enum ordering. Expert consensus is
# admitted at a moderate threshold but remains distinct from high-grade evidence.
_GRADE_ADMISSION: dict[EvidenceGrade, frozenset[EvidenceGrade]] = {
    EvidenceGrade.PROVISIONAL: frozenset(EvidenceGrade),
    EvidenceGrade.LIMITED: frozenset(
        {
            EvidenceGrade.LIMITED,
            EvidenceGrade.MODERATE,
            EvidenceGrade.EXPERT_CONSENSUS,
            EvidenceGrade.HIGH,
        }
    ),
    EvidenceGrade.MODERATE: frozenset(
        {
            EvidenceGrade.MODERATE,
            EvidenceGrade.EXPERT_CONSENSUS,
            EvidenceGrade.HIGH,
        }
    ),
    EvidenceGrade.EXPERT_CONSENSUS: frozenset({EvidenceGrade.EXPERT_CONSENSUS}),
    EvidenceGrade.HIGH: frozenset({EvidenceGrade.HIGH}),
}


def assess_plant_water_requirement(
    request: PlantWaterRequirementRequest,
) -> PlantWaterRequirementAssessment:
    """Assess one immutable resolved evidence snapshot.

    Assessment IDs use ``pwr.assessment.<sha256>`` where the digest is the
    lowercase SHA-256 of the UTF-8 request ID. No clock, randomness, library
    lookup, or external state participates in the result.
    """
    if not isinstance(request, PlantWaterRequirementRequest):
        raise TypeError("request must be a PlantWaterRequirementRequest")

    resolution = request.knowledge_resolution
    if resolution.selected_profile_id is None:
        return _non_success(
            request,
            status=PlantWaterRequirementStatus.UNAVAILABLE,
            reason=PlantWaterRequirementReasonCode.PROFILE_NOT_RESOLVED,
            summary="Plant profile resolution is unavailable.",
            issue="plant profile was not resolved",
        )

    claim = next(
        (
            item
            for item in resolution.effective_claims
            if item.field_path == _PLANT_FACTOR_PATH
        ),
        None,
    )
    if claim is None:
        # RETURN_PARTIAL cannot be represented without a value by the existing
        # assessment contract, so both policy modes produce typed unavailability.
        return _non_success(
            request,
            status=PlantWaterRequirementStatus.UNAVAILABLE,
            reason=PlantWaterRequirementReasonCode.MISSING_WATER_EVIDENCE,
            summary="Plant-factor evidence is unavailable.",
            issue="approved water.plant_factor evidence was not resolved",
        )

    if claim.conflict_unresolved:
        # RETURN_CONFLICT returns the conflict directly; REQUIRE_RESOLUTION reaches
        # the same typed outcome because its required resolution is absent.
        issues = ["water.plant_factor evidence has an unresolved conflict"]
        if claim.claim_resolution is not None:
            issues.extend(claim.claim_resolution.unresolved_issues)
        return _non_success(
            request,
            status=PlantWaterRequirementStatus.CONFLICTING_EVIDENCE,
            reason=PlantWaterRequirementReasonCode.CONFLICTING_WATER_EVIDENCE,
            summary="Plant-factor evidence remains conflicting.",
            issue=None,
            claim=claim,
            issues=tuple(issues),
        )

    admission_issues = _admission_issues(request, claim)
    if admission_issues:
        return _non_success(
            request,
            status=PlantWaterRequirementStatus.INSUFFICIENT_QUALITY,
            reason=PlantWaterRequirementReasonCode.EVIDENCE_BELOW_POLICY,
            summary="Plant-factor evidence does not satisfy the active policy.",
            issue=None,
            claim=claim,
            issues=admission_issues,
        )

    regional_result = _evaluate_regional_applicability(
        claim.regional_applicability,
        request.context.regional_applicability,
    )
    if (
        regional_result is RegionalApplicabilityResult.MISMATCH
        and request.policy.require_regional_match
    ):
        return _non_success(
            request,
            status=PlantWaterRequirementStatus.REGIONAL_MISMATCH,
            reason=PlantWaterRequirementReasonCode.REGIONAL_SCOPE_MISMATCH,
            summary="Plant-factor evidence does not match the evaluation region.",
            issue="water.plant_factor regional applicability conflicts with context",
            claim=claim,
            regional_result=regional_result,
        )

    value, range_preserved = _apply_range_policy(claim, request.policy.range_handling)
    partial = regional_result in {
        RegionalApplicabilityResult.PARTIAL_MATCH,
        RegionalApplicabilityResult.UNAVAILABLE_CONTEXT,
        RegionalApplicabilityResult.MISMATCH,
    }
    status = (
        PlantWaterRequirementStatus.PARTIAL
        if partial
        else PlantWaterRequirementStatus.AVAILABLE
    )
    reason_codes = [
        PlantWaterRequirementReasonCode.REQUIREMENT_PARTIAL
        if partial
        else PlantWaterRequirementReasonCode.REQUIREMENT_AVAILABLE
    ]
    if range_preserved:
        reason_codes.append(PlantWaterRequirementReasonCode.RANGE_PRESERVED)
    known_count = (
        1
        if regional_result
        in {
            RegionalApplicabilityResult.PARTIAL_MATCH,
            RegionalApplicabilityResult.UNAVAILABLE_CONTEXT,
        }
        else 2
    )
    unresolved_issues = (
        (f"regional applicability is {regional_result.value}",) if partial else ()
    )
    return _assessment(
        request,
        selected_profile_id=resolution.selected_profile_id,
        status=status,
        value=value,
        unit=claim.unit,
        regional_result=regional_result,
        confidence=claim.confidence,
        known_required_input_count=known_count,
        claim=claim,
        reason_codes=tuple(reason_codes),
        summary=(
            "Plant-factor evidence is available with incomplete applicability."
            if partial
            else "Plant-factor evidence is available and applicable."
        ),
        unresolved_issues=unresolved_issues,
    )


def _admission_issues(
    request: PlantWaterRequirementRequest,
    claim: EffectivePlantKnowledgeClaim,
) -> tuple[str, ...]:
    issues: list[str] = []
    policy = request.policy
    if _PLANT_FACTOR_PATH not in policy.accepted_claim_paths:
        issues.append("policy does not admit water.plant_factor")
    if ConsumerCapability.WATER_DEMAND not in claim.intended_consumer_capabilities:
        issues.append("claim does not declare the water_demand consumer")
    if claim.unit is not KnowledgeUnit.RATIO:
        issues.append("water.plant_factor must use the ratio unit")
    if not _valid_factor_value(claim.value):
        issues.append("water.plant_factor value is structurally invalid")
    if claim.review_state in {ReviewState.REJECTED, ReviewState.DEPRECATED}:
        issues.append(f"claim review state is {claim.review_state.value}")
    elif claim.review_state not in _REVIEW_ADMISSION[policy.minimum_review_state]:
        issues.append("claim review state is below policy")
    if claim.evidence_grade not in _GRADE_ADMISSION[policy.minimum_evidence_grade]:
        issues.append("claim evidence grade is below policy")
    if claim.confidence < policy.minimum_confidence:
        issues.append("claim confidence is below policy")
    return tuple(sorted(set(issues), key=str.casefold))


def _valid_factor_value(value: object) -> bool:
    if isinstance(value, KnowledgeRange):
        return (
            value.unit is KnowledgeUnit.RATIO
            and value.minimum >= 0
            and value.maximum <= 2
        )
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
        and 0 <= value <= 2
    )


def _evaluate_regional_applicability(
    evidence: RegionalApplicability,
    context: RegionalApplicability,
) -> RegionalApplicabilityResult:
    if evidence.scope is RegionalScope.UNRESTRICTED:
        return RegionalApplicabilityResult.UNRESTRICTED

    outcomes: list[bool | None] = []
    for evidence_values, context_values in (
        (evidence.countries, context.countries),
        (evidence.states_or_provinces, context.states_or_provinces),
        (evidence.climate_zone_ids, context.climate_zone_ids),
        (evidence.wucols_regions, context.wucols_regions),
    ):
        if evidence_values:
            outcomes.append(
                None
                if not context_values
                else bool(set(evidence_values).intersection(context_values))
            )

    if evidence.seasons:
        outcomes.append(
            None
            if not context.seasons
            else (
                Season.YEAR_ROUND in evidence.seasons
                or Season.YEAR_ROUND in context.seasons
                or bool(set(evidence.seasons).intersection(context.seasons))
            )
        )

    if evidence.usda_zone_minimum is not None:
        outcomes.append(
            _range_overlap(
                evidence.usda_zone_minimum,
                evidence.usda_zone_maximum,
                context.usda_zone_minimum,
                context.usda_zone_maximum,
                key=_usda_zone_key,
            )
        )
    for evidence_value, context_value, unspecified in (
        (evidence.coastal, context.coastal, CoastalApplicability.UNSPECIFIED),
        (evidence.inland, context.inland, InlandApplicability.UNSPECIFIED),
    ):
        if evidence_value is not unspecified:
            outcomes.append(
                None if context_value is unspecified else evidence_value is context_value
            )
    if (
        evidence.elevation_minimum_meters is not None
        or evidence.elevation_maximum_meters is not None
    ):
        outcomes.append(
            _range_overlap(
                evidence.elevation_minimum_meters,
                evidence.elevation_maximum_meters,
                context.elevation_minimum_meters,
                context.elevation_maximum_meters,
            )
        )

    if False in outcomes:
        return RegionalApplicabilityResult.MISMATCH
    if outcomes and all(outcome is True for outcome in outcomes):
        return RegionalApplicabilityResult.MATCH
    if True in outcomes:
        return RegionalApplicabilityResult.PARTIAL_MATCH
    return RegionalApplicabilityResult.UNAVAILABLE_CONTEXT


def _range_overlap(
    evidence_minimum: object,
    evidence_maximum: object,
    context_minimum: object,
    context_maximum: object,
    *,
    key: Callable[[object], Any] = lambda value: value,
) -> bool | None:
    if context_minimum is None and context_maximum is None:
        return None
    evidence_low = float("-inf") if evidence_minimum is None else key(evidence_minimum)
    evidence_high = float("inf") if evidence_maximum is None else key(evidence_maximum)
    context_low = float("-inf") if context_minimum is None else key(context_minimum)
    context_high = float("inf") if context_maximum is None else key(context_maximum)
    return context_low <= evidence_high and evidence_low <= context_high


def _usda_zone_key(value: object) -> tuple[int, int]:
    text = str(value)
    return int(text[:-1]), 0 if text[-1] == "a" else 1


def _apply_range_policy(
    claim: EffectivePlantKnowledgeClaim,
    handling: RangeHandling,
) -> tuple[float | KnowledgeRange, bool]:
    value = claim.value
    if not isinstance(value, KnowledgeRange):
        return float(value), False
    if handling is RangeHandling.USE_TYPICAL_IF_PRESENT and value.typical is not None:
        return float(value.typical), False
    return value, True


def _non_success(
    request: PlantWaterRequirementRequest,
    *,
    status: PlantWaterRequirementStatus,
    reason: PlantWaterRequirementReasonCode,
    summary: str,
    issue: str | None,
    claim: EffectivePlantKnowledgeClaim | None = None,
    issues: tuple[str, ...] = (),
    regional_result: RegionalApplicabilityResult = RegionalApplicabilityResult.NOT_EVALUATED,
) -> PlantWaterRequirementAssessment:
    combined_issues = (*issues, *((issue,) if issue is not None else ()))
    return _assessment(
        request,
        selected_profile_id=request.selected_profile_id,
        status=status,
        value=None,
        unit=None,
        regional_result=regional_result,
        confidence=0.0,
        known_required_input_count=0,
        claim=claim,
        reason_codes=(reason,),
        summary=summary,
        unresolved_issues=combined_issues,
    )


def _assessment(
    request: PlantWaterRequirementRequest,
    *,
    selected_profile_id: str | None,
    status: PlantWaterRequirementStatus,
    value: float | KnowledgeRange | None,
    unit: KnowledgeUnit | None,
    regional_result: RegionalApplicabilityResult,
    confidence: float,
    known_required_input_count: int,
    claim: EffectivePlantKnowledgeClaim | None,
    reason_codes: tuple[PlantWaterRequirementReasonCode, ...],
    summary: str,
    unresolved_issues: tuple[str, ...],
) -> PlantWaterRequirementAssessment:
    claim_ids = () if claim is None else (claim.claim_id,)
    source_ids = () if claim is None else claim.source_ids
    claim_resolution_ids = (
        ()
        if claim is None or claim.claim_resolution_id is None
        else (claim.claim_resolution_id,)
    )
    traces = tuple(
        trace
        for trace in request.knowledge_resolution.claim_traces
        if trace.field_path == _PLANT_FACTOR_PATH
    )
    ordered_codes = tuple(sorted(set(reason_codes), key=lambda item: item.value))
    detail = _explanation_detail(
        selected_profile_id,
        claim,
        value,
        regional_result,
        status,
    )
    return PlantWaterRequirementAssessment(
        assessment_id=_assessment_id(request.request_id),
        request_id=request.request_id,
        selected_profile_id=selected_profile_id,
        status=status,
        value=value,
        unit=unit,
        regional_result=regional_result,
        applicable_region=(
            claim.regional_applicability
            if claim is not None
            else request.context.regional_applicability
        ),
        applicable_season=request.context.season,
        confidence=PlantWaterRequirementConfidence(
            confidence=confidence,
            completeness=known_required_input_count / _REQUIRED_INPUT_COUNT,
            known_required_input_count=known_required_input_count,
            required_input_count=_REQUIRED_INPUT_COUNT,
        ),
        claim_ids=claim_ids,
        source_ids=source_ids,
        claim_resolution_ids=claim_resolution_ids,
        claim_traces=traces,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        explanation=PlantWaterRequirementExplanation(
            reason_codes=ordered_codes,
            summary=summary,
            detail=detail,
        ),
        unresolved_issues=tuple(sorted(set(unresolved_issues), key=str.casefold)),
        created_at=request.created_at,
    )


def _assessment_id(request_id: str) -> str:
    digest = sha256(request_id.encode("utf-8")).hexdigest()
    return f"pwr.assessment.{digest}"


def _explanation_detail(
    profile_id: str | None,
    claim: EffectivePlantKnowledgeClaim | None,
    value: float | KnowledgeRange | None,
    regional_result: RegionalApplicabilityResult,
    status: PlantWaterRequirementStatus,
) -> str:
    resolution = claim.claim_resolution if claim is not None else None
    return "; ".join(
        (
            f"profile={profile_id or 'none'}",
            f"claim={claim.claim_id if claim is not None else 'none'}",
            f"value={_format_value(value)}",
            f"sources={','.join(claim.source_ids) if claim is not None else 'none'}",
            f"confidence={claim.confidence if claim is not None else 0.0}",
            f"review_state={claim.review_state.value if claim is not None else 'none'}",
            f"evidence_grade={claim.evidence_grade.value if claim is not None else 'none'}",
            f"claim_version={claim.claim_version if claim is not None else 'none'}",
            f"resolution={resolution.resolution_id if resolution is not None else 'none'}",
            (
                "resolution_method="
                f"{resolution.resolution_method.value if resolution is not None else 'none'}"
            ),
            f"applicability={regional_result.value}",
            f"status={status.value}",
        )
    )


def _format_value(value: float | KnowledgeRange | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, KnowledgeRange):
        return (
            f"range({value.minimum},{value.typical},{value.maximum},"
            f"{value.unit.value})"
        )
    return str(value)
