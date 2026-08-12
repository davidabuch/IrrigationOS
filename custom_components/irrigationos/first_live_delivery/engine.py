"""Fail-closed policy for the first-live physical command boundary."""

from __future__ import annotations

from ..live_commissioning.models import LiveCommissioningSummary
from .models import (
    MAX_FIRST_LIVE_DELIVERY_RUNTIME_SECONDS,
    PHYSICAL_FIRST_LIVE_DELIVERY_ENABLED,
    FirstLiveDeliveryStatus,
    FirstLiveDeliverySummary,
)

FIRST_LIVE_DELIVERY_POLICY_REVISION = 1


def build_first_live_delivery_summary(
    commissioning: LiveCommissioningSummary,
) -> FirstLiveDeliverySummary:
    """Evaluate physical-delivery readiness while retaining the release kill switch."""

    blockers: set[str] = set()
    if commissioning.status.value != "first_live_trial_eligible":
        blockers.add("commissioning_trial_not_eligible")
    if commissioning.approval_consumed:
        blockers.add("commissioning_approval_consumed")
    runtime = commissioning.requested_runtime_seconds
    if runtime is None or not 1 <= runtime <= MAX_FIRST_LIVE_DELIVERY_RUNTIME_SECONDS:
        blockers.add("runtime_outside_first_live_delivery_limit")
    if commissioning.target_controller_slot is None or commissioning.target_controller_slot <= 0:
        blockers.add("controller_slot_not_bound")
    if commissioning.target_area_slot is None or commissioning.target_area_slot <= 0:
        blockers.add("area_slot_not_bound")
    if not PHYSICAL_FIRST_LIVE_DELIVERY_ENABLED:
        blockers.add("physical_delivery_release_gate_disabled")

    if not blockers:
        status = FirstLiveDeliveryStatus.READY_FOR_FUTURE_ENABLEMENT
    elif blockers == {"physical_delivery_release_gate_disabled"}:
        status = FirstLiveDeliveryStatus.RELEASE_GATE_DISABLED
    else:
        status = FirstLiveDeliveryStatus.BLOCKED

    return FirstLiveDeliverySummary(
        status=status,
        blocker_codes=tuple(sorted(blockers)),
        commissioning_status=commissioning.status.value,
        target_controller_slot=commissioning.target_controller_slot,
        target_area_slot=commissioning.target_area_slot,
        requested_runtime_seconds=runtime,
        max_runtime_seconds=MAX_FIRST_LIVE_DELIVERY_RUNTIME_SECONDS,
        physical_transport_implemented=True,
        emergency_stop_implemented=True,
        physical_delivery_release_gate_enabled=PHYSICAL_FIRST_LIVE_DELIVERY_ENABLED,
        autonomous_scheduling_enabled=False,
        ha_service_registered=False,
        live_mode_commissionable=False,
        live_control_feature_enabled=False,
        live_control_authorized=False,
    )
