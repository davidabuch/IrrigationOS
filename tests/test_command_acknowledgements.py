"""Tests for non-actuating acknowledgement and timeout state handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

command_acknowledgements = load_integration_module("command_acknowledgements")


def _pending() -> Any:
    return command_acknowledgements.begin_acknowledgement_wait(
        command_id="command-1",
        dispatched_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )


def test_acknowledgement_window_is_bounded_and_synthetic() -> None:
    pending = _pending()
    assert pending.state is command_acknowledgements.CommandAcknowledgementState.WAITING
    assert pending.synthetic_only is True
    assert pending.deadline_at_utc - pending.recorded_at_utc == timedelta(seconds=30)


def test_acknowledgement_before_deadline_is_accepted() -> None:
    pending = _pending()
    record = command_acknowledgements.resolve_acknowledgement(
        pending,
        observed_at=pending.recorded_at_utc + timedelta(seconds=5),
        accepted=True,
        detail_code="provider_accepted",
    )
    assert (
        record.state
        is command_acknowledgements.CommandAcknowledgementState.ACKNOWLEDGED
    )
    assert record.terminal is True
    assert record.detail_code == "provider_accepted"


def test_rejection_before_deadline_is_terminal() -> None:
    pending = _pending()
    record = command_acknowledgements.resolve_acknowledgement(
        pending,
        observed_at=pending.recorded_at_utc + timedelta(seconds=5),
        accepted=False,
        detail_code="provider_rejected",
    )
    assert record.state is command_acknowledgements.CommandAcknowledgementState.REJECTED
    assert record.detail_code == "provider_rejected"


def test_late_acknowledgement_fails_closed_as_timeout() -> None:
    pending = _pending()
    record = command_acknowledgements.resolve_acknowledgement(
        pending,
        observed_at=pending.deadline_at_utc + timedelta(microseconds=1),
        accepted=True,
        detail_code="provider_accepted",
    )
    assert (
        record.state is command_acknowledgements.CommandAcknowledgementState.TIMED_OUT
    )
    assert record.detail_code == "acknowledgement_arrived_after_deadline"


def test_timeout_evaluation_changes_state_only_after_deadline() -> None:
    pending = _pending()
    assert (
        command_acknowledgements.evaluate_acknowledgement_timeout(
            pending, now=pending.deadline_at_utc
        )
        is pending
    )
    timed_out = command_acknowledgements.evaluate_acknowledgement_timeout(
        pending, now=pending.deadline_at_utc + timedelta(microseconds=1)
    )
    assert (
        timed_out.state
        is command_acknowledgements.CommandAcknowledgementState.TIMED_OUT
    )
    assert timed_out.detail_code == "acknowledgement_deadline_exceeded"


def test_terminal_record_cannot_be_resolved_again() -> None:
    pending = _pending()
    terminal = command_acknowledgements.resolve_acknowledgement(
        pending,
        observed_at=pending.recorded_at_utc + timedelta(seconds=1),
        accepted=True,
        detail_code="provider_accepted",
    )
    with pytest.raises(ValueError, match="acknowledgement_already_terminal"):
        command_acknowledgements.resolve_acknowledgement(
            terminal,
            observed_at=terminal.recorded_at_utc + timedelta(seconds=1),
            accepted=True,
            detail_code="duplicate",
        )


def test_required_identifiers_and_detail_codes_are_validated() -> None:
    with pytest.raises(ValueError, match="command_id_required"):
        command_acknowledgements.begin_acknowledgement_wait(
            command_id=" ", dispatched_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
        )
    pending = _pending()
    with pytest.raises(ValueError, match="detail_code_required"):
        command_acknowledgements.resolve_acknowledgement(
            pending,
            observed_at=pending.recorded_at_utc,
            accepted=True,
            detail_code=" ",
        )
