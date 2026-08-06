"""Deterministic conversion of recommendations into machine-readable plans."""
from __future__ import annotations

from ..recommendations import RecommendationCategory, RecommendationSafetyFlag
from .models import (
    IrrigationPlan,
    PlanAction,
    PlanActionType,
    PlanExecutionDisposition,
    PlanningDirective,
    PlanningRequest,
    PlanStatus,
)

_ACTION_TYPES = {
    RecommendationCategory.ADJUST_IRRIGATION: PlanActionType.IRRIGATE,
    RecommendationCategory.INSPECT: PlanActionType.INSPECT,
    RecommendationCategory.MONITOR: PlanActionType.MONITOR,
    RecommendationCategory.NO_ACTION: PlanActionType.NO_ACTION,
    RecommendationCategory.PROTECT_FROM_FREEZE: PlanActionType.PROTECT_FROM_FREEZE,
    RecommendationCategory.PROTECT_FROM_HEAT: PlanActionType.PROTECT_FROM_HEAT,
    RecommendationCategory.SEEK_EXPERT_REVIEW: PlanActionType.SEEK_EXPERT_REVIEW,
}


def _directive_map(request: PlanningRequest) -> dict[str, PlanningDirective]:
    return {item.recommendation_id: item for item in request.directives}


def build_irrigation_plan(request: PlanningRequest) -> IrrigationPlan:
    """Build a plan without scheduling, hardware commands, or invented facts."""
    directives = _directive_map(request)
    recommendation_ids = {
        item.recommendation_id for item in request.recommendations.recommendations
    }
    unresolved = set(request.recommendations.unresolved_issues)
    for directive_id in directives.keys() - recommendation_ids:
        unresolved.add(f"directive references unknown recommendation {directive_id}")

    actions: list[PlanAction] = []
    for recommendation in request.recommendations.recommendations:
        directive = directives.get(recommendation.recommendation_id)
        action_type = _ACTION_TYPES[recommendation.category]
        blocking: set[str] = set()
        target_id = directive.target_id if directive else None
        quantity = directive.quantity if directive else None
        quantity_unit = directive.quantity_unit if directive else None
        runtime_seconds = directive.runtime_seconds if directive else None
        cycle_count = directive.cycle_count if directive else 1
        soak_seconds = directive.soak_seconds if directive else 0

        if action_type is PlanActionType.IRRIGATE:
            if directive is None:
                blocking.add("missing planning directive")
                blocking.add("missing target")
                blocking.add("missing irrigation quantity")
            else:
                if quantity is None:
                    blocking.add("missing irrigation quantity")
                if (
                    request.policy.require_runtime_for_automatic_execution
                    and runtime_seconds is None
                ):
                    blocking.add("missing calculated runtime")

        safety_constraints = {flag.value for flag in recommendation.safety_flags}
        no_auto = (
            RecommendationSafetyFlag.NO_AUTOMATIC_EXECUTION
            in recommendation.safety_flags
        )
        if blocking:
            disposition = PlanExecutionDisposition.BLOCKED
        elif no_auto or action_type is not PlanActionType.IRRIGATE:
            disposition = PlanExecutionDisposition.MANUAL_ONLY
        else:
            disposition = PlanExecutionDisposition.READY

        for reason in blocking:
            unresolved.add(f"{recommendation.recommendation_id}: {reason}")

        actions.append(
            PlanAction(
                action_id=(
                    f"plan-action:{request.request_id}:"
                    f"{recommendation.recommendation_id}"
                ),
                recommendation_id=recommendation.recommendation_id,
                action_type=action_type,
                disposition=disposition,
                target_id=target_id,
                quantity=quantity,
                quantity_unit=quantity_unit,
                runtime_seconds=runtime_seconds,
                cycle_count=cycle_count,
                soak_seconds=soak_seconds,
                preconditions=recommendation.preconditions,
                safety_constraints=tuple(sorted(safety_constraints)),
                blocking_reasons=tuple(sorted(blocking)),
                supporting_assessment_ids=recommendation.supporting_assessment_ids,
            )
        )

    actions_tuple = tuple(sorted(actions, key=lambda item: item.action_id))
    if actions_tuple and all(
        item.disposition is PlanExecutionDisposition.READY for item in actions_tuple
    ):
        status = PlanStatus.READY
    elif any(
        item.disposition is not PlanExecutionDisposition.BLOCKED
        for item in actions_tuple
    ):
        status = PlanStatus.PARTIAL
    else:
        status = PlanStatus.NOT_EXECUTABLE

    return IrrigationPlan(
        plan_id=f"plan:{request.request_id}",
        request_id=request.request_id,
        recommendation_assessment_id=request.recommendations.assessment_id,
        status=status,
        actions=actions_tuple,
        unresolved_issues=tuple(sorted(unresolved)),
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        created_at=request.created_at,
    )
