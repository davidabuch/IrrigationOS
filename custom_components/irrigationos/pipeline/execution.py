"""Execution-simulation integration for synchronized pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..execution import (
    ExecutionPlanStatus,
    ExecutionPolicy,
    ExecutionRequest,
    build_execution_plan,
)
from .models import AreaExecutionEvaluation, AreaSchedulingEvaluation

_EXECUTION_POLICY = ExecutionPolicy(
    policy_id="pipeline.simulation-only-execution",
    policy_version="1.0.0",
)


def build_area_execution_plans(
    scheduling: tuple[AreaSchedulingEvaluation, ...],
    *,
    evaluated_at: datetime,
) -> tuple[AreaExecutionEvaluation, ...]:
    """Build simulated controller-command plans without invoking hardware."""
    results: list[AreaExecutionEvaluation] = []

    for item in scheduling:
        if item.schedule is None:
            results.append(
                AreaExecutionEvaluation(
                    area_id=item.area_id,
                    execution_plan=None,
                    blocker_codes=tuple(
                        dict.fromkeys((*item.blocker_codes, "scheduling_unavailable"))
                    ),
                )
            )
            continue

        execution_plan = build_execution_plan(
            ExecutionRequest(
                request_id=f"exec:{item.area_id}",
                schedule=item.schedule,
                policy=_EXECUTION_POLICY,
                created_at=evaluated_at,
            )
        )
        blockers = item.blocker_codes
        if execution_plan.status is ExecutionPlanStatus.NO_COMMANDS:
            blockers = tuple(dict.fromkeys((*blockers, "execution_no_commands")))
        elif execution_plan.status is ExecutionPlanStatus.PARTIAL:
            blockers = tuple(dict.fromkeys((*blockers, "execution_partial")))
        elif execution_plan.status is ExecutionPlanStatus.BLOCKED:
            blockers = tuple(dict.fromkeys((*blockers, "execution_blocked")))

        results.append(
            AreaExecutionEvaluation(
                area_id=item.area_id,
                execution_plan=execution_plan,
                blocker_codes=blockers,
            )
        )

    return tuple(results)
