"""Simulation-only deterministic irrigation execution planning."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..scheduling import ScheduledActionDisposition
from .models import (
    CommandOutcome,
    CommandResult,
    ControllerCommand,
    ControllerCommandDisposition,
    ControllerCommandType,
    ExecutionPlan,
    ExecutionPlanStatus,
    ExecutionRequest,
)


def _command(
    *,
    request: ExecutionRequest,
    action_index: int,
    cycle_number: int,
    command_type: ControllerCommandType,
    planned_at: datetime,
    runtime_seconds: int | None,
) -> ControllerCommand:
    action = request.schedule.actions[action_index]
    if action.target_id is None:
        raise ValueError("scheduled execution action is incomplete")
    suffix = "start" if command_type is ControllerCommandType.START_ZONE else "stop"
    key = f"exec:{request.schedule.schedule_id}:{action.plan_action_id}:{cycle_number}:{suffix}"
    disposition = (
        ControllerCommandDisposition.SKIPPED_IDEMPOTENT
        if key.casefold() in request.completed_idempotency_keys
        else ControllerCommandDisposition.READY
    )
    return ControllerCommand(
        command_id=f"command:{request.request_id}:{action_index + 1}:{cycle_number}:{suffix}",
        idempotency_key=key,
        scheduled_action_id=action.scheduled_action_id,
        target_id=action.target_id,
        command_type=command_type,
        disposition=disposition,
        planned_at=planned_at,
        cycle_number=cycle_number,
        runtime_seconds=runtime_seconds,
        acknowledgement_timeout_seconds=request.policy.acknowledgement_timeout_seconds,
        maximum_attempts=request.policy.maximum_attempts,
        retry_delay_seconds=request.policy.retry_delay_seconds,
        attribution_source="irrigationos",
        source_action=action,
    )


def build_execution_plan(request: ExecutionRequest) -> ExecutionPlan:
    """Translate a schedule into simulated commands without invoking hardware."""
    commands: list[ControllerCommand] = []
    unresolved = set(request.schedule.unresolved_issues)
    unresolved.update(request.safety_blocks)

    for action_index, action in enumerate(request.schedule.actions):
        if action.disposition is not ScheduledActionDisposition.SCHEDULED:
            unresolved.add(
                f"{action.scheduled_action_id}: action is {action.disposition.value}"
            )
            continue
        if request.safety_blocks:
            for reason in request.safety_blocks:
                unresolved.add(f"{action.scheduled_action_id}: {reason}")
            continue
        if action.cycle_runtime_seconds is None or action.target_id is None:
            unresolved.add(f"{action.scheduled_action_id}: incomplete scheduled action")
            continue

        for cycle_index, cycle_start in enumerate(action.cycle_starts_at, start=1):
            commands.append(
                _command(
                    request=request,
                    action_index=action_index,
                    cycle_number=cycle_index,
                    command_type=ControllerCommandType.START_ZONE,
                    planned_at=cycle_start,
                    runtime_seconds=action.cycle_runtime_seconds,
                )
            )
            commands.append(
                _command(
                    request=request,
                    action_index=action_index,
                    cycle_number=cycle_index,
                    command_type=ControllerCommandType.STOP_ZONE,
                    planned_at=cycle_start + timedelta(seconds=action.cycle_runtime_seconds),
                    runtime_seconds=None,
                )
            )

    ordered = tuple(sorted(commands, key=lambda item: (item.planned_at, item.command_id)))
    ready_count = sum(
        command.disposition is ControllerCommandDisposition.READY for command in ordered
    )
    if request.safety_blocks:
        status = ExecutionPlanStatus.BLOCKED
    elif not ordered:
        status = ExecutionPlanStatus.NO_COMMANDS
    elif ready_count == len(ordered):
        status = ExecutionPlanStatus.READY
    elif ready_count:
        status = ExecutionPlanStatus.PARTIAL
    else:
        status = ExecutionPlanStatus.NO_COMMANDS

    return ExecutionPlan(
        execution_plan_id=f"execution-plan:{request.request_id}",
        request_id=request.request_id,
        schedule_id=request.schedule.schedule_id,
        status=status,
        commands=ordered,
        unresolved_issues=tuple(sorted(unresolved)),
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        created_at=request.created_at,
        source_schedule=request.schedule,
    )


def evaluate_command_outcome(
    command: ControllerCommand,
    *,
    acknowledged: bool,
    attempt_number: int,
    observed_at: datetime,
    rejected_reason: str | None = None,
) -> CommandResult:
    """Model an acknowledgement, retry, timeout, or rejection deterministically."""
    if rejected_reason is not None:
        outcome = CommandOutcome.REJECTED
    elif acknowledged:
        outcome = CommandOutcome.ACKNOWLEDGED
    elif attempt_number < command.maximum_attempts:
        outcome = CommandOutcome.RETRY_REQUIRED
    else:
        outcome = CommandOutcome.TIMED_OUT
    return CommandResult(
        command_id=command.command_id,
        idempotency_key=command.idempotency_key,
        outcome=outcome,
        attempt_number=attempt_number,
        observed_at=observed_at,
        reason=rejected_reason,
    )
