"""Deterministic non-actuating command intent and receipt construction."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import (
    CommandAttribution,
    CommandIntent,
    CommandIntentAction,
    CommandReceipt,
    CommandReceiptOutcome,
)

MAX_RECORDED_RUNTIME_SECONDS = 3600


def build_command_intent(
    *,
    created_at: datetime,
    attribution: CommandAttribution,
    action: CommandIntentAction,
    controller_id: str,
    zone_id: str | None,
    requested_runtime_seconds: int | None,
    reason_code: str,
) -> CommandIntent:
    """Build a validated canonical intent without dispatching anything."""

    created_at_utc = created_at.astimezone(UTC)
    controller_id = controller_id.strip()
    reason_code = reason_code.strip()
    if not controller_id:
        raise ValueError("controller_id_required")
    if not reason_code:
        raise ValueError("reason_code_required")
    if action is CommandIntentAction.START_ZONE:
        if zone_id is None or not zone_id.strip():
            raise ValueError("zone_id_required_for_start")
        if requested_runtime_seconds is None or not (
            1 <= requested_runtime_seconds <= MAX_RECORDED_RUNTIME_SECONDS
        ):
            raise ValueError("runtime_out_of_bounds")
    elif requested_runtime_seconds is not None:
        raise ValueError("runtime_only_valid_for_start")

    normalized_zone = None if zone_id is None else zone_id.strip()
    seed = "|".join(
        (
            created_at_utc.isoformat(),
            attribution.value,
            action.value,
            controller_id,
            normalized_zone or "",
            "" if requested_runtime_seconds is None else str(requested_runtime_seconds),
            reason_code,
        )
    )
    command_id = hashlib.sha256(seed.encode()).hexdigest()
    return CommandIntent(
        command_id=command_id,
        created_at_utc=created_at_utc,
        attribution=attribution,
        action=action,
        controller_id=controller_id,
        zone_id=normalized_zone,
        requested_runtime_seconds=requested_runtime_seconds,
        reason_code=reason_code,
    )


def build_not_dispatched_receipt(
    intent: CommandIntent, *, recorded_at: datetime
) -> CommandReceipt:
    """Record explicit evidence that the intent never crossed a dispatch boundary."""

    recorded_at_utc = recorded_at.astimezone(UTC)
    receipt_id = hashlib.sha256(
        f"{intent.command_id}|{recorded_at_utc.isoformat()}|not_dispatched".encode()
    ).hexdigest()
    return CommandReceipt(
        receipt_id=receipt_id,
        command_id=intent.command_id,
        recorded_at_utc=recorded_at_utc,
        outcome=CommandReceiptOutcome.NOT_DISPATCHED,
        detail_code="live_command_delivery_disabled",
    )
