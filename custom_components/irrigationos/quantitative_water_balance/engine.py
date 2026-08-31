"""Pure deterministic quantitative water-balance evaluation."""

from __future__ import annotations

import hashlib
from datetime import timedelta

from .models import (
    AccountingIntervalState,
    DemandFactorSource,
    ForecastReconciliationState,
    IrrigationTriggerState,
    OpeningBalanceState,
    ProductionAreaWaterBalance,
    ProductionAreaWaterBalanceRequest,
    RatioQuantity,
    WaterBalanceLedgerEvent,
    WaterBalanceLedgerEventKind,
    WaterBalanceState,
    WaterQuantity,
)
from .policy import BASELINE_WATER_BUDGET_POLICY_VERSION
from .precipitation import apply_effective_precipitation_policy

BALANCE_VALIDITY = timedelta(minutes=15)


def calculate_production_area_water_balance(
    request: ProductionAreaWaterBalanceRequest,
) -> ProductionAreaWaterBalance:
    """Calculate actual loss/receipt separately from provisional forecast cover."""

    blockers: set[str] = set()
    accounting_blockers: set[str] = set()
    reasons: set[str] = set()
    complete_interval = request.accounting_interval_state is AccountingIntervalState.COMPLETE
    if request.accounting_interval_state is AccountingIntervalState.GAP:
        accounting_blockers.add("accounting_evidence_gap")
    elif request.accounting_interval_state is AccountingIntervalState.OVERLAP:
        accounting_blockers.add("accounting_evidence_overlap")
    elif request.accounting_interval_state is AccountingIntervalState.REPLAY:
        accounting_blockers.add("accounting_evidence_replay")
    if complete_interval and request.reference_et_mm is None:
        accounting_blockers.add("reference_et_unavailable")
    elif complete_interval and request.calculated_at - request.window_end > timedelta(hours=6):
        accounting_blockers.add("reference_et_stale")
    if request.plant_factor is None:
        accounting_blockers.add("plant_factor_unresolved")
    if complete_interval and request.observed_precipitation_mm is None:
        accounting_blockers.add("observed_precipitation_unavailable")
    if (
        request.observed_precipitation_mm is not None
        and _upper(request.observed_precipitation_mm) > 0
        and request.effective_precipitation_policy is None
    ):
        accounting_blockers.add("effective_precipitation_policy_unavailable")
    if request.unquantified_irrigation_session_ids:
        accounting_blockers.add("unquantified_irrigation_observed")
    if (
        request.unquantified_irrigation_session_ids
        and request.quantified_irrigation_credit_mm is None
    ):
        accounting_blockers.add("quantified_irrigation_credit_unavailable")
    opening = request.opening_deficit_mm
    opening_state = request.opening_balance_state
    if not request.ledger_healthy:
        accounting_blockers.add("water_balance_ledger_unhealthy")
    blockers.update(accounting_blockers)

    irrigation_credit = request.quantified_irrigation_credit_mm
    if irrigation_credit is None and not request.unquantified_irrigation_session_ids:
        irrigation_credit = WaterQuantity.millimeters(0)
        reasons.add("no_irrigation_observed")
    elif irrigation_credit is not None and _upper(irrigation_credit) > 0:
        reasons.add("quantified_irrigation_credit_applied")

    demand = _multiply(request.reference_et_mm, request.plant_factor)
    effective_observed = apply_effective_precipitation_policy(
        request.observed_precipitation_mm, request.effective_precipitation_policy
    )
    prior = _unresolved_deferral(request)
    actual = (
        opening
        if request.accounting_interval_state is AccountingIntervalState.NO_NEW_EVIDENCE
        else _actual_deficit(opening, demand, effective_observed, irrigation_credit)
    )
    if (
        complete_interval
        and opening is None
        and not request.unquantified_irrigation_session_ids
        and _saturation_proves_zero(
            effective_observed, irrigation_credit, request.root_zone_available_water_mm, demand
        )
    ):
        actual = WaterQuantity.millimeters(0)
        opening_state = OpeningBalanceState.RECONSTRUCTED
        reasons.add("opening_balance_reconstructed_by_observed_saturation")
    elif opening is None:
        accounting_blockers.add("opening_balance_unknown")
    if request.unquantified_irrigation_session_ids:
        accounting_blockers.add("water_balance_invalidated_by_unquantified_irrigation")
    if accounting_blockers:
        actual = None
    blockers.update(accounting_blockers)

    trigger = _multiply(request.root_zone_available_water_mm, request.allowable_depletion_fraction)
    if request.root_zone_available_water_mm is None:
        blockers.add("root_zone_reservoir_unavailable")
    if request.allowable_depletion_fraction is None:
        blockers.add("allowable_depletion_unavailable")
    trigger_state = _trigger_state(actual, trigger)
    irrigation_indicated = (
        True
        if trigger_state is IrrigationTriggerState.AT_OR_ABOVE_TRIGGER
        else False
        if trigger_state is IrrigationTriggerState.BELOW_TRIGGER
        else None
    )
    target_depth = (
        _minimum(actual, request.root_zone_available_water_mm)
        if irrigation_indicated is True
        else None
    )
    if trigger_state is IrrigationTriggerState.UNCERTAIN_RANGE:
        blockers.add("irrigation_trigger_range_uncertain")
    if irrigation_indicated is True:
        reasons.add("allowable_depletion_trigger_reached")
    elif irrigation_indicated is False:
        reasons.add("deficit_below_allowable_depletion_trigger")
    if request.demand_factor_source is DemandFactorSource.GENERIC_LANDSCAPE_CLASS:
        reasons.add("generic_landscape_demand_factor_applied")
    elif request.demand_factor_source is DemandFactorSource.CURATED_PLANT_KNOWLEDGE:
        reasons.add("curated_plant_demand_factor_applied")

    forecast_effective = apply_effective_precipitation_policy(
        None if request.forecast is None else request.forecast.precipitation_mm,
        request.effective_precipitation_policy,
    )
    effective_reconciliation_observed = apply_effective_precipitation_policy(
        request.forecast_window_observed_precipitation_mm,
        request.effective_precipitation_policy,
    )
    reconciliation = _reconciliation_state(request, prior, effective_reconciliation_observed)
    if (
        prior is not None
        and prior.forecast_window_end is not None
        and request.calculated_at > prior.forecast_window_end
        and effective_reconciliation_observed is None
    ):
        blockers.add("forecast_reconciliation_precipitation_unavailable")
    if (
        request.forecast is not None
        and _upper(request.forecast.precipitation_mm) > 0
        and forecast_effective is None
    ):
        reasons.add("forecast_effective_precipitation_unavailable")
    covered: WaterQuantity | None = None
    residual: WaterQuantity | None = actual
    deferred: WaterQuantity | None = None
    if actual is not None and _forecast_qualifies(request, forecast_effective):
        covered = _minimum(
            actual,
            forecast_effective,
            _scale(actual, request.forecast_policy.maximum_deficit_cover_fraction),
        )
        if covered is not None and _upper(covered) > 0:
            residual = _subtract(actual, covered)
            deferred = covered
            reconciliation = ForecastReconciliationState.DEFERRED_FOR_FORECAST
            reasons.add("irrigation_demand_deferred_for_qualifying_forecast")
    elif request.forecast is not None:
        reasons.add("forecast_did_not_qualify_for_deferral")

    if reconciliation is ForecastReconciliationState.FORECAST_REALIZED:
        reasons.add("forecast_deferral_fully_realized")
    elif reconciliation is ForecastReconciliationState.FORECAST_PARTIALLY_REALIZED:
        reasons.add("forecast_deferral_partially_realized")
    elif reconciliation is ForecastReconciliationState.FORECAST_NOT_REALIZED:
        reasons.add("forecast_deficit_restored")

    state = (
        WaterBalanceState.AVAILABLE
        if actual is not None
        else WaterBalanceState.INSUFFICIENT_EVIDENCE
    )
    if state is WaterBalanceState.AVAILABLE:
        reasons.add("actual_water_balance_calculated")
    else:
        reasons.add("water_balance_withheld_insufficient_evidence")
    required = 8
    known = sum(
        value is not None
        for value in (
            opening,
            request.reference_et_mm,
            request.plant_factor,
            request.observed_precipitation_mm,
            effective_observed,
            irrigation_credit,
            request.root_zone_available_water_mm,
            request.allowable_depletion_fraction,
        )
    )
    confidences = [item.confidence for item in request.evidence]
    confidences.extend(
        value
        for value in (
            request.demand_factor_confidence,
            request.root_zone_confidence,
            None
            if request.effective_precipitation_policy is None
            else request.effective_precipitation_policy.confidence,
        )
        if value is not None
    )
    return ProductionAreaWaterBalance(
        target=request.target,
        state=state,
        window_start=request.window_start,
        window_end=request.window_end,
        calculated_at=request.calculated_at,
        valid_until=request.calculated_at + BALANCE_VALIDITY,
        reference_et_mm=request.reference_et_mm,
        plant_factor=request.plant_factor,
        gross_landscape_demand_mm=demand,
        observed_precipitation_mm=request.observed_precipitation_mm,
        effective_observed_precipitation_mm=effective_observed,
        quantified_irrigation_credit_mm=irrigation_credit,
        unquantified_irrigation_session_ids=request.unquantified_irrigation_session_ids,
        actual_net_deficit_mm=actual,
        forecast_precipitation_mm=(
            None if request.forecast is None else request.forecast.precipitation_mm
        ),
        effective_forecast_precipitation_mm=forecast_effective,
        forecast_window_observed_precipitation_mm=(
            request.forecast_window_observed_precipitation_mm
        ),
        effective_forecast_window_observed_precipitation_mm=(effective_reconciliation_observed),
        forecast_window_start=(None if request.forecast is None else request.forecast.window_start),
        forecast_window_end=(None if request.forecast is None else request.forecast.window_end),
        forecast_covered_deficit_mm=covered,
        residual_uncovered_deficit_mm=residual,
        deferred_deficit_mm=deferred,
        forecast_reconciliation_state=reconciliation,
        accounting_interval_state=request.accounting_interval_state,
        opening_balance_state=opening_state,
        demand_factor_source=request.demand_factor_source,
        root_zone_available_water_mm=request.root_zone_available_water_mm,
        allowable_depletion_fraction=request.allowable_depletion_fraction,
        irrigation_trigger_deficit_mm=trigger,
        trigger_state=trigger_state,
        irrigation_indicated=irrigation_indicated,
        target_replenishment_depth_mm=target_depth,
        baseline_water_budget_policy_version=BASELINE_WATER_BUDGET_POLICY_VERSION,
        confidence=0.0 if not confidences else min(confidences),
        completeness=known / required,
        evidence=request.evidence,
        reason_codes=tuple(sorted(reasons)),
        blocker_codes=tuple(sorted(blockers)),
    )


