"""Diagnostics for IrrigationOS."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .coordinator import IrrigationOSCoordinator

TO_REDACT = {
    CONF_API_KEY,
    "id",
    "person_id",
    "native_id",
    "controller_native_id",
    "account_id",
    "controller_id",
    "area_id",
    "serial_number",
    "serialNumber",
    "macAddress",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
) -> dict[str, Any]:
    """Return redacted diagnostics."""
    del hass
    snapshot = asdict(entry.runtime_data.data)
    landscape = asdict(entry.runtime_data.landscape)
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator": {
            "last_update_success": entry.runtime_data.last_update_success,
            "last_successful_refresh": (
                entry.runtime_data.last_successful_refresh.isoformat()
                if entry.runtime_data.last_successful_refresh is not None
                else None
            ),
            "refresh_count": entry.runtime_data.refresh_count,
            "last_exception": (
                str(entry.runtime_data.last_exception)
                if entry.runtime_data.last_exception is not None
                else None
            ),
            "data": async_redact_data(snapshot, TO_REDACT),
            "landscape": async_redact_data(landscape, TO_REDACT),
        },
    }
