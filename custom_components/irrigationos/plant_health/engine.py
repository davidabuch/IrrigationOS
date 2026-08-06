"""Deterministic evidence-gated plant health engine."""

from __future__ import annotations

from .models import (
    PlantHealthAssessment,
    PlantHealthClassification,
    PlantHealthConfidence,
    PlantHealthExplanation,
    PlantHealthIndicator,
    PlantHealthRequest,
    PlantHealthSeverity,
    PlantHealthStatus,
)

_SEVERITY_RANK = {
    PlantHealthSeverity.NONE: 0,
    PlantHealthSeverity.MILD: 1,
    PlantHealthSeverity.MODERATE: 2,
    PlantHealthSeverity.SEVERE: 3,
    PlantHealthSeverity.CRITICAL: 4,
}

_NEGATIVE_INDICATORS = {
    PlantHealthIndicator.WILTING,
    PlantHealthIndicator.DISCOLORATION,
    PlantHealthIndicator.DEFOLIATION,
    PlantHealthIndicator.TISSUE_DAMAGE,
    PlantHealthIndicator.DISEASE_SIGNS,
    PlantHealthIndicator.PEST_SIGNS,
    PlantHealthIndicator.NUTRIENT_DEFICIENCY_SIGNS,
}


def assess_plant_health(request: PlantHealthRequest) -> PlantHealthAssessment:
    """Assess health only from admitted direct evidence; stress remains context."""
    admitted = tuple(
        item
        for item in request.direct_evidence
        if item.confidence >= request.policy.minimum_confidence
    )
    required = request.policy.minimum_direct_evidence_count
    admitted_count = min(len(admitted), required)
    completeness = admitted_count / required
    confidence_value = min((item.confidence for item in admitted), default=0.0)
    confidence = PlantHealthConfidence(
        confidence=confidence_value,
        completeness=completeness,
        admitted_evidence_count=admitted_count,
        required_evidence_count=required,
    )
    assessment_id = f"plant-health:{request.request_id}"

    if len(admitted) < required:
        return PlantHealthAssessment(
            assessment_id=assessment_id,
            request_id=request.request_id,
            plant_instance_id=request.plant_instance_id,
            selected_profile_id=request.selected_profile_id,
            status=PlantHealthStatus.INSUFFICIENT_DIRECT_EVIDENCE,
            classification=PlantHealthClassification.UNKNOWN,
            confidence=confidence,
            evidence_ids=tuple(sorted(item.evidence_id for item in admitted)),
            source_ids=tuple(sorted({item.source_id for item in admitted})),
            aggregate_stress_assessment_id=request.aggregate_stress.assessment_id,
            policy_id=request.policy.policy_id,
            policy_version=request.policy.policy_version,
            algorithm_version=request.algorithm_version,
            explanation=PlantHealthExplanation(
                reason_codes=("direct_evidence_insufficient", "stress_context_not_diagnostic"),
                summary="Direct evidence is insufficient to classify plant health.",
            ),
            unresolved_issues=("additional direct health evidence required",),
            created_at=request.created_at,
        )

    positive_vigor = any(
        item.indicator is PlantHealthIndicator.VIGOR
        and item.severity in {PlantHealthSeverity.NONE, PlantHealthSeverity.MILD}
        for item in admitted
    )
    recovery = any(
        item.indicator is PlantHealthIndicator.RECOVERY
        and item.severity in {PlantHealthSeverity.NONE, PlantHealthSeverity.MILD}
        for item in admitted
    )
    negative = tuple(item for item in admitted if item.indicator in _NEGATIVE_INDICATORS)
    worst = max((_SEVERITY_RANK[item.severity] for item in negative), default=0)

    if worst >= 4:
        classification = PlantHealthClassification.CRITICAL
    elif worst == 3:
        classification = PlantHealthClassification.POOR
    elif worst == 2:
        classification = PlantHealthClassification.FAIR
    elif worst == 1:
        classification = PlantHealthClassification.GOOD
    elif positive_vigor and recovery:
        classification = PlantHealthClassification.EXCELLENT
    else:
        classification = PlantHealthClassification.GOOD

    reason_codes = ["direct_evidence_classified", "stress_context_preserved"]
    if negative:
        reason_codes.append("negative_indicator_observed")
    if positive_vigor:
        reason_codes.append("vigor_observed")
    if recovery:
        reason_codes.append("recovery_observed")

    return PlantHealthAssessment(
        assessment_id=assessment_id,
        request_id=request.request_id,
        plant_instance_id=request.plant_instance_id,
        selected_profile_id=request.selected_profile_id,
        status=PlantHealthStatus.AVAILABLE,
        classification=classification,
        confidence=confidence,
        evidence_ids=tuple(sorted(item.evidence_id for item in admitted)),
        source_ids=tuple(sorted({item.source_id for item in admitted})),
        aggregate_stress_assessment_id=request.aggregate_stress.assessment_id,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        explanation=PlantHealthExplanation(
            reason_codes=tuple(sorted(reason_codes)),
            summary=(
                "Direct evidence supports a "
                f"{classification.value} plant health classification."
            ),
        ),
        unresolved_issues=(),
        created_at=request.created_at,
    )
