"""Deterministic acknowledgement and timeout state machine without dispatch."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from .models import CommandAcknowledgementRecord, CommandAcknowledgementState

ACKNOWLEDGEMENT_TIMEOUT_SECONDS = 30


def _event_id(
    *, command_id: str, state: CommandAcknowledgementState, recorded_at: datetime
) -> str:
    seed = f"{command_id}|{state.value}|{recorded_at.astimezone(UTC).isoformat()}"
    return hashlib.sha256(seed.encode()).hexdigest()


def begin_acknowledgement_wait(
    *, command_id: str, dispatched_at: datetime
) -> CommandAcknowledgementRecord:
    """Start a synthetic acknowledgement window for state-machine validation."""

    command_id = command_id.strip()
    if not command_id:
        raise ValueError("command_id_required")
    recorded_at = dispatched_at.astimezone(UTC)
    deadline = recorded_at + timedelta(seconds=ACKNOWLEDGEMENT_TIMEOUT_SECONDS)
    return CommandAcknowledgementRecord(
        event_id=_event_id(
            command_id=command_id,
            state=CommandAcknowledgementState.WAITING,
            recorded_at=recorded_at,
        ),
        command_id=command_id,
        state=CommandAcknowledgementState.WAITING,
        recorded_at_utc=recorded_at,
        deadline_at_utc=deadline,
        detail_code="awaiting_provider_acknowledgement",
    )


def resolve_acknowledgement(
    pending: CommandAcknowledgementRecord,
    *,
    observed_at: datetime,
    accepted: bool,
    detail_code: str,
) -> CommandAcknowledgementRecord:
    """Resolve a waiting record deterministically, enforcing the deadline first."""

    if pending.state is not CommandAcknowledgementState.WAITING:
        raise ValueError("acknowledgement_already_terminal")
    detail_code = detail_code.strip()
    if not detail_code:
        raise ValueError("detail_code_required")
    recorded_at = observed_at.astimezone(UTC)
    if recorded_at > pending.deadline_at_utc:
        state = CommandAcknowledgementState.TIMED_OUT
        detail = "acknowledgement_arrived_after_deadline"
    elif accepted:
        state = CommandAcknowledgementState.ACKNOWLEDGED
        detail = detail_code
    else:
        state = CommandAcknowledgementState.REJECTED
        detail = detail_code
    return CommandAcknowledgementRecord(
        event_id=_event_id(
            command_id=pending.command_id, state=state, recorded_at=recorded_at
        ),
        command_id=pending.command_id,
        state=state,
        recorded_at_utc=recorded_at,
        deadline_at_utc=pending.deadline_at_utc,
        detail_code=detail,
    )


def evaluate_acknowledgement_timeout(
    pending: CommandAcknowledgementRecord, *, now: datetime
) -> CommandAcknowledgementRecord:
    """Return pending evidence or transition it to timed-out after the deadline."""

    if pending.state is not CommandAcknowledgementState.WAITING:
        return pending
    recorded_at = now.astimezone(UTC)
    if recorded_at <= pending.deadline_at_utc:
        return pending
    return CommandAcknowledgementRecord(
        event_id=_event_id(
            command_id=pending.command_id,
            state=CommandAcknowledgementState.TIMED_OUT,
            recorded_at=recorded_at,
        ),
        command_id=pending.command_id,
        state=CommandAcknowledgementState.TIMED_OUT,
        recorded_at_utc=recorded_at,
        deadline_at_utc=pending.deadline_at_utc,
        detail_code="acknowledgement_deadline_exceeded",
    )
