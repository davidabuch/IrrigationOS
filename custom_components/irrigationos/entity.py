"""Base IrrigationOS entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controllers import IrrigationArea, IrrigationController
from .coordinator import IrrigationOSCoordinator


class IrrigationOSEntity(CoordinatorEntity[IrrigationOSCoordinator]):
    """Base entity backed by the IrrigationOS coordinator."""

    _attr_has_entity_name = True


class IrrigationOSControllerEntity(IrrigationOSEntity):
    """Entity associated with a controller-agnostic controller."""

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        controller: IrrigationController,
    ) -> None:
        super().__init__(coordinator)
        self.controller_id = controller.controller_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.controller_id)},
            manufacturer=controller.provider.title(),
            model=controller.model,
            name=controller.name,
            serial_number=controller.serial_number,
        )

    @property
    def controller(self) -> IrrigationController:
        """Return the latest controller snapshot."""
        for controller in self.coordinator.data.controllers:
            if controller.controller_id == self.controller_id:
                return controller
        raise RuntimeError(f"Controller {self.controller_id} is no longer available")


class IrrigationOSAreaEntity(IrrigationOSEntity):
    """Entity associated with a controller-agnostic irrigation area."""

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator)
        self.area_id = area.area_id
        self.controller_id = area.controller_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, area.area_id)},
            via_device=(DOMAIN, area.controller_id),
            manufacturer=self.coordinator.data.provider.title(),
            model="Irrigation area",
            name=area.name,
        )

    @property
    def area(self) -> IrrigationArea:
        """Return the latest irrigation-area snapshot."""
        for area in self.coordinator.data.areas:
            if area.area_id == self.area_id:
                return area
        raise RuntimeError(f"Irrigation area {self.area_id} is no longer available")
