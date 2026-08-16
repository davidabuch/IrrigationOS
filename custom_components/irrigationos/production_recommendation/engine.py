"""Pure observational composition of canonical production recommendations."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..landscape import EstablishmentStage
from ..pipeline import PipelineEvaluation
from ..plant_water_requirement import PlantWaterRequirementStatus
from ..production_targets import find_production_area, select_production_targets
from ..recommendations import RecommendationCategory, RecommendationStatus
from .models import (
    DeliveryReadinessState,
    ProductionAreaRecommendation,
    ProductionRecommendationEvidence,
    ProductionRecommendationSnapshot,
    ProductionRecommendationState,
    RecommendationEvidenceKind,
    ScientificNeedState,
)

RECOMMENDATION_VALIDITY = timedelta(minutes=15)
MAX_WEATHER_AGE = timedelta(hours=2)


def build_production_recommendations(
    pipeline: PipelineEvaluation,
    *,
    execution_blocker_codes: tuple[str, ...] = (),
) -> ProductionRecommendationSnapshot:
    """Compose current recommendations without granting or invoking authority."""

    calculated_at = pipeline.evaluated_at
    targets = select_production_targets(pipeline.observation_snapshot)
    recommendations: list[ProductionAreaRecommendation] = []
    for target in targets:
        area = find_production_area(pipeline.observation_snapshot, target)
        if area is None:  # Defensive: selector and snapshot must remain coherent.
            continue
        profile = next(
            (item for item in pipeline.landscape_profile.areas if item.area_id == area.area_id),
            None,
        )
        knowledge = next(
            (
                item
                for item in pipeline.scientific_inputs.area_knowledge
                if item.area_id == area.area_id
            ),
            None,
        )
        water = _by_area(pipeline.water_requirements, area.area_id)
        stress = _by_area(pipeline.plant_stress, area.area_id)
        health = _by_area(pipeline.plant_health, area.area_id)
        advisory = _by_area(pipeline.recommendations, area.area_id)

        blockers: set[str] = set()
        evidence: list[ProductionRecommendationEvidence] = [
            ProductionRecommendationEvidence(
                kind=RecommendationEvidenceKind.CONTROLLER_OBSERVATION,
                status=pipeline.observation_snapshot.observation.quality.value,
                observed_at=pipeline.observation_snapshot.observation.observed_at,
            )
        ]
        if profile is None or not profile.is_complete:
            blockers.add("landscape_profile_incomplete")
        evidence.append(
            ProductionRecommendationEvidence(
                kind=RecommendationEvidenceKind.LANDSCAPE_PROFILE,
                status="complete" if profile is not None and profile.is_complete else "incomplete",
            )
        )
        if knowledge is None or knowledge.selected_profile_id is None:
            blockers.add("plant_profile_unresolved")
        evidence.append(
            ProductionRecommendationEvidence(
                kind=RecommendationEvidenceKind.PLANT_KNOWLEDGE,
                status=(
                    "resolved"
                    if knowledge is not None and knowledge.selected_profile_id
                    else "unresolved"
                ),
                confidence=None if knowledge is None else knowledge.resolution_confidence,
            )
        )
        if profile is None or profile.establishment_stage.value is EstablishmentStage.UNKNOWN:
            blockers.add("establishment_stage_unknown")

        water_assessment = None if water is None else water.assessment
        usable_water = water_assessment is not None and water_assessment.status in {
            PlantWaterRequirementStatus.AVAILABLE,
            PlantWaterRequirementStatus.PARTIAL,
        }
        if not usable_water:
            blockers.add("plant_water_requirement_unavailable")
        evidence.append(
            ProductionRecommendationEvidence(
                kind=RecommendationEvidenceKind.PLANT_WATER_REQUIREMENT,
                status="unavailable" if water_assessment is None else water_assessment.status.value,
                confidence=(
                    None
                    if water_assessment is None
                    else water_assessment.confidence.confidence
                ),
            )
        )
        evidence.extend(
            (
                ProductionRecommendationEvidence(
                    kind=RecommendationEvidenceKind.PLANT_STRESS,
                    status=(
                        "unavailable"
                        if stress is None or stress.assessment is None
                        else stress.assessment.overall_status.value
                    ),
                ),
                ProductionRecommendationEvidence(
                    kind=RecommendationEvidenceKind.PLANT_HEALTH,
                    status=(
                        "unavailable"
                        if health is None or health.assessment is None
                        else health.assessment.status.value
                    ),
                ),
            )
        )
        weather = pipeline.scientific_inputs.weather
        weather_status = "unavailable"
        if weather is None:
            blockers.add("weather_observation_unavailable")
        elif calculated_at - weather.observed_at > MAX_WEATHER_AGE:
            weather_status = "stale"
            blockers.add("weather_observation_stale")
        else:
            weather_status = "available"
        evidence.append(
            ProductionRecommendationEvidence(
                kind=RecommendationEvidenceKind.WEATHER_OBSERVATION,
                status=weather_status,
                observed_at=None if weather is None else weather.observed_at,
            )
        )

        scientific_need = ScientificNeedState.UNAVAILABLE
        advisory_assessment = None if advisory is None else advisory.assessment
        if (
            advisory_assessment is not None
            and advisory_assessment.status is RecommendationStatus.AVAILABLE
        ):
            if advisory_assessment.recommendations and all(
                item.category is RecommendationCategory.NO_ACTION
                for item in advisory_assessment.recommendations
            ):
                scientific_need = ScientificNeedState.NOT_INDICATED
            elif any(
                item.category is RecommendationCategory.ADJUST_IRRIGATION
                for item in advisory_assessment.recommendations
            ):
                scientific_need = ScientificNeedState.INDICATED

        # Plant factor evidence is not an irrigation depth. Current pipeline output
        # therefore cannot support a quantitative delivery or scheduling contract.
        blockers.update(
            {
                "target_irrigation_depth_unavailable",
                "delivery_evidence_incomplete",
                "runtime_estimate_unavailable",
                "scheduling_window_unavailable",
            }
        )
        if scientific_need is ScientificNeedState.UNAVAILABLE:
            blockers.add("scientific_need_unavailable")

        confidence = 0.0 if water_assessment is None else water_assessment.confidence.confidence
        completeness = (
            0.0 if water_assessment is None else water_assessment.confidence.completeness
        )
        recommendations.append(
            ProductionAreaRecommendation(
                target=target,
                state=ProductionRecommendationState.INSUFFICIENT_EVIDENCE,
                scientific_need=scientific_need,
                delivery_readiness=DeliveryReadinessState.INCOMPLETE,
                irrigation_depth=None,
                estimated_runtime_seconds=None,
                scheduling_window=None,
                evidence=tuple(sorted(evidence, key=lambda item: item.kind.value)),
                confidence=confidence,
                completeness=completeness,
                reason_codes=("recommendation_withheld_insufficient_evidence",),
                blocker_codes=tuple(sorted(blockers)),
                execution_blocker_codes=tuple(sorted(set(execution_blocker_codes))),
                calculated_at=calculated_at,
                valid_until=calculated_at + RECOMMENDATION_VALIDITY,
            )
        )

    all_blockers = tuple(
        sorted(
            {
                code
                for recommendation in recommendations
                for code in recommendation.blocker_codes
            }
        )
    )
    state = (
        ProductionRecommendationState.INSUFFICIENT_EVIDENCE
        if recommendations
        else ProductionRecommendationState.NOT_AVAILABLE
    )
    return ProductionRecommendationSnapshot(
        state=state,
        calculated_at=calculated_at if recommendations else None,
        recommendations=tuple(recommendations),
        reason_codes=(
            ("recommendation_withheld_insufficient_evidence",)
            if recommendations
            else ("no_production_targets",)
        ),
        blocker_codes=(
            all_blockers
            if recommendations
            else ("no_configured_production_targets",)
        ),
    )


def _by_area(values: tuple[Any, ...], area_id: str) -> Any | None:
    return next((item for item in values if getattr(item, "area_id", None) == area_id), None)