def deferral_event_for_balance(
    balance: ProductionAreaWaterBalance, forecast_id: str
) -> WaterBalanceLedgerEvent | None:
    """Create immutable persistence evidence for a qualifying deferral."""

    if (
        balance.forecast_reconciliation_state
        is not ForecastReconciliationState.DEFERRED_FOR_FORECAST
        or balance.deferred_deficit_mm is None
        or balance.forecast_window_start is None
        or balance.forecast_window_end is None
        or balance.actual_net_deficit_mm is None
    ):
        return None
    event_id = _event_id("deferral", balance.target, forecast_id, balance.calculated_at)
    return WaterBalanceLedgerEvent(
        event_id=event_id,
        kind=WaterBalanceLedgerEventKind.FORECAST_DEFERRAL,
        target=balance.target,
        recorded_at=balance.calculated_at,
        window_start=(balance.window_start if balance.window_end > balance.window_start else None),
        accounted_through=balance.window_end,
        carry_forward_deficit_mm=balance.actual_net_deficit_mm,
        forecast_id=forecast_id,
        forecast_window_start=balance.forecast_window_start,
        forecast_window_end=balance.forecast_window_end,
        deferred_deficit_mm=balance.deferred_deficit_mm,
    )


def ledger_event_for_balance(
    balance: ProductionAreaWaterBalance,
    prior_events: tuple[WaterBalanceLedgerEvent, ...],
) -> WaterBalanceLedgerEvent | None:
    """Select the single semantic ledger event for a completed balance window."""

    prior = _unresolved_deferral_events(balance.target, prior_events)
    if (
        prior is None
        and balance.forecast_reconciliation_state
        is ForecastReconciliationState.DEFERRED_FOR_FORECAST
    ):
        forecast_id = next(
            (
                item.evidence_id.removeprefix("weather.forecast.")
                for item in balance.evidence
                if item.kind.value == "forecast_precipitation"
            ),
            None,
        )
        if forecast_id is not None:
            return deferral_event_for_balance(balance, forecast_id)
    if prior is not None:
        reconciliation = reconciliation_event_for_balance(balance, prior)
        if reconciliation is not None:
            return reconciliation
    return None


