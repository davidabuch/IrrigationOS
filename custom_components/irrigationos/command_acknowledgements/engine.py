"""Deterministic acknowledgement and timeout state machine without dispatch."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
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


def serialize_acknowledgement_record(record: CommandAcknowledgementRecord) -> str:
    """Serialize immutable acknowledgement evidence deterministically."""

    return json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))


def parse_acknowledgement_json_lines(
    lines: Iterable[str],
) -> tuple[CommandAcknowledgementRecord, ...]:
    """Parse persisted acknowledgement evidence or reject the full history."""

    records: list[CommandAcknowledgementRecord] = []
    try:
        for line in lines:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("acknowledgement_record_not_object")
            records.append(CommandAcknowledgementRecord.from_dict(payload))
    except (KeyError, TypeError, ValueError) as err:
        raise ValueError("acknowledgement_evidence_invalid") from err
    return tuple(records)


def reconcile_acknowledgement_history(
    records: Iterable[CommandAcknowledgementRecord], *, now: datetime
) -> tuple[
    dict[str, CommandAcknowledgementRecord],
    tuple[CommandAcknowledgementRecord, ...],
]:
    """Reconstruct pending windows and fail expired windows closed after restart."""

    latest_by_command: dict[str, CommandAcknowledgementRecord] = {}
    for record in records:
        latest_by_command[record.command_id] = record

    pending: dict[str, CommandAcknowledgementRecord] = {}
    timeout_transitions: list[CommandAcknowledgementRecord] = []
    for command_id, record in latest_by_command.items():
        if record.state is not CommandAcknowledgementState.WAITING:
            continue
        reconciled = evaluate_acknowledgement_timeout(record, now=now)
        if reconciled is record:
            pending[command_id] = record
        else:
            timeout_transitions.append(reconciled)
    return pending, tuple(timeout_transitions)
