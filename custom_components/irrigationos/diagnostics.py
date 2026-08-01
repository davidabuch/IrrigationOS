"""Diagnostics for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .coordinator import IrrigationOSCoordinator

TO_REDACT = {CONF_API_KEY, "id", "person_id", "serialNumber", "macAddress"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
) -> dict[str, Any]:
    """Return redacted diagnostics."""
    del hass
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator": {
            "last_update_success": entry.runtime_data.last_update_success,
            "data": async_redact_data(entry.runtime_data.data or {}, TO_REDACT),
        },
    }
