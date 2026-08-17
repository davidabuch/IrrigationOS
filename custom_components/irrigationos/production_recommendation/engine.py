"""Pure observational composition of canonical production recommendations."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..landscape import EstablishmentStage
from ..pipeline import PipelineEvaluation
from ..plant_water_requirement import PlantWaterRequirementStatus
from ..production_targets import find_production_area, select_production_targets
from ..quantitative_water_balance import (
    ForecastReconciliationState,
    WaterBalanceSnapshot,
    WaterBalanceState,
)
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
    water_balances: WaterBalanceSnapshot | None = None,
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
        balance = None
        if water_balances is not None:
            balance = next(
                (item for item in water_balances.balances if item.target == target),
                None,
            )

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
        evidence.append(
            ProductionRecommendationEvidence(
                kind=RecommendationEvidenceKind.QUANTITATIVE_WATER_BALANCE,
                status="unavailable" if balance is None else balance.state.value,
                confidence=None if balance is None else balance.confidence,
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

        recommendation_state = ProductionRecommendationState.INSUFFICIENT_EVIDENCE
        reason_codes = ("recommendation_withheld_insufficient_evidence",)
        if balance is None or balance.state is not WaterBalanceState.AVAILABLE:
            blockers.add("quantitative_water_balance_unavailable")
        elif balance.actual_net_deficit_mm is not None:
            if (
                balance.forecast_reconciliation_state
                is ForecastReconciliationState.DEFERRED_FOR_FORECAST
            ):
                scientific_need = ScientificNeedState.DEFERRED
                recommendation_state = (
                    ProductionRecommendationState.IRRIGATION_DEFERRED_FOR_FORECAST
                )
                reason_codes = ("scientific_need_deferred_for_forecast",)
            elif _quantity_upper(balance.actual_net_deficit_mm) <= 0:
                scientific_need = ScientificNeedState.NOT_INDICATED
                recommendation_state = ProductionRecommendationState.NO_IRRIGATION_RECOMMENDED
                reason_codes = ("no_current_water_deficit",)
            else:
                scientific_need = ScientificNeedState.INDICATED
                recommendation_state = ProductionRecommendationState.IRRIGATION_RECOMMENDED
                reason_codes = ("quantitative_water_deficit_present",)
        blockers.update(
            {
                "delivery_evidence_incomplete",
                "target_irrigation_depth_unavailable",
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
                state=recommendation_state,
                scientific_need=scientific_need,
                delivery_readiness=DeliveryReadinessState.INCOMPLETE,
                irrigation_depth=None,
                estimated_runtime_seconds=None,
                scheduling_window=None,
                evidence=tuple(sorted(evidence, key=lambda item: item.kind.value)),
                confidence=confidence,
                completeness=completeness,
                reason_codes=reason_codes,
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
    states = {item.state for item in recommendations}
    state = (
        ProductionRecommendationState.NOT_AVAILABLE
        if not recommendations
        else next(iter(states))
        if len(states) == 1
        else ProductionRecommendationState.MIXED
    )
    return ProductionRecommendationSnapshot(
        state=state,
        calculated_at=calculated_at if recommendations else None,
        recommendations=tuple(recommendations),
        reason_codes=(
            tuple(sorted({code for item in recommendations for code in item.reason_codes}))
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


def _quantity_upper(value: Any) -> float:
    return value.scalar if value.scalar is not None else value.maximum
