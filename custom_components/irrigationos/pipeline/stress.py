"""Compose existing plant-stress engines into the Home Assistant pipeline."""

from __future__ import annotations

from datetime import datetime

from ..environment import EnvironmentalIntelligenceReport
from ..plant_stress import (
    MissingEvidenceBehavior,
    OverallRiskAggregation,
    PartialEvidenceBehavior,
    PlantStressDimension,
    PlantStressRiskContext,
    PlantStressRiskPolicy,
    PlantStressRiskRequest,
    PlantStressRiskStatus,
    aggregate_plant_stress,
    assess_freeze_stress,
    assess_heat_stress,
    assess_water_deficit_stress,
)
from ..scientific_inputs import ScientificInputSnapshot
from .models import AreaPlantStressEvaluation, AreaWaterRequirementEvaluation

_POLICY = PlantStressRiskPolicy(
    policy_id="irrigationos-stress-policy",
    policy_version="1.0.0",
    enabled_dimensions=(
        PlantStressDimension.FREEZE,
        PlantStressDimension.HEAT,
        PlantStressDimension.WATER_DEFICIT,
    ),
    minimum_confidence=0.75,
    partial_evidence_behavior=PartialEvidenceBehavior.RETURN_PARTIAL,
    missing_evidence_behavior=MissingEvidenceBehavior.RETURN_SPECIFIC_STATUS,
    overall_risk_aggregation=OverallRiskAggregation.HIGHEST_AVAILABLE,
)
_USABLE = {PlantStressRiskStatus.AVAILABLE, PlantStressRiskStatus.PARTIAL}


def build_area_plant_stress(
    scientific_inputs: ScientificInputSnapshot,
    water_requirements: tuple[AreaWaterRequirementEvaluation, ...],
    environmental_report: EnvironmentalIntelligenceReport | None,
    *,
    evaluated_at: datetime,
) -> tuple[AreaPlantStressEvaluation, ...]:
    """Run all independent stress dimensions once per eligible irrigation area."""
    knowledge_by_area = {item.area_id: item for item in scientific_inputs.area_knowledge}
    results: list[AreaPlantStressEvaluation] = []

    for water in water_requirements:
        blockers: list[str] = []
        knowledge = knowledge_by_area.get(water.area_id)
        resolution = None if knowledge is None else knowledge.knowledge_resolution
        if water.assessment is None:
            blockers.append("water_requirement_unavailable")
        if resolution is None or resolution.selected_profile_id is None:
            blockers.append("plant_knowledge_profile_unresolved")
        if water.season is None:
            blockers.append("season_unavailable")
        if environmental_report is None:
            blockers.append("environmental_intelligence_unavailable")

        if blockers:
            results.append(
                AreaPlantStressEvaluation(
                    area_id=water.area_id,
                    assessment=None,
                    blocker_codes=tuple(dict.fromkeys(blockers)),
                )
            )
            continue

        assert water.assessment is not None
        assert resolution is not None
        assert water.season is not None
        assert environmental_report is not None
        request = PlantStressRiskRequest(
            request_id=f"plant_stress.request.{_safe_id(water.area_id)}",
            knowledge_resolution=resolution,
            water_requirement_assessment=water.assessment,
            environmental_report=environmental_report,
            context=PlantStressRiskContext(
                location_id=environmental_report.analysis_window.location_id,
                analysis_window_id=environmental_report.analysis_window.window_id,
                regional_applicability=water.assessment.applicable_region,
                season=water.season,
            ),
            policy=_POLICY,
            created_at=evaluated_at,
        )
        dimensions = (
            assess_freeze_stress(request).dimensions[0],
            assess_heat_stress(request).dimensions[0],
            assess_water_deficit_stress(request).dimensions[0],
        )
        assessment = aggregate_plant_stress(request, dimensions)
        for dimension in assessment.dimensions:
            if dimension.status not in _USABLE:
                blockers.append(f"stress_{dimension.dimension.value}_{dimension.status.value}")
            elif dimension.status is PlantStressRiskStatus.PARTIAL:
                blockers.append(f"stress_{dimension.dimension.value}_partial")
        results.append(
            AreaPlantStressEvaluation(
                area_id=water.area_id,
                assessment=assessment,
                blocker_codes=tuple(blockers),
            )
        )
    return tuple(results)


def _safe_id(value: str) -> str:
    return "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in value
    )
