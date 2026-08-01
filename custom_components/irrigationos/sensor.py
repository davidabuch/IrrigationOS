"""Sensor platform for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_OBSERVATION
from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSControllerEntity, IrrigationOSEntity, IrrigationOSZoneEntity
from .models import RachioController, RachioZone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IrrigationOS sensors."""
    del hass
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        IrrigationOSStatusSensor(coordinator),
        IrrigationOSControllerCountSensor(coordinator),
        IrrigationOSZoneCountSensor(coordinator),
    ]
    entities.extend(
        IrrigationOSControllerStatusSensor(coordinator, controller)
        for controller in coordinator.data.controllers
    )
    entities.extend(
        IrrigationOSZoneSummarySensor(coordinator, zone) for zone in coordinator.data.zones
    )
    async_add_entities(entities)


class IrrigationOSStatusSensor(IrrigationOSEntity, SensorEntity):
    """Show the observation-only system state."""

    _attr_name = "Status"
    _attr_unique_id = "irrigationos_status"
    _attr_icon = "mdi:sprinkler-variant"

    @property
    def native_value(self) -> str:
        """Return system state."""
        return MODE_OBSERVATION


class IrrigationOSControllerCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered controllers."""

    _attr_name = "Controller count"
    _attr_unique_id = "irrigationos_controller_count"
    _attr_native_unit_of_measurement = "controllers"

    @property
    def native_value(self) -> int:
        """Return controller count."""
        return len(self.coordinator.data.controllers)


class IrrigationOSZoneCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered zones."""

    _attr_name = "Zone count"
    _attr_unique_id = "irrigationos_zone_count"
    _attr_native_unit_of_measurement = "zones"

    @property
    def native_value(self) -> int:
        """Return zone count."""
        return len(self.coordinator.data.zones)


class IrrigationOSControllerStatusSensor(IrrigationOSControllerEntity, SensorEntity):
    """Expose a controller's reported cloud status."""

    _attr_name = "Status"
    _attr_icon = "mdi:access-point-network"

    def __init__(self, coordinator: IrrigationOSCoordinator, controller: RachioController) -> None:
        super().__init__(coordinator, controller)
        self._attr_unique_id = f"{controller.native_id}_status"

    @property
    def native_value(self) -> str:
        """Return controller status."""
        return self.controller.status.lower()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return non-sensitive controller details."""
        controller = self.controller
        return {
            "controller_on": controller.on,
            "model": controller.model,
            "zone_count": len(controller.zones),
        }


class IrrigationOSZoneSummarySensor(IrrigationOSZoneEntity, SensorEntity):
    """Expose read-only Rachio zone metadata."""

    _attr_name = "Observation"
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator: IrrigationOSCoordinator, zone: RachioZone) -> None:
        super().__init__(coordinator, zone)
        self._attr_unique_id = f"{zone.native_id}_observation"

    @property
    def native_value(self) -> str:
        """Return zone state for this observation-only release."""
        return "enabled" if self.zone.enabled else "disabled"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safe zone metadata from Rachio."""
        zone = self.zone
        return {
            "zone_number": zone.zone_number,
            "soil": zone.soil_name,
            "crop": zone.crop_name,
            "nozzle": zone.nozzle_name,
            "nozzle_inches_per_hour": zone.nozzle_inches_per_hour,
            "root_zone_depth_inches": zone.root_zone_depth_inches,
            "efficiency": zone.efficiency,
            "last_watered_epoch_ms": zone.last_watered_epoch_ms,
        }
