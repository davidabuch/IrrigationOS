"""Behavioral tests for deterministic Runtime Monitoring."""
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast

from tests.helpers import load_integration_module
from tests.test_execution import execution_request

EXECUTION = load_integration_module("execution")
RUNTIME = load_integration_module("runtime_monitoring")


def execution_plan() -> Any:
    return EXECUTION.build_execution_plan(execution_request())


def result_for(command: Any, outcome: Any, *, attempt: int = 1, reason: str | None = None) -> Any:
    return EXECUTION.CommandResult(
        command_id=command.command_id,
        idempotency_key=command.idempotency_key,
        outcome=outcome,
        attempt_number=attempt,
        observed_at=command.planned_at,
        reason=reason,
    )


def runtime_request(
    *,
    plan: Any | None = None,
    results: tuple[Any, ...] = (),
    online: bool = True,
    interrupted: bool = False,
    interruption_reason: str | None = None,
    observed_offset_seconds: int = 0,
) -> Any:
    current = execution_plan() if plan is None else plan
    observed_at = min(command.planned_at for command in current.commands) + timedelta(
        seconds=observed_offset_seconds
    ) if current.commands else current.created_at
    return RUNTIME.RuntimeMonitoringRequest(
        request_id="runtime-request-1",
        execution_plan=current,
        command_results=results,
        observation=RUNTIME.RuntimeObservation(
            observation_id="runtime-observation-1",
            observed_at=observed_at,
            controller_online=online,
            interrupted=interrupted,
            interruption_reason=interruption_reason,
        ),
        policy=RUNTIME.RuntimePolicy(
            policy_id="runtime-policy",
            policy_version="1.0.0",
            missing_result_grace_seconds=60,
        ),
        created_at=observed_at,
    )


def acknowledged_results(plan: Any) -> tuple[Any, ...]:
    return tuple(
        result_for(command, EXECUTION.CommandOutcome.ACKNOWLEDGED)
        for command in plan.commands
    )


def test_all_acknowledged_commands_complete_execution() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(
        runtime_request(plan=plan, results=acknowledged_results(plan))
    )
    assert report.status is RUNTIME.RuntimeStatus.COMPLETED
    assert report.acknowledged_command_count == 6
    assert report.unresolved_command_count == 0


def test_no_results_before_deadline_remains_pending() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan, observed_offset_seconds=-1))
    assert report.status is RUNTIME.RuntimeStatus.PENDING
    assert report.issues == ()


def test_missing_results_after_deadline_are_missed() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan, observed_offset_seconds=120))
    assert report.status is RUNTIME.RuntimeStatus.MISSED
    assert any(
        issue.issue_type is RUNTIME.RuntimeIssueType.MISSING_RESULT
        for issue in report.issues
    )


def test_partial_acknowledgement_is_partial_after_deadline() -> None:
    plan = execution_plan()
    results = (result_for(plan.commands[0], EXECUTION.CommandOutcome.ACKNOWLEDGED),)
    report = RUNTIME.build_runtime_report(
        runtime_request(plan=plan, results=results, observed_offset_seconds=700)
    )
    assert report.status is RUNTIME.RuntimeStatus.PARTIAL
    assert report.acknowledged_command_count == 1


def test_retry_required_generates_retry_recommendation() -> None:
    plan = execution_plan()
    results = (result_for(plan.commands[0], EXECUTION.CommandOutcome.RETRY_REQUIRED),)
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan, results=results))
    assert report.status is RUNTIME.RuntimeStatus.IN_PROGRESS
    assert any(
        item.action_type is RUNTIME.RecoveryActionType.RETRY_COMMAND
        for item in report.recovery_recommendations
    )


