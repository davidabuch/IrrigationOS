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
    AccountingIntervalState,
    DemandFactorSource,
    OpeningBalanceState,
    ProductionAreaWaterBalanceRequest,
    RatioQuantity,
    WaterBalanceLedgerEvent,
    WaterBalanceSnapshot,
    WaterBalanceState,
    WaterBalanceTargetState,
    WaterQuantity,
)
from .policy import (
    PRODUCTION_EFFECTIVE_PRECIPITATION_POLICY,
    allowable_depletion_fraction,
    generic_demand_factor,
    root_zone_reservoir,
)
from .weather_evidence import canonical_weather_balance_evidence


def build_water_balance_snapshot(
    pipeline: PipelineEvaluation,
    *,
    completed_sessions: tuple[WateringSession, ...] = (),
    ledger_events: tuple[WaterBalanceLedgerEvent, ...] = (),
    target_states: tuple[WaterBalanceTargetState, ...] = (),
    weather_observations: ObservationWindow | None = None,
    weather_forecast: ForecastWindow | None = None,
    ledger_healthy: bool = True,
) -> WaterBalanceSnapshot:
    """Build truthful current balances without inventing missing quantitative facts."""

    calculated_at = pipeline.evaluated_at
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
        curated_factor = (
            _plant_factor(assessment.value)
            if assessment is not None
            and assessment.status
            in {PlantWaterRequirementStatus.AVAILABLE, PlantWaterRequirementStatus.PARTIAL}
            else None
        )
        profile = next(
            (item for item in pipeline.landscape_profile.areas if item.area_id == area.area_id),
            None,
        )
        generic_factor = (
            None if profile is None else generic_demand_factor(profile.plant_type.value)
        )
        plant_factor = curated_factor or generic_factor
        factor_source = (
            DemandFactorSource.CURATED_PLANT_KNOWLEDGE
            if curated_factor is not None
            else DemandFactorSource.GENERIC_LANDSCAPE_CLASS
            if generic_factor is not None
            else DemandFactorSource.UNRESOLVED
        )
        reservoir = (
            None
            if profile is None
            else root_zone_reservoir(
                profile.soil_texture.value,
                profile.root_depth_inches.value,
            )
        )
        depletion = (
            None
            if profile is None
            else allowable_depletion_fraction(
                profile.plant_type.value,
                profile.establishment_stage.value,
            )
        )
        target_ledger = tuple(item for item in ledger_events if item.target == target)
        prior_state = next((item for item in target_states if item.target == target), None)
        interval_state, window_start, window_end = _accounting_interval(
            weather_observations, prior_state, calculated_at
        )
        et0, observed_rain, forecast, weather_evidence = canonical_weather_balance_evidence(
            _slice_observations(weather_observations, window_start, window_end),
            weather_forecast,
        )
        prior_deferral = _unresolved_deferral(target_ledger)
        forecast_window_rain = None
        if (
            prior_deferral is not None
            and prior_deferral.forecast_window_start is not None
            and prior_deferral.forecast_window_end is not None
        ):
            _, forecast_window_rain, _, _ = canonical_weather_balance_evidence(
                _slice_observations(
                    weather_observations,
                    prior_deferral.forecast_window_start,
                    prior_deferral.forecast_window_end,
                ),
                None,
            )
        sessions = tuple(
            sorted(
                session.session_id
                for session in completed_sessions
                if session.area_id == area.area_id
                and session.ended_at is not None
                and window_start < session.ended_at <= window_end
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
                    effective_precipitation_policy=(
                        None
                        if observed_rain is not None
                        and _quantity_upper(observed_rain) == 0
                        and forecast is None
                        else PRODUCTION_EFFECTIVE_PRECIPITATION_POLICY
                    ),
                    forecast=forecast,
                    accounting_interval_state=interval_state,
                    forecast_window_observed_precipitation_mm=forecast_window_rain,
                    opening_balance_state=(
                        OpeningBalanceState.UNKNOWN
                        if prior_state is None
                        else OpeningBalanceState.DURABLE_CARRY_FORWARD
                        if prior_state.state is OpeningBalanceState.RECONSTRUCTED
                        else prior_state.state
                    ),
                    opening_deficit_mm=(None if prior_state is None else prior_state.deficit_mm),
                    demand_factor_source=factor_source,
                    demand_factor_confidence=(
                        assessment.confidence.confidence
                        if curated_factor is not None and assessment is not None
                        else min(0.55, profile.plant_type.confidence_percent / 100)
                        if generic_factor is not None and profile is not None
                        else None
                    ),
                    root_zone_available_water_mm=reservoir,
                    root_zone_confidence=(
                        min(
                            0.60,
                            profile.soil_texture.confidence_percent / 100,
                            profile.root_depth_inches.confidence_percent / 100,
                        )
                        if reservoir is not None and profile is not None
                        else None
                    ),
                    allowable_depletion_fraction=depletion,
                    ledger_healthy=ledger_healthy,
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


def _quantity_upper(value: WaterQuantity) -> float:
    if value.scalar is not None:
        return value.scalar
    if value.maximum is None:  # guarded by WaterQuantity validation
        raise ValueError("water quantity range is incomplete")
    return value.maximum


def _unresolved_deferral(
    events: tuple[WaterBalanceLedgerEvent, ...],
) -> WaterBalanceLedgerEvent | None:
    reconciled = {
        event.forecast_id for event in events if event.kind.value == "forecast_reconciliation"
    }
    candidates = [
        event
        for event in events
        if event.kind.value == "forecast_deferral" and event.forecast_id not in reconciled
    ]
    return (
        None
        if not candidates
        else max(candidates, key=lambda item: (item.recorded_at, item.event_id))
    )


def _slice_observations(
    observations: ObservationWindow | None, start: datetime, end: datetime
) -> ObservationWindow | None:
    """Return only evidence inside the exact non-overlapping accounting window."""
    if observations is None:
        return None
    selected = tuple(item for item in observations.observations if start <= item.observed_at < end)
    if not selected:
        return None
    return ObservationWindow(
        window_id=f"{observations.window_id}.slice",
        location_id=observations.location_id,
        starts_at=start,
        ends_at=end,
        observations=selected,
    )


def _accounting_interval(
    observations: ObservationWindow | None,
    prior: WaterBalanceTargetState | None,
    calculated_at: datetime,
) -> tuple[AccountingIntervalState, datetime, datetime]:
    """Select only exact completed hourly evidence after the durable boundary."""

    if prior is None:
        if observations is None:
            return AccountingIntervalState.NO_NEW_EVIDENCE, calculated_at, calculated_at
        start = observations.starts_at
        end = observations.ends_at
        if not _has_complete_hourly_evidence(observations, start, end):
            return AccountingIntervalState.GAP, start, start
        return AccountingIntervalState.COMPLETE, start, end
    boundary = prior.accounted_through
    if observations is None or observations.ends_at == boundary:
        return AccountingIntervalState.NO_NEW_EVIDENCE, boundary, boundary
    if observations.ends_at < boundary:
        return AccountingIntervalState.REPLAY, boundary, boundary
    if observations.starts_at > boundary:
        return AccountingIntervalState.GAP, boundary, boundary
    if not _has_complete_hourly_evidence(observations, boundary, observations.ends_at):
        return AccountingIntervalState.GAP, boundary, boundary
    return AccountingIntervalState.COMPLETE, boundary, observations.ends_at


def _has_complete_hourly_evidence(
    observations: ObservationWindow, start: datetime, end: datetime
) -> bool:
    """Prove every completed hourly interval is represented exactly once in order."""

    duration_seconds = (end - start).total_seconds()
    if duration_seconds <= 0 or duration_seconds % 3600 != 0:
        return False
    selected = tuple(
        item.observed_at
        for item in observations.observations
        if start <= item.observed_at < end
    )
    expected_count = int(duration_seconds // 3600)
    return len(selected) == expected_count and all(
        observed_at == start + timedelta(hours=index)
        for index, observed_at in enumerate(selected)
    )


def target_state_for_balance(
    balance: object,
    previous: WaterBalanceTargetState | None = None,
) -> WaterBalanceTargetState | None:
    """Derive bounded current state only from a completed advancing interval."""

    from .models import ProductionAreaWaterBalance

    if not isinstance(balance, ProductionAreaWaterBalance):
        raise TypeError("balance must be a production-area water balance")
    if balance.accounting_interval_state is not AccountingIntervalState.COMPLETE:
        return None
    if balance.unquantified_irrigation_session_ids:
        return WaterBalanceTargetState(
            target=balance.target,
            state=OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION,
            window_start=balance.window_start,
            accounted_through=balance.window_end,
            recorded_at=balance.calculated_at,
            invalidated_session_ids=balance.unquantified_irrigation_session_ids,
            reason_code="water_balance_invalidated_by_unquantified_irrigation",
        )
    if balance.actual_net_deficit_mm is not None:
        state = (
            OpeningBalanceState.RECONSTRUCTED
            if balance.opening_balance_state is OpeningBalanceState.RECONSTRUCTED
            else OpeningBalanceState.DURABLE_CARRY_FORWARD
        )
        return WaterBalanceTargetState(
            target=balance.target,
            state=state,
            window_start=balance.window_start,
            accounted_through=balance.window_end,
            recorded_at=balance.calculated_at,
            deficit_mm=balance.actual_net_deficit_mm,
            reason_code=(
                "opening_balance_reconstructed_by_observed_saturation"
                if state is OpeningBalanceState.RECONSTRUCTED
                else "durable_water_balance_carry_forward"
            ),
        )
    return WaterBalanceTargetState(
        target=balance.target,
        state=(
            OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION
            if balance.opening_balance_state
            is OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION
            else OpeningBalanceState.UNKNOWN
        ),
        window_start=balance.window_start,
        accounted_through=balance.window_end,
        recorded_at=balance.calculated_at,
        invalidated_session_ids=(
            balance.unquantified_irrigation_session_ids
            if balance.unquantified_irrigation_session_ids
            else previous.invalidated_session_ids
            if previous is not None
            and previous.state is OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION
            else ()
        ),
        reason_code=(
            "water_balance_invalidated_by_unquantified_irrigation"
            if balance.opening_balance_state
            is OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION
            else "opening_balance_unknown"
        ),
    )
