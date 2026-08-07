"""Immutable Home Assistant pipeline evaluation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..controllers import ControllerRegistrySnapshot
from ..environment import EnvironmentalIntelligenceReport
from ..execution import ExecutionPlan
from ..landscape import EstablishmentStage, LandscapeProfile
from ..planning import IrrigationPlan
from ..plant_health import PlantHealthAssessment
from ..plant_knowledge import Season
from ..plant_stress import PlantStressRiskAssessment
from ..plant_water_requirement import PlantWaterRequirementAssessment
from ..recommendations import RecommendationAssessment
from ..scheduling import IrrigationSchedule
from ..scientific_inputs import ScientificInputSnapshot

PIPELINE_SCHEMA_VERSION = "1.0"
PIPELINE_ALGORITHM_VERSION = "1.0.9"


class PipelineStage(StrEnum):
    """Ordered IrrigationOS pipeline stages."""

    OBSERVATIONS = "observations"
    KNOWLEDGE = "knowledge"
    WATER_REQUIREMENT = "water_requirement"
    STRESS = "stress"
    HEALTH = "health"
    RECOMMENDATIONS = "recommendations"
    PLANNING = "planning"
    SCHEDULING = "scheduling"
    EXECUTION = "execution"
    RUNTIME_MONITORING = "runtime_monitoring"


class PipelineStageStatus(StrEnum):
    """Readiness state for one pipeline stage."""

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class PipelineEvaluationStatus(StrEnum):
    """Overall status for one synchronized evaluation."""

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PipelineStageEvaluation:
    """Immutable readiness result for one pipeline stage."""

    stage: PipelineStage
    status: PipelineStageStatus
    reason: str
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaWaterRequirementEvaluation:
    """Water-requirement result and context for one irrigation area."""

    area_id: str
    establishment_stage: EstablishmentStage
    season: Season | None
    assessment: PlantWaterRequirementAssessment | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaPlantStressEvaluation:
    """Aggregate plant-stress result for one irrigation area."""

    area_id: str
    assessment: PlantStressRiskAssessment | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaPlantHealthEvaluation:
    """Plant-health result for one irrigation area."""

    area_id: str
    assessment: PlantHealthAssessment | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaRecommendationEvaluation:
    """Advisory recommendation result for one irrigation area."""

    area_id: str
    assessment: RecommendationAssessment | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaPlanningEvaluation:
    """Machine-readable planning result for one irrigation area."""

    area_id: str
    plan: IrrigationPlan | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaSchedulingEvaluation:
    """Proposed scheduling result for one irrigation area."""

    area_id: str
    schedule: IrrigationSchedule | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AreaExecutionEvaluation:
    """Simulation-only execution result for one irrigation area."""

    area_id: str
    execution_plan: ExecutionPlan | None
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineEvaluation:
    """Canonical immutable output cached by the HA coordinator."""

    schema_version: str
    algorithm_version: str
    evaluated_at: datetime
    status: PipelineEvaluationStatus
    current_stage: PipelineStage
    observation_snapshot: ControllerRegistrySnapshot
    landscape_profile: LandscapeProfile
    scientific_inputs: ScientificInputSnapshot
    stages: tuple[PipelineStageEvaluation, ...]
    configured_area_count: int
    complete_profile_count: int
    water_requirements: tuple[AreaWaterRequirementEvaluation, ...] = ()
    environmental_report: EnvironmentalIntelligenceReport | None = None
    plant_stress: tuple[AreaPlantStressEvaluation, ...] = ()
    plant_health: tuple[AreaPlantHealthEvaluation, ...] = ()
    recommendations: tuple[AreaRecommendationEvaluation, ...] = ()
    planning: tuple[AreaPlanningEvaluation, ...] = ()
    scheduling: tuple[AreaSchedulingEvaluation, ...] = ()
    execution: tuple[AreaExecutionEvaluation, ...] = ()

    def stage(self, stage: PipelineStage) -> PipelineStageEvaluation:
        """Return one stage evaluation."""
        for evaluation in self.stages:
            if evaluation.stage is stage:
                return evaluation
        raise KeyError(f"Unknown pipeline stage: {stage}")

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        """Return unique blocker codes in stable stage order."""
        return tuple(
            dict.fromkeys(
                code for evaluation in self.stages for code in evaluation.blocker_codes
            )
        )
