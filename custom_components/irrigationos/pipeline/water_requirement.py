"""Adapt resolved scientific inputs into Plant Water Requirement assessments."""

from __future__ import annotations

from datetime import datetime

from ..landscape import EstablishmentStage, IrrigationAreaProfile, LandscapeProfile, SunExposure
from ..plant_knowledge import (
    EvidenceGrade,
    RegionalApplicability,
    RegionalScope,
    ReviewState,
    Season,
)
from ..plant_water_requirement import (
    ConflictBehavior,
    ExposureClassification,
    MicroclimateClassification,
    MissingDataBehavior,
    PlantWaterRequirementContext,
    PlantWaterRequirementPolicy,
    PlantWaterRequirementRequest,
    PlantWaterRequirementStatus,
    RangeHandling,
    assess_plant_water_requirement,
)
from ..scientific_inputs import Hemisphere, ScientificInputSnapshot
from .models import AreaWaterRequirementEvaluation

_POLICY = PlantWaterRequirementPolicy(
    policy_id="irrigationos-water-policy",
    policy_version="1.0.0",
    accepted_claim_paths=("water.plant_factor",),
    minimum_review_state=ReviewState.APPROVED,
    minimum_evidence_grade=EvidenceGrade.MODERATE,
    minimum_confidence=0.75,
    require_regional_match=True,
    range_handling=RangeHandling.PRESERVE,
    missing_data_behavior=MissingDataBehavior.RETURN_UNAVAILABLE,
    conflict_behavior=ConflictBehavior.RETURN_CONFLICT,
)
_USABLE_STATUSES = {
    PlantWaterRequirementStatus.AVAILABLE,
    PlantWaterRequirementStatus.PARTIAL,
}


def build_area_water_requirements(
    landscape: LandscapeProfile,
    scientific_inputs: ScientificInputSnapshot,
    *,
    evaluated_at: datetime,
) -> tuple[AreaWaterRequirementEvaluation, ...]:
    """Assess each area once using resolved knowledge and explicit HA context."""
    season = _season_for_hemisphere(evaluated_at, scientific_inputs.regional_context.hemisphere)
    knowledge_by_area = {item.area_id: item for item in scientific_inputs.area_knowledge}
    results: list[AreaWaterRequirementEvaluation] = []

    for profile in landscape.areas:
        blockers: list[str] = []
        if profile.establishment_stage.value is EstablishmentStage.UNKNOWN:
            blockers.append("establishment_stage_not_configured")
        if season is None:
            blockers.append("location_hemisphere_unavailable")

        knowledge = knowledge_by_area.get(profile.area_id)
        resolution = None if knowledge is None else knowledge.knowledge_resolution
        if resolution is None or resolution.selected_profile_id is None:
            blockers.append("plant_knowledge_profile_unresolved")

        if blockers:
            results.append(
                AreaWaterRequirementEvaluation(
                    area_id=profile.area_id,
                    establishment_stage=profile.establishment_stage.value,
                    season=season,
                    assessment=None,
                    blocker_codes=tuple(dict.fromkeys(blockers)),
                )
            )
            continue

        assert season is not None
        assert resolution is not None
        context = PlantWaterRequirementContext(
            regional_applicability=_regional_context(scientific_inputs, season),
            season=season,
            establishment_stage=profile.establishment_stage.value,
            exposure=_exposure(profile),
            microclimate=MicroclimateClassification.UNKNOWN,
        )
        safe_area_id = "".join(
            character if character.isalnum() or character == "_" else "_"
            for character in profile.area_id
        )
        assessment = assess_plant_water_requirement(
            PlantWaterRequirementRequest(
                request_id=f"pwr.request.{safe_area_id}",
                knowledge_resolution=resolution,
                context=context,
                policy=_POLICY,
                created_at=evaluated_at,
            )
        )
        if assessment.status not in _USABLE_STATUSES:
            blockers.append(f"water_requirement_{assessment.status.value}")
        elif assessment.status is PlantWaterRequirementStatus.PARTIAL:
            blockers.append("water_requirement_partial")

        results.append(
            AreaWaterRequirementEvaluation(
                area_id=profile.area_id,
                establishment_stage=profile.establishment_stage.value,
                season=season,
                assessment=assessment,
                blocker_codes=tuple(blockers),
            )
        )

    return tuple(results)


def _season_for_hemisphere(
    evaluated_at: datetime, hemisphere: Hemisphere
) -> Season | None:
    if hemisphere is Hemisphere.UNKNOWN:
        return None
    northern = {
        12: Season.WINTER,
        1: Season.WINTER,
        2: Season.WINTER,
        3: Season.SPRING,
        4: Season.SPRING,
        5: Season.SPRING,
        6: Season.SUMMER,
        7: Season.SUMMER,
        8: Season.SUMMER,
        9: Season.AUTUMN,
        10: Season.AUTUMN,
        11: Season.AUTUMN,
    }[evaluated_at.month]
    if hemisphere is Hemisphere.NORTHERN:
        return northern
    return {
        Season.WINTER: Season.SUMMER,
        Season.SPRING: Season.AUTUMN,
        Season.SUMMER: Season.WINTER,
        Season.AUTUMN: Season.SPRING,
    }[northern]


def _regional_context(
    scientific_inputs: ScientificInputSnapshot, season: Season
) -> RegionalApplicability:
    context = scientific_inputs.regional_context
    elevation = context.elevation_meters
    return RegionalApplicability(
        scope=RegionalScope.REGIONAL,
        countries=((context.country_code,) if context.country_code is not None else ()),
        elevation_minimum_meters=elevation,
        elevation_maximum_meters=elevation,
        seasons=(season,),
    )


def _exposure(profile: IrrigationAreaProfile) -> ExposureClassification:
    exposure = profile.sun_exposure.value
    if exposure is SunExposure.FULL_SUN:
        return ExposureClassification.EXPOSED
    if exposure in {SunExposure.MOSTLY_SHADE, SunExposure.FULL_SHADE}:
        return ExposureClassification.SHELTERED
    if exposure is SunExposure.UNKNOWN:
        return ExposureClassification.UNKNOWN
    return ExposureClassification.TYPICAL
