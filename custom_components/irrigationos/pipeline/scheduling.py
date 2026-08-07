"""Scheduling integration for synchronized pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..planning import PlanExecutionDisposition
from ..scheduling import (
    ScheduleStatus,
    SchedulingPolicy,
    SchedulingRequest,
    build_irrigation_schedule,
)
from .models import AreaPlanningEvaluation, AreaSchedulingEvaluation

_SCHEDULING_POLICY = SchedulingPolicy(
    policy_id="pipeline.conservative-scheduling",
    policy_version="1.0.0",
)


def build_area_schedules(
    planning: tuple[AreaPlanningEvaluation, ...],
    *,
    evaluated_at: datetime,
) -> tuple[AreaSchedulingEvaluation, ...]:
    """Build proposed schedules without inventing permitted watering windows."""
    results: list[AreaSchedulingEvaluation] = []

    for item in planning:
        if item.plan is None:
            results.append(
                AreaSchedulingEvaluation(
                    area_id=item.area_id,
                    schedule=None,
                    blocker_codes=tuple(
                        dict.fromkeys((*item.blocker_codes, "planning_unavailable"))
                    ),
                )
            )
            continue

        schedule = build_irrigation_schedule(
            SchedulingRequest(
                request_id=f"sched:{item.area_id}",
                plan=item.plan,
                windows=(),
                policy=_SCHEDULING_POLICY,
                created_at=evaluated_at,
            )
        )
        blockers = item.blocker_codes
        if any(
            action.disposition is PlanExecutionDisposition.READY
            for action in item.plan.actions
        ):
            blockers = tuple(
                dict.fromkeys((*blockers, "scheduling_window_not_configured"))
            )
        if schedule.status is ScheduleStatus.PARTIAL:
            blockers = tuple(dict.fromkeys((*blockers, "scheduling_partial")))
        elif schedule.status is ScheduleStatus.NOT_SCHEDULABLE:
            blockers = tuple(dict.fromkeys((*blockers, "scheduling_not_schedulable")))

        results.append(
            AreaSchedulingEvaluation(
                area_id=item.area_id,
                schedule=schedule,
                blocker_codes=blockers,
            )
        )

    return tuple(results)
