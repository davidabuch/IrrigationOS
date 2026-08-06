"""Build synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..controllers import ControllerRegistrySnapshot
from ..landscape import LandscapeProfile
from ..scientific_inputs import ScientificInputSnapshot, ScientificInputStatus
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

    if configured == 0:
        pass
    elif complete < configured:
        stages[1] = PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.PARTIAL,
            reason="Landscape profiles or scientific inputs are incomplete.",
            blocker_codes=tuple(
                dict.fromkeys(
                    ("incomplete_landscape_profiles", *scientific_inputs.blocker_codes)
                )
            ),
        )
    elif scientific_inputs.status is ScientificInputStatus.READY:
        stages[1] = PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.READY,
            reason="Landscape profiles and curated plant knowledge are resolved.",
        )
    elif scientific_inputs.status is ScientificInputStatus.PARTIAL:
        stages[1] = PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.PARTIAL,
            reason="Scientific inputs are available with unresolved gaps.",
            blocker_codes=scientific_inputs.blocker_codes,
        )
    else:
        stages[1] = PipelineStageEvaluation(
            stage=PipelineStage.KNOWLEDGE,
            status=PipelineStageStatus.BLOCKED,
            reason="Required scientific inputs are unavailable.",
            blocker_codes=scientific_inputs.blocker_codes,
        )

    stages.append(
        PipelineStageEvaluation(
            stage=PipelineStage.WATER_REQUIREMENT,
            status=PipelineStageStatus.BLOCKED,
            reason=(
                "Current weather and plant knowledge are integrated, but seasonal and "
                "establishment context are not yet configured."
            ),
            blocker_codes=("plant_water_context_not_configured",),
        )
    )
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
                reason="An upstream scientific assessment is not yet available.",
                blocker_codes=("upstream_scientific_stage_blocked",),
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
        scientific_inputs=scientific_inputs,
        stages=tuple(stages),
        configured_area_count=configured,
        complete_profile_count=complete,
    )
