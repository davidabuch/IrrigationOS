"""Tests for deterministic non-actuating safety preemption semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

acknowledgements = load_integration_module("command_acknowledgements")
safety_preemption = load_integration_module("safety_preemption")

NOW = datetime(2026, 8, 10, 20, 0, tzinfo=UTC)


def _reasons(**overrides: object) -> tuple[str, ...]:
    values: dict[str, Any] = {
        "health_state": "healthy",
        "observation_age_seconds": 30.0,
        "observation_stale_after_seconds": 720.0,
        "controller_available": True,
        "ownership_confirmed": True,
        "active_watering_conflict": False,
        "execution_authorization_status": "manual_review_eligible",
    }
    values.update(overrides)
    return safety_preemption.evaluate_preemption_reasons(**values)


def test_healthy_context_requires_no_preemption() -> None:
    assert _reasons() == ()


def test_failed_safety_gates_produce_canonical_sorted_reasons() -> None:
    reasons = _reasons(
        health_state="degraded",
        observation_age_seconds=900.0,
        controller_available=False,
        ownership_confirmed=False,
        active_watering_conflict=True,
        execution_authorization_status="blocked",
    )
    assert reasons == tuple(sorted(reasons))
    assert set(reasons) == {
        "active_watering_conflict",
        "controller_unavailable",
        "execution_not_review_eligible",
        "observation_stale",
        "ownership_not_confirmed",
        "system_unhealthy",
    }


def test_missing_observation_age_fails_closed_as_stale() -> None:
    assert _reasons(observation_age_seconds=None) == ("observation_stale",)


def test_preemption_event_is_deterministic_and_non_actuating() -> None:
    reasons = ("system_unhealthy", "controller_unavailable")
    first = safety_preemption.build_preemption_event(
        command_id="command-1", evaluated_at=NOW, reason_codes=reasons
    )
    second = safety_preemption.build_preemption_event(
        command_id="command-1", evaluated_at=NOW, reason_codes=tuple(reversed(reasons))
    )
    assert first == second
    assert first.synthetic_only is True
    assert first.dispatch_capability is False
    assert first.reason_codes == tuple(sorted(reasons))


def test_preemption_event_requires_command_and_reason() -> None:
    with pytest.raises(ValueError, match="command_id_required"):
        safety_preemption.build_preemption_event(
            command_id=" ", evaluated_at=NOW, reason_codes=("system_unhealthy",)
        )
    with pytest.raises(ValueError, match="preemption_reason_required"):
        safety_preemption.build_preemption_event(
            command_id="command-1", evaluated_at=NOW, reason_codes=()
        )


def test_acknowledgement_preemption_is_terminal() -> None:
    pending = acknowledgements.begin_acknowledgement_wait(
        command_id="command-1", dispatched_at=NOW
    )
    record = acknowledgements.preempt_acknowledgement(
        pending,
        observed_at=NOW + timedelta(seconds=2),
        detail_code="safety_preemption_required",
    )
    assert record.state is acknowledgements.CommandAcknowledgementState.PREEMPTED
    assert record.terminal is True
    assert record.detail_code == "safety_preemption_required"


def test_terminal_acknowledgement_cannot_be_preempted_again() -> None:
    pending = acknowledgements.begin_acknowledgement_wait(
        command_id="command-1", dispatched_at=NOW
    )
    preempted = acknowledgements.preempt_acknowledgement(
        pending,
        observed_at=NOW + timedelta(seconds=2),
        detail_code="safety_preemption_required",
    )
    with pytest.raises(ValueError, match="acknowledgement_already_terminal"):
        acknowledgements.preempt_acknowledgement(
            preempted,
            observed_at=NOW + timedelta(seconds=3),
            detail_code="duplicate_preemption",
        )