def reconciliation_event_for_balance(
    balance: ProductionAreaWaterBalance,
    prior_deferral: WaterBalanceLedgerEvent,
) -> WaterBalanceLedgerEvent | None:
    """Create immutable evidence that closes one forecast deferral."""

    if (
        prior_deferral.kind is not WaterBalanceLedgerEventKind.FORECAST_DEFERRAL
        or prior_deferral.target != balance.target
        or prior_deferral.forecast_id is None
        or prior_deferral.forecast_window_start is None
        or prior_deferral.forecast_window_end is None
        or prior_deferral.deferred_deficit_mm is None
    ):
        return None
    if balance.forecast_reconciliation_state not in {
        ForecastReconciliationState.FORECAST_REALIZED,
        ForecastReconciliationState.FORECAST_PARTIALLY_REALIZED,
        ForecastReconciliationState.FORECAST_NOT_REALIZED,
    }:
        return None
    if balance.effective_forecast_window_observed_precipitation_mm is None:
        return None
    event_id = _event_id(
        "reconciliation",
        balance.target,
        prior_deferral.forecast_id,
        balance.calculated_at,
    )
    return WaterBalanceLedgerEvent(
        event_id=event_id,
        kind=WaterBalanceLedgerEventKind.FORECAST_RECONCILIATION,
        target=balance.target,
        recorded_at=balance.calculated_at,
        window_start=(balance.window_start if balance.window_end > balance.window_start else None),
        accounted_through=balance.window_end,
        carry_forward_deficit_mm=(balance.actual_net_deficit_mm or WaterQuantity.millimeters(0)),
        forecast_id=prior_deferral.forecast_id,
        forecast_window_start=prior_deferral.forecast_window_start,
        forecast_window_end=prior_deferral.forecast_window_end,
        deferred_deficit_mm=prior_deferral.deferred_deficit_mm,
        realized_effective_precipitation_mm=(
            balance.effective_forecast_window_observed_precipitation_mm
        ),
    )


