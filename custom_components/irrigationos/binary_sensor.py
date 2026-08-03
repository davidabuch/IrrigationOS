"""Binary sensor platform for IrrigationOS."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controllers import ControllerAvailability, IrrigationArea, IrrigationController
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
    entities: list[BinarySensorEntity] = [IrrigationOSCloudHealthySensor(coordinator)]
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
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return cloud health."""
        return bool(self.coordinator.last_update_success)


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

    @property
    def is_on(self) -> bool:
        """Return whether the area is enabled in its controller."""
        return self.area.enabled
