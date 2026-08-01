"""Data coordinator for IrrigationOS."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .adapters.rachio import (
    RachioApiClient,
    RachioApiError,
    RachioAuthenticationError,
    RachioControllerAdapter,
    RachioRateLimitError,
)
from .const import (
    CONF_API_KEY,
    CONF_AREA_PROFILES,
    CONF_PERSON_ID,
    DOMAIN,
    UPDATE_INTERVAL_MINUTES,
)
from .controllers import ControllerRegistrySnapshot
from .landscape import LandscapeProfile, build_landscape_profile

_LOGGER = logging.getLogger(__name__)


class IrrigationOSCoordinator(DataUpdateCoordinator[ControllerRegistrySnapshot]):
    """Coordinate read-only controller observations and the Landscape Digital Twin."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.landscape = LandscapeProfile(schema_version=1, areas=())
        self.last_successful_refresh: datetime | None = None
        self.refresh_count = 0
        client = RachioApiClient(
            async_get_clientsession(hass),
            str(entry.data[CONF_API_KEY]),
        )
        self.adapter = RachioControllerAdapter(client)

    async def _async_update_data(self) -> ControllerRegistrySnapshot:
        account_id = str(self.entry.data[CONF_PERSON_ID])
        try:
            snapshot = await self.adapter.async_get_snapshot(account_id)
        except RachioAuthenticationError as err:
            raise ConfigEntryAuthFailed("Rachio authentication failed") from err
        except RachioRateLimitError as err:
            detail = (
                f"; retry after {err.retry_after_seconds} seconds"
                if err.retry_after_seconds is not None
                else ""
            )
            raise UpdateFailed(f"Rachio rate limit reached{detail}") from err
        except (RachioApiError, ValueError) as err:
            raise UpdateFailed(str(err)) from err

        overrides = self.entry.options.get(CONF_AREA_PROFILES, {})
        if not isinstance(overrides, dict):
            overrides = {}
        self.landscape = build_landscape_profile(snapshot, _string_key_mapping(overrides))
        self.last_successful_refresh = dt_util.utcnow()
        self.refresh_count += 1
        return snapshot


def _string_key_mapping(value: dict[Any, Any]) -> dict[str, Any]:
    """Return a mapping with string keys for persisted config-entry options."""
    return {str(key): item for key, item in value.items()}
