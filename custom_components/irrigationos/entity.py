"""Base IrrigationOS entity."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IrrigationOSCoordinator


class IrrigationOSEntity(CoordinatorEntity[IrrigationOSCoordinator]):
    """Base entity backed by the IrrigationOS coordinator."""

    _attr_has_entity_name = True
