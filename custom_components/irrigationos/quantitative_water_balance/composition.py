"""Observational composition from the existing IrrigationOS pipeline."""

from __future__ import annotations

from datetime import timedelta

from ..observation_history import WateringSession
from ..pipeline import PipelineEvaluation
from ..plant_knowledge import KnowledgeRange
from ..plant_water_requirement import PlantWaterRequirementStatus
from ..production_targets import find_production_area, select_production_targets
from .engine import calculate_production_area_water_balance
from .models import (
    ProductionAreaWaterBalanceRequest,
    RatioQuantity,
    WaterBalanceLedgerEvent,
    WaterBalanceSnapshot,
    WaterBalanceState,
    WaterQuantity,
)


def build_water_balance_snapshot(
    pipeline: PipelineEvaluation,
    *,
    completed_sessions: tuple[WateringSession, ...] = (),
    ledger_events: tuple[WaterBalanceLedgerEvent, ...] = (),
) -> WaterBalanceSnapshot:
    """Build truthful current balances without inventing missing quantitative facts."""

    calculated_at = pipeline.evaluated_at
    window_start = calculated_at - timedelta(hours=24)
    balances = []
    for target in select_production_targets(pipeline.observation_snapshot):
        area = find_production_area(pipeline.observation_snapshot, target)
        if area is None:
            continue
        water = next(
            (item for item in pipeline.water_requirements if item.area_id == area.area_id),
            None,
        )
        assessment = None if water is None else water.assessment
        plant_factor = (
            _plant_factor(assessment.value)
            if assessment is not None
            and assessment.status
            in {PlantWaterRequirementStatus.AVAILABLE, PlantWaterRequirementStatus.PARTIAL}
            else None
        )
        sessions = tuple(
            sorted(
                session.session_id
                for session in completed_sessions
                if session.area_id == area.area_id
                and session.ended_at is not None
                and session.ended_at >= window_start
                and session.started_at <= calculated_at
            )
        )
        # Current HA weather normalization supplies current conditions only. It does
        # not fabricate ET0, historical precipitation, or future forecast evidence.
        balances.append(
            calculate_production_area_water_balance(
                ProductionAreaWaterBalanceRequest(
                    target=target,
                    window_start=window_start,
                    window_end=calculated_at,
                    calculated_at=calculated_at,
                    reference_et_mm=None,
                    plant_factor=plant_factor,
                    observed_precipitation_mm=None,
                    quantified_irrigation_credit_mm=(
                        WaterQuantity.millimeters(0) if not sessions else None
                    ),
                    unquantified_irrigation_session_ids=sessions,
                    effective_precipitation_policy=None,
                    forecast=None,
                    ledger_events=tuple(
                        item for item in ledger_events if item.target == target
                    ),
                )
            )
        )
    blockers = tuple(sorted({code for item in balances for code in item.blocker_codes}))
    state = WaterBalanceState.NOT_AVAILABLE
    if balances:
        state = (
            WaterBalanceState.AVAILABLE
            if all(item.state is WaterBalanceState.AVAILABLE for item in balances)
            else WaterBalanceState.INSUFFICIENT_EVIDENCE
        )
    return WaterBalanceSnapshot(
        state=state,
        calculated_at=calculated_at if balances else None,
        balances=tuple(balances),
        reason_codes=(
            ("actual_water_balance_calculated",)
            if state is WaterBalanceState.AVAILABLE
            else (
                ("water_balance_withheld_insufficient_evidence",)
                if balances
                else ("no_production_targets",)
            )
        ),
        blocker_codes=blockers if balances else ("no_configured_production_targets",),
    )


def _plant_factor(value: object) -> RatioQuantity | None:
    if isinstance(value, KnowledgeRange):
        return RatioQuantity(
            minimum=float(value.minimum),
            typical=None if value.typical is None else float(value.typical),
            maximum=float(value.maximum),
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return RatioQuantity(scalar=float(value))
