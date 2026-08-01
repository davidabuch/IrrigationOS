"""Config flow for IrrigationOS."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .adapters.rachio import (
    RachioApiClient,
    RachioApiError,
    RachioAuthenticationError,
    RachioInvalidResponseError,
    RachioRateLimitError,
)
from .const import (
    CONF_API_KEY,
    CONF_OPERATING_MODE,
    CONF_PERSON_ID,
    DEFAULT_OPERATING_MODE,
    DOMAIN,
    NAME,
)
from .models import RachioAccountSnapshot

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=NAME): str,
    }
)


class IrrigationOSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle IrrigationOS configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Collect and validate the Rachio API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            client = RachioApiClient(async_get_clientsession(self.hass), api_key)
            try:
                person_id, payload = await client.async_get_account()
                snapshot = RachioAccountSnapshot.from_person_payload(payload)
            except RachioAuthenticationError:
                errors["base"] = "invalid_auth"
            except RachioRateLimitError:
                errors["base"] = "rate_limited"
            except RachioInvalidResponseError:
                errors["base"] = "invalid_response"
            except (RachioApiError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(person_id)
                self._abort_if_unique_id_configured()
                controller_count = len(snapshot.controllers)
                zone_count = len(snapshot.zones)
                return self.async_create_entry(
                    title=str(user_input.get(CONF_NAME, NAME)),
                    data={
                        CONF_API_KEY: api_key,
                        CONF_PERSON_ID: person_id,
                        CONF_OPERATING_MODE: DEFAULT_OPERATING_MODE,
                        "discovered_controller_count": controller_count,
                        "discovered_zone_count": zone_count,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
