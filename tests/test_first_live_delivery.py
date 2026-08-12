"""Tests for the release-gated first-live physical delivery foundation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from tests.helpers import load_integration_module

commissioning_models = load_integration_module("live_commissioning.models")
delivery = load_integration_module("first_live_delivery")

FirstLiveTrialApproval = commissioning_models.FirstLiveTrialApproval
LiveCommissioningStatus = commissioning_models.LiveCommissioningStatus
LiveCommissioningSummary = commissioning_models.LiveCommissioningSummary


def _commissioning_summary(**overrides: object) -> Any:
    values: dict[str, object] = {
        "status": LiveCommissioningStatus.FIRST_LIVE_TRIAL_ELIGIBLE,
        "integrated_review_status": "validated_review_eligible",
        "evaluated_at": datetime(2026, 8, 12, 20, 0, tzinfo=UTC),
        "blocker_codes": (),
        "operator_approval_present": True,
        "approval_expires_at": datetime(2026, 8, 12, 20, 10, tzinfo=UTC),
        "approval_consumed": False,
        "target_controller_id": "controller-canonical",
        "target_controller_slot": 1,
        "target_area_slot": 1,
        "requested_runtime_seconds": 120,
        "max_runtime_seconds": 120,
        "supervised_daytime": True,
        "commissioning_window_open": True,
        "health_state": "healthy",
        "observation_age_seconds": 1.0,
        "active_external_watering_count": 0,
        "approval_ttl_seconds": 600,
        "single_use_approval": True,
        "approval_persists_across_restart": False,
        "required_acceptance_evidence": (),
    }
    values.update(overrides)
    return LiveCommissioningSummary(**values)


def test_release_gate_is_enabled_only_for_eligible_trial_foundation() -> None:
    summary = delivery.build_first_live_delivery_summary(_commissioning_summary())
    assert summary.status is delivery.FirstLiveDeliveryStatus.READY_FOR_FUTURE_ENABLEMENT
    assert summary.blocker_codes == ()
    assert summary.physical_transport_implemented is True
    assert summary.emergency_stop_implemented is True
    assert summary.physical_delivery_release_gate_enabled is True
    assert summary.autonomous_scheduling_enabled is False
    assert summary.ha_service_registered is False
    assert summary.live_control_authorized is False


def test_noneligible_commissioning_remains_blocked() -> None:
    summary = delivery.build_first_live_delivery_summary(
        _commissioning_summary(
            status=LiveCommissioningStatus.BLOCKED,
            requested_runtime_seconds=121,
        )
    )
    assert summary.status is delivery.FirstLiveDeliveryStatus.BLOCKED
    assert "commissioning_trial_not_eligible" in summary.blocker_codes
    assert "runtime_outside_first_live_delivery_limit" in summary.blocker_codes


def test_diagnostics_do_not_expose_native_controller_identifiers() -> None:
    summary = delivery.build_first_live_delivery_summary(_commissioning_summary())
    payload = summary.to_dict()
    assert "device_id" not in payload
    assert "zone_id" not in payload


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _Session:
    def __init__(self, status: int = 204) -> None:
        self.status = status
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        return _Response(self.status)


async def test_transport_uses_only_documented_bounded_start_and_stop_endpoints() -> None:
    session = _Session()
    transport = delivery.RachioFirstLiveTransport(cast(Any, session), "secret")
    await transport.async_start_zone(zone_id="zone-native", runtime_seconds=120)
    await transport.async_emergency_stop(device_id="device-native")

    assert len(session.calls) == 2
    assert session.calls[0]["method"] == "PUT"
    assert str(session.calls[0]["url"]).endswith("/public/zone/start")
    assert session.calls[0]["json"] == {"id": "zone-native", "duration": 120}
    assert str(session.calls[1]["url"]).endswith("/public/device/stop_water")
    assert session.calls[1]["json"] == {"id": "device-native"}


async def test_transport_rejects_runtime_above_first_live_limit_before_network() -> None:
    session = _Session()
    transport = delivery.RachioFirstLiveTransport(cast(Any, session), "secret")
    try:
        await transport.async_start_zone(zone_id="zone-native", runtime_seconds=121)
    except ValueError as err:
        assert "between 1 and 120" in str(err)
    else:
        raise AssertionError("expected ValueError")
    assert session.calls == []


async def test_transport_raises_on_non_success_response() -> None:
    session = _Session(status=500)
    transport = delivery.RachioFirstLiveTransport(cast(Any, session), "secret")
    try:
        await transport.async_emergency_stop(device_id="device-native")
    except delivery.FirstLiveTransportError as err:
        assert "HTTP 500" in str(err)
    else:
        raise AssertionError("expected FirstLiveTransportError")
