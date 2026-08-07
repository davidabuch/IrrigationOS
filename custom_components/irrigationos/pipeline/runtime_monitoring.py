"""Runtime-monitoring integration for synchronized pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..controllers import ControllerAvailability, ControllerRegistrySnapshot
from ..execution import ExecutionPlanStatus
from ..runtime_monitoring import (
    RuntimeMonitoringRequest,
    RuntimeObservation,
    RuntimePolicy,
    RuntimeStatus,
    build_runtime_report,
)
from .models import AreaExecutionEvaluation, AreaRuntimeMonitoringEvaluation

_RUNTIME_POLICY = RuntimePolicy(
    policy_id="pipeline.simulation-runtime-monitoring",
    policy_version="1.0.0",
    missing_result_grace_seconds=60,
)


def build_area_runtime_reports(
    execution: tuple[AreaExecutionEvaluation, ...],
    snapshot: ControllerRegistrySnapshot,
    *,
    evaluated_at: datetime,
) -> tuple[AreaRuntimeMonitoringEvaluation, ...]:
    """Evaluate simulated execution without inventing live command outcomes."""
    areas = {area.area_id: area for area in snapshot.configured_areas}
    controllers = {controller.controller_id: controller for controller in snapshot.controllers}
    results: list[AreaRuntimeMonitoringEvaluation] = []

    for item in execution:
        plan = item.execution_plan
        if plan is None:
            results.append(
                AreaRuntimeMonitoringEvaluation(
                    area_id=item.area_id,
                    report=None,
                    blocker_codes=tuple(
                        dict.fromkeys((*item.blocker_codes, "execution_unavailable"))
                    ),
                )
            )
            continue

        # A simulated plan with runnable commands cannot be truthfully monitored until
        # command-result and interruption observations are integrated. Do not fabricate
        # acknowledgements, timeouts, or a "not interrupted" assertion.
        if plan.status in {ExecutionPlanStatus.READY, ExecutionPlanStatus.PARTIAL}:
            results.append(
                AreaRuntimeMonitoringEvaluation(
                    area_id=item.area_id,
                    report=None,
                    blocker_codes=tuple(
                        dict.fromkeys(
                            (*item.blocker_codes, "runtime_command_results_unavailable")
                        )
                    ),
                )
            )
            continue

        area = areas.get(item.area_id)
        controller = controllers.get(area.controller_id) if area is not None else None
        if controller is None or controller.availability is ControllerAvailability.UNKNOWN:
            results.append(
                AreaRuntimeMonitoringEvaluation(
                    area_id=item.area_id,
                    report=None,
                    blocker_codes=tuple(
                        dict.fromkeys(
                            (*item.blocker_codes, "runtime_controller_state_unavailable")
                        )
                    ),
                )
            )
            continue

        report = build_runtime_report(
            RuntimeMonitoringRequest(
                request_id=f"runtime:{item.area_id}",
                execution_plan=plan,
                command_results=(),
                observation=RuntimeObservation(
                    observation_id=f"runtime-observation:{item.area_id}",
                    observed_at=snapshot.observation.observed_at,
                    controller_online=(
                        controller.availability is ControllerAvailability.ONLINE
                    ),
                ),
                policy=_RUNTIME_POLICY,
                created_at=evaluated_at,
            )
        )
        blockers = item.blocker_codes
        if report.status is RuntimeStatus.NO_EXECUTION:
            blockers = tuple(dict.fromkeys((*blockers, "runtime_no_execution")))
        elif report.status is RuntimeStatus.BLOCKED:
            blockers = tuple(dict.fromkeys((*blockers, "runtime_blocked")))

        results.append(
            AreaRuntimeMonitoringEvaluation(
                area_id=item.area_id,
                report=report,
                blocker_codes=blockers,
            )
        )

    return tuple(results)
