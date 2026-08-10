"""Tests for non-actuating command attribution and receipt evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.helpers import load_integration_module

command_receipts = load_integration_module("command_receipts")


def test_start_zone_intent_is_deterministic_and_attributed() -> None:
    when = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)
    kwargs = dict(
        created_at=when,
        attribution=command_receipts.CommandAttribution.IRRIGATIONOS,
        action=command_receipts.CommandIntentAction.START_ZONE,
        controller_id="controller-1",
        zone_id="zone-2",
        requested_runtime_seconds=600,
        reason_code="shadow_plan_candidate",
    )
    first = command_receipts.build_command_intent(**kwargs)
    second = command_receipts.build_command_intent(**kwargs)
    assert first.command_id == second.command_id
    assert first.attribution.value == "irrigationos"
    assert first.requested_runtime_seconds == 600


def test_start_zone_requires_zone_and_bounded_runtime() -> None:
    when = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="zone_id_required_for_start"):
        command_receipts.build_command_intent(
            created_at=when,
            attribution=command_receipts.CommandAttribution.OPERATOR,
            action=command_receipts.CommandIntentAction.START_ZONE,
            controller_id="controller-1",
            zone_id=None,
            requested_runtime_seconds=60,
            reason_code="test",
        )
    with pytest.raises(ValueError, match="runtime_out_of_bounds"):
        command_receipts.build_command_intent(
            created_at=when,
            attribution=command_receipts.CommandAttribution.OPERATOR,
            action=command_receipts.CommandIntentAction.START_ZONE,
            controller_id="controller-1",
            zone_id="zone-1",
            requested_runtime_seconds=3601,
            reason_code="test",
        )


def test_stop_intent_rejects_runtime() -> None:
    with pytest.raises(ValueError, match="runtime_only_valid_for_start"):
        command_receipts.build_command_intent(
            created_at=datetime(2026, 8, 10, 6, 0, tzinfo=UTC),
            attribution=command_receipts.CommandAttribution.SAFETY_MANAGER,
            action=command_receipts.CommandIntentAction.STOP_ALL,
            controller_id="controller-1",
            zone_id=None,
            requested_runtime_seconds=1,
            reason_code="safety_stop",
        )


def test_receipt_is_explicitly_not_dispatched() -> None:
    when = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)
    intent = command_receipts.build_command_intent(
        created_at=when,
        attribution=command_receipts.CommandAttribution.IRRIGATIONOS,
        action=command_receipts.CommandIntentAction.STOP_ALL,
        controller_id="controller-1",
        zone_id=None,
        requested_runtime_seconds=None,
        reason_code="safety_test",
    )
    receipt = command_receipts.build_not_dispatched_receipt(intent, recorded_at=when)
    assert receipt.command_id == intent.command_id
    assert receipt.outcome is command_receipts.CommandReceiptOutcome.NOT_DISPATCHED
    assert receipt.detail_code == "live_command_delivery_disabled"
