"""Observational composition from the existing IrrigationOS pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..observation_history import WateringSession
from ..pipeline import PipelineEvaluation
from ..plant_knowledge import KnowledgeRange
from ..plant_water_requirement import PlantWaterRequirementStatus
from ..production_targets import find_production_area, select_production_targets
from ..weather import ForecastWindow, ObservationWindow
from .engine import calculate_production_area_water_balance
from .models import (
    ProductionAreaWaterBalanceRequest,
    RatioQuantity,
    WaterBalanceLedgerEvent,
    WaterBalanceSnapshot,
    WaterBalanceState,
    WaterQuantity,
)
from .weather_evidence import canonical_weather_balance_evidence


def build_water_balance_snapshot(
    pipeline: PipelineEvaluation,
    *,
    completed_sessions: tuple[WateringSession, ...] = (),
    ledger_events: tuple[WaterBalanceLedgerEvent, ...] = (),
    weather_observations: ObservationWindow | None = None,
    weather_forecast: ForecastWindow | None = None,
) -> WaterBalanceSnapshot:
    """Build truthful current balances without inventing missing quantitative facts."""

    calculated_at = pipeline.evaluated_at
    default_window_start = calculated_at - timedelta(hours=24)
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
        target_ledger = tuple(item for item in ledger_events if item.target == target)
        carried = target_ledger[-1] if target_ledger else None
        window_start = (
            carried.accounted_through if carried is not None else default_window_start
        )
        window_end = _completed_weather_boundary(
            weather_observations, window_start=window_start, calculated_at=calculated_at
        )
        et0, observed_rain, forecast, weather_evidence = canonical_weather_balance_evidence(
            _slice_observations(weather_observations, window_start, window_end),
            weather_forecast,
        )
        sessions = tuple(
            sorted(
                session.session_id
                for session in completed_sessions
                if session.area_id == area.area_id
                and session.ended_at is not None
                and session.ended_at >= window_start
                and session.started_at <= window_end
            )
        )
        balances.append(
            calculate_production_area_water_balance(
                ProductionAreaWaterBalanceRequest(
                    target=target,
                    window_start=window_start,
                    window_end=window_end,
                    calculated_at=calculated_at,
                    reference_et_mm=et0,
                    plant_factor=plant_factor,
                    observed_precipitation_mm=observed_rain,
                    quantified_irrigation_credit_mm=(
                        WaterQuantity.millimeters(0) if not sessions else None
                    ),
                    unquantified_irrigation_session_ids=sessions,
                    effective_precipitation_policy=None,
                    forecast=forecast,
                    ledger_events=target_ledger,
                    evidence=weather_evidence,
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


def _slice_observations(
    observations: ObservationWindow | None, start: datetime, end: datetime
) -> ObservationWindow | None:
    """Return only evidence inside the exact non-overlapping accounting window."""
    if observations is None:
        return None
    selected = tuple(
        item for item in observations.observations if start <= item.observed_at < end
    )
    if not selected:
        return None
    return ObservationWindow(
        window_id=f"{observations.window_id}.slice",
        location_id=observations.location_id,
        starts_at=start,
        ends_at=end,
        observations=selected,
    )


def _completed_weather_boundary(
    observations: ObservationWindow | None,
    *,
    window_start: datetime,
    calculated_at: datetime,
) -> datetime:
    """Advance accounting only through the newest fully completed weather interval."""
    if observations is None:
        return calculated_at
    boundary = min(observations.ends_at, calculated_at)
    return boundary if boundary > window_start else calculated_at
