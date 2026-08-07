"""Recommendation integration for synchronized pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..recommendations import (
    RecommendationPolicy,
    RecommendationRequest,
    RecommendationStatus,
    assess_recommendations,
)
from .models import (
    AreaPlantHealthEvaluation,
    AreaPlantStressEvaluation,
    AreaRecommendationEvaluation,
    AreaWaterRequirementEvaluation,
)

_RECOMMENDATION_POLICY = RecommendationPolicy(
    policy_id="pipeline.conservative-advisory",
    policy_version="1.0.0",
)


def build_area_recommendations(
    water_requirements: tuple[AreaWaterRequirementEvaluation, ...],
    plant_stress: tuple[AreaPlantStressEvaluation, ...],
    plant_health: tuple[AreaPlantHealthEvaluation, ...],
    *,
    evaluated_at: datetime,
) -> tuple[AreaRecommendationEvaluation, ...]:
    """Compose advisory recommendations from accepted upstream assessments."""
    water_by_area = {item.area_id: item for item in water_requirements}
    stress_by_area = {item.area_id: item for item in plant_stress}
    health_by_area = {item.area_id: item for item in plant_health}
    area_ids = tuple(sorted(set(water_by_area) | set(stress_by_area) | set(health_by_area)))
    results: list[AreaRecommendationEvaluation] = []

    for area_id in area_ids:
        water = water_by_area.get(area_id)
        stress = stress_by_area.get(area_id)
        health = health_by_area.get(area_id)
        missing: list[str] = []
        if water is None or water.assessment is None:
            missing.append("plant_water_requirement_unavailable")
        if stress is None or stress.assessment is None:
            missing.append("plant_stress_unavailable")
        if health is None or health.assessment is None:
            missing.append("plant_health_unavailable")

        if missing:
            results.append(
                AreaRecommendationEvaluation(
                    area_id=area_id,
                    assessment=None,
                    blocker_codes=tuple(sorted(set(missing))),
                )
            )
            continue

        assert water is not None and water.assessment is not None
        assert stress is not None and stress.assessment is not None
        assert health is not None and health.assessment is not None

        assessment = assess_recommendations(
            RecommendationRequest(
                request_id=f"pipeline-recommendation:{area_id}",
                plant_health=health.assessment,
                aggregate_stress=stress.assessment,
                water_requirement=water.assessment,
                policy=_RECOMMENDATION_POLICY,
                created_at=evaluated_at,
            )
        )
        upstream_blockers = tuple(
            dict.fromkeys(
                (
                    *water.blocker_codes,
                    *stress.blocker_codes,
                    *health.blocker_codes,
                )
            )
        )
        blockers = upstream_blockers
        if assessment.status is RecommendationStatus.PARTIAL:
            blockers = tuple(
                dict.fromkeys((*upstream_blockers, "recommendation_evidence_partial"))
            )
        elif assessment.status is RecommendationStatus.INSUFFICIENT_EVIDENCE:
            blockers = tuple(
                dict.fromkeys(
                    (*upstream_blockers, "recommendation_evidence_insufficient")
                )
            )
        results.append(
            AreaRecommendationEvaluation(
                area_id=area_id,
                assessment=assessment,
                blocker_codes=blockers,
            )
        )

    return tuple(results)
