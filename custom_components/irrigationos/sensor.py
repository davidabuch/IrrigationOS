"""Sensor platform for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IrrigationOS sensors."""
    del hass
    async_add_entities([IrrigationOSStatusSensor(entry.runtime_data)])


class IrrigationOSStatusSensor(IrrigationOSEntity, SensorEntity):
    """Show the observation-only system state."""

    _attr_name = "Status"
    _attr_unique_id = "irrigationos_status"
    _attr_icon = "mdi:sprinkler-variant"

    @property
    def native_value(self) -> str:
        """Return system state."""
        return "observation"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safe summary information."""
        devices = self.coordinator.data.get("devices", []) if self.coordinator.data else []
        return {"discovered_controller_count": len(devices)}
