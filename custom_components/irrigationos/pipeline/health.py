"""Plant Health integration for synchronized pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..plant_health import (
    PlantHealthPolicy,
    PlantHealthRequest,
    PlantHealthStatus,
    assess_plant_health,
)
from ..scientific_inputs import ScientificInputSnapshot
from .models import AreaPlantHealthEvaluation, AreaPlantStressEvaluation

_HEALTH_POLICY = PlantHealthPolicy(
    policy_id="pipeline.direct-health-evidence",
    policy_version="1.0.0",
)


def build_area_plant_health(
    scientific_inputs: ScientificInputSnapshot,
    plant_stress: tuple[AreaPlantStressEvaluation, ...],
    *,
    evaluated_at: datetime,
) -> tuple[AreaPlantHealthEvaluation, ...]:
    """Assess Plant Health without treating stress as diagnostic evidence."""
    knowledge_by_area = {item.area_id: item for item in scientific_inputs.area_knowledge}
    results: list[AreaPlantHealthEvaluation] = []

    for stress_result in plant_stress:
        assessment = stress_result.assessment
        if assessment is None:
            results.append(
                AreaPlantHealthEvaluation(
                    area_id=stress_result.area_id,
                    assessment=None,
                    blocker_codes=("plant_stress_unavailable",),
                )
            )
            continue

        knowledge = knowledge_by_area.get(stress_result.area_id)
        selected_profile_id = None if knowledge is None else knowledge.selected_profile_id
        health = assess_plant_health(
            PlantHealthRequest(
                request_id=f"pipeline-health:{stress_result.area_id}",
                plant_instance_id=stress_result.area_id,
                selected_profile_id=selected_profile_id,
                direct_evidence=(),
                aggregate_stress=assessment,
                policy=_HEALTH_POLICY,
                created_at=evaluated_at,
            )
        )
        blockers: tuple[str, ...] = ()
        if health.status is PlantHealthStatus.INSUFFICIENT_DIRECT_EVIDENCE:
            blockers = ("plant_health_direct_evidence_required",)
        elif health.status not in {PlantHealthStatus.AVAILABLE, PlantHealthStatus.PARTIAL}:
            blockers = (f"plant_health_{health.status.value}",)
        results.append(
            AreaPlantHealthEvaluation(
                area_id=stress_result.area_id,
                assessment=health,
                blocker_codes=blockers,
            )
        )

    return tuple(results)
