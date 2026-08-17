"""Tests for immutable shadow-evaluation evidence and deduplication primitives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from tests.helpers import load_integration_module

MODELS = load_integration_module("shadow_evaluation.models")


class ExampleEnum(StrEnum):
    VALUE = "value"


@dataclass(frozen=True)
class Example:
    area_id: str
    native_id: str
    serial_number: str
    value: ExampleEnum
    when: datetime


def test_jsonable_preserves_canonical_context_but_removes_provider_secrets() -> None:
    payload = MODELS.jsonable(
        Example(
            area_id="controller:slot:1",
            native_id="provider-secret",
            serial_number="serial-secret",
            value=ExampleEnum.VALUE,
            when=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        )
    )
    assert payload["area_id"] == "controller:slot:1"
    assert payload["value"] == "value"
    assert payload["when"] == "2026-08-09T20:00:00+00:00"
    assert "native_id" not in payload
    assert "serial_number" not in payload


def test_section_hash_is_deterministic_and_semantic() -> None:
    first = MODELS.semantic_value({"b": 2, "a": 1})
    second = MODELS.semantic_value({"a": 1, "b": 2})
    changed = MODELS.semantic_value({"a": 1, "b": 3})
    assert first == second
    assert first != changed


def test_shadow_contract_is_immutable() -> None:
    record = MODELS.ShadowEvaluationRecord(
        schema_version=1,
        evaluation_id="abc",
        reason=MODELS.ShadowEvaluationReason.NIGHTLY,
        timestamp_utc=datetime(2026, 8, 10, 3, 0, tzinfo=UTC),
        timestamp_local=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        integration_version="1.0.18",
        pipeline_algorithm_version="1.0.10",
        decision_fingerprint="fingerprint",
        payload={},
    )
    assert record.reason.value == "nightly"


def test_current_shadow_schema_is_two_while_legacy_records_remain_data() -> None:
    assert MODELS.SHADOW_EVALUATION_SCHEMA_VERSION == 2
    legacy = MODELS.ShadowEvaluationRecord(
        schema_version=1,
        evaluation_id="legacy",
        reason=MODELS.ShadowEvaluationReason.DECISION_CHANGE,
        timestamp_utc=datetime(2026, 8, 10, 3, 0, tzinfo=UTC),
        timestamp_local=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        integration_version="1.0.43",
        pipeline_algorithm_version="1.0.10",
        decision_fingerprint="legacy-fingerprint",
        payload={"scheduling": []},
    )
    assert legacy.schema_version == 1


def _decision(**changes: object) -> dict[str, object]:
    recommendation = {
        "target": {"controller_slot": 1, "area_slot": 1},
        "state": "irrigation_recommended",
        "scientific_need": "indicated",
        "calculated_at": "2026-08-17T12:00:00+00:00",
        "valid_until": "2026-08-17T12:15:00+00:00",
        "evidence": [
            {
                "kind": "controller_observation",
                "status": "confirmed",
                "observed_at": "2026-08-17T12:00:00+00:00",
            },
            {
                "kind": "weather_observation",
                "status": "available",
                "observed_at": "2026-08-17T11:45:00+00:00",
            },
        ],
    }
    balance = {
        "target": {"controller_slot": 1, "area_slot": 1},
        "window_start": "2026-08-16T12:00:00+00:00",
        "window_end": "2026-08-17T12:00:00+00:00",
        "calculated_at": "2026-08-17T12:00:00+00:00",
        "valid_until": "2026-08-17T12:15:00+00:00",
        "observed_precipitation_mm": {"scalar": 2.0, "unit": "millimeters"},
        "actual_net_deficit_mm": {"scalar": 8.0, "unit": "millimeters"},
        "forecast_precipitation_mm": {"scalar": 10.0, "unit": "millimeters"},
        "forecast_window_start": "2026-08-18T00:00:00+00:00",
        "forecast_window_end": "2026-08-18T12:00:00+00:00",
    }
    payload: dict[str, object] = {
        "production_recommendations": {
            "calculated_at": "2026-08-17T12:00:00+00:00",
            "recommendations": [recommendation],
        },
        "quantitative_water_balances": {
            "calculated_at": "2026-08-17T12:00:00+00:00",
            "balances": [balance],
        },
    }
    payload.update(changes)
    return payload


def _fingerprint(value: object) -> str:
    projected = MODELS.semantic_decision_value(value)
    canonical = json.dumps(projected, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_decision_projection_ignores_only_derived_evaluation_timing() -> None:
    first = _decision()
    shifted = _decision()
    shifted_recommendations = shifted["production_recommendations"]
    shifted_balances = shifted["quantitative_water_balances"]
    assert isinstance(shifted_recommendations, dict)
    assert isinstance(shifted_balances, dict)
    shifted_recommendations["calculated_at"] = "2026-08-17T12:05:00+00:00"
    recommendation = shifted_recommendations["recommendations"][0]
    assert isinstance(recommendation, dict)
    recommendation["calculated_at"] = "2026-08-17T12:05:00+00:00"
    recommendation["valid_until"] = "2026-08-17T12:20:00+00:00"
    shifted_balances["calculated_at"] = "2026-08-17T12:05:00+00:00"
    balance = shifted_balances["balances"][0]
    assert isinstance(balance, dict)
    balance["window_start"] = "2026-08-16T12:05:00+00:00"
    balance["window_end"] = "2026-08-17T12:05:00+00:00"
    balance["calculated_at"] = "2026-08-17T12:05:00+00:00"
    balance["valid_until"] = "2026-08-17T12:20:00+00:00"

    assert _fingerprint(first) == _fingerprint(shifted)


def test_decision_projection_retains_scientific_and_target_changes() -> None:
    baseline = _decision()
    changed_recommendation = _decision()
    recommendations = changed_recommendation["production_recommendations"]
    assert isinstance(recommendations, dict)
    recommendations["recommendations"][0]["scientific_need"] = "not_indicated"

    changed_target = _decision()
    target_recommendations = changed_target["production_recommendations"]
    target_balances = changed_target["quantitative_water_balances"]
    assert isinstance(target_recommendations, dict)
    assert isinstance(target_balances, dict)
    target_recommendations["recommendations"][0]["target"]["area_slot"] = 2
    target_balances["balances"][0]["target"]["area_slot"] = 2

    assert _fingerprint(baseline) != _fingerprint(changed_recommendation)
    assert _fingerprint(baseline) != _fingerprint(changed_target)


def test_decision_projection_retains_water_and_forecast_evidence() -> None:
    baseline = _decision()
    changed_forecast = _decision()
    changed_precipitation = _decision()
    changed_deficit = _decision()
    for payload, field, value in (
        (changed_forecast, "forecast_precipitation_mm", 12.0),
        (changed_precipitation, "observed_precipitation_mm", 3.0),
        (changed_deficit, "actual_net_deficit_mm", 6.0),
    ):
        balances = payload["quantitative_water_balances"]
        assert isinstance(balances, dict)
        balances["balances"][0][field]["scalar"] = value

    assert _fingerprint(baseline) != _fingerprint(changed_forecast)
    assert _fingerprint(baseline) != _fingerprint(changed_precipitation)
    assert _fingerprint(baseline) != _fingerprint(changed_deficit)


def test_forecast_windows_remain_semantic_while_accounting_windows_do_not() -> None:
    baseline = _decision()
    changed = _decision()
    balances = changed["quantitative_water_balances"]
    assert isinstance(balances, dict)
    balances["balances"][0]["forecast_window_end"] = "2026-08-19T12:00:00+00:00"
    assert _fingerprint(baseline) != _fingerprint(changed)


def test_source_weather_observation_time_remains_semantic() -> None:
    baseline = _decision()
    refreshed_weather = _decision()
    recommendations = refreshed_weather["production_recommendations"]
    assert isinstance(recommendations, dict)
    recommendations["recommendations"][0]["evidence"][1]["observed_at"] = (
        "2026-08-17T12:05:00+00:00"
    )

    assert _fingerprint(baseline) != _fingerprint(refreshed_weather)


def test_routine_controller_poll_time_alone_does_not_defeat_deduplication() -> None:
    baseline = _decision()
    refreshed_controller = _decision()
    recommendations = refreshed_controller["production_recommendations"]
    assert isinstance(recommendations, dict)
    recommendations["recommendations"][0]["evidence"][0]["observed_at"] = (
        "2026-08-17T12:05:00+00:00"
    )

    assert _fingerprint(baseline) == _fingerprint(refreshed_controller)


def test_freshness_policy_transition_remains_semantic() -> None:
    baseline = _decision()
    stale = _decision()
    recommendations = stale["production_recommendations"]
    assert isinstance(recommendations, dict)
    recommendation = recommendations["recommendations"][0]
    recommendation["evidence"][1]["status"] = "stale"
    recommendation["blocker_codes"] = ["weather_observation_stale"]

    assert _fingerprint(baseline) != _fingerprint(stale)
