"""Sensor platform for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_OBSERVATION
from .controllers import IrrigationArea, IrrigationController
from .coordinator import IrrigationOSCoordinator
from .entity import (
    IrrigationOSAreaEntity,
    IrrigationOSControllerEntity,
    IrrigationOSEntity,
    IrrigationOSLandscapeAreaEntity,
)
from .reconciliation import EntityInventory, controller_first


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
        IrrigationOSLandscapeStatusSensor(coordinator),
        IrrigationOSLastRefreshSensor(coordinator),
        IrrigationOSDiscoverySummarySensor(coordinator),
    ]
    inventory = EntityInventory()
    entities.extend(_new_dynamic_entities(coordinator, inventory))
    async_add_entities(entities)

    def _async_reconcile() -> None:
        additions = _new_dynamic_entities(coordinator, inventory)
        if additions:
            async_add_entities(additions)

    entry.async_on_unload(coordinator.async_add_listener(_async_reconcile))


def _new_dynamic_entities(
    coordinator: IrrigationOSCoordinator,
    inventory: EntityInventory,
) -> list[SensorEntity]:
    """Create sensors for newly discovered canonical objects and slots."""
    candidates: dict[str, SensorEntity] = {}
    for controller in coordinator.data.controllers:
        candidates[f"controller:{controller.controller_id}"] = (
            IrrigationOSControllerStatusSensor(coordinator, controller)
        )
    for area in coordinator.data.areas:
        candidates[f"area:{area.area_id}"] = IrrigationOSAreaSummarySensor(
            coordinator, area
        )
        if area.configured:
            candidates[f"landscape:{area.area_id}"] = IrrigationOSLandscapeProfileSensor(
                coordinator, area
            )
    result = inventory.reconcile(set(candidates))
    return [candidates[key] for key in controller_first(result.added)]


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

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_name = "Controller provider"
    _attr_unique_id = "irrigationos_controller_provider"
    _attr_icon = "mdi:access-point-network"

    @property
    def native_value(self) -> str:
        """Return provider name."""
        return self.coordinator.data.provider


class IrrigationOSControllerCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered controllers."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_name = "Controller count"
    _attr_unique_id = "irrigationos_controller_count"
    _attr_native_unit_of_measurement = "controllers"

    @property
    def native_value(self) -> int:
        """Return controller count."""
        return len(self.coordinator.data.controllers)


class IrrigationOSAreaCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered irrigation areas."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_name = "Irrigation area count"
    _attr_unique_id = "irrigationos_area_count"
    _attr_native_unit_of_measurement = "areas"

    @property
    def native_value(self) -> int:
        """Return irrigation-area count."""
        return len(self.coordinator.data.configured_areas)


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
            "capacity": controller.capacity,
            "watering_observation_quality": (
                controller.watering_observation_quality.value
            ),
        }


class IrrigationOSAreaSummarySensor(IrrigationOSAreaEntity, SensorEntity):
    """Expose normalized irrigation-area metadata."""

    _attr_name = "Observation"
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_observation"
        self._attr_suggested_object_id = f"zone_{area.slot_number}_observation"

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
            "slot_number": area.slot_number,
            "configured": area.configured,
            "vendor_name": area.vendor_name,
            "enabled": area.enabled,
            "last_watered_epoch_ms": area.last_watered_epoch_ms,
            "root_zone_depth_inches": area.root_zone_depth_inches,
            "efficiency": area.efficiency,
            "soil_name": area.soil_name,
            "crop_name": area.crop_name,
            "nozzle_name": area.nozzle_name,
            "nozzle_inches_per_hour": area.nozzle_inches_per_hour,
        }


class IrrigationOSLandscapeStatusSensor(IrrigationOSEntity, SensorEntity):
    """Expose overall Landscape Digital Twin completion."""

    _attr_name = "Landscape profile status"
    _attr_unique_id = "irrigationos_landscape_profile_status"
    _attr_icon = "mdi:land-plots"

    @property
    def native_value(self) -> str:
        """Return overall landscape profile state."""
        landscape = self.coordinator.landscape
        if not landscape.areas:
            return "unavailable"
        if landscape.complete_area_count == len(landscape.areas):
            return "complete"
        return "incomplete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return aggregate landscape details."""
        landscape = self.coordinator.landscape
        return {
            "schema_version": landscape.schema_version,
            "area_count": len(landscape.areas),
            "complete_area_count": landscape.complete_area_count,
        }


