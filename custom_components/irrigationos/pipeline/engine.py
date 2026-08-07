"""Build synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..controllers import ControllerRegistrySnapshot
from ..landscape import LandscapeProfile
from ..plant_water_requirement import PlantWaterRequirementStatus
from ..scientific_inputs import ScientificInputSnapshot, ScientificInputStatus
from .models import (
    PIPELINE_ALGORITHM_VERSION,
    PIPELINE_SCHEMA_VERSION,
    AreaWaterRequirementEvaluation,
    PipelineEvaluation,
    PipelineEvaluationStatus,
    PipelineStage,
    PipelineStageEvaluation,
    PipelineStageStatus,
)
from .water_requirement import build_area_water_requirements


def build_pipeline_evaluation(
    snapshot: ControllerRegistrySnapshot,
    landscape: LandscapeProfile,
    scientific_inputs: ScientificInputSnapshot,
    *,
    evaluated_at: datetime,
) -> PipelineEvaluation:
    """Build one immutable, truthful pipeline snapshot for Home Assistant."""
    configured = len(snapshot.configured_areas)
    complete = landscape.complete_area_count
    stages: list[PipelineStageEvaluation] = [
        PipelineStageEvaluation(
            stage=PipelineStage.OBSERVATIONS,
            status=PipelineStageStatus.READY,
            reason="Controller observations were refreshed successfully.",
        )
    ]

    knowledge_stage = _knowledge_stage(configured, complete, scientific_inputs)
    stages.append(knowledge_stage)

    water_requirements = build_area_water_requirements(
        landscape,
        scientific_inputs,
        evaluated_at=evaluated_at,
    )
    water_stage = _water_requirement_stage(
        configured,
        knowledge_stage,
        water_requirements,
    )
    stages.append(water_stage)

    downstream = (
        PipelineStage.STRESS,
        PipelineStage.HEALTH,
        PipelineStage.RECOMMENDATIONS,
        PipelineStage.PLANNING,
        PipelineStage.SCHEDULING,
        PipelineStage.EXECUTION,
        PipelineStage.RUNTIME_MONITORING,
    )
    for stage in downstream:
        stages.append(
            PipelineStageEvaluation(
                stage=stage,
                status=PipelineStageStatus.BLOCKED,
                reason="An upstream scientific stage is not yet integrated with Home Assistant.",
                blocker_codes=("upstream_scientific_stage_not_integrated",),
            )
        )

    current_stage = next(
        (item.stage for item in stages if item.status is not PipelineStageStatus.READY),
        PipelineStage.RUNTIME_MONITORING,
    )
    if configured == 0:
        status = PipelineEvaluationStatus.BLOCKED
    else:
        status = PipelineEvaluationStatus.PARTIAL

    return PipelineEvaluation(
        schema_version=PIPELINE_SCHEMA_VERSION,
        algorithm_version=PIPELINE_ALGORITHM_VERSION,
        evaluated_at=evaluated_at,
        status=status,
        current_stage=current_stage,
        observation_snapshot=snapshot,
        landscape_profile=landscape,
        scientific_inputs=scientific_inputs,
        stages=tuple(stages),
        configured_area_count=configured,
        complete_profile_count=complete,
        water_requirements=water_requirements,
    )


def _knowledge_stage(
    configured: int,
    complete: int,
    scientific_inputs: ScientificInputSnapshot,
) -> PipelineStageEvaluation:
    if configured == 0:
        return PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.BLOCKED,
            reason="No configured irrigation areas are available.",
            blocker_codes=("no_configured_areas",),
        )
    if complete < configured:
        return PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.PARTIAL,
            reason="Landscape profiles or scientific inputs are incomplete.",
            blocker_codes=tuple(
                dict.fromkeys(
                    ("incomplete_landscape_profiles", *scientific_inputs.blocker_codes)
                )
            ),
        )
    if scientific_inputs.status is ScientificInputStatus.READY:
        return PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.READY,
            reason="Landscape profiles and curated plant knowledge are resolved.",
        )
    if scientific_inputs.status is ScientificInputStatus.PARTIAL:
        return PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.PARTIAL,
            reason="Scientific inputs are available with unresolved gaps.",
            blocker_codes=scientific_inputs.blocker_codes,
        )
    return PipelineStageEvaluation(
        stage=PipelineStage.KNOWLEDGE,
        status=PipelineStageStatus.BLOCKED,
        reason="Required scientific inputs are unavailable.",
        blocker_codes=scientific_inputs.blocker_codes,
    )


def _water_requirement_stage(
    configured: int,
    knowledge_stage: PipelineStageEvaluation,
    water_requirements: tuple[AreaWaterRequirementEvaluation, ...],
) -> PipelineStageEvaluation:
    if configured == 0:
        return PipelineStageEvaluation(
            stage=PipelineStage.WATER_REQUIREMENT,
            status=PipelineStageStatus.BLOCKED,
            reason="No configured irrigation areas are available.",
            blocker_codes=("no_configured_areas",),
        )

    blocker_codes = tuple(
        dict.fromkeys(code for item in water_requirements for code in item.blocker_codes)
    )
    usable = tuple(
        item
        for item in water_requirements
        if item.assessment is not None
        and item.assessment.status
        in {
            PlantWaterRequirementStatus.AVAILABLE,
            PlantWaterRequirementStatus.PARTIAL,
        }
    )
    fully_available = tuple(
        item
        for item in water_requirements
        if item.assessment is not None
        and item.assessment.status is PlantWaterRequirementStatus.AVAILABLE
    )

    if len(fully_available) == configured:
        return PipelineStageEvaluation(
            stage=PipelineStage.WATER_REQUIREMENT,
            status=PipelineStageStatus.READY,
            reason="Plant Water Requirement was assessed for every configured area.",
        )
    if usable:
        return PipelineStageEvaluation(
            stage=PipelineStage.WATER_REQUIREMENT,
            status=PipelineStageStatus.PARTIAL,
            reason="Plant Water Requirement is available with incomplete context or coverage.",
            blocker_codes=blocker_codes,
        )

    inherited = knowledge_stage.blocker_codes
    return PipelineStageEvaluation(
        stage=PipelineStage.WATER_REQUIREMENT,
        status=PipelineStageStatus.BLOCKED,
        reason="Plant Water Requirement could not produce an evidence-backed assessment.",
        blocker_codes=tuple(
            dict.fromkeys((*blocker_codes, *inherited, "plant_water_requirement_unavailable"))
        ),
    )
