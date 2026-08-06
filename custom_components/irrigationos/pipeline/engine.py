"""Build synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..controllers import ControllerRegistrySnapshot
from ..landscape import LandscapeProfile
from .models import (
    PIPELINE_ALGORITHM_VERSION,
    PIPELINE_SCHEMA_VERSION,
    PipelineEvaluation,
    PipelineEvaluationStatus,
    PipelineStage,
    PipelineStageEvaluation,
    PipelineStageStatus,
)


def build_pipeline_evaluation(
    snapshot: ControllerRegistrySnapshot,
    landscape: LandscapeProfile,
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

    if configured == 0:
        stages.append(
            PipelineStageEvaluation(
                stage=PipelineStage.KNOWLEDGE,
                status=PipelineStageStatus.BLOCKED,
                reason="No configured irrigation areas are available.",
                blocker_codes=("no_configured_areas",),
            )
        )
    elif complete < configured:
        stages.append(
            PipelineStageEvaluation(
                stage=PipelineStage.KNOWLEDGE,
                status=PipelineStageStatus.PARTIAL,
                reason="One or more landscape profiles are incomplete.",
                blocker_codes=("incomplete_landscape_profiles",),
            )
        )
    else:
        stages.append(
            PipelineStageEvaluation(
                stage=PipelineStage.KNOWLEDGE,
                status=PipelineStageStatus.READY,
                reason="All configured landscape profiles are complete.",
            )
        )

    downstream = (
        PipelineStage.WATER_REQUIREMENT,
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
                reason=(
                    "The Home Assistant integration does not yet collect all scientific "
                    "inputs required for this stage."
                ),
                blocker_codes=("scientific_inputs_not_integrated",),
            )
        )

    current_stage = next(
        (item.stage for item in stages if item.status is not PipelineStageStatus.READY),
        PipelineStage.RUNTIME_MONITORING,
    )
    if configured == 0:
        status = PipelineEvaluationStatus.BLOCKED
    elif complete < configured:
        status = PipelineEvaluationStatus.PARTIAL
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
        stages=tuple(stages),
        configured_area_count=configured,
        complete_profile_count=complete,
    )
