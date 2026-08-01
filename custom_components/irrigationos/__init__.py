"""IrrigationOS integration setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import IrrigationOSCoordinator

type IrrigationOSConfigEntry = ConfigEntry[IrrigationOSCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> bool:
    """Set up IrrigationOS from a config entry."""
    coordinator = IrrigationOSCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> bool:
    """Unload an IrrigationOS config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
