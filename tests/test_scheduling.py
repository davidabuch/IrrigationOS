"""Behavioral tests for the deterministic Scheduling Engine."""
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast

from tests.helpers import load_integration_module
from tests.test_planning import planning_request, recommendation_assessment

PLANNING = load_integration_module("planning")
SCHEDULING = load_integration_module("scheduling")
RECOMMENDATIONS = load_integration_module("recommendations")


def ready_plan() -> Any:
    assessment = recommendation_assessment(water_deficit=True)
    recommendation = next(
        item
        for item in assessment.recommendations
        if item.category is RECOMMENDATIONS.RecommendationCategory.ADJUST_IRRIGATION
    )
    directive = PLANNING.PlanningDirective(
        recommendation_id=recommendation.recommendation_id,
        target_id="zone-7",
        quantity=12.5,
        quantity_unit=PLANNING.PlanQuantityUnit.MILLIMETERS,
        runtime_seconds=1800,
        cycle_count=3,
        soak_seconds=600,
    )
    plan = PLANNING.build_irrigation_plan(
        planning_request(assessment=assessment, directives=(directive,))
    )
    action = next(
        item for item in plan.actions if item.action_type is PLANNING.PlanActionType.IRRIGATE
    )
    ready_action = replace(
        action,
        disposition=PLANNING.PlanExecutionDisposition.READY,
        safety_constraints=(),
    )
    return replace(plan, status=PLANNING.PlanStatus.READY, actions=(ready_action,))


def schedule_request(
    *,
    plan: Any | None = None,
    window_seconds: int = 7200,
    blocking_constraints: tuple[str, ...] = (),
    minimum_gap: int = 0,
) -> Any:
    current = ready_plan() if plan is None else plan
    start = current.created_at
    return SCHEDULING.SchedulingRequest(
        request_id="scheduling-request-1",
        plan=current,
        windows=(
            SCHEDULING.SchedulingWindow(
                window_id="window-1",
                starts_at=start,
                ends_at=start + timedelta(seconds=window_seconds),
            ),
        ),
        policy=SCHEDULING.SchedulingPolicy(
            policy_id="scheduling-policy",
            policy_version="1.0.0",
            minimum_inter_action_seconds=minimum_gap,
        ),
        created_at=start,
        blocking_constraints=blocking_constraints,
    )


def test_ready_irrigation_action_is_scheduled() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request())
    assert schedule.status is SCHEDULING.ScheduleStatus.READY
    assert schedule.actions[0].disposition is SCHEDULING.ScheduledActionDisposition.SCHEDULED
    assert schedule.actions[0].window_id == "window-1"


def test_cycle_and_soak_is_preserved() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request())
    action = schedule.actions[0]
    assert len(action.cycle_starts_at) == 3
    assert action.cycle_starts_at[1] - action.cycle_starts_at[0] == timedelta(seconds=1200)
    assert action.starts_at is not None
    assert action.ends_at is not None
    assert action.ends_at - action.starts_at == timedelta(seconds=3000)


def test_action_that_does_not_fit_is_blocked() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(
        schedule_request(window_seconds=2999)
    )
    assert schedule.status is SCHEDULING.ScheduleStatus.NOT_SCHEDULABLE
    assert schedule.actions[0].blocking_reasons == (
        "no permitted window can fit action",
    )


def test_weather_or_freeze_constraint_blocks_schedule() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(
        schedule_request(blocking_constraints=("freeze hold", "weather delay"))
    )
    assert schedule.actions[0].disposition is SCHEDULING.ScheduledActionDisposition.BLOCKED
    assert schedule.actions[0].blocking_reasons == ("freeze hold", "weather delay")


def test_manual_plan_action_remains_manual_only() -> None:
    plan = PLANNING.build_irrigation_plan(planning_request())
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request(plan=plan))
    assert schedule.status is SCHEDULING.ScheduleStatus.PARTIAL
    assert schedule.actions[0].disposition is SCHEDULING.ScheduledActionDisposition.MANUAL_ONLY


def test_blocked_plan_action_remains_blocked() -> None:
    plan = PLANNING.build_irrigation_plan(
        planning_request(assessment=recommendation_assessment(water_deficit=True))
    )
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request(plan=plan))
    irrigation = next(
        item
        for item in schedule.actions
        if item.source_action.action_type is PLANNING.PlanActionType.IRRIGATE
    )
    assert irrigation.disposition is SCHEDULING.ScheduledActionDisposition.BLOCKED


def test_schedule_preserves_source_plan_action() -> None:
    plan = ready_plan()
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request(plan=plan))
    assert schedule.actions[0].source_action == plan.actions[0]
    assert schedule.plan_id == plan.plan_id


def test_schedule_serialization_is_deterministic() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request())
    assert schedule.to_dict() == schedule.to_dict()
    assert schedule.to_dict()["status"] == "ready"


def test_models_are_immutable() -> None:
    schedule = SCHEDULING.build_irrigation_schedule(schedule_request())
    try:
        cast(Any, schedule).status = SCHEDULING.ScheduleStatus.PARTIAL
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("scheduling model was mutable")


def test_window_requires_timezone_aware_datetimes() -> None:
    aware = ready_plan().created_at
    try:
        SCHEDULING.SchedulingWindow(
            window_id="window-1",
            starts_at=aware.replace(tzinfo=None),
            ends_at=aware + timedelta(hours=1),
        )
    except ValueError as error:
        assert "timezone-aware" in str(error)
    else:
        raise AssertionError("naive scheduling window was accepted")


def test_window_requires_positive_duration() -> None:
    start = ready_plan().created_at
    try:
        SCHEDULING.SchedulingWindow("window-1", start, start)
    except ValueError as error:
        assert "positive duration" in str(error)
    else:
        raise AssertionError("zero-duration window was accepted")


def test_windows_require_deterministic_ordering() -> None:
    plan = ready_plan()
    start = plan.created_at
    first = SCHEDULING.SchedulingWindow(
        "window-b",
        start + timedelta(hours=2),
        start + timedelta(hours=3),
    )
    second = SCHEDULING.SchedulingWindow("window-a", start, start + timedelta(hours=1))
    try:
        replace(schedule_request(plan=plan), windows=(first, second))
    except ValueError as error:
        assert "deterministic" in str(error)
    else:
        raise AssertionError("unordered windows were accepted")


def test_request_rejects_untyped_plan() -> None:
    try:
        replace(schedule_request(), plan={})
    except ValueError as error:
        assert "IrrigationPlan" in str(error)
    else:
        raise AssertionError("invalid plan was accepted")


def test_policy_rejects_negative_gap() -> None:
    try:
        SCHEDULING.SchedulingPolicy("policy", "1.0.0", -1)
    except ValueError as error:
        assert "non-negative" in str(error)
    else:
        raise AssertionError("negative scheduling gap was accepted")


def test_no_windows_produces_typed_blocking_reason() -> None:
    request = replace(schedule_request(), windows=())
    schedule = SCHEDULING.build_irrigation_schedule(request)
    assert schedule.status is SCHEDULING.ScheduleStatus.NOT_SCHEDULABLE
    assert schedule.actions[0].blocking_reasons == (
        "no permitted window can fit action",
    )
