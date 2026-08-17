"""Behavioral tests for v1.0.45 quantitative water-balance semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
    }
    values.update(changes)
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


def test_actual_balance_uses_only_occurred_water() -> None:
    result = QWB.calculate_production_area_water_balance(
        request(forecast=forecast())
    )

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
        request(
            plant_factor=QWB.RatioQuantity(minimum=0.3, typical=0.5, maximum=0.7)
        )
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


def test_carried_balance_requires_an_exactly_adjacent_evidence_window() -> None:
    prior = deferral()
    adjacent = QWB.calculate_production_area_water_balance(request(ledger_events=(prior,)))
    assert adjacent.actual_net_deficit_mm == quantity(11.82)

    for start, message in (
        (NOW - timedelta(days=1, minutes=1), "overlaps"),
        (NOW - timedelta(days=1) + timedelta(minutes=1), "gap"),
    ):
        with pytest.raises(ValueError, match=message):
            request(window_start=start, ledger_events=(prior,))


def test_overlapping_et_precipitation_and_replayed_windows_are_rejected() -> None:
    prior = deferral()
    overlap = NOW - timedelta(days=1, hours=1)

    with pytest.raises(ValueError, match="overlaps"):
        request(
            window_start=overlap,
            reference_et_mm=quantity(3),
            observed_precipitation_mm=quantity(0),
            ledger_events=(prior,),
        )
    with pytest.raises(ValueError, match="overlaps"):
        request(
            window_start=overlap,
            reference_et_mm=quantity(0),
            observed_precipitation_mm=quantity(3),
            ledger_events=(prior,),
        )

    first = QWB.calculate_production_area_water_balance(
        request(
            forecast_window_observed_precipitation_mm=quantity(0),
            ledger_events=(prior,),
        )
    )
    reconciliation = QWB.reconciliation_event_for_balance(first, prior)
    assert reconciliation is not None
    with pytest.raises(ValueError, match="overlaps"):
        request(ledger_events=(prior, reconciliation))


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
    deferral_event = QWB.deferral_event_for_balance(
        initial, "weather.forecast.demo"
    )
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
    assert reconciliation_balance.actual_net_deficit_mm == quantity(
        reconciled_deficit
    )
    reconciliation_event = QWB.reconciliation_event_for_balance(
        reconciliation_balance, deferral_event
    )
    assert reconciliation_event is not None

    restored_event = QWB.WaterBalanceLedgerEvent.from_dict(
        reconciliation_event.to_dict()
    )
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

    et0, rain, future, evidence = QWB.canonical_weather_balance_evidence(
        observations, forecasts
    )

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
