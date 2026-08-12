"""Contracts for the first-live physical command-delivery boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

FIRST_LIVE_DELIVERY_SCHEMA_VERSION = 1
PHYSICAL_FIRST_LIVE_DELIVERY_ENABLED = False
MAX_FIRST_LIVE_DELIVERY_RUNTIME_SECONDS = 120


class FirstLiveDeliveryStatus(StrEnum):
    """Release-level physical delivery state."""

    BLOCKED = "blocked"
    RELEASE_GATE_DISABLED = "release_gate_disabled"
    READY_FOR_FUTURE_ENABLEMENT = "ready_for_future_enablement"


@dataclass(frozen=True, slots=True)
class FirstLiveDeliveryRequest:
    """One bounded physical command request for a pre-commissioned target."""

    controller_slot: int
    area_slot: int
    device_id: str
    zone_id: str
    runtime_seconds: int
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class FirstLiveDeliverySummary:
    """Fail-closed evidence for the physical delivery boundary."""

    status: FirstLiveDeliveryStatus
    blocker_codes: tuple[str, ...]
    commissioning_status: str
    target_controller_slot: int | None
    target_area_slot: int | None
    requested_runtime_seconds: int | None
    max_runtime_seconds: int
    physical_transport_implemented: bool
    emergency_stop_implemented: bool
    physical_delivery_release_gate_enabled: bool
    autonomous_scheduling_enabled: bool
    ha_service_registered: bool
    live_mode_commissionable: bool = False
    live_control_feature_enabled: bool = False
    live_control_authorized: bool = False
    schema_version: int = FIRST_LIVE_DELIVERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return privacy-safe delivery evidence without native controller IDs."""

        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
