"""Tests for deterministic non-actuating sunrise hard-stop semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import load_integration_module

acknowledgements = load_integration_module("command_acknowledgements")
sunrise_hard_stop = load_integration_module("sunrise_hard_stop")

SUNRISE = datetime(2026, 8, 11, 13, 12, tzinfo=UTC)


def test_boundary_is_not_reached_before_sunrise() -> None:
    assert not sunrise_hard_stop.sunrise_boundary_reached(
        now=SUNRISE - timedelta(seconds=1), sunrise_at=SUNRISE
    )


def test_boundary_is_reached_at_sunrise() -> None:
    assert sunrise_hard_stop.sunrise_boundary_reached(
        now=SUNRISE, sunrise_at=SUNRISE
    )


def test_boundary_is_reached_after_sunrise() -> None:
    assert sunrise_hard_stop.sunrise_boundary_reached(
        now=SUNRISE + timedelta(minutes=5), sunrise_at=SUNRISE
    )


def test_boundary_normalizes_timezone_aware_values() -> None:
    local = SUNRISE.astimezone(UTC)
    assert sunrise_hard_stop.sunrise_boundary_reached(now=local, sunrise_at=SUNRISE)


def test_boundary_requires_timezone_aware_values() -> None:
    naive = datetime(2026, 8, 11, 13, 12)
    with pytest.raises(ValueError, match="now_timezone_required"):
        sunrise_hard_stop.sunrise_boundary_reached(now=naive, sunrise_at=SUNRISE)
    with pytest.raises(ValueError, match="sunrise_timezone_required"):
        sunrise_hard_stop.sunrise_boundary_reached(now=SUNRISE, sunrise_at=naive)


def test_event_is_deterministic_and_non_actuating() -> None:
    first = sunrise_hard_stop.build_sunrise_hard_stop_event(
        command_id="command-1", evaluated_at=SUNRISE, sunrise_at=SUNRISE
    )
    second = sunrise_hard_stop.build_sunrise_hard_stop_event(
        command_id="command-1", evaluated_at=SUNRISE, sunrise_at=SUNRISE
    )
    assert first == second
    assert first.synthetic_only is True
    assert first.dispatch_capability is False
    assert first.detail_code == "sunrise_hard_stop_reached"


def test_event_rejects_pre_sunrise_time() -> None:
    with pytest.raises(ValueError, match="sunrise_boundary_not_reached"):
        sunrise_hard_stop.build_sunrise_hard_stop_event(
            command_id="command-1",
            evaluated_at=SUNRISE - timedelta(seconds=1),
            sunrise_at=SUNRISE,
        )


def test_existing_acknowledgement_preemption_state_is_terminal() -> None:
    pending = acknowledgements.begin_acknowledgement_wait(
        command_id="command-1", dispatched_at=SUNRISE - timedelta(seconds=10)
    )
    record = acknowledgements.preempt_acknowledgement(
        pending,
        observed_at=SUNRISE,
        detail_code="sunrise_hard_stop_reached",
    )
    assert record.state is acknowledgements.CommandAcknowledgementState.PREEMPTED
    assert record.terminal is True
    assert record.detail_code == "sunrise_hard_stop_reached"