class IrrigationOSLandscapeProfileSensor(
    IrrigationOSLandscapeAreaEntity, SensorEntity
):
    """Expose the canonical landscape profile for an irrigation area."""

    _attr_name = "Landscape profile"
    _attr_icon = "mdi:land-plots"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_landscape_profile"
        self._attr_suggested_object_id = f"zone_{area.slot_number}_landscape_profile"

    @property
    def native_value(self) -> str:
        """Return profile completion state."""
        return "complete" if self.profile.is_complete else "incomplete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile values with provenance and confidence."""
        profile = self.profile
        return {
            "completion_percent": profile.completion_percent,
            "display_name": profile.display_name.value,
            "plant_type": profile.plant_type.value.value,
            "plant_description": profile.plant_description.value,
            "irrigation_method": profile.irrigation_method.value.value,
            "sun_exposure": profile.sun_exposure.value.value,
            "slope_percent": profile.slope_percent.value,
            "soil_texture": profile.soil_texture.value.value,
            "soil_description": profile.soil_description.value,
            "root_depth_inches": profile.root_depth_inches.value,
            "application_rate_inches_per_hour": (
                profile.application_rate_inches_per_hour.value
            ),
            "distribution_efficiency": profile.distribution_efficiency.value,
            "sources": {
                "plant_type": profile.plant_type.source.value,
                "irrigation_method": profile.irrigation_method.source.value,
                "sun_exposure": profile.sun_exposure.source.value,
                "slope_percent": profile.slope_percent.source.value,
                "soil_texture": profile.soil_texture.source.value,
                "root_depth_inches": profile.root_depth_inches.source.value,
                "application_rate": (
                    profile.application_rate_inches_per_hour.source.value
                ),
                "distribution_efficiency": (
                    profile.distribution_efficiency.source.value
                ),
            },
            "confidence": {
                "plant_type": profile.plant_type.confidence_percent,
                "irrigation_method": profile.irrigation_method.confidence_percent,
                "sun_exposure": profile.sun_exposure.confidence_percent,
                "slope_percent": profile.slope_percent.confidence_percent,
                "soil_texture": profile.soil_texture.confidence_percent,
                "root_depth_inches": profile.root_depth_inches.confidence_percent,
                "application_rate": (
                    profile.application_rate_inches_per_hour.confidence_percent
                ),
                "distribution_efficiency": (
                    profile.distribution_efficiency.source.value
                ),
            },
        }


class IrrigationOSLastRefreshSensor(IrrigationOSEntity, SensorEntity):
    """Expose the last successful controller refresh."""

    _attr_name = "Last successful refresh"
    _attr_unique_id = "irrigationos_last_successful_refresh"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return the last successful refresh timestamp."""
        return self.coordinator.last_successful_refresh

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return refresh telemetry."""
        return {"refresh_count": self.coordinator.refresh_count}


class IrrigationOSDiscoverySummarySensor(IrrigationOSEntity, SensorEntity):
    """Summarize live controller and irrigation-area discovery."""

    _attr_name = "Discovery summary"
    _attr_unique_id = "irrigationos_discovery_summary"
    _attr_icon = "mdi:radar"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return a compact discovery state."""
        return "ready" if self.coordinator.data.controllers else "no_controllers"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return discovered names for field validation."""
        return {
            "controller_names": [item.name for item in self.coordinator.data.controllers],
            "area_names": [
                item.vendor_name or item.name
                for item in self.coordinator.data.configured_areas
            ],
            "watering_areas": [
                item.name
                for item in self.coordinator.data.areas
                if item.state.value == "watering"
            ],
            "observed_at": self.coordinator.data.observation.observed_at.isoformat(),
            "fresh_until": self.coordinator.data.observation.fresh_until.isoformat(),
            "source_quality": self.coordinator.data.observation.quality.value,
            "partial_failure_count": len(self.coordinator.data.observation.errors),
        }
