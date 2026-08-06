"""Behavioral tests for the simulation-only Execution Engine."""
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast

from tests.helpers import load_integration_module
from tests.test_scheduling import schedule_request

EXECUTION = load_integration_module("execution")
SCHEDULING = load_integration_module("scheduling")


def ready_schedule() -> Any:
    return SCHEDULING.build_irrigation_schedule(schedule_request())


def execution_request(
    *,
    schedule: Any | None = None,
    safety_blocks: tuple[str, ...] = (),
    completed_keys: tuple[str, ...] = (),
) -> Any:
    current = ready_schedule() if schedule is None else schedule
    return EXECUTION.ExecutionRequest(
        request_id="execution-request-1",
        schedule=current,
        policy=EXECUTION.ExecutionPolicy(
            policy_id="execution-policy",
            policy_version="1.0.0",
            acknowledgement_timeout_seconds=30,
            maximum_attempts=3,
            retry_delay_seconds=15,
        ),
        created_at=current.created_at,
        safety_blocks=safety_blocks,
        completed_idempotency_keys=completed_keys,
    )


def test_ready_schedule_builds_start_and_stop_commands() -> None:
    plan = EXECUTION.build_execution_plan(execution_request())
    assert plan.status is EXECUTION.ExecutionPlanStatus.READY
    assert len(plan.commands) == 6
    assert plan.commands[0].command_type is EXECUTION.ControllerCommandType.START_ZONE
    assert plan.commands[1].command_type is EXECUTION.ControllerCommandType.STOP_ZONE


def test_commands_preserve_cycle_timing() -> None:
    plan = EXECUTION.build_execution_plan(execution_request())
    first_start, first_stop, second_start = plan.commands[:3]
    assert first_stop.planned_at - first_start.planned_at == timedelta(seconds=600)
    assert second_start.planned_at - first_start.planned_at == timedelta(seconds=1200)


def test_commands_have_stable_attribution_and_provenance() -> None:
    schedule = ready_schedule()
    plan = EXECUTION.build_execution_plan(execution_request(schedule=schedule))
    assert plan.source_schedule == schedule
    assert plan.commands[0].source_action == schedule.actions[0]
    assert plan.commands[0].attribution_source == "irrigationos"


def test_same_request_produces_same_command_identifiers() -> None:
    request = execution_request()
    first = EXECUTION.build_execution_plan(request)
    second = EXECUTION.build_execution_plan(request)
    assert tuple(command.command_id for command in first.commands) == tuple(
        command.command_id for command in second.commands
    )
    assert tuple(command.idempotency_key for command in first.commands) == tuple(
        command.idempotency_key for command in second.commands
    )


def test_completed_idempotency_key_is_skipped() -> None:
    initial = EXECUTION.build_execution_plan(execution_request())
    completed = (initial.commands[0].idempotency_key,)
    plan = EXECUTION.build_execution_plan(execution_request(completed_keys=completed))
    assert plan.status is EXECUTION.ExecutionPlanStatus.PARTIAL
    assert plan.commands[0].disposition is EXECUTION.ControllerCommandDisposition.SKIPPED_IDEMPOTENT


def test_all_completed_commands_produce_no_commands_status() -> None:
    initial = EXECUTION.build_execution_plan(execution_request())
    completed = tuple(sorted(command.idempotency_key for command in initial.commands))
    plan = EXECUTION.build_execution_plan(execution_request(completed_keys=completed))
    assert plan.status is EXECUTION.ExecutionPlanStatus.NO_COMMANDS


def test_safety_block_prevents_command_generation() -> None:
    plan = EXECUTION.build_execution_plan(
        execution_request(safety_blocks=("freeze interlock",))
    )
    assert plan.status is EXECUTION.ExecutionPlanStatus.BLOCKED
    assert plan.commands == ()
    assert "freeze interlock" in plan.unresolved_issues


def test_unscheduled_actions_do_not_generate_commands() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(
        schedule_request(blocking_constraints=("weather delay",))
    )
    plan = EXECUTION.build_execution_plan(execution_request(schedule=schedule))
    assert plan.status is EXECUTION.ExecutionPlanStatus.NO_COMMANDS
    assert plan.commands == ()


def test_acknowledgement_is_modeled() -> None:
    command = EXECUTION.build_execution_plan(execution_request()).commands[0]
    result = EXECUTION.evaluate_command_outcome(
        command,
        acknowledged=True,
        attempt_number=1,
        observed_at=command.planned_at,
    )
    assert result.outcome is EXECUTION.CommandOutcome.ACKNOWLEDGED


def test_failed_attempt_requests_retry_before_limit() -> None:
    command = EXECUTION.build_execution_plan(execution_request()).commands[0]
    result = EXECUTION.evaluate_command_outcome(
        command,
        acknowledged=False,
        attempt_number=2,
        observed_at=command.planned_at,
    )
    assert result.outcome is EXECUTION.CommandOutcome.RETRY_REQUIRED


def test_final_failed_attempt_times_out() -> None:
    command = EXECUTION.build_execution_plan(execution_request()).commands[0]
    result = EXECUTION.evaluate_command_outcome(
        command,
        acknowledged=False,
        attempt_number=3,
        observed_at=command.planned_at,
    )
    assert result.outcome is EXECUTION.CommandOutcome.TIMED_OUT


def test_rejection_reason_has_priority() -> None:
    command = EXECUTION.build_execution_plan(execution_request()).commands[0]
    result = EXECUTION.evaluate_command_outcome(
        command,
        acknowledged=False,
        attempt_number=1,
        observed_at=command.planned_at,
        rejected_reason="controller offline",
    )
    assert result.outcome is EXECUTION.CommandOutcome.REJECTED
    assert result.reason == "controller offline"


def test_execution_serialization_is_deterministic() -> None:
    plan = EXECUTION.build_execution_plan(execution_request())
    assert plan.to_dict() == plan.to_dict()
    assert plan.to_dict()["status"] == "ready"


def test_execution_models_are_immutable() -> None:
    plan = EXECUTION.build_execution_plan(execution_request())
    try:
        cast(Any, plan).status = EXECUTION.ExecutionPlanStatus.BLOCKED
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("execution model was mutable")


def test_request_rejects_untyped_schedule() -> None:
    try:
        replace(execution_request(), schedule={})
    except ValueError as error:
        assert "IrrigationSchedule" in str(error)
    else:
        raise AssertionError("invalid schedule was accepted")


def test_policy_rejects_invalid_retry_values() -> None:
    try:
        EXECUTION.ExecutionPolicy("policy", "1.0.0", maximum_attempts=0)
    except ValueError as error:
        assert "positive integer" in str(error)
    else:
        raise AssertionError("invalid retry policy was accepted")


def test_completed_keys_require_deterministic_ordering() -> None:
    try:
        replace(execution_request(), completed_idempotency_keys=("z", "a"))
    except ValueError as error:
        assert "deterministic" in str(error)
    else:
        raise AssertionError("unordered idempotency keys were accepted")
