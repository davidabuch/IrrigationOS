"""Build synchronized Home Assistant pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..controllers import ControllerRegistrySnapshot
from ..landscape import LandscapeProfile
from ..planning import PlanStatus
from ..plant_health import PlantHealthStatus
from ..plant_stress import PlantStressRiskStatus
from ..plant_water_requirement import PlantWaterRequirementStatus
from ..recommendations import RecommendationStatus
from ..scientific_inputs import ScientificInputSnapshot, ScientificInputStatus
from .environmental_intelligence import build_environmental_report
from .health import build_area_plant_health
from .models import (
    PIPELINE_ALGORITHM_VERSION,
    PIPELINE_SCHEMA_VERSION,
    AreaPlanningEvaluation,
    AreaPlantHealthEvaluation,
    AreaPlantStressEvaluation,
    AreaRecommendationEvaluation,
    AreaWaterRequirementEvaluation,
    PipelineEvaluation,
    PipelineEvaluationStatus,
    PipelineStage,
    PipelineStageEvaluation,
    PipelineStageStatus,
)
from .planning import build_area_plans
from .recommendation import build_area_recommendations
from .stress import build_area_plant_stress
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

    environmental_report = build_environmental_report(
        scientific_inputs, evaluated_at=evaluated_at
    )
    plant_stress = build_area_plant_stress(
        scientific_inputs,
        water_requirements,
        environmental_report,
        evaluated_at=evaluated_at,
    )
    stress_stage = _stress_stage(configured, water_stage, plant_stress)
    stages.append(stress_stage)

    plant_health = build_area_plant_health(
        scientific_inputs, plant_stress, evaluated_at=evaluated_at
    )
    health_stage = _health_stage(configured, stress_stage, plant_health)
    stages.append(health_stage)

    recommendations = build_area_recommendations(
        water_requirements,
        plant_stress,
        plant_health,
        evaluated_at=evaluated_at,
    )
    recommendation_stage = _recommendation_stage(
        configured, health_stage, recommendations
    )
    stages.append(recommendation_stage)

    planning = build_area_plans(recommendations, evaluated_at=evaluated_at)
    planning_stage = _planning_stage(configured, recommendation_stage, planning)
    stages.append(planning_stage)

    downstream = (
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
        environmental_report=environmental_report,
        plant_stress=plant_stress,
        plant_health=plant_health,
        recommendations=recommendations,
        planning=planning,
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


def _stress_stage(
    configured: int,
    water_stage: PipelineStageEvaluation,
    plant_stress: tuple[AreaPlantStressEvaluation, ...],
) -> PipelineStageEvaluation:
    if configured == 0:
        return PipelineStageEvaluation(
            stage=PipelineStage.STRESS,
            status=PipelineStageStatus.BLOCKED,
            reason="No configured irrigation areas are available.",
            blocker_codes=("no_configured_areas",),
        )

    blockers = tuple(
        dict.fromkeys(code for item in plant_stress for code in item.blocker_codes)
    )
    assessments = tuple(item.assessment for item in plant_stress if item.assessment is not None)
    fully_available = tuple(
        assessment
        for assessment in assessments
        if assessment.overall_status is PlantStressRiskStatus.AVAILABLE
    )
    usable = tuple(
        assessment
        for assessment in assessments
        if assessment.overall_status
        in {PlantStressRiskStatus.AVAILABLE, PlantStressRiskStatus.PARTIAL}
    )
    if len(fully_available) == configured:
        return PipelineStageEvaluation(
            stage=PipelineStage.STRESS,
            status=PipelineStageStatus.READY,
            reason="Plant Stress was assessed for every configured area.",
        )
    if usable:
        return PipelineStageEvaluation(
            stage=PipelineStage.STRESS,
            status=PipelineStageStatus.PARTIAL,
            reason="Plant Stress is available with incomplete environmental or plant evidence.",
            blocker_codes=blockers,
        )
    return PipelineStageEvaluation(
        stage=PipelineStage.STRESS,
        status=PipelineStageStatus.BLOCKED,
        reason="Plant Stress could not produce an evidence-backed assessment.",
        blocker_codes=tuple(
            dict.fromkeys((*blockers, *water_stage.blocker_codes, "plant_stress_unavailable"))
        ),
    )


def _health_stage(
    configured: int,
    stress_stage: PipelineStageEvaluation,
    plant_health: tuple[AreaPlantHealthEvaluation, ...],
) -> PipelineStageEvaluation:
    if configured == 0:
        return PipelineStageEvaluation(
            stage=PipelineStage.HEALTH,
            status=PipelineStageStatus.BLOCKED,
            reason="No configured irrigation areas are available.",
            blocker_codes=("no_configured_areas",),
        )

    blockers = tuple(
        dict.fromkeys(code for item in plant_health for code in item.blocker_codes)
    )
    assessments = tuple(item.assessment for item in plant_health if item.assessment is not None)
    fully_available = tuple(
        assessment
        for assessment in assessments
        if assessment.status is PlantHealthStatus.AVAILABLE
    )
    usable = tuple(
        assessment
        for assessment in assessments
        if assessment.status in {PlantHealthStatus.AVAILABLE, PlantHealthStatus.PARTIAL}
    )
    if len(fully_available) == configured:
        return PipelineStageEvaluation(
            stage=PipelineStage.HEALTH,
            status=PipelineStageStatus.READY,
            reason="Plant Health was classified from direct evidence for every configured area.",
        )
    if usable:
        return PipelineStageEvaluation(
            stage=PipelineStage.HEALTH,
            status=PipelineStageStatus.PARTIAL,
            reason="Plant Health is available for some areas with direct evidence.",
            blocker_codes=blockers,
        )
    return PipelineStageEvaluation(
        stage=PipelineStage.HEALTH,
        status=PipelineStageStatus.BLOCKED,
        reason="Plant Health requires direct manual, sensor, or visual evidence.",
        blocker_codes=tuple(
            dict.fromkeys((*blockers, *stress_stage.blocker_codes, "plant_health_unavailable"))
        ),
    )


def _recommendation_stage(
    configured: int,
    health_stage: PipelineStageEvaluation,
    recommendations: tuple[AreaRecommendationEvaluation, ...],
) -> PipelineStageEvaluation:
    if configured == 0:
        return PipelineStageEvaluation(
            stage=PipelineStage.RECOMMENDATIONS,
            status=PipelineStageStatus.BLOCKED,
            reason="No configured irrigation areas are available.",
            blocker_codes=("no_configured_areas",),
        )

    blockers = tuple(
        dict.fromkeys(code for item in recommendations for code in item.blocker_codes)
    )
    assessments = tuple(
        item.assessment for item in recommendations if item.assessment is not None
    )
    fully_available = tuple(
        assessment
        for assessment in assessments
        if assessment.status is RecommendationStatus.AVAILABLE
    )
    usable = tuple(
        assessment
        for assessment in assessments
        if assessment.status in {RecommendationStatus.AVAILABLE, RecommendationStatus.PARTIAL}
    )
    if len(fully_available) == configured:
        return PipelineStageEvaluation(
            stage=PipelineStage.RECOMMENDATIONS,
            status=PipelineStageStatus.READY,
            reason="Advisory recommendations were generated for every configured area.",
        )
    if usable:
        return PipelineStageEvaluation(
            stage=PipelineStage.RECOMMENDATIONS,
            status=PipelineStageStatus.PARTIAL,
            reason="Advisory recommendations are available with unresolved evidence gaps.",
            blocker_codes=blockers,
        )
    return PipelineStageEvaluation(
        stage=PipelineStage.RECOMMENDATIONS,
        status=PipelineStageStatus.BLOCKED,
        reason="Recommendations could not be generated from the available upstream assessments.",
        blocker_codes=tuple(
            dict.fromkeys((*blockers, *health_stage.blocker_codes, "recommendations_unavailable"))
        ),
    )


def _planning_stage(
    configured: int,
    recommendation_stage: PipelineStageEvaluation,
    planning: tuple[AreaPlanningEvaluation, ...],
) -> PipelineStageEvaluation:
    if configured == 0:
        return PipelineStageEvaluation(
            stage=PipelineStage.PLANNING,
            status=PipelineStageStatus.BLOCKED,
            reason="No configured irrigation areas are available.",
            blocker_codes=("no_configured_areas",),
        )

    blockers = tuple(
        dict.fromkeys(code for item in planning for code in item.blocker_codes)
    )
    plans = tuple(item.plan for item in planning if item.plan is not None)
    ready = tuple(plan for plan in plans if plan.status is PlanStatus.READY)
    usable = tuple(
        plan for plan in plans if plan.status in {PlanStatus.READY, PlanStatus.PARTIAL}
    )
    if len(ready) == configured:
        return PipelineStageEvaluation(
            stage=PipelineStage.PLANNING,
            status=PipelineStageStatus.READY,
            reason="Machine-readable irrigation plans were generated for every configured area.",
        )
    if usable:
        return PipelineStageEvaluation(
            stage=PipelineStage.PLANNING,
            status=PipelineStageStatus.PARTIAL,
            reason=(
                "Machine-readable plans are available with manual-only actions or "
                "unresolved planning inputs."
            ),
            blocker_codes=blockers,
        )
    return PipelineStageEvaluation(
        stage=PipelineStage.PLANNING,
        status=PipelineStageStatus.BLOCKED,
        reason="Planning could not produce a usable plan from the available recommendations.",
        blocker_codes=tuple(
            dict.fromkeys(
                (*blockers, *recommendation_stage.blocker_codes, "planning_unavailable")
            )
        ),
    )
