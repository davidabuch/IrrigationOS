"""Binary sensor platform for IrrigationOS."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    """Set up IrrigationOS binary sensors."""
    del hass
    async_add_entities([IrrigationOSCloudHealthySensor(entry.runtime_data)])


class IrrigationOSCloudHealthySensor(IrrigationOSEntity, BinarySensorEntity):
    """Report whether the latest cloud refresh succeeded."""

    _attr_name = "Cloud connection"
    _attr_unique_id = "irrigationos_cloud_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return cloud health."""
        return self.coordinator.last_update_success
