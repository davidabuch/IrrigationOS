"""Binary sensor platform for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controllers import (
    ControllerAvailability,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
)
from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSAreaEntity, IrrigationOSControllerEntity, IrrigationOSEntity
from .reconciliation import EntityInventory, controller_first


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IrrigationOS binary sensors."""
    del hass
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        IrrigationOSCloudHealthySensor(coordinator),
        IrrigationOSRealtimeHealthySensor(coordinator),
        IrrigationOSPollingFallbackHealthySensor(coordinator),
        IrrigationOSWateringActiveSensor(coordinator),
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
) -> list[BinarySensorEntity]:
    """Create binary sensors for newly discovered canonical objects and slots."""
    candidates: dict[str, BinarySensorEntity] = {}
    for controller in coordinator.data.controllers:
        candidates[f"controller:{controller.controller_id}"] = (
            IrrigationOSControllerOnlineSensor(coordinator, controller)
        )
    for area in coordinator.data.areas:
        candidates[f"area:{area.area_id}"] = IrrigationOSAreaEnabledSensor(
            coordinator, area
        )
    result = inventory.reconcile(set(candidates))
    return [candidates[key] for key in controller_first(result.added)]


class IrrigationOSCloudHealthySensor(IrrigationOSEntity, BinarySensorEntity):
    """Report whether the latest cloud refresh succeeded."""

    _attr_name = "Cloud connection"
    _attr_unique_id = "irrigationos_cloud_connection"
    entity_id = "binary_sensor.irrigationos_cloud_connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return cloud health."""
        return bool(self.coordinator.last_update_success)


class IrrigationOSRealtimeHealthySensor(IrrigationOSEntity, BinarySensorEntity):
    """Report whether realtime webhook observation is healthy."""

    _attr_name = "Realtime observation"
    _attr_unique_id = "irrigationos_realtime_observation"
    entity_id = "binary_sensor.irrigationos_realtime_observation"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return realtime registration health."""
        manager = self.coordinator.realtime
        return bool(manager is not None and manager.enabled and manager.remote_health.healthy)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safe realtime telemetry for the Control Center."""
        manager = self.coordinator.realtime
        if manager is None:
            return {
                "url_source": "none",
                "registered_controllers": 0,
                "expected_controllers": 0,
                "accepted_event_count": 0,
                "rejected_event_count": 0,
                "duplicate_event_count": 0,
                "last_received_event": None,
                "last_rejection_reason": None,
                "last_rejection_timestamp": None,
            }
        return {
            "url_source": manager.url_source,
            "registered_controllers": manager.remote_health.registered_controllers,
            "expected_controllers": manager.remote_health.expected_controllers,
            "error_category": manager.remote_health.error_category,
            "accepted_event_count": manager.accepted_event_count,
            "rejected_event_count": manager.rejected_event_count,
            "duplicate_event_count": manager.duplicate_event_count,
            "last_received_event": manager.last_received_event,
            "last_rejection_reason": manager.last_rejection_reason,
            "last_rejection_timestamp": manager.last_rejection_timestamp,
        }


class IrrigationOSPollingFallbackHealthySensor(IrrigationOSEntity, BinarySensorEntity):
    """Report whether fallback polling is available and succeeding."""

    _attr_name = "Polling fallback"
    _attr_unique_id = "irrigationos_polling_fallback"
    entity_id = "binary_sensor.irrigationos_polling_fallback"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return polling fallback health."""
        return bool(self.coordinator.last_update_success)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return polling telemetry."""
        interval = self.coordinator.update_interval
        return {
            "enabled": interval is not None,
            "interval_minutes": (
                round(interval.total_seconds() / 60) if interval is not None else None
            ),
            "last_successful_refresh": self.coordinator.last_successful_refresh,
            "refresh_count": self.coordinator.refresh_count,
        }


class IrrigationOSWateringActiveSensor(IrrigationOSEntity, BinarySensorEntity):
    """Report whether any configured irrigation zone is watering."""

    _attr_name = "Watering active"
    _attr_unique_id = "irrigationos_watering_active"
    entity_id = "binary_sensor.irrigationos_watering_active"
    _attr_icon = "mdi:sprinkler-variant"

    @property
    def is_on(self) -> bool:
        """Return whether any configured area is watering."""
        return bool(self._watering_areas())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return active zone identities and user-facing names."""
        watering = self._watering_areas()
        return {
            "active_zone_count": len(watering),
            "active_zone_slots": [area.slot_number for area in watering],
            "active_zone_names": [self._display_name(area) for area in watering],
            "active_zone_vendor_names": [area.vendor_name for area in watering],
        }

    def _watering_areas(self) -> list[IrrigationArea]:
        return [
            area
            for area in self.coordinator.data.configured_areas
            if area.state is IrrigationAreaState.WATERING
        ]

    def _display_name(self, area: IrrigationArea) -> str:
        try:
            profile = self.coordinator.landscape.get_area(area.area_id)
        except KeyError:
            return f"Zone {area.slot_number}"
        if profile.display_name.source.value == "user":
            return profile.display_name.value
        return f"Zone {area.slot_number}"


class IrrigationOSControllerOnlineSensor(IrrigationOSControllerEntity, BinarySensorEntity):
    """Report whether a controller is online."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        controller: IrrigationController,
    ) -> None:
        super().__init__(coordinator, controller)
        self._attr_unique_id = f"{controller.controller_id}_online"

    @property
    def is_on(self) -> bool:
        """Return online state."""
        return self.controller.availability is ControllerAvailability.ONLINE


class IrrigationOSAreaEnabledSensor(IrrigationOSAreaEntity, BinarySensorEntity):
    """Report whether an irrigation area is enabled."""

    _attr_name = "Enabled"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_enabled"
        self._attr_suggested_object_id = f"zone_{area.slot_number}_enabled"

    @property
    def is_on(self) -> bool:
        """Return whether the area is enabled in its controller."""
        return self.area.enabled
