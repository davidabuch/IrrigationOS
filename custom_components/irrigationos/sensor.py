"""Sensor platform for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_OBSERVATION
from .controllers import IrrigationArea, IrrigationController
from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSAreaEntity, IrrigationOSControllerEntity, IrrigationOSEntity


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
        IrrigationOSProviderSensor(coordinator),
        IrrigationOSControllerCountSensor(coordinator),
        IrrigationOSAreaCountSensor(coordinator),
    ]
    entities.extend(
        IrrigationOSControllerStatusSensor(coordinator, controller)
        for controller in coordinator.data.controllers
    )
    entities.extend(
        IrrigationOSAreaSummarySensor(coordinator, area) for area in coordinator.data.areas
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


class IrrigationOSProviderSensor(IrrigationOSEntity, SensorEntity):
    """Expose the active controller provider."""

    _attr_name = "Controller provider"
    _attr_unique_id = "irrigationos_controller_provider"
    _attr_icon = "mdi:access-point-network"

    @property
    def native_value(self) -> str:
        """Return provider name."""
        return self.coordinator.data.provider


class IrrigationOSControllerCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered controllers."""

    _attr_name = "Controller count"
    _attr_unique_id = "irrigationos_controller_count"
    _attr_native_unit_of_measurement = "controllers"

    @property
    def native_value(self) -> int:
        """Return controller count."""
        return len(self.coordinator.data.controllers)


class IrrigationOSAreaCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered irrigation areas."""

    _attr_name = "Irrigation area count"
    _attr_unique_id = "irrigationos_area_count"
    _attr_native_unit_of_measurement = "areas"

    @property
    def native_value(self) -> int:
        """Return irrigation-area count."""
        return len(self.coordinator.data.areas)


class IrrigationOSControllerStatusSensor(IrrigationOSControllerEntity, SensorEntity):
    """Expose a controller's normalized status."""

    _attr_name = "Status"
    _attr_icon = "mdi:access-point-network"

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        controller: IrrigationController,
    ) -> None:
        super().__init__(coordinator, controller)
        self._attr_unique_id = f"{controller.controller_id}_status"

    @property
    def native_value(self) -> str:
        """Return controller availability."""
        return self.controller.availability.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return non-sensitive controller details."""
        controller = self.controller
        return {
            "provider": controller.provider,
            "enabled": controller.enabled,
            "model": controller.model,
            "area_count": len(controller.areas),
            "supports_current_watering": controller.capabilities.observe_current_watering,
            "supports_last_watered": controller.capabilities.observe_last_watered,
            "supports_start_area": controller.capabilities.supports_start_area,
            "supports_stop_area": controller.capabilities.supports_stop_area,
        }


class IrrigationOSAreaSummarySensor(IrrigationOSAreaEntity, SensorEntity):
    """Expose normalized irrigation-area metadata."""

    _attr_name = "Observation"
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_observation"

    @property
    def native_value(self) -> str:
        """Return the normalized area state."""
        return self.area.state.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return read-only area details."""
        area = self.area
        return {
            "native_number": area.native_number,
            "enabled": area.enabled,
            "last_watered_epoch_ms": area.last_watered_epoch_ms,
            "root_zone_depth_inches": area.root_zone_depth_inches,
            "efficiency": area.efficiency,
            "soil_name": area.soil_name,
            "crop_name": area.crop_name,
            "nozzle_name": area.nozzle_name,
            "nozzle_inches_per_hour": area.nozzle_inches_per_hour,
        }
