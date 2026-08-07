"""Planning integration for synchronized pipeline evaluations."""

from __future__ import annotations

from datetime import datetime

from ..planning import (
    PlanningPolicy,
    PlanningRequest,
    PlanStatus,
    build_irrigation_plan,
)
from .models import AreaPlanningEvaluation, AreaRecommendationEvaluation

_PLANNING_POLICY = PlanningPolicy(
    policy_id="pipeline.advisory-planning",
    policy_version="1.0.0",
)


def build_area_plans(
    recommendations: tuple[AreaRecommendationEvaluation, ...],
    *,
    evaluated_at: datetime,
) -> tuple[AreaPlanningEvaluation, ...]:
    """Build machine-readable plans without inventing directives or actuation data."""
    results: list[AreaPlanningEvaluation] = []

    for item in recommendations:
        if item.assessment is None:
            results.append(
                AreaPlanningEvaluation(
                    area_id=item.area_id,
                    plan=None,
                    blocker_codes=tuple(
                        dict.fromkeys(
                            (*item.blocker_codes, "recommendations_unavailable")
                        )
                    ),
                )
            )
            continue

        plan = build_irrigation_plan(
            PlanningRequest(
                request_id=f"pipeline-planning:{item.area_id}",
                recommendations=item.assessment,
                directives=(),
                policy=_PLANNING_POLICY,
                created_at=evaluated_at,
            )
        )
        blockers = item.blocker_codes
        if plan.status is PlanStatus.PARTIAL:
            blockers = tuple(dict.fromkeys((*blockers, "planning_partial")))
        elif plan.status is PlanStatus.NOT_EXECUTABLE:
            blockers = tuple(dict.fromkeys((*blockers, "planning_not_executable")))
        results.append(
            AreaPlanningEvaluation(
                area_id=item.area_id,
                plan=plan,
                blocker_codes=blockers,
            )
        )

    return tuple(results)
