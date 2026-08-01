"""Data coordinator for IrrigationOS."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adapters.rachio import RachioApiClient, RachioApiError
from .const import CONF_API_KEY, DOMAIN


class IrrigationOSCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate read-only controller observations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.entry = entry
        self.client = RachioApiClient(
            async_get_clientsession(hass),
            str(entry.data[CONF_API_KEY]),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            person_id = str(self.entry.data["person_id"])
            return await self.client.async_get_person(person_id)
        except RachioApiError as err:
            raise UpdateFailed(str(err)) from err
