"""Base IrrigationOS entities."""

from __future__ import annotations

from contextlib import suppress

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controllers import IrrigationArea, IrrigationController
from .coordinator import IrrigationOSCoordinator
from .landscape import IrrigationAreaProfile


class IrrigationOSEntity(CoordinatorEntity[IrrigationOSCoordinator]):
    """Base entity backed by the IrrigationOS coordinator."""

    _attr_has_entity_name = True


class IrrigationOSControllerEntity(IrrigationOSEntity):
    """Entity associated with a canonical controller."""

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        controller: IrrigationController,
    ) -> None:
        super().__init__(coordinator)
        self.controller_id = controller.controller_id
        self._last_controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.controller_id)},
            manufacturer=controller.provider.title(),
            model=controller.model,
            name=controller.name,
            serial_number=controller.serial_number,
        )

    def _current_controller(self) -> IrrigationController | None:
        return next(
            (
                controller
                for controller in self.coordinator.data.controllers
                if controller.controller_id == self.controller_id
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Remain registered but unavailable when hardware disappears."""
        return super().available and self._current_controller() is not None

    @property
    def controller(self) -> IrrigationController:
        """Return current data or the last-known safe snapshot."""
        current = self._current_controller()
        if current is not None:
            self._last_controller = current
        return self._last_controller


class IrrigationOSAreaEntity(IrrigationOSEntity):
    """Entity associated with a permanent canonical controller slot."""

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator)
        self.area_id = area.area_id
        self.controller_id = area.controller_id
        self._last_area = area
        self._attr_entity_registry_enabled_default = area.configured
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, area.area_id)},
            via_device=(DOMAIN, area.controller_id),
            manufacturer=self.coordinator.data.provider.title(),
            model="Irrigation slot",
            name=area.name,
        )

    def _current_area(self) -> IrrigationArea | None:
        return next(
            (area for area in self.coordinator.data.areas if area.area_id == self.area_id),
            None,
        )

    @property
    def available(self) -> bool:
        """Remain registered but unavailable when a controller disappears."""
        return super().available and self._current_area() is not None

    @property
    def area(self) -> IrrigationArea:
        """Return current data or the last-known safe slot snapshot."""
        current = self._current_area()
        if current is not None:
            self._last_area = current
        return self._last_area


class IrrigationOSLandscapeAreaEntity(IrrigationOSAreaEntity):
    """Entity associated with a configured Landscape Digital Twin profile."""

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._last_profile = coordinator.landscape.get_area(area.area_id)

    @property
    def profile(self) -> IrrigationAreaProfile:
        """Return current or last-known landscape state without raising."""
        with suppress(KeyError):
            self._last_profile = self.coordinator.landscape.get_area(self.area_id)
        return self._last_profile
