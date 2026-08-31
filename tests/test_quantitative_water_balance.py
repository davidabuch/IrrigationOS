"""Behavioral tests for v1.0.45 quantitative water-balance semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers import load_integration_module
from tests.test_environment_engine import (
    ForecastWindow,
    ObservationWindow,
)
from tests.test_environment_engine import (
    fact as weather_fact,
)
from tests.test_environment_engine import (
    forecast as hourly_weather_forecast,
)
from tests.test_environment_engine import (
    observation as historical_weather_observation,
)

QWB = load_integration_module("quantitative_water_balance")
TARGETS = load_integration_module("production_targets")

NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)
TARGET = TARGETS.ProductionTarget(1, 1)


def quantity(value: float) -> Any:
    return QWB.WaterQuantity.millimeters(value)


def request(**changes: object) -> Any:
    values: dict[str, object] = {
        "target": TARGET,
        "window_start": NOW - timedelta(days=1),
        "window_end": NOW,
        "calculated_at": NOW,
        "reference_et_mm": quantity(10),
        "plant_factor": QWB.RatioQuantity(scalar=0.5),
        "observed_precipitation_mm": quantity(1),
        "quantified_irrigation_credit_mm": quantity(0),
        "unquantified_irrigation_session_ids": (),
        "effective_precipitation_policy": QWB.EffectivePrecipitationPolicy(
            policy_id="water.effective.test",
            effective_fraction=0.8,
            confidence=0.8,
            rationale_code="site_policy_supplied",
        ),
        "forecast": None,
        "opening_balance_state": QWB.OpeningBalanceState.RECONSTRUCTED,
        "opening_deficit_mm": quantity(0),
    }
    values.update(changes)
    if values.get("ledger_events"):
        ledger_events = cast(tuple[Any, ...], values["ledger_events"])
        carried = max(
            ledger_events,
            key=lambda item: (item.accounted_through, item.event_id),
        )
        values["opening_balance_state"] = QWB.OpeningBalanceState.DURABLE_CARRY_FORWARD
        values["opening_deficit_mm"] = carried.carry_forward_deficit_mm
    return QWB.ProductionAreaWaterBalanceRequest(**values)


def forecast(
    precipitation: float = 10,
    *,
    issued_at: datetime = NOW,
    confidence: float = 0.9,
) -> Any:
    return QWB.ForecastPrecipitationEvidence(
        forecast_id="weather.forecast.demo",
        issued_at=issued_at,
        window_start=NOW + timedelta(hours=2),
        window_end=NOW + timedelta(hours=24),
        precipitation_mm=quantity(precipitation),
        probability_percent=None,
        confidence=confidence,
        quality="good",
        source="synthetic_test_weather",
    )


def deferral(amount: float = 7.62) -> Any:
    return QWB.WaterBalanceLedgerEvent(
        event_id="water_balance.deferral.demo",
        kind=QWB.WaterBalanceLedgerEventKind.FORECAST_DEFERRAL,
        target=TARGET,
        forecast_id="weather.forecast.prior",
        recorded_at=NOW - timedelta(days=1),
        accounted_through=NOW - timedelta(days=1),
        forecast_window_start=NOW - timedelta(hours=23),
        forecast_window_end=NOW - timedelta(hours=1),
        deferred_deficit_mm=quantity(amount),
        carry_forward_deficit_mm=quantity(amount),
    )


def composition_observations(
    start: datetime,
    offsets: tuple[int, ...],
    *,
    interval_hours: int,
    precipitation_mm: float = 0,
    et0_mm: float = 1,
) -> ObservationWindow:
    """Build explicit hourly evidence without concealing gaps in test fixtures."""

    observations = tuple(
        historical_weather_observation(
            start + timedelta(hours=offset),
            f"composition-hour-{offset}",
            weather_fact(precipitation_mm, start + timedelta(hours=offset)),
            weather_fact(et0_mm, start + timedelta(hours=offset)),
        )
        for offset in offsets
    )
    return ObservationWindow(
        window_id="composition-window",
        location_id="property-1",
        starts_at=start,
        ends_at=start + timedelta(hours=interval_hours),
        observations=observations,
    )


def composition_prior(boundary: datetime, deficit_mm: float = 5) -> Any:
    """Build a durable opening at the exact accounting boundary."""

    return QWB.WaterBalanceTargetState(
        target=TARGET,
        state=QWB.OpeningBalanceState.DURABLE_CARRY_FORWARD,
        window_start=boundary - timedelta(hours=1),
        accounted_through=boundary,
        recorded_at=boundary,
        deficit_mm=quantity(deficit_mm),
        reason_code="durable_water_balance_carry_forward",
    )


def test_actual_balance_uses_only_occurred_water() -> None:
    result = QWB.calculate_production_area_water_balance(request(forecast=forecast()))

    assert result.actual_net_deficit_mm.scalar == pytest.approx(4.2)
    assert result.effective_forecast_precipitation_mm.scalar == pytest.approx(8.0)
    assert result.forecast_covered_deficit_mm.scalar == pytest.approx(3.36)
    assert result.residual_uncovered_deficit_mm.scalar == pytest.approx(0.84)
    assert result.deferred_deficit_mm.scalar == pytest.approx(3.36)
    assert result.forecast_reconciliation_state.value == "deferred_for_forecast"
    assert result.execution_authorized is False


def test_missing_probability_does_not_invent_one_and_is_deterministic() -> None:
    first = QWB.calculate_production_area_water_balance(request(forecast=forecast()))
    second = QWB.calculate_production_area_water_balance(request(forecast=forecast()))

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.forecast_covered_deficit_mm is not None


def test_trivial_or_stale_forecast_cannot_defer() -> None:
    trivial = QWB.calculate_production_area_water_balance(
        request(forecast=forecast(precipitation=1))
    )
    stale = QWB.calculate_production_area_water_balance(
        request(forecast=forecast(issued_at=NOW - timedelta(hours=7)))
    )
    expired = QWB.calculate_production_area_water_balance(
        request(
            forecast=QWB.ForecastPrecipitationEvidence(
                forecast_id="weather.forecast.expired",
                issued_at=NOW - timedelta(hours=2),
                window_start=NOW - timedelta(hours=2),
                window_end=NOW - timedelta(hours=1),
                precipitation_mm=quantity(10),
                probability_percent=None,
                confidence=0.9,
                quality="good",
                source="synthetic_test_weather",
            )
        )
    )

    for result in (trivial, stale, expired):
        assert result.forecast_covered_deficit_mm is None
        assert result.deferred_deficit_mm is None
        assert result.actual_net_deficit_mm.scalar == pytest.approx(4.2)


@pytest.mark.parametrize(
    ("actual_rain", "expected_state", "expected_deficit"),
    [
        (7.62, "forecast_realized", 0.0),
        (2.54, "forecast_partially_realized", 5.08),
        (0.0, "forecast_not_realized", 7.62),
    ],
)
def test_forecast_reconciliation_restores_only_unrealized_deficit(
    actual_rain: float, expected_state: str, expected_deficit: float
) -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(0),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(actual_rain),
            forecast_window_observed_precipitation_mm=quantity(actual_rain),
            effective_precipitation_policy=QWB.EffectivePrecipitationPolicy(
                policy_id="water.effective.full_test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            ledger_events=(deferral(),),
        )
    )

    assert result.forecast_reconciliation_state.value == expected_state
    assert result.actual_net_deficit_mm.scalar == pytest.approx(expected_deficit)


def test_new_et_accumulates_while_deferred() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(2),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            forecast_window_observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=QWB.EffectivePrecipitationPolicy(
                policy_id="water.effective.full_test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            ledger_events=(deferral(),),
        )
    )

    assert result.actual_net_deficit_mm.scalar == pytest.approx(9.62)
    assert "forecast_deficit_restored" in result.reason_codes


def test_rain_outside_forecast_window_affects_actual_but_not_realization() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(0),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(6),
            forecast_window_observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=QWB.EffectivePrecipitationPolicy(
                policy_id="water.effective.full_test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            ledger_events=(deferral(),),
        )
    )

    assert result.actual_net_deficit_mm == quantity(1.62)
    assert result.forecast_reconciliation_state.value == "forecast_not_realized"


def test_plant_factor_range_is_preserved_in_gross_demand() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(plant_factor=QWB.RatioQuantity(minimum=0.3, typical=0.5, maximum=0.7))
    )

    assert result.plant_factor.minimum == 0.3
    assert result.gross_landscape_demand_mm.minimum == pytest.approx(3)
    assert result.gross_landscape_demand_mm.typical == pytest.approx(5)
    assert result.gross_landscape_demand_mm.maximum == pytest.approx(7)


@pytest.mark.parametrize(
    ("change", "blocker"),
    [
        ({"reference_et_mm": None}, "reference_et_unavailable"),
        ({"plant_factor": None}, "plant_factor_unresolved"),
        (
            {
                "window_end": NOW - timedelta(hours=7),
                "window_start": NOW - timedelta(days=1, hours=7),
            },
            "reference_et_stale",
        ),
    ],
)
def test_missing_or_stale_scientific_evidence_fails_closed(
    change: dict[str, object], blocker: str
) -> None:
    result = QWB.calculate_production_area_water_balance(request(**change))

    assert result.state.value == "insufficient_evidence"
    assert result.actual_net_deficit_mm is None
    assert blocker in result.blocker_codes


def test_unquantified_watering_is_visible_and_never_converted_from_runtime() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            quantified_irrigation_credit_mm=None,
            unquantified_irrigation_session_ids=("watering.session.1",),
        )
    )

    assert result.quantified_irrigation_credit_mm is None
    assert result.actual_net_deficit_mm is None
    assert result.unquantified_irrigation_session_ids == ("watering.session.1",)
    assert "unquantified_irrigation_observed" in result.blocker_codes
    serialized = result.to_dict()
    assert "runtime" not in str(serialized).casefold()
    assert "application_rate" not in str(serialized).casefold()


def test_effective_precipitation_requires_explicit_policy() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(effective_precipitation_policy=None)
    )

    assert result.effective_observed_precipitation_mm is None
    assert "effective_precipitation_policy_unavailable" in result.blocker_codes


def test_exact_zero_precipitation_needs_no_effective_precipitation_policy() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            observed_precipitation_mm=quantity(0),
            quantified_irrigation_credit_mm=None,
            effective_precipitation_policy=None,
        )
    )

    assert result.state.value == "available"
    assert result.effective_observed_precipitation_mm == quantity(0)
    assert result.quantified_irrigation_credit_mm == quantity(0)
    assert result.actual_net_deficit_mm == quantity(5)
    assert "effective_precipitation_policy_unavailable" not in result.blocker_codes
    assert "quantified_irrigation_credit_unavailable" not in result.blocker_codes
    assert "no_irrigation_observed" in result.reason_codes


def test_zero_forecast_needs_no_transformation_but_positive_forecast_does() -> None:
    zero = QWB.calculate_production_area_water_balance(
        request(
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=None,
            forecast=forecast(0),
        )
    )
    positive = QWB.calculate_production_area_water_balance(
        request(
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=None,
            forecast=forecast(10),
        )
    )

    assert zero.effective_forecast_precipitation_mm == quantity(0)
    assert positive.state.value == "available"
    assert positive.effective_forecast_precipitation_mm is None
    assert "forecast_effective_precipitation_unavailable" in positive.reason_codes
    assert positive.actual_net_deficit_mm == quantity(5)


def test_quantified_irrigation_credit_is_applied_without_runtime_inference() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=None,
            quantified_irrigation_credit_mm=quantity(2),
        )
    )

    assert result.state.value == "available"
    assert result.actual_net_deficit_mm == quantity(3)
    assert "quantified_irrigation_credit_applied" in result.reason_codes
    assert "unquantified_irrigation_observed" not in result.blocker_codes


def test_forecast_cover_policy_deliberately_retains_twenty_percent() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(10),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=QWB.EffectivePrecipitationPolicy(
                policy_id="water.effective.full_test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            forecast=forecast(20),
        )
    )

    assert result.actual_net_deficit_mm == quantity(10)
    assert result.forecast_covered_deficit_mm == quantity(8)
    assert result.residual_uncovered_deficit_mm == quantity(2)
    assert result.actual_net_deficit_mm == quantity(10)


def test_gap_overlap_and_replay_intervals_fail_closed() -> None:
    for interval_state, blocker in (
        (QWB.AccountingIntervalState.GAP, "accounting_evidence_gap"),
        (QWB.AccountingIntervalState.OVERLAP, "accounting_evidence_overlap"),
        (QWB.AccountingIntervalState.REPLAY, "accounting_evidence_replay"),
    ):
        result = QWB.calculate_production_area_water_balance(
            request(
                window_start=NOW,
                window_end=NOW,
                accounting_interval_state=interval_state,
            )
        )
        assert result.actual_net_deficit_mm is None
        assert blocker in result.blocker_codes


@pytest.mark.parametrize(
    ("actual_rain", "reconciled_deficit", "final_deficit"),
    [(0.0, 10.0, 11.0), (6.0, 4.0, 5.0), (12.0, 0.0, 1.0)],
)
def test_forecast_reconciliation_carries_full_actual_deficit_without_double_counting(
    actual_rain: float,
    reconciled_deficit: float,
    final_deficit: float,
) -> None:
    policy = QWB.EffectivePrecipitationPolicy(
        policy_id="water.effective.full_test",
        effective_fraction=1,
        confidence=1,
        rationale_code="measured_effective_precipitation",
    )
    initial = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(8),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=policy,
            forecast=forecast(12),
        )
    )
    deferral_event = QWB.deferral_event_for_balance(initial, "weather.forecast.demo")
    assert deferral_event is not None
    assert deferral_event.deferred_deficit_mm == quantity(6.4)
    assert deferral_event.carry_forward_deficit_mm == quantity(8)

    reconciliation_balance = QWB.calculate_production_area_water_balance(
        request(
            window_start=NOW,
            window_end=NOW + timedelta(hours=25),
            calculated_at=NOW + timedelta(hours=25),
            reference_et_mm=quantity(2),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(actual_rain),
            forecast_window_observed_precipitation_mm=quantity(actual_rain),
            effective_precipitation_policy=policy,
            forecast=None,
            ledger_events=(deferral_event,),
        )
    )
    assert reconciliation_balance.actual_net_deficit_mm == quantity(reconciled_deficit)
    reconciliation_event = QWB.reconciliation_event_for_balance(
        reconciliation_balance, deferral_event
    )
    assert reconciliation_event is not None

    restored_event = QWB.WaterBalanceLedgerEvent.from_dict(reconciliation_event.to_dict())
    final = QWB.calculate_production_area_water_balance(
        request(
            window_start=NOW + timedelta(hours=25),
            window_end=NOW + timedelta(hours=26),
            calculated_at=NOW + timedelta(hours=26),
            reference_et_mm=quantity(1),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=None,
            forecast=None,
            ledger_events=(deferral_event, restored_event),
        )
    )
    assert final.actual_net_deficit_mm == quantity(final_deficit)
    assert final.forecast_reconciliation_state.value == "no_forecast_adjustment"
    assert final.execution_authorized is False


def test_ledger_round_trip_is_immutable_and_rejects_corruption() -> None:
    event = deferral()
    restored = QWB.WaterBalanceLedgerEvent.from_dict(event.to_dict())
    assert restored == event
    with pytest.raises(FrozenInstanceError):
        event.forecast_id = "changed"
    corrupted = event.to_dict()
    corrupted["target"] = {"controller_slot": 0, "area_slot": 1}
    with pytest.raises(ValueError):
        QWB.WaterBalanceLedgerEvent.from_dict(corrupted)


def test_deferral_event_is_deterministic_and_contains_no_authority() -> None:
    balance = QWB.calculate_production_area_water_balance(request(forecast=forecast()))
    first = QWB.deferral_event_for_balance(balance, "weather.forecast.demo")
    second = QWB.deferral_event_for_balance(balance, "weather.forecast.demo")

    assert first == second
    assert first is not None
    serialized = str(first.to_dict()).casefold()
    assert not any(
        authority in serialized
        for authority in ("execution", "recommendation", "pending_action", "monitor")
    )


def test_reconciliation_event_preserves_the_original_deferral() -> None:
    prior = deferral()
    balance = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(0),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(2.54),
            forecast_window_observed_precipitation_mm=quantity(2.54),
            effective_precipitation_policy=QWB.EffectivePrecipitationPolicy(
                policy_id="water.effective.full_test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            ledger_events=(prior,),
        )
    )

    event = QWB.reconciliation_event_for_balance(balance, prior)

    assert event is not None
    assert event.forecast_id == prior.forecast_id
    assert event.forecast_window_start == prior.forecast_window_start
    assert event.forecast_window_end == prior.forecast_window_end
    assert event.deferred_deficit_mm == prior.deferred_deficit_mm
    assert event.realized_effective_precipitation_mm == quantity(2.54)
    assert event.carry_forward_deficit_mm == quantity(5.08)

    replay = QWB.calculate_production_area_water_balance(
        request(
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            calculated_at=NOW + timedelta(hours=1),
            reference_et_mm=quantity(0),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=QWB.EffectivePrecipitationPolicy(
                policy_id="water.effective.full_test",
                effective_fraction=1,
                confidence=1,
                rationale_code="measured_effective_precipitation",
            ),
            ledger_events=(prior, event),
        )
    )
    assert replay.actual_net_deficit_mm == quantity(5.08)


def test_canonical_weather_domain_is_admitted_without_a_second_weather_model() -> None:
    observed = historical_weather_observation(
        NOW - timedelta(hours=1),
        "observed-1",
        weather_fact(2.0, NOW - timedelta(hours=1)),
        weather_fact(4.0, NOW - timedelta(hours=1)),
    )
    observations = ObservationWindow(
        window_id="observed-window",
        location_id="property-1",
        starts_at=NOW - timedelta(hours=2),
        ends_at=NOW,
        observations=(observed,),
    )
    predicted = hourly_weather_forecast(
        NOW + timedelta(hours=1),
        "forecast-1",
        weather_fact(6.0, NOW + timedelta(hours=1)),
        weather_fact(0.5, NOW + timedelta(hours=1)),
    )
    forecasts = ForecastWindow(
        window_id="forecast-window",
        location_id="property-1",
        generated_at=NOW,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=2),
        hourly_forecasts=(predicted,),
    )

    et0, rain, future, evidence = QWB.canonical_weather_balance_evidence(observations, forecasts)

    assert et0 == quantity(4)
    assert rain == quantity(2)
    assert future is not None
    assert future.precipitation_mm == quantity(6)
    assert future.issued_at == NOW
    assert len(evidence) == 3
    assert QWB.canonical_weather_balance_evidence(observations, forecasts) == (
        et0,
        rain,
        future,
        evidence,
    )


def test_new_domain_has_no_execution_transport_or_network_dependency() -> None:
    package = (
        Path(__file__).parents[1]
        / "custom_components"
        / "irrigationos"
        / "quantitative_water_balance"
    )
    source = "\n".join(path.read_text() for path in sorted(package.glob("*.py")))
    forbidden = (
        "first_live_delivery",
        "supervised_operation",
        "unattended_canary",
        "adapters.rachio",
        "requests",
        "httpx",
        "urllib.request",
    )

    assert not any(name in source for name in forbidden)

    integration = package.parent
    physical_packages = (
        integration / "first_live_delivery",
        integration / "supervised_operation",
        integration / "unattended_canary",
    )
    physical_source = "\n".join(
        path.read_text()
        for directory in physical_packages
        for path in sorted(directory.glob("*.py"))
    )
    assert "quantitative_water_balance" not in physical_source


def test_three_day_current_state_carry_is_bounded_and_adjacent() -> None:
    state = None
    deficit = 0.0
    for day, daily_et in enumerate((2.0, 3.0, 4.0), start=1):
        start = NOW + timedelta(days=day - 1)
        end = start + timedelta(days=1)
        changes: dict[str, object] = {
            "window_start": start,
            "window_end": end,
            "calculated_at": end,
            "reference_et_mm": quantity(daily_et),
            "plant_factor": QWB.RatioQuantity(scalar=1),
            "observed_precipitation_mm": quantity(0),
            "effective_precipitation_policy": None,
            "opening_balance_state": (
                QWB.OpeningBalanceState.RECONSTRUCTED if state is None else state.state
            ),
            "opening_deficit_mm": quantity(0) if state is None else state.deficit_mm,
            "root_zone_available_water_mm": quantity(20),
            "allowable_depletion_fraction": QWB.RatioQuantity(scalar=0.4),
        }
        balance = QWB.calculate_production_area_water_balance(request(**changes))
        deficit += daily_et
        assert balance.actual_net_deficit_mm == quantity(deficit)
        assert balance.irrigation_indicated is (day == 3)
        state = QWB.target_state_for_balance(balance, state)
        assert state is not None

    assert state is not None
    assert state.accounted_through == NOW + timedelta(days=3)
    assert state.deficit_mm == quantity(9)


def test_unknown_bootstrap_never_silently_assumes_zero_deficit() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            opening_balance_state=QWB.OpeningBalanceState.UNKNOWN,
            opening_deficit_mm=None,
        )
    )

    assert result.state is QWB.WaterBalanceState.INSUFFICIENT_EVIDENCE
    assert result.actual_net_deficit_mm is None
    assert result.opening_balance_state is QWB.OpeningBalanceState.UNKNOWN
    assert "opening_balance_unknown" in result.blocker_codes


def test_saturation_bootstrap_uses_lower_water_and_upper_reservoir_demand() -> None:
    base = {
        "opening_balance_state": QWB.OpeningBalanceState.UNKNOWN,
        "opening_deficit_mm": None,
        "reference_et_mm": quantity(2),
        "plant_factor": QWB.RatioQuantity(scalar=1),
        "root_zone_available_water_mm": QWB.WaterQuantity(minimum=18, typical=19, maximum=20),
        "observed_precipitation_mm": QWB.WaterQuantity(minimum=22, typical=23, maximum=24),
        "effective_precipitation_policy": QWB.EffectivePrecipitationPolicy(
            policy_id="water.effective.full_test",
            effective_fraction=1,
            confidence=1,
            rationale_code="measured_effective_precipitation",
        ),
    }
    anchored = QWB.calculate_production_area_water_balance(request(**base))
    below = QWB.calculate_production_area_water_balance(
        request(
            **{
                **base,
                "observed_precipitation_mm": QWB.WaterQuantity(
                    minimum=21.999, typical=23, maximum=24
                ),
            }
        )
    )

    assert anchored.actual_net_deficit_mm == quantity(0)
    assert anchored.opening_balance_state is QWB.OpeningBalanceState.RECONSTRUCTED
    assert below.actual_net_deficit_mm is None
    assert "opening_balance_unknown" in below.blocker_codes


def test_production_composition_can_bootstrap_only_from_observed_saturation() -> None:
    from tests.test_production_recommendation import _evaluation

    evaluation = _evaluation()
    end = evaluation.evaluated_at
    start = end - timedelta(hours=1)
    observed = historical_weather_observation(
        start,
        "saturating-observation",
        weather_fact(1000.0, start),
        weather_fact(1.0, start),
    )
    observations = ObservationWindow(
        window_id="saturating-window",
        location_id="property-1",
        starts_at=start,
        ends_at=end,
        observations=(observed,),
    )

    snapshot = QWB.build_water_balance_snapshot(evaluation, weather_observations=observations)

    assert snapshot.balances[0].actual_net_deficit_mm == quantity(0)
    assert snapshot.balances[0].confidence == pytest.approx(0.55)
    assert snapshot.balances[0].opening_balance_state is QWB.OpeningBalanceState.RECONSTRUCTED


def test_contiguous_hourly_evidence_advances_exact_durable_boundary() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    end = start + timedelta(hours=4)
    prior = composition_prior(start)
    balance = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=end),
        target_states=(prior,),
        weather_observations=composition_observations(
            start, (0, 1, 2, 3), interval_hours=4
        ),
    ).balances[0]
    state = QWB.target_state_for_balance(balance, prior)

    assert balance.accounting_interval_state is QWB.AccountingIntervalState.COMPLETE
    assert (balance.window_start, balance.window_end) == (start, end)
    assert state is not None
    assert state.window_start == prior.accounted_through
    assert state.accounted_through == end


def test_internal_missing_hour_fails_closed_without_changing_durable_state() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    prior = composition_prior(start)
    balance = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=start + timedelta(hours=4)),
        target_states=(prior,),
        weather_observations=composition_observations(
            start, (0, 1, 3), interval_hours=4
        ),
    ).balances[0]

    assert balance.accounting_interval_state is QWB.AccountingIntervalState.GAP
    assert (balance.window_start, balance.window_end) == (start, start)
    assert balance.actual_net_deficit_mm is None
    assert "accounting_evidence_gap" in balance.blocker_codes
    assert QWB.target_state_for_balance(balance, prior) is None
    assert prior.deficit_mm == quantity(5)
    assert prior.accounted_through == start


def test_duplicate_hourly_evidence_is_rejected_by_observation_window() -> None:
    first = historical_weather_observation(
        NOW,
        "duplicate-hour-a",
        weather_fact(0.0, NOW),
        weather_fact(1.0, NOW),
    )
    second = historical_weather_observation(
        NOW,
        "duplicate-hour-b",
        weather_fact(0.0, NOW),
        weather_fact(1.0, NOW),
    )

    with pytest.raises(ValueError, match="timestamps must not contain duplicates"):
        ObservationWindow(
            window_id="duplicate-window",
            location_id="property-1",
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
            observations=(first, second),
        )


def test_out_of_order_hourly_evidence_is_rejected_by_observation_window() -> None:
    first = historical_weather_observation(
        NOW,
        "ordered-hour-a",
        weather_fact(0.0, NOW),
        weather_fact(1.0, NOW),
    )
    second_at = NOW + timedelta(hours=1)
    second = historical_weather_observation(
        second_at,
        "ordered-hour-b",
        weather_fact(0.0, second_at),
        weather_fact(1.0, second_at),
    )

    with pytest.raises(ValueError, match="chronological order"):
        ObservationWindow(
            window_id="out-of-order-window",
            location_id="property-1",
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=2),
            observations=(second, first),
        )


def test_missing_first_required_hour_fails_closed() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    prior = composition_prior(start)
    balance = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=start + timedelta(hours=4)),
        target_states=(prior,),
        weather_observations=composition_observations(
            start, (1, 2, 3), interval_hours=4
        ),
    ).balances[0]

    assert balance.accounting_interval_state is QWB.AccountingIntervalState.GAP
    assert QWB.target_state_for_balance(balance, prior) is None
    assert prior.accounted_through == start


def test_missing_final_required_hour_prevents_boundary_advancement() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    prior = composition_prior(start)
    balance = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=start + timedelta(hours=4)),
        target_states=(prior,),
        weather_observations=composition_observations(
            start, (0, 1, 2), interval_hours=4
        ),
    ).balances[0]

    assert balance.accounting_interval_state is QWB.AccountingIntervalState.GAP
    assert balance.window_end == prior.accounted_through
    assert QWB.target_state_for_balance(balance, prior) is None


def test_repeated_refresh_without_new_completed_hour_has_no_state_write_candidate() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    end = start + timedelta(hours=1)
    observations = composition_observations(start, (0,), interval_hours=1)
    prior = composition_prior(start)
    first = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=end),
        target_states=(prior,),
        weather_observations=observations,
    ).balances[0]
    advanced = QWB.target_state_for_balance(first, prior)
    assert advanced is not None

    repeated = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=end + timedelta(minutes=5)),
        target_states=(advanced,),
        weather_observations=observations,
    ).balances[0]

    assert repeated.accounting_interval_state is QWB.AccountingIntervalState.NO_NEW_EVIDENCE
    assert repeated.actual_net_deficit_mm == advanced.deficit_mm
    assert QWB.target_state_for_balance(repeated, advanced) is None


def test_saturating_bootstrap_with_internal_hour_gap_remains_unknown() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    balance = QWB.build_water_balance_snapshot(
        replace(_evaluation(), evaluated_at=start + timedelta(hours=3)),
        weather_observations=composition_observations(
            start,
            (0, 2),
            interval_hours=3,
            precipitation_mm=1000,
            et0_mm=1,
        ),
    ).balances[0]

    assert balance.accounting_interval_state is QWB.AccountingIntervalState.GAP
    assert balance.opening_balance_state is QWB.OpeningBalanceState.UNKNOWN
    assert balance.actual_net_deficit_mm is None
    assert QWB.target_state_for_balance(balance) is None


def test_late_missing_hour_allows_one_exact_contiguous_advance() -> None:
    from tests.test_production_recommendation import _evaluation

    start = NOW
    end = start + timedelta(hours=4)
    prior = composition_prior(start)
    evaluation = replace(_evaluation(), evaluated_at=end)
    incomplete = QWB.build_water_balance_snapshot(
        evaluation,
        target_states=(prior,),
        weather_observations=composition_observations(
            start, (0, 1, 3), interval_hours=4
        ),
    ).balances[0]
    assert QWB.target_state_for_balance(incomplete, prior) is None

    recovered = QWB.build_water_balance_snapshot(
        evaluation,
        target_states=(prior,),
        weather_observations=composition_observations(
            start, (0, 1, 2, 3), interval_hours=4
        ),
    ).balances[0]
    recovered_state = QWB.target_state_for_balance(recovered, prior)

    assert recovered.accounting_interval_state is QWB.AccountingIntervalState.COMPLETE
    assert recovered_state is not None
    assert recovered_state.window_start == prior.accounted_through
    assert recovered_state.accounted_through == end
    assert recovered_state.deficit_mm == recovered.actual_net_deficit_mm

    replay = QWB.build_water_balance_snapshot(
        replace(evaluation, evaluated_at=end + timedelta(minutes=5)),
        target_states=(recovered_state,),
        weather_observations=composition_observations(
            start, (0, 1, 2, 3), interval_hours=4
        ),
    ).balances[0]
    assert replay.accounting_interval_state is QWB.AccountingIntervalState.NO_NEW_EVIDENCE
    assert replay.actual_net_deficit_mm == recovered_state.deficit_mm
    assert QWB.target_state_for_balance(replay, recovered_state) is None


def test_forecast_cannot_bootstrap_and_unquantified_watering_invalidates() -> None:
    forecast_only = QWB.calculate_production_area_water_balance(
        request(
            opening_balance_state=QWB.OpeningBalanceState.UNKNOWN,
            opening_deficit_mm=None,
            reference_et_mm=quantity(1),
            observed_precipitation_mm=quantity(0),
            root_zone_available_water_mm=quantity(10),
            forecast=forecast(100),
        )
    )
    assert forecast_only.actual_net_deficit_mm is None
    assert forecast_only.opening_balance_state is QWB.OpeningBalanceState.UNKNOWN

    invalidated = QWB.calculate_production_area_water_balance(
        request(unquantified_irrigation_session_ids=("watering.session.9",))
    )
    state = QWB.target_state_for_balance(invalidated)
    assert state is not None
    assert state.deficit_mm is None
    assert state.state is QWB.OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION
    assert state.accounted_through == NOW
    assert state.invalidated_session_ids == ("watering.session.9",)


def test_unquantified_session_is_consumed_once_and_later_saturation_rebootstraps() -> None:
    from dataclasses import replace

    from tests.test_production_recommendation import _evaluation

    history = load_integration_module("observation_history")
    evaluation = _evaluation()
    end = evaluation.evaluated_at.replace(minute=0)
    start = end - timedelta(hours=1)
    prior = QWB.WaterBalanceTargetState(
        target=TARGET,
        state=QWB.OpeningBalanceState.DURABLE_CARRY_FORWARD,
        window_start=start - timedelta(hours=1),
        accounted_through=start,
        recorded_at=start,
        deficit_mm=quantity(5),
        reason_code="durable_water_balance_carry_forward",
    )
    session = history.WateringSession.from_dict(
        {
            "session_id": "watering.session.native",
            "controller_id": "controller-1",
            "area_id": "area-1",
            "slot_number": 1,
            "area_name": "Zone 1",
            "started_at": (start + timedelta(minutes=10)).isoformat(),
            "ended_at": (start + timedelta(minutes=20)).isoformat(),
            "duration_seconds": 600,
            "state": "inactive",
            "observation_source": "polling",
            "observation_quality": "confirmed",
            "timestamp_precision": "polling_window",
            "attribution": "external_unknown",
            "attribution_confidence": 0.0,
            "attribution_evidence": [],
            "reconstructed_after_restart": False,
            "incomplete": False,
            "first_observed_at": (start + timedelta(minutes=10)).isoformat(),
            "last_observed_at": (start + timedelta(minutes=20)).isoformat(),
        }
    )
    hourly = historical_weather_observation(
        start,
        "ordinary-hour",
        weather_fact(0.0, start),
        weather_fact(1.0, start),
    )
    observations = ObservationWindow(
        window_id="ordinary-window",
        location_id="property-1",
        starts_at=start,
        ends_at=end,
        observations=(hourly,),
    )
    evaluation = replace(evaluation, evaluated_at=end)
    first = QWB.build_water_balance_snapshot(
        evaluation,
        completed_sessions=(session,),
        target_states=(prior,),
        weather_observations=observations,
    ).balances[0]
    invalidated = QWB.target_state_for_balance(first, prior)
    assert invalidated is not None
    assert invalidated.deficit_mm is None

    replay = QWB.build_water_balance_snapshot(
        evaluation,
        completed_sessions=(session,),
        target_states=(invalidated,),
        weather_observations=observations,
    ).balances[0]
    assert replay.unquantified_irrigation_session_ids == ()
    assert QWB.target_state_for_balance(replay, invalidated) is None

    next_end = end + timedelta(hours=1)
    saturating = historical_weather_observation(
        end,
        "saturating-hour",
        weather_fact(1000.0, end),
        weather_fact(1.0, end),
    )
    recovered = QWB.build_water_balance_snapshot(
        replace(evaluation, evaluated_at=next_end),
        completed_sessions=(session,),
        target_states=(invalidated,),
        weather_observations=ObservationWindow(
            window_id="next-window",
            location_id="property-1",
            starts_at=end,
            ends_at=next_end,
            observations=(saturating,),
        ),
    ).balances[0]
    assert recovered.actual_net_deficit_mm == quantity(0)
    assert recovered.opening_balance_state is QWB.OpeningBalanceState.RECONSTRUCTED


def test_generic_policy_is_bounded_and_species_source_remains_explicit() -> None:
    landscape = load_integration_module("landscape")
    generic = QWB.generic_demand_factor(landscape.PlantType.SHRUB)

    assert generic is not None
    assert (generic.minimum, generic.typical, generic.maximum) == (0.3, 0.45, 0.6)
    generic_result = QWB.calculate_production_area_water_balance(
        request(
            plant_factor=generic,
            demand_factor_source=QWB.DemandFactorSource.GENERIC_LANDSCAPE_CLASS,
            demand_factor_confidence=0.55,
        )
    )
    curated_result = QWB.calculate_production_area_water_balance(
        request(
            plant_factor=QWB.RatioQuantity(scalar=0.52),
            demand_factor_source=QWB.DemandFactorSource.CURATED_PLANT_KNOWLEDGE,
            demand_factor_confidence=0.9,
        )
    )
    assert generic_result.demand_factor_source.value == "generic_landscape_class"
    assert generic_result.confidence == 0.55
    assert "generic_landscape_demand_factor_applied" in generic_result.reason_codes
    assert curated_result.plant_factor.scalar == 0.52
    assert curated_result.confidence == 0.8
    assert "curated_plant_demand_factor_applied" in curated_result.reason_codes


def test_soil_root_reservoir_and_establishment_policy_are_deterministic() -> None:
    landscape = load_integration_module("landscape")
    shallow = QWB.root_zone_reservoir(landscape.SoilTexture.SAND, 12)
    deep = QWB.root_zone_reservoir(landscape.SoilTexture.LOAM, 24)
    unknown = QWB.root_zone_reservoir(landscape.SoilTexture.UNKNOWN, 24)
    new = QWB.allowable_depletion_fraction(
        landscape.PlantType.TREE, landscape.EstablishmentStage.NEWLY_PLANTED
    )
    established = QWB.allowable_depletion_fraction(
        landscape.PlantType.TREE, landscape.EstablishmentStage.ESTABLISHED
    )

    assert shallow is not None and deep is not None
    assert shallow.maximum < deep.minimum
    assert unknown is None
    assert new.scalar == 0.2
    assert established.scalar == 0.5


def test_positive_deficit_below_trigger_waits_and_crossing_targets_depth() -> None:
    below = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(3),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=None,
            root_zone_available_water_mm=quantity(20),
            allowable_depletion_fraction=QWB.RatioQuantity(scalar=0.4),
        )
    )
    crossing = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(9),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(0),
            effective_precipitation_policy=None,
            root_zone_available_water_mm=quantity(20),
            allowable_depletion_fraction=QWB.RatioQuantity(scalar=0.4),
        )
    )

    assert below.actual_net_deficit_mm == quantity(3)
    assert below.trigger_state is QWB.IrrigationTriggerState.BELOW_TRIGGER
    assert below.irrigation_indicated is False
    assert below.target_replenishment_depth_mm is None
    assert crossing.trigger_state is QWB.IrrigationTriggerState.AT_OR_ABOVE_TRIGGER
    assert crossing.irrigation_indicated is True
    assert crossing.target_replenishment_depth_mm == quantity(9)
    assert crossing.target_replenishment_depth_mm.scalar <= 20


def test_effective_rain_reduces_deficit_only_through_explicit_policy() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(
            reference_et_mm=quantity(10),
            plant_factor=QWB.RatioQuantity(scalar=1),
            observed_precipitation_mm=quantity(4),
            effective_precipitation_policy=QWB.PRODUCTION_EFFECTIVE_PRECIPITATION_POLICY,
        )
    )

    assert result.effective_observed_precipitation_mm == quantity(2.6)
    assert result.actual_net_deficit_mm == quantity(7.4)