def _unresolved_deferral(
    request: ProductionAreaWaterBalanceRequest,
) -> WaterBalanceLedgerEvent | None:
    return _unresolved_deferral_events(request.target, request.ledger_events)


def _unresolved_deferral_events(
    target: object, events: tuple[WaterBalanceLedgerEvent, ...]
) -> WaterBalanceLedgerEvent | None:
    reconciled = {
        event.forecast_id
        for event in events
        if event.kind is WaterBalanceLedgerEventKind.FORECAST_RECONCILIATION
    }
    candidates = [
        event
        for event in events
        if event.target == target
        and event.kind is WaterBalanceLedgerEventKind.FORECAST_DEFERRAL
        and event.forecast_id not in reconciled
    ]
    return (
        None
        if not candidates
        else max(candidates, key=lambda item: (item.recorded_at, item.event_id))
    )


def _trigger_state(
    deficit: WaterQuantity | None, trigger: WaterQuantity | None
) -> IrrigationTriggerState:
    if deficit is None or trigger is None:
        return IrrigationTriggerState.UNAVAILABLE
    if _upper(deficit) + 1e-9 < _lower(trigger):
        return IrrigationTriggerState.BELOW_TRIGGER
    if _lower(deficit) + 1e-9 >= _upper(trigger):
        return IrrigationTriggerState.AT_OR_ABOVE_TRIGGER
    return IrrigationTriggerState.UNCERTAIN_RANGE


def _reconciliation_state(
    request: ProductionAreaWaterBalanceRequest,
    prior: WaterBalanceLedgerEvent | None,
    effective_observed: WaterQuantity | None,
) -> ForecastReconciliationState:
    if prior is None:
        return ForecastReconciliationState.NO_FORECAST_ADJUSTMENT
    if prior.forecast_window_end is None or prior.deferred_deficit_mm is None:
        return ForecastReconciliationState.RECONCILIATION_INCOMPLETE
    if request.calculated_at <= prior.forecast_window_end:
        return ForecastReconciliationState.FORECAST_PENDING
    if effective_observed is None:
        return ForecastReconciliationState.RECONCILIATION_INCOMPLETE
    realized_low = _lower(effective_observed)
    realized_high = _upper(effective_observed)
    deferred_high = _upper(prior.deferred_deficit_mm)
    if realized_high <= 0:
        return ForecastReconciliationState.FORECAST_NOT_REALIZED
    if realized_low + 1e-9 >= deferred_high:
        return ForecastReconciliationState.FORECAST_REALIZED
    return ForecastReconciliationState.FORECAST_PARTIALLY_REALIZED


