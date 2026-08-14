"""Behavioral tests for the deterministic production-readiness gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.helpers import load_integration_module

readiness = load_integration_module("production_readiness")

ProductionReadinessInputs = readiness.ProductionReadinessInputs
ProductionReadinessState = readiness.ProductionReadinessState
ProductionTarget = readiness.ProductionTarget
evaluate_production_readiness = readiness.evaluate_production_readiness

NOW = datetime(2026, 8, 13, 15, 0, tzinfo=UTC)
TARGETS = tuple(ProductionTarget(1, slot) for slot in (1, 2, 4, 5))


def _ready_inputs(**overrides: object) -> object:
    values: dict[str, object] = {
        "evaluated_at": NOW,
        "health_state": "HEALTHY",
        "observation_age_seconds": 30,
        "cloud_connection_healthy": True,
        "realtime_observation_healthy": True,
        "ownership_confirmed": True,
        "boundary_review_acknowledged": True,
        "topology_matches": True,
        "ownership_persistence_healthy": True,
        "production_targets": TARGETS,
        "validated_targets": TARGETS,
        "validated_target_persistence_healthy": True,
        "first_live_persistence_healthy": True,
        "supervised_operation_persistence_healthy": True,
        "aggregate_persistence_healthy": True,
        "operational_log_healthy": True,
        "active_external_watering_count": 0,
        "supervised_operation_in_progress": False,
        "safety_prerequisites_met": True,
        "unattended_canary_approval_present": False,
    }
    values.update(overrides)
    return ProductionReadinessInputs(**values)


def test_all_prerequisites_reach_supervised_production_only() -> None:
    summary = evaluate_production_readiness(_ready_inputs())
    assert summary.state is ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
    assert summary.blocker_codes == ()
    assert summary.unattended_canary_blocker_codes == (
        "unattended_canary_approval_required",
    )
    assert summary.production_target_count == 4
    assert summary.validated_production_target_count == 4
    assert summary.live_control_authorized is False


def test_unattended_canary_requires_explicit_additional_prerequisite() -> None:
    summary = evaluate_production_readiness(
        _ready_inputs(unattended_canary_approval_present=True)
    )
    assert summary.state is ProductionReadinessState.READY_FOR_UNATTENDED_CANARY
    assert summary.unattended_canary_blocker_codes == ()
    assert summary.live_control_authorized is False


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"health_state": "INITIALIZING"}, "system_not_healthy"),
        ({"health_state": "UNHEALTHY"}, "system_not_healthy"),
        ({"ownership_confirmed": False}, "controller_ownership_not_confirmed"),
        ({"topology_matches": False}, "controller_topology_mismatch"),
        ({"observation_age_seconds": 721}, "observation_stale"),
        ({"cloud_connection_healthy": False}, "cloud_connection_unhealthy"),
        ({"realtime_observation_healthy": False}, "realtime_observation_unhealthy"),
        (
            {"validated_targets": TARGETS[:-1]},
            "configured_target_not_validated",
        ),
        (
            {"validated_target_persistence_healthy": False},
            "validated_target_persistence_unhealthy",
        ),
        (
            {"first_live_persistence_healthy": False},
            "first_live_persistence_unhealthy",
        ),
        (
            {"supervised_operation_persistence_healthy": False},
            "supervised_operation_persistence_unhealthy",
        ),
        ({"active_external_watering_count": 1}, "active_watering_conflict"),
        ({"supervised_operation_in_progress": True}, "supervised_operation_in_progress"),
        ({"unattended_canary_in_progress": True}, "unattended_canary_in_progress"),
        (
            {"unattended_canary_persistence_healthy": False},
            "unattended_canary_persistence_unhealthy",
        ),
        ({"safety_prerequisites_met": False}, "safety_prerequisites_not_met"),
    ],
)
def test_each_required_failure_is_fail_closed(
    overrides: dict[str, object], blocker: str
) -> None:
    summary = evaluate_production_readiness(_ready_inputs(**overrides))
    assert summary.state is ProductionReadinessState.NOT_READY
    assert blocker in summary.blocker_codes


def test_unused_slots_do_not_enter_target_set_or_block_readiness() -> None:
    summary = evaluate_production_readiness(_ready_inputs())
    assert [target.area_slot for target in summary.production_targets] == [1, 2, 4, 5]
    assert 3 not in {target.area_slot for target in summary.production_targets}
    assert 16 not in {target.area_slot for target in summary.production_targets}
    assert summary.state is ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION


def test_blocker_order_and_serialization_are_deterministic() -> None:
    inputs = _ready_inputs(
        health_state="INITIALIZING",
        ownership_confirmed=False,
        validated_targets=(),
    )
    first = evaluate_production_readiness(inputs)
    second = evaluate_production_readiness(inputs)
    assert first == second
    assert first.blocker_codes == tuple(sorted(first.blocker_codes))
    assert first.to_dict() == second.to_dict()
    assert "native" not in repr(first.to_dict()).lower()


def test_restart_initializing_never_restores_ready_state() -> None:
    before_restart = evaluate_production_readiness(_ready_inputs())
    after_restart = evaluate_production_readiness(
        _ready_inputs(
            health_state="INITIALIZING",
            observation_age_seconds=None,
            cloud_connection_healthy=False,
            realtime_observation_healthy=False,
            safety_prerequisites_met=False,
        )
    )
    assert before_restart.production_ready is True
    assert after_restart.state is ProductionReadinessState.NOT_READY
    assert after_restart.production_ready is False
