"""Binary sensor platform for IrrigationOS."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSControllerEntity, IrrigationOSEntity, IrrigationOSZoneEntity
from .models import RachioController, RachioZone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IrrigationOS binary sensors."""
    del hass
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [IrrigationOSCloudHealthySensor(coordinator)]
    entities.extend(
        IrrigationOSControllerOnlineSensor(coordinator, controller)
        for controller in coordinator.data.controllers
    )
    entities.extend(
        IrrigationOSZoneEnabledSensor(coordinator, zone) for zone in coordinator.data.zones
    )
    async_add_entities(entities)


class IrrigationOSCloudHealthySensor(IrrigationOSEntity, BinarySensorEntity):
    """Report whether the latest cloud refresh succeeded."""

    _attr_name = "Cloud connection"
    _attr_unique_id = "irrigationos_cloud_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return cloud health."""
        return bool(self.coordinator.last_update_success)


class IrrigationOSControllerOnlineSensor(IrrigationOSControllerEntity, BinarySensorEntity):
    """Report whether a Rachio controller is online."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: IrrigationOSCoordinator, controller: RachioController) -> None:
        super().__init__(coordinator, controller)
        self._attr_unique_id = f"{controller.native_id}_online"

    @property
    def is_on(self) -> bool:
        """Return online state."""
        return self.controller.status.upper() == "ONLINE"


class IrrigationOSZoneEnabledSensor(IrrigationOSZoneEntity, BinarySensorEntity):
    """Report whether a Rachio zone is enabled."""

    _attr_name = "Enabled"

    def __init__(self, coordinator: IrrigationOSCoordinator, zone: RachioZone) -> None:
        super().__init__(coordinator, zone)
        self._attr_unique_id = f"{zone.native_id}_enabled"

    @property
    def is_on(self) -> bool:
        """Return whether the zone is enabled in Rachio."""
        return self.zone.enabled
