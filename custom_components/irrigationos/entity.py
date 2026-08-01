"""Base IrrigationOS entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IrrigationOSCoordinator
from .models import RachioController, RachioZone


class IrrigationOSEntity(CoordinatorEntity[IrrigationOSCoordinator]):
    """Base entity backed by the IrrigationOS coordinator."""

    _attr_has_entity_name = True


class IrrigationOSControllerEntity(IrrigationOSEntity):
    """Entity associated with a Rachio controller."""

    def __init__(self, coordinator: IrrigationOSCoordinator, controller: RachioController) -> None:
        super().__init__(coordinator)
        self.controller_id = controller.native_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.native_id)},
            manufacturer="Rachio",
            model=controller.model,
            name=controller.name,
            serial_number=controller.serial_number,
        )

    @property
    def controller(self) -> RachioController:
        """Return the latest controller snapshot."""
        for controller in self.coordinator.data.controllers:
            if controller.native_id == self.controller_id:
                return controller
        raise RuntimeError(f"Controller {self.controller_id} is no longer available")


class IrrigationOSZoneEntity(IrrigationOSEntity):
    """Entity associated with a Rachio zone."""

    def __init__(self, coordinator: IrrigationOSCoordinator, zone: RachioZone) -> None:
        super().__init__(coordinator)
        self.zone_id = zone.native_id
        self.controller_id = zone.controller_native_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone.native_id)},
            via_device=(DOMAIN, zone.controller_native_id),
            manufacturer="Rachio",
            model="Irrigation zone",
            name=zone.name,
        )

    @property
    def zone(self) -> RachioZone:
        """Return the latest zone snapshot."""
        for zone in self.coordinator.data.zones:
            if zone.native_id == self.zone_id:
                return zone
        raise RuntimeError(f"Zone {self.zone_id} is no longer available")
