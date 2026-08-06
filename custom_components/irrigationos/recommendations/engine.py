"""Deterministic, advisory-only recommendation engine."""

from __future__ import annotations

from ..plant_health import PlantHealthClassification, PlantHealthStatus
from ..plant_stress import (
    PlantStressDimension,
    PlantStressRiskClassification,
    PlantStressRiskStatus,
)
from .models import (
    Recommendation,
    RecommendationAssessment,
    RecommendationCategory,
    RecommendationExplanation,
    RecommendationPriority,
    RecommendationRequest,
    RecommendationSafetyFlag,
    RecommendationStatus,
)

_HIGH_RISKS = {
    PlantStressRiskClassification.HIGH,
    PlantStressRiskClassification.VERY_HIGH,
}


def _recommendation(
    request: RecommendationRequest,
    category: RecommendationCategory,
    priority: RecommendationPriority,
    confidence: float,
    reason_codes: tuple[str, ...],
    summary: str,
    *,
    preconditions: tuple[str, ...] = (),
    extra_safety_flags: tuple[RecommendationSafetyFlag, ...] = (),
) -> Recommendation:
    safety_flags = tuple(
        sorted(
            {
                RecommendationSafetyFlag.ADVISORY_ONLY,
                RecommendationSafetyFlag.NO_AUTOMATIC_EXECUTION,
                *extra_safety_flags,
            },
            key=lambda item: item.value,
        )
    )
    return Recommendation(
        recommendation_id=f"recommendation:{request.request_id}:{category.value}",
        category=category,
        priority=priority,
        confidence=confidence,
        supporting_assessment_ids=tuple(
            sorted(
                {
                    request.aggregate_stress.assessment_id,
                    request.plant_health.assessment_id,
                    request.water_requirement.assessment_id,
                }
            )
        ),
        preconditions=tuple(sorted(preconditions)),
        safety_flags=safety_flags,
        explanation=RecommendationExplanation(
            reason_codes=tuple(sorted(reason_codes)),
            summary=summary,
        ),
    )


