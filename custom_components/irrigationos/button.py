"""Diagnostic buttons for IrrigationOS."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSEntity
from .health import IrrigationOSHealthState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the non-actuating health incident reset button."""

    del hass
    async_add_entities([IrrigationOSResetHealthIncidentButton(entry.runtime_data)])


class IrrigationOSResetHealthIncidentButton(IrrigationOSEntity, ButtonEntity):
    """Acknowledge recovered health history without touching irrigation equipment."""

    _attr_name = "Reset health incident"
    _attr_unique_id = "irrigationos_reset_health_incident"
    entity_id = "button.irrigationos_reset_health_incident"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:restore-alert"

    def __init__(self, coordinator: IrrigationOSCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Allow acknowledgement only while current health is fully healthy."""

        return self.coordinator.health_assessment.state is IrrigationOSHealthState.HEALTHY

    async def async_press(self) -> None:
        """Reset the diagnostic latch only."""

        await self.coordinator.reset_health_incident_latch()
