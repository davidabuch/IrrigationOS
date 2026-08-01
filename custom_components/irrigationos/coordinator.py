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
    RachioRateLimitError,
)
from .const import CONF_API_KEY, CONF_PERSON_ID, DOMAIN, UPDATE_INTERVAL_MINUTES
from .models import RachioAccountSnapshot

_LOGGER = logging.getLogger(__name__)


class IrrigationOSCoordinator(DataUpdateCoordinator[RachioAccountSnapshot]):
    """Coordinate read-only Rachio observations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.client = RachioApiClient(
            async_get_clientsession(hass),
            str(entry.data[CONF_API_KEY]),
        )

    async def _async_update_data(self) -> RachioAccountSnapshot:
        person_id = str(self.entry.data[CONF_PERSON_ID])
        try:
            payload = await self.client.async_get_person(person_id)
            return RachioAccountSnapshot.from_person_payload(payload)
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
