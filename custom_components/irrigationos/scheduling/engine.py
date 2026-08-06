"""Deterministic conversion of irrigation plans into proposed schedules."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..planning import PlanExecutionDisposition
from .models import (
    IrrigationSchedule,
    ScheduledAction,
    ScheduledActionDisposition,
    ScheduleStatus,
    SchedulingRequest,
    SchedulingWindow,
)


def _fit_action(
    *,
    earliest: datetime,
    runtime_seconds: int,
    cycle_count: int,
    soak_seconds: int,
    windows: tuple[SchedulingWindow, ...],
) -> tuple[datetime, datetime, tuple[datetime, ...], int, str] | None:
    cycle_runtime = runtime_seconds // cycle_count
    remainder = runtime_seconds % cycle_count
    total_duration = runtime_seconds + soak_seconds * (cycle_count - 1)
    for window in windows:
        start = max(earliest, window.starts_at)
        end = start + timedelta(seconds=total_duration)
        if end > window.ends_at:
            continue
        cycle_starts: list[datetime] = []
        cursor = start
        for index in range(cycle_count):
            cycle_starts.append(cursor)
            current_runtime = cycle_runtime + (1 if index < remainder else 0)
            cursor += timedelta(seconds=current_runtime)
            if index < cycle_count - 1:
                cursor += timedelta(seconds=soak_seconds)
        return start, end, tuple(cycle_starts), cycle_runtime, window.window_id
    return None


def build_irrigation_schedule(request: SchedulingRequest) -> IrrigationSchedule:
    """Schedule plan actions without issuing hardware commands or changing the plan."""
    unresolved = set(request.plan.unresolved_issues)
    unresolved.update(request.blocking_constraints)
    actions: list[ScheduledAction] = []
    earliest = request.created_at

    for action in request.plan.actions:
        reasons = set(action.blocking_reasons)
        if request.blocking_constraints:
            reasons.update(request.blocking_constraints)

        if action.disposition is PlanExecutionDisposition.BLOCKED:
            disposition = ScheduledActionDisposition.BLOCKED
        elif action.disposition is PlanExecutionDisposition.MANUAL_ONLY:
            disposition = ScheduledActionDisposition.MANUAL_ONLY
        elif action.runtime_seconds is None:
            disposition = ScheduledActionDisposition.BLOCKED
            reasons.add("missing runtime for scheduling")
        elif request.blocking_constraints:
            disposition = ScheduledActionDisposition.BLOCKED
        else:
            match = _fit_action(
                earliest=earliest,
                runtime_seconds=action.runtime_seconds,
                cycle_count=action.cycle_count,
                soak_seconds=action.soak_seconds,
                windows=request.windows,
            )
            if match is None:
                disposition = ScheduledActionDisposition.BLOCKED
                reasons.add("no permitted window can fit action")
            else:
                starts_at, ends_at, cycle_starts, cycle_runtime, window_id = match
                scheduled = ScheduledAction(
                    scheduled_action_id=f"scheduled-action:{request.request_id}:{action.action_id}",
                    plan_action_id=action.action_id,
                    disposition=ScheduledActionDisposition.SCHEDULED,
                    target_id=action.target_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    cycle_starts_at=cycle_starts,
                    cycle_runtime_seconds=cycle_runtime,
                    window_id=window_id,
                    blocking_reasons=(),
                    source_action=action,
                )
                actions.append(scheduled)
                earliest = ends_at + timedelta(
                    seconds=request.policy.minimum_inter_action_seconds
                )
                continue

        for reason in reasons:
            unresolved.add(f"{action.action_id}: {reason}")
        actions.append(
            ScheduledAction(
                scheduled_action_id=f"scheduled-action:{request.request_id}:{action.action_id}",
                plan_action_id=action.action_id,
                disposition=disposition,
                target_id=action.target_id,
                starts_at=None,
                ends_at=None,
                cycle_starts_at=(),
                cycle_runtime_seconds=None,
                window_id=None,
                blocking_reasons=tuple(sorted(reasons)),
                source_action=action,
            )
        )

    actions_tuple = tuple(sorted(actions, key=lambda item: item.scheduled_action_id))
    if actions_tuple and all(
        action.disposition is ScheduledActionDisposition.SCHEDULED
        for action in actions_tuple
    ):
        status = ScheduleStatus.READY
    elif any(
        action.disposition is not ScheduledActionDisposition.BLOCKED
        for action in actions_tuple
    ):
        status = ScheduleStatus.PARTIAL
    else:
        status = ScheduleStatus.NOT_SCHEDULABLE

    return IrrigationSchedule(
        schedule_id=f"schedule:{request.request_id}",
        request_id=request.request_id,
        plan_id=request.plan.plan_id,
        status=status,
        actions=actions_tuple,
        unresolved_issues=tuple(sorted(unresolved)),
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        created_at=request.created_at,
    )
