"""Deterministic comparison of execution intent with observed command outcomes."""
from __future__ import annotations

from datetime import timedelta

from ..execution import CommandOutcome, ControllerCommandDisposition, ExecutionPlanStatus
from .models import (
    RecoveryActionType,
    RecoveryRecommendation,
    RuntimeIssue,
    RuntimeIssueType,
    RuntimeMonitoringRequest,
    RuntimeReport,
    RuntimeStatus,
)


def _issue(
    request: RuntimeMonitoringRequest,
    issue_type: RuntimeIssueType,
    detail: str,
    command_id: str | None = None,
) -> RuntimeIssue:
    suffix = command_id or "global"
    return RuntimeIssue(
        issue_id=f"runtime-issue:{request.request_id}:{issue_type.value}:{suffix}",
        issue_type=issue_type,
        command_id=command_id,
        detail=detail,
    )


def build_runtime_report(request: RuntimeMonitoringRequest) -> RuntimeReport:
    """Build an immutable runtime assessment without issuing recovery commands."""
    plan = request.execution_plan
    expected = tuple(
        command
        for command in plan.commands
        if command.disposition is ControllerCommandDisposition.READY
    )
    results_by_command = {result.command_id: result for result in request.command_results}
    issues: list[RuntimeIssue] = []
    acknowledged = 0
    retry_ids: list[str] = []
    remainder_ids: list[str] = []
    inspect_controller = False
    manual_review = False

    if plan.status is ExecutionPlanStatus.BLOCKED:
        status = RuntimeStatus.BLOCKED
    elif not expected:
        status = RuntimeStatus.NO_EXECUTION
    else:
        for command in expected:
            result = results_by_command.get(command.command_id)
            if result is None:
                due_at = command.planned_at + timedelta(
                    seconds=command.acknowledgement_timeout_seconds
                    + request.policy.missing_result_grace_seconds
                )
                if request.observation.observed_at >= due_at:
                    issues.append(
                        _issue(
                            request,
                            RuntimeIssueType.MISSING_RESULT,
                            "No command result was observed before the monitoring deadline.",
                            command.command_id,
                        )
                    )
                    remainder_ids.append(command.command_id)
                continue
            if result.idempotency_key != command.idempotency_key:
                raise ValueError("command result idempotency key does not match execution plan")
            if result.outcome is CommandOutcome.ACKNOWLEDGED:
                acknowledged += 1
            elif result.outcome is CommandOutcome.RETRY_REQUIRED:
                issues.append(
                    _issue(
                        request,
                        RuntimeIssueType.RETRY_REQUIRED,
                        "Command requires another execution attempt.",
                        command.command_id,
                    )
                )
                retry_ids.append(command.command_id)
            elif result.outcome is CommandOutcome.TIMED_OUT:
                issues.append(
                    _issue(
                        request,
                        RuntimeIssueType.COMMAND_TIMED_OUT,
                        "Command exhausted its acknowledgement attempts.",
                        command.command_id,
                    )
                )
                remainder_ids.append(command.command_id)
            elif result.outcome is CommandOutcome.REJECTED:
                issues.append(
                    _issue(
                        request,
                        RuntimeIssueType.COMMAND_REJECTED,
                        result.reason or "Controller rejected the command.",
                        command.command_id,
                    )
                )
                manual_review = True

        if not request.observation.controller_online:
            issues.append(
                _issue(
                    request,
                    RuntimeIssueType.CONTROLLER_OFFLINE,
                    "The controller was offline at observation time.",
                )
            )
            inspect_controller = True
        if request.observation.interrupted:
            issues.append(
                _issue(
                    request,
                    RuntimeIssueType.EXTERNAL_INTERRUPTION,
                    request.observation.interruption_reason or "Execution was interrupted.",
                )
            )
            remainder_ids.extend(
                command.command_id
                for command in expected
                if command.command_id not in results_by_command
            )

        unresolved = len(expected) - acknowledged
        if request.observation.interrupted:
            status = RuntimeStatus.INTERRUPTED
        elif any(issue.issue_type is RuntimeIssueType.CONTROLLER_OFFLINE for issue in issues):
            status = RuntimeStatus.FAILED
        elif acknowledged == len(expected):
            status = RuntimeStatus.COMPLETED
        elif acknowledged and any(
            issue.issue_type
            in {
                RuntimeIssueType.MISSING_RESULT,
                RuntimeIssueType.COMMAND_TIMED_OUT,
                RuntimeIssueType.COMMAND_REJECTED,
            }
            for issue in issues
        ):
            status = RuntimeStatus.PARTIAL
        elif any(
            issue.issue_type
            in {
                RuntimeIssueType.MISSING_RESULT,
                RuntimeIssueType.COMMAND_TIMED_OUT,
            }
            for issue in issues
        ):
            status = RuntimeStatus.MISSED
        elif any(issue.issue_type is RuntimeIssueType.COMMAND_REJECTED for issue in issues):
            status = RuntimeStatus.FAILED
        elif acknowledged or request.command_results:
            status = RuntimeStatus.IN_PROGRESS
        else:
            status = RuntimeStatus.PENDING

    if plan.status is ExecutionPlanStatus.BLOCKED or not expected:
        acknowledged = 0
        unresolved = len(expected)
    else:
        unresolved = len(expected) - acknowledged

    recommendations: list[RecoveryRecommendation] = []
    if retry_ids:
        recommendations.append(
            RecoveryRecommendation(
                recommendation_id=f"runtime-recovery:{request.request_id}:retry",
                action_type=RecoveryActionType.RETRY_COMMAND,
                command_ids=tuple(sorted(set(retry_ids))),
                reason="Retry commands that remain within their execution policy.",
            )
        )
    if remainder_ids:
        recommendations.append(
            RecoveryRecommendation(
                recommendation_id=f"runtime-recovery:{request.request_id}:remainder",
                action_type=RecoveryActionType.RESCHEDULE_REMAINDER,
                command_ids=tuple(sorted(set(remainder_ids))),
                reason="Return unresolved work to Scheduling for a new schedule decision.",
            )
        )
    if inspect_controller:
        recommendations.append(
            RecoveryRecommendation(
                recommendation_id=f"runtime-recovery:{request.request_id}:controller",
                action_type=RecoveryActionType.INSPECT_CONTROLLER,
                command_ids=(),
                reason="Restore and verify controller connectivity before further execution.",
            )
        )
    if manual_review:
        recommendations.append(
            RecoveryRecommendation(
                recommendation_id=f"runtime-recovery:{request.request_id}:review",
                action_type=RecoveryActionType.MANUAL_REVIEW,
                command_ids=(),
                reason="Review rejected commands and safety context before retrying.",
            )
        )
    if not recommendations:
        recommendations.append(
            RecoveryRecommendation(
                recommendation_id=f"runtime-recovery:{request.request_id}:none",
                action_type=RecoveryActionType.NONE,
                command_ids=(),
                reason="No recovery action is currently required.",
            )
        )

    return RuntimeReport(
        report_id=f"runtime-report:{request.request_id}",
        request_id=request.request_id,
        execution_plan_id=plan.execution_plan_id,
        status=status,
        expected_command_count=len(expected),
        acknowledged_command_count=acknowledged,
        unresolved_command_count=unresolved,
        issues=tuple(sorted(issues, key=lambda item: item.issue_id)),
        recovery_recommendations=tuple(
            sorted(recommendations, key=lambda item: item.recommendation_id)
        ),
        policy_id=request.policy.policy_id,
        policy_version=request.policy.policy_version,
        algorithm_version=request.algorithm_version,
        created_at=request.created_at,
        source_execution_plan=plan,
    )