def test_timeout_generates_reschedule_remainder() -> None:
    plan = execution_plan()
    results = (result_for(plan.commands[0], EXECUTION.CommandOutcome.TIMED_OUT, attempt=3),)
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan, results=results))
    assert report.status is RUNTIME.RuntimeStatus.MISSED
    assert any(
        item.action_type is RUNTIME.RecoveryActionType.RESCHEDULE_REMAINDER
        for item in report.recovery_recommendations
    )


def test_rejection_requires_manual_review() -> None:
    plan = execution_plan()
    results = (
        result_for(
            plan.commands[0],
            EXECUTION.CommandOutcome.REJECTED,
            reason="safety interlock",
        ),
    )
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan, results=results))
    assert report.status is RUNTIME.RuntimeStatus.FAILED
    assert any(
        item.action_type is RUNTIME.RecoveryActionType.MANUAL_REVIEW
        for item in report.recovery_recommendations
    )


def test_controller_offline_is_failed() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan, online=False))
    assert report.status is RUNTIME.RuntimeStatus.FAILED
    assert any(
        issue.issue_type is RUNTIME.RuntimeIssueType.CONTROLLER_OFFLINE
        for issue in report.issues
    )


def test_external_interruption_has_priority() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(
        runtime_request(
            plan=plan,
            interrupted=True,
            interruption_reason="rain sensor interruption",
        )
    )
    assert report.status is RUNTIME.RuntimeStatus.INTERRUPTED


def test_blocked_execution_plan_remains_blocked() -> None:
    plan = EXECUTION.build_execution_plan(execution_request(safety_blocks=("freeze interlock",)))
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan))
    assert report.status is RUNTIME.RuntimeStatus.BLOCKED
    assert report.expected_command_count == 0


def test_no_command_execution_plan_has_no_execution_status() -> None:
    initial = execution_plan()
    keys = tuple(sorted(command.idempotency_key for command in initial.commands))
    plan = EXECUTION.build_execution_plan(execution_request(completed_keys=keys))
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan))
    assert report.status is RUNTIME.RuntimeStatus.NO_EXECUTION


def test_report_preserves_execution_provenance() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(runtime_request(plan=plan))
    assert report.source_execution_plan == plan
    assert report.execution_plan_id == plan.execution_plan_id


def test_runtime_serialization_is_deterministic() -> None:
    report = RUNTIME.build_runtime_report(runtime_request())
    assert report.to_dict() == report.to_dict()
    assert report.to_dict()["status"] == "pending"


def test_runtime_models_are_immutable() -> None:
    report = RUNTIME.build_runtime_report(runtime_request())
    try:
        cast(Any, report).status = RUNTIME.RuntimeStatus.COMPLETED
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("runtime model was mutable")


def test_request_rejects_untyped_execution_plan() -> None:
    try:
        replace(runtime_request(), execution_plan={})
    except ValueError as error:
        assert "ExecutionPlan" in str(error)
    else:
        raise AssertionError("invalid execution plan was accepted")


def test_results_require_deterministic_ordering() -> None:
    plan = execution_plan()
    results = acknowledged_results(plan)
    try:
        replace(runtime_request(plan=plan), command_results=tuple(reversed(results)))
    except ValueError as error:
        assert "deterministic" in str(error)
    else:
        raise AssertionError("unordered results were accepted")


def test_mismatched_idempotency_key_is_rejected() -> None:
    plan = execution_plan()
    result = replace(
        result_for(plan.commands[0], EXECUTION.CommandOutcome.ACKNOWLEDGED),
        idempotency_key="different-key",
    )
    try:
        RUNTIME.build_runtime_report(runtime_request(plan=plan, results=(result,)))
    except ValueError as error:
        assert "idempotency" in str(error)
    else:
        raise AssertionError("mismatched result was accepted")


def test_no_recovery_needed_is_explicit() -> None:
    plan = execution_plan()
    report = RUNTIME.build_runtime_report(
        runtime_request(plan=plan, results=acknowledged_results(plan))
    )
    assert report.recovery_recommendations[0].action_type is RUNTIME.RecoveryActionType.NONE
