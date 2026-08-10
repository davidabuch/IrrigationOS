"""Pure tests for v1.0.19 actual-vs-shadow reconciliation semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.helpers import load_integration_module

MATCHING = load_integration_module("actual_vs_shadow.matching")
MODELS = load_integration_module("actual_vs_shadow.models")

START = datetime(2026, 8, 10, 3, 0, tzinfo=UTC)


def _shadow_record() -> dict[str, object]:
    return {
        "evaluation_id": "eval-1",
        "timestamp_utc": START.isoformat(),
        "payload": {
            "scheduling": {
                "actions": [
                    {
                        "scheduled_action_id": "sched-1",
                        "disposition": "scheduled",
                        "target_id": "controller:slot:1",
                        "starts_at": (START + timedelta(hours=10)).isoformat(),
                        "ends_at": (START + timedelta(hours=10, minutes=20)).isoformat(),
                        "cycle_starts_at": [
                            (START + timedelta(hours=10)).isoformat(),
                            (START + timedelta(hours=10, minutes=10)).isoformat(),
                        ],
                        "cycle_runtime_seconds": 300,
                        "source_action": {"action_type": "irrigate", "runtime_seconds": 600},
                    },
                    {
                        "scheduled_action_id": "inspect-1",
                        "disposition": "scheduled",
                        "target_id": "controller:slot:2",
                        "starts_at": (START + timedelta(hours=11)).isoformat(),
                        "ends_at": (START + timedelta(hours=11, minutes=5)).isoformat(),
                        "cycle_starts_at": [(START + timedelta(hours=11)).isoformat()],
                        "cycle_runtime_seconds": 300,
                        "source_action": {"action_type": "inspect", "runtime_seconds": 300},
                    },
                ]
            }
        },
    }


def test_extracts_only_scheduled_irrigation_and_cycle_runtime() -> None:
    actions = MATCHING.extract_scheduled_irrigation_actions(_shadow_record())
    assert len(actions) == 1
    assert actions[0]["target_id"] == "controller:slot:1"
    assert actions[0]["runtime_seconds"] == 600


def test_close_timing_and_runtime_are_agreement() -> None:
    result = MATCHING.classify_match(
        planned_start=START,
        planned_runtime_seconds=600,
        observed_start=START + timedelta(minutes=5),
        observed_runtime_seconds=620,
        incomplete=False,
        observation_quality="confirmed",
        timestamp_precision="event_bounded",
    )
    assert result["outcome"] == "agreement"
    assert result["confidence"] == "high"


def test_large_timing_or_runtime_difference_is_partial() -> None:
    result = MATCHING.classify_match(
        planned_start=START,
        planned_runtime_seconds=600,
        observed_start=START + timedelta(minutes=30),
        observed_runtime_seconds=900,
        incomplete=False,
        observation_quality="confirmed",
        timestamp_precision="event_bounded",
    )
    assert result["outcome"] == "partial"
    assert "start_timing_difference" in result["reason_codes"]
    assert "runtime_difference" in result["reason_codes"]


def test_incomplete_observation_reduces_confidence() -> None:
    result = MATCHING.classify_match(
        planned_start=START,
        planned_runtime_seconds=600,
        observed_start=START,
        observed_runtime_seconds=600,
        incomplete=True,
        observation_quality="partial",
        timestamp_precision="polling_window",
    )
    assert result["confidence"] == "low"
    assert "observation_incomplete" in result["reason_codes"]


def test_reconciliation_record_is_immutable_contract() -> None:
    record = MODELS.ActualVsShadowRecord(
        comparison_id="comparison",
        kind=MODELS.ReconciliationKind.PLANNED_VS_OBSERVED,
        outcome=MODELS.ReconciliationOutcome.AGREEMENT,
        confidence=MODELS.ReconciliationConfidence.HIGH,
        reason_codes=("planned_zone_observed",),
        reconciled_at_utc=START,
        reconciled_at_local=START,
    )
    payload = record.to_dict()
    assert payload["kind"] == "planned_vs_observed"
    assert payload["outcome"] == "agreement"
    assert payload["schema_version"] == 1