def assess_recommendations(request: RecommendationRequest) -> RecommendationAssessment:
    """Create conservative recommendations without planning or execution authority."""
    recommendations: list[Recommendation] = []
    unresolved: set[str] = set()

    health = request.plant_health
    stress = request.aggregate_stress
    confidence_candidates = [
        health.confidence.confidence,
        stress.confidence.confidence,
        request.water_requirement.confidence.confidence,
    ]
    confidence = min(confidence_candidates)

    if health.status not in {PlantHealthStatus.AVAILABLE, PlantHealthStatus.PARTIAL}:
        recommendations.append(
            _recommendation(
                request,
                RecommendationCategory.INSPECT,
                RecommendationPriority.MODERATE,
                confidence,
                ("direct_health_evidence_insufficient", "inspection_needed"),
                "Inspect the plant because direct health evidence is insufficient.",
                preconditions=("record direct plant health observations",),
                extra_safety_flags=(RecommendationSafetyFlag.VERIFY_SITE_CONDITIONS,),
            )
        )
        unresolved.add("direct plant health evidence is insufficient")
    elif health.classification is PlantHealthClassification.CRITICAL:
        recommendations.append(
            _recommendation(
                request,
                RecommendationCategory.SEEK_EXPERT_REVIEW,
                RecommendationPriority.URGENT,
                confidence,
                ("critical_health_observed", "expert_review_recommended"),
                "Seek expert review because direct evidence supports critical plant health.",
                extra_safety_flags=(
                    RecommendationSafetyFlag.EXPERT_REVIEW_RECOMMENDED,
                    RecommendationSafetyFlag.VERIFY_SITE_CONDITIONS,
                ),
            )
        )
    elif health.classification is PlantHealthClassification.POOR:
        recommendations.append(
            _recommendation(
                request,
                RecommendationCategory.SEEK_EXPERT_REVIEW,
                RecommendationPriority.HIGH,
                confidence,
                ("expert_review_recommended", "poor_health_observed"),
                "Seek expert review because direct evidence supports poor plant health.",
                extra_safety_flags=(RecommendationSafetyFlag.EXPERT_REVIEW_RECOMMENDED,),
            )
        )
    elif health.classification is PlantHealthClassification.FAIR:
        recommendations.append(
            _recommendation(
                request,
                RecommendationCategory.INSPECT,
                RecommendationPriority.HIGH,
                confidence,
                ("fair_health_observed", "inspection_needed"),
                "Inspect the plant to identify the cause of its fair health classification.",
                preconditions=("review direct health indicators",),
                extra_safety_flags=(RecommendationSafetyFlag.VERIFY_SITE_CONDITIONS,),
            )
        )

    for dimension in stress.dimensions:
        if dimension.status not in {
            PlantStressRiskStatus.AVAILABLE,
            PlantStressRiskStatus.PARTIAL,
        }:
            unresolved.add(f"{dimension.dimension.value} stress evidence is unavailable")
            continue
        if dimension.risk not in _HIGH_RISKS:
            continue
        priority = (
            RecommendationPriority.URGENT
            if dimension.risk is PlantStressRiskClassification.VERY_HIGH
            else RecommendationPriority.HIGH
        )
        if dimension.dimension is PlantStressDimension.WATER_DEFICIT:
            recommendations.append(
                _recommendation(
                    request,
                    RecommendationCategory.ADJUST_IRRIGATION,
                    priority,
                    min(confidence, dimension.confidence.confidence),
                    ("high_water_deficit_risk", "verify_irrigation_conditions"),
                    "Review irrigation because water-deficit stress risk is elevated.",
                    preconditions=(
                        "confirm soil and irrigation delivery conditions",
                        "review current watering restrictions",
                    ),
                    extra_safety_flags=(RecommendationSafetyFlag.VERIFY_SITE_CONDITIONS,),
                )
            )
        elif dimension.dimension is PlantStressDimension.HEAT:
            recommendations.append(
                _recommendation(
                    request,
                    RecommendationCategory.PROTECT_FROM_HEAT,
                    priority,
                    min(confidence, dimension.confidence.confidence),
                    ("high_heat_risk", "heat_protection_consideration"),
                    "Consider temporary heat protection because heat-stress risk is elevated.",
                    preconditions=("verify local heat exposure",),
                )
            )
        elif dimension.dimension is PlantStressDimension.FREEZE:
            recommendations.append(
                _recommendation(
                    request,
                    RecommendationCategory.PROTECT_FROM_FREEZE,
                    priority,
                    min(confidence, dimension.confidence.confidence),
                    ("freeze_protection_consideration", "high_freeze_risk"),
                    "Consider freeze protection because freeze-stress risk is elevated.",
                    preconditions=("verify local minimum-temperature exposure",),
                )
            )

    if not recommendations:
        if confidence < request.policy.minimum_confidence:
            recommendations.append(
                _recommendation(
                    request,
                    RecommendationCategory.MONITOR,
                    RecommendationPriority.LOW,
                    confidence,
                    ("confidence_below_policy", "monitor_pending_better_evidence"),
                    "Monitor conditions while gathering higher-confidence evidence.",
                )
            )
            unresolved.add("recommendation confidence is below policy")
        else:
            recommendations.append(
                _recommendation(
                    request,
                    RecommendationCategory.NO_ACTION,
                    RecommendationPriority.LOW,
                    confidence,
                    ("health_not_concerning", "no_high_stress_risk"),
                    "No immediate advisory action is supported by the available evidence.",
                )
            )

    deduplicated = {item.recommendation_id: item for item in recommendations}
    ordered = tuple(deduplicated[key] for key in sorted(deduplicated))
    status = RecommendationStatus.PARTIAL if unresolved else RecommendationStatus.AVAILABLE
    return RecommendationAssessment(
        assessment_id=f"recommendation-assessment:{request.request_id}",
        request_id=request.request_id,
        status=status,
        recommendations=ordered,
        plant_health_assessment_id=health.assessment_id,
        aggregate_stress_assessment_id=stress.assessment_id,
        water_requirement_assessment_id=request.water_requirement.assessment_id,
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        unresolved_issues=tuple(sorted(unresolved)),
        created_at=request.created_at,
    )
