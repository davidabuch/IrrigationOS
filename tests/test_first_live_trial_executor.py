"""Tests for the commissioned one-shot first-live watering trial executor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from tests.helpers import load_integration_module

controllers = load_integration_module("controllers.models")
commissioning = load_integration_module("live_commissioning")
delivery = load_integration_module("first_live_delivery")
NOW = datetime(2026, 8, 12, 19, 0, tzinfo=UTC)


def _snapshot(
    *, fresh: bool = True, enabled: bool = True,
    quality: object | None = None, state: object | None = None,
) -> Any:
    area = controllers.IrrigationArea(
        area_id="controller-canonical:slot:2",
        controller_id="controller-canonical",
        slot_number=2,
        name="Zone 2",
        enabled=enabled,
        configured=True,
        state=state or controllers.IrrigationAreaState.IDLE,
        binding=controllers.VendorBinding("rachio", "native-zone-secret"),
    )
    controller = controllers.IrrigationController(
        controller_id="controller-canonical",
        binding=controllers.VendorBinding("rachio", "native-device-secret"),
        name="Controller",
        availability=controllers.ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=2,
        watering_observation_quality=controllers.ObservationQuality.CONFIRMED,
        capabilities=controllers.ControllerCapabilities(),
        areas=(area,),
    )
    return controllers.ControllerRegistrySnapshot(
        provider="rachio",
        account_id="account",
        account_name=None,
        controllers=(controller,),
        observation=controllers.ObservationMetadata(
            observed_at=NOW - timedelta(seconds=5),
            fresh_until=NOW + (timedelta(seconds=30) if fresh else timedelta(seconds=-1)),
            source="rachio",
            quality=quality or controllers.ObservationQuality.CONFIRMED,
        ),
    )


def _manager() -> Any:
    manager = commissioning.LiveCommissioningManager()
    manager.approve_trial(
        controller_id="controller-canonical",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=60,
        approved_at=NOW - timedelta(seconds=10),
        supervised_daytime=True,
    )
    manager.set_supervised_commissioning_window(open_window=True)
    manager.consider(
        integrated_review_status="validated_review_eligible",
        evaluated_at=NOW - timedelta(seconds=1),
        health_state="healthy",
        observation_age_seconds=5.0,
        active_external_watering_count=0,
    )
    return manager


def _request(**overrides: object) -> Any:
    values: dict[str, object] = {
        "controller_id": "controller-canonical",
        "controller_slot": 1,
        "area_slot": 2,
        "runtime_seconds": 60,
        "requested_at": NOW,
    }
    values.update(overrides)
    return delivery.FirstLiveDeliveryRequest(**values)


class _AuditSink:
    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.events: list[object] = []

    async def async_record(self, event: object) -> bool:
        self.events.append(event)
        return self.succeed


class _Transport:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, int]] = []

    async def async_start_zone(self, *, zone_id: str, runtime_seconds: int) -> None:
        self.calls.append((zone_id, runtime_seconds))
        if self.fail:
            raise delivery.FirstLiveTransportError("ambiguous network outcome")


async def test_eligible_trial_resolves_native_target_and_dispatches_once() -> None:
    manager = _manager()
    transport = _Transport()
    executor = delivery.FirstLiveTrialExecutor(
        commissioning=manager, transport=cast(Any, transport), audit_sink=cast(Any, _AuditSink())
    )
    result = await executor.async_execute(request=_request(), snapshot=_snapshot())
    assert result.status is delivery.FirstLiveTrialExecutionStatus.START_DISPATCHED
    assert result.approval_consumed_before_dispatch is True
    assert result.retry_permitted is False
    assert transport.calls == [("native-zone-secret", 60)]


async def test_approval_is_consumed_before_ambiguous_transport_failure() -> None:
    manager = _manager()
    transport = _Transport(fail=True)
    executor = delivery.FirstLiveTrialExecutor(
        commissioning=manager, transport=cast(Any, transport), audit_sink=cast(Any, _AuditSink())
    )
    result = await executor.async_execute(request=_request(), snapshot=_snapshot())
    assert result.status is delivery.FirstLiveTrialExecutionStatus.TRANSPORT_OUTCOME_UNKNOWN
    assert result.approval_consumed_before_dispatch is True
    manager.consider(
        integrated_review_status="validated_review_eligible",
        evaluated_at=NOW + timedelta(seconds=1),
        health_state="healthy",
        observation_age_seconds=6.0,
        active_external_watering_count=0,
    )
    assert "operator_approval_already_consumed" in manager.summary.blocker_codes


async def test_mismatched_approved_target_fails_before_transport() -> None:
    manager = _manager()
    transport = _Transport()
    executor = delivery.FirstLiveTrialExecutor(
        commissioning=manager, transport=cast(Any, transport), audit_sink=cast(Any, _AuditSink())
    )
    result = await executor.async_execute(
        request=_request(controller_id="different-controller"), snapshot=_snapshot()
    )
    assert result.status is delivery.FirstLiveTrialExecutionStatus.BLOCKED
    assert "approved_controller_mismatch" in result.blocker_codes
    assert transport.calls == []


async def test_stale_snapshot_or_disabled_zone_fails_closed() -> None:
    for snapshot in (_snapshot(fresh=False), _snapshot(enabled=False)):
        manager = _manager()
        transport = _Transport()
        executor = delivery.FirstLiveTrialExecutor(
            commissioning=manager,
            transport=cast(Any, transport),
            audit_sink=cast(Any, _AuditSink()),
        )
        result = await executor.async_execute(request=_request(), snapshot=snapshot)
        assert result.status is delivery.FirstLiveTrialExecutionStatus.BLOCKED
        assert transport.calls == []


async def test_uncertain_snapshot_or_area_state_fails_closed() -> None:
    for snapshot in (
        _snapshot(quality=controllers.ObservationQuality.PARTIAL),
        _snapshot(state=controllers.IrrigationAreaState.UNKNOWN),
    ):
        manager = _manager()
        transport = _Transport()
        executor = delivery.FirstLiveTrialExecutor(
            commissioning=manager,
            transport=cast(Any, transport),
            audit_sink=cast(Any, _AuditSink()),
        )
        result = await executor.async_execute(request=_request(), snapshot=snapshot)
        assert result.status is delivery.FirstLiveTrialExecutionStatus.BLOCKED
        assert transport.calls == []



async def test_stale_commissioning_preflight_or_expired_approval_blocks_dispatch() -> None:
    for requested_at in (NOW + timedelta(seconds=20), NOW + timedelta(minutes=11)):
        manager = _manager()
        transport = _Transport()
        executor = delivery.FirstLiveTrialExecutor(
            commissioning=manager,
            transport=cast(Any, transport),
            audit_sink=cast(Any, _AuditSink()),
        )
        result = await executor.async_execute(
            request=_request(requested_at=requested_at), snapshot=_snapshot()
        )
        assert result.status is delivery.FirstLiveTrialExecutionStatus.BLOCKED
        assert transport.calls == []



async def test_audit_intent_failure_blocks_before_approval_consumption_or_transport() -> None:
    manager = _manager()
    transport = _Transport()
    audit = _AuditSink(succeed=False)
    executor = delivery.FirstLiveTrialExecutor(
        commissioning=manager, transport=cast(Any, transport), audit_sink=cast(Any, audit)
    )
    result = await executor.async_execute(request=_request(), snapshot=_snapshot())
    assert result.status is delivery.FirstLiveTrialExecutionStatus.BLOCKED
    assert result.blocker_codes == ("durable_audit_intent_not_recorded",)
    assert result.approval_consumed_before_dispatch is False
    assert transport.calls == []


def test_execution_result_never_contains_native_rachio_ids() -> None:
    fields = delivery.FirstLiveTrialExecutionResult.__dataclass_fields__
    assert "device_id" not in fields
    assert "zone_id" not in fields
