"""Data coordinator for IrrigationOS."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adapters.rachio import (
    RachioApiClient,
    RachioApiError,
    RachioAuthenticationError,
    RachioControllerAdapter,
    RachioRateLimitError,
)
from .const import CONF_API_KEY, CONF_PERSON_ID, DOMAIN, UPDATE_INTERVAL_MINUTES
from .controllers import ControllerRegistrySnapshot

_LOGGER = logging.getLogger(__name__)


class IrrigationOSCoordinator(DataUpdateCoordinator[ControllerRegistrySnapshot]):
    """Coordinate read-only controller observations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry
        client = RachioApiClient(
            async_get_clientsession(hass),
            str(entry.data[CONF_API_KEY]),
        )
        self.adapter = RachioControllerAdapter(client)

    async def _async_update_data(self) -> ControllerRegistrySnapshot:
        account_id = str(self.entry.data[CONF_PERSON_ID])
        try:
            return await self.adapter.async_get_snapshot(account_id)
        except RachioAuthenticationError as err:
            raise UpdateFailed("Rachio authentication failed") from err
        except RachioRateLimitError as err:
            detail = (
                f"; retry after {err.retry_after_seconds} seconds"
                if err.retry_after_seconds is not None
                else ""
            )
            raise UpdateFailed(f"Rachio rate limit reached{detail}") from err
        except (RachioApiError, ValueError) as err:
            raise UpdateFailed(str(err)) from err