def _forecast_qualifies(
    request: ProductionAreaWaterBalanceRequest,
    effective: WaterQuantity | None,
) -> bool:
    forecast = request.forecast
    if forecast is None or effective is None:
        return False
    policy = request.forecast_policy
    if forecast.issued_at > request.calculated_at or forecast.window_end <= request.calculated_at:
        return False
    if request.calculated_at - forecast.issued_at > timedelta(
        hours=policy.maximum_forecast_age_hours
    ):
        return False
    if forecast.window_end - request.calculated_at > timedelta(hours=policy.maximum_horizon_hours):
        return False
    if forecast.confidence < policy.minimum_source_confidence:
        return False
    if forecast.quality not in {"good", "estimated"}:
        return False
    return _lower(effective) >= policy.minimum_effective_precipitation_mm


def _actual_deficit(
    opening: WaterQuantity | None,
    demand: WaterQuantity | None,
    observed: WaterQuantity | None,
    irrigation: WaterQuantity | None,
) -> WaterQuantity | None:
    if demand is None or observed is None or irrigation is None:
        return None
    total = demand if opening is None else _add(opening, demand)
    return _subtract(_subtract(total, observed), irrigation)


def _saturation_proves_zero(
    observed: WaterQuantity | None,
    irrigation: WaterQuantity | None,
    reservoir: WaterQuantity | None,
    demand: WaterQuantity | None,
) -> bool:
    """Prove zero closing deficit from actual water under worst-case bounds."""

    if observed is None or irrigation is None or reservoir is None or demand is None:
        return False
    return _lower(observed) + _lower(irrigation) + 1e-9 >= (_upper(reservoir) + _upper(demand))


def _multiply(water: WaterQuantity | None, ratio: RatioQuantity | None) -> WaterQuantity | None:
    if water is None or ratio is None:
        return None
    w = _bounds(water)
    r = _bounds(ratio)
    return _from_bounds(w[0] * r[0], _maybe_product(w[1], r[1]), w[2] * r[2])


def _scale(value: WaterQuantity | None, factor: float | None) -> WaterQuantity | None:
    if value is None or factor is None:
        return None
    low, typical, high = _bounds(value)
    return _from_bounds(low * factor, None if typical is None else typical * factor, high * factor)


def _add(left: WaterQuantity, right: WaterQuantity) -> WaterQuantity:
    a, at, b = _bounds(left)
    c, ct, d = _bounds(right)
    return _from_bounds(a + c, None if at is None or ct is None else at + ct, b + d)


def _subtract(left: WaterQuantity, right: WaterQuantity) -> WaterQuantity:
    a, at, b = _bounds(left)
    c, ct, d = _bounds(right)
    return _from_bounds(
        max(0.0, a - d),
        None if at is None or ct is None else max(0.0, at - ct),
        max(0.0, b - c),
    )


def _minimum(*values: WaterQuantity | None) -> WaterQuantity | None:
    present = [value for value in values if value is not None]
    if len(present) != len(values):
        return None
    lows = [_lower(value) for value in present]
    highs = [_upper(value) for value in present]
    typicals = [_bounds(value)[1] for value in present]
    known_typicals = [value for value in typicals if value is not None]
    typical = min(known_typicals) if len(known_typicals) == len(typicals) else None
    return _from_bounds(min(lows), typical, min(highs))


def _bounds(value: WaterQuantity | RatioQuantity) -> tuple[float, float | None, float]:
    scalar = value.scalar
    if scalar is not None:
        return scalar, scalar, scalar
    minimum = value.minimum
    maximum = value.maximum
    if minimum is None or maximum is None:  # guarded by immutable model validation
        raise ValueError("quantity range is incomplete")
    return minimum, value.typical, maximum


def _from_bounds(low: float, typical: float | None, high: float) -> WaterQuantity:
    low, high = min(low, high), max(low, high)
    if abs(low - high) < 1e-12:
        return WaterQuantity.millimeters(round(low, 6))
    if typical is not None:
        typical = min(high, max(low, typical))
    return WaterQuantity(
        minimum=round(low, 6),
        typical=None if typical is None else round(typical, 6),
        maximum=round(high, 6),
    )


def _lower(value: WaterQuantity) -> float:
    return _bounds(value)[0]


def _upper(value: WaterQuantity) -> float:
    return _bounds(value)[2]


def _maybe_product(left: float | None, right: float | None) -> float | None:
    return None if left is None or right is None else left * right


def _event_id(kind: str, target: object, forecast_id: str, at: object) -> str:
    digest = hashlib.sha256(f"{kind}|{target}|{forecast_id}|{at}".encode()).hexdigest()
    return f"water_balance.{kind}.{digest[:32]}"
