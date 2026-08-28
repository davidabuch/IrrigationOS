"""Transient manual-watering preferences shared by HA control entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import (
    MANUAL_WATERING_DEFAULT_RUNTIME_SECONDS,
    MANUAL_WATERING_MAX_RUNTIME_SECONDS,
    MANUAL_WATERING_MIN_RUNTIME_SECONDS,
)
from .controllers import IrrigationArea

if TYPE_CHECKING:
    from .coordinator import IrrigationOSCoordinator


class ManualWateringDurationManager:
    """Hold restored per-area UI preferences without scientific authority."""

    def __init__(self) -> None:
        self._runtime_seconds: dict[str, int] = {}

    def runtime_seconds(self, area_id: str) -> int:
        """Return the current UI-selected runtime or its safe default."""

        return self._runtime_seconds.get(
            area_id, MANUAL_WATERING_DEFAULT_RUNTIME_SECONDS
        )

    def set_runtime_seconds(self, area_id: str, runtime_seconds: int) -> None:
        """Set one validated finite manual runtime."""

        if not (
            MANUAL_WATERING_MIN_RUNTIME_SECONDS
            <= runtime_seconds
            <= MANUAL_WATERING_MAX_RUNTIME_SECONDS
        ):
            raise ValueError("manual watering runtime is outside the supported range")
        if runtime_seconds % 60:
            raise ValueError("manual watering runtime must use whole minutes")
        self._runtime_seconds[area_id] = runtime_seconds


def manual_watering_object_id(
    controller_slot: int, area_slot: int, suffix: str
) -> str:
    """Build predictable IDs while avoiding collisions on multi-controller installs."""

    prefix = (
        f"zone_{area_slot}"
        if controller_slot == 1
        else f"controller_{controller_slot}_zone_{area_slot}"
    )
    return f"{prefix}_{suffix}"


def manual_watering_display_name(
    coordinator: IrrigationOSCoordinator, area: IrrigationArea, controller_slot: int
) -> str:
    """Return commissioned name, provider name, then canonical slot fallback."""

    profile = coordinator.landscape_intelligence.get_zone_by_slots(
        controller_slot, area.slot_number
    )
    if profile is not None:
        return profile.display_name
    return area.vendor_name or f"Zone {area.slot_number}"
