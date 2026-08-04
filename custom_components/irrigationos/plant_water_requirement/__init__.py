"""Stable public API for Plant Water Requirement assessment."""

from .engine import assess_plant_water_requirement
from .models import (
    PLANT_WATER_REQUIREMENT_ALGORITHM_VERSION,
    PLANT_WATER_REQUIREMENT_SCHEMA_VERSION,
    ConflictBehavior,
    EstablishmentStage,
    ExposureClassification,
    MicroclimateClassification,
    MissingDataBehavior,
    PlantWaterRequirementAssessment,
    PlantWaterRequirementConfidence,
    PlantWaterRequirementContext,
    PlantWaterRequirementExplanation,
    PlantWaterRequirementPolicy,
    PlantWaterRequirementReasonCode,
    PlantWaterRequirementRequest,
    PlantWaterRequirementStatus,
    RangeHandling,
    RegionalApplicabilityResult,
)

__all__ = (
    "PLANT_WATER_REQUIREMENT_ALGORITHM_VERSION",
    "PLANT_WATER_REQUIREMENT_SCHEMA_VERSION",
    "ConflictBehavior",
    "EstablishmentStage",
    "ExposureClassification",
    "MicroclimateClassification",
    "MissingDataBehavior",
    "PlantWaterRequirementAssessment",
    "PlantWaterRequirementConfidence",
    "PlantWaterRequirementContext",
    "PlantWaterRequirementExplanation",
    "PlantWaterRequirementPolicy",
    "PlantWaterRequirementReasonCode",
    "PlantWaterRequirementRequest",
    "PlantWaterRequirementStatus",
    "RangeHandling",
    "RegionalApplicabilityResult",
    "assess_plant_water_requirement",
)
