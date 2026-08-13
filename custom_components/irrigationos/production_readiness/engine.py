"""Pure deterministic production-readiness evaluation."""

from __future__ import annotations

from .models import (
    ProductionReadinessInputs,
    ProductionReadinessState,
    ProductionReadinessSummary,
)

MAX_PRODUCTION_OBSERVATION_AGE_SECONDS = 12 * 60


def evaluate_production_readiness(
    inputs: ProductionReadinessInputs,
) -> ProductionReadinessSummary:
    """Evaluate advisory readiness without persisting or authorizing control."""

    blockers: set[str] = set()
    if inputs.health_state != "HEALTHY":
        blockers.add("system_not_healthy")
    if not inputs.ownership_confirmed:
        blockers.add("controller_ownership_not_confirmed")
    if not inputs.boundary_review_acknowledged:
        blockers.add("execution_boundary_review_not_acknowledged")
    if not inputs.topology_matches:
        blockers.add("controller_topology_mismatch")
    if inputs.observation_age_seconds is None or (
        inputs.observation_age_seconds > MAX_PRODUCTION_OBSERVATION_AGE_SECONDS
    ):
        blockers.add("observation_stale")
    if not inputs.cloud_connection_healthy:
        blockers.add("cloud_connection_unhealthy")
    if not inputs.realtime_observation_healthy:
        blockers.add("realtime_observation_unhealthy")
    if not set(inputs.production_targets).issubset(inputs.validated_targets):
        blockers.add("configured_target_not_validated")
    if not inputs.validated_target_persistence_healthy:
        blockers.add("validated_target_persistence_unhealthy")
    if not inputs.first_live_persistence_healthy:
        blockers.add("first_live_persistence_unhealthy")
    if not inputs.supervised_operation_persistence_healthy:
        blockers.add("supervised_operation_persistence_unhealthy")
    if (
        not inputs.aggregate_persistence_healthy
        or not inputs.ownership_persistence_healthy
        or not inputs.operational_log_healthy
    ):
        blockers.add("critical_persistence_or_runtime_fault")
    if inputs.active_external_watering_count > 0:
        blockers.add("active_watering_conflict")
    if inputs.supervised_operation_in_progress:
        blockers.add("supervised_operation_in_progress")
    if not inputs.safety_prerequisites_met:
        blockers.add("safety_prerequisites_not_met")
    if not inputs.production_targets:
        blockers.add("no_configured_production_targets")

    ordered_blockers = tuple(sorted(blockers))
    canary_blockers = (
        ()
        if inputs.unattended_canary_approval_present
        else ("unattended_canary_approval_required",)
    )
    if ordered_blockers:
        state = ProductionReadinessState.NOT_READY
    elif canary_blockers:
        state = ProductionReadinessState.READY_FOR_SUPERVISED_PRODUCTION
    else:
        state = ProductionReadinessState.READY_FOR_UNATTENDED_CANARY

    return ProductionReadinessSummary(
        state=state,
        evaluated_at=inputs.evaluated_at,
        blocker_codes=ordered_blockers,
        unattended_canary_blocker_codes=canary_blockers,
        production_targets=tuple(sorted(set(inputs.production_targets))),
        validated_targets=tuple(sorted(set(inputs.validated_targets))),
        health_state=inputs.health_state,
        observation_age_seconds=inputs.observation_age_seconds,
        active_external_watering_count=inputs.active_external_watering_count,
        supervised_operation_in_progress=inputs.supervised_operation_in_progress,
        ownership_confirmed=inputs.ownership_confirmed,
        topology_matches=inputs.topology_matches,
        persistence_health={
            "aggregate": inputs.aggregate_persistence_healthy,
            "ownership": inputs.ownership_persistence_healthy,
            "validated_targets": inputs.validated_target_persistence_healthy,
            "first_live_acceptance": inputs.first_live_persistence_healthy,
            "supervised_operation_acceptance": (
                inputs.supervised_operation_persistence_healthy
            ),
            "operational_log": inputs.operational_log_healthy,
        },
    )
