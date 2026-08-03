"""Config and options flows for IrrigationOS."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .adapters.factory import DEFAULT_PROVIDER_FACTORY
from .const import (
    CONF_API_KEY,
    CONF_AREA_ID,
    CONF_AREA_PROFILES,
    CONF_CONTROLLER_PROVIDER,
    CONF_IDENTITY_REGISTRY,
    CONF_OPERATING_MODE,
    CONF_PERSON_ID,
    DEFAULT_CONTROLLER_PROVIDER,
    DEFAULT_OPERATING_MODE,
    DOMAIN,
    NAME,
)
from .controllers import (
    ControllerAuthenticationError,
    ControllerIdentityRegistry,
    ControllerInvalidResponseError,
    ControllerProviderError,
    ControllerRateLimitError,
)
from .landscape import IrrigationMethod, PlantType, SoilTexture, SunExposure

CONF_DISPLAY_NAME = "display_name"
CONF_PLANT_TYPE = "plant_type"
CONF_PLANT_DESCRIPTION = "plant_description"
CONF_IRRIGATION_METHOD = "irrigation_method"
CONF_SUN_EXPOSURE = "sun_exposure"
CONF_SLOPE_PERCENT = "slope_percent"
CONF_SOIL_TEXTURE = "soil_texture"
CONF_SOIL_DESCRIPTION = "soil_description"
CONF_ROOT_DEPTH_INCHES = "root_depth_inches"
CONF_APPLICATION_RATE = "application_rate_inches_per_hour"
CONF_DISTRIBUTION_EFFICIENCY = "distribution_efficiency"
CONF_PROFILE_CONFIDENCE = "profile_confidence_percent"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=NAME): str,
    }
)


class IrrigationOSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle IrrigationOS configuration."""

    VERSION = 2

    def __init__(self) -> None:
        self._pending_data: dict[str, Any] | None = None
        self._pending_title = NAME
        self._discovery_summary: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the Landscape Digital Twin options flow."""
        del config_entry
        return IrrigationOSOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect and validate the Rachio API key."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        result = await self._async_validate_credentials(str(user_input[CONF_API_KEY]).strip())
        if isinstance(result, str):
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_SCHEMA, errors={"base": result}
            )
        person_id, snapshot, identities = result
        await self.async_set_unique_id(person_id)
        self._abort_if_unique_id_configured()
        self._pending_title = str(user_input.get(CONF_NAME, NAME))
        self._pending_data = {
            CONF_API_KEY: str(user_input[CONF_API_KEY]).strip(),
            CONF_PERSON_ID: person_id,
            CONF_CONTROLLER_PROVIDER: snapshot.provider,
            CONF_IDENTITY_REGISTRY: identities.as_dict(),
            CONF_OPERATING_MODE: DEFAULT_OPERATING_MODE,
            "discovered_controller_count": len(snapshot.controllers),
            "discovered_area_count": len(snapshot.configured_areas),
        }
        self._discovery_summary = {
            "controller_count": str(len(snapshot.controllers)),
            "area_count": str(len(snapshot.configured_areas)),
            "controller_names": ", ".join(item.name for item in snapshot.controllers) or "None",
            "area_names": ", ".join(
                item.vendor_name or item.name for item in snapshot.configured_areas
            )
            or "None",
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show discovered hardware before creating the config entry."""
        if self._pending_data is None:
            return await self.async_step_user()
        if user_input is not None:
            return self.async_create_entry(title=self._pending_title, data=self._pending_data)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=self._discovery_summary,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start a Rachio API-key reauthentication flow."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate and store a replacement Rachio API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            result = await self._async_validate_credentials(api_key)
            if isinstance(result, str):
                errors["base"] = result
            else:
                person_id, _snapshot, _identities = result
                await self.async_set_unique_id(person_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def _async_validate_credentials(
        self, api_key: str
    ) -> tuple[str, Any, ControllerIdentityRegistry] | str:
        """Validate credentials and return a normalized discovery snapshot."""
        identities = ControllerIdentityRegistry()
        adapter = DEFAULT_PROVIDER_FACTORY.create(
            DEFAULT_CONTROLLER_PROVIDER,
            async_get_clientsession(self.hass),
            api_key,
            identities,
        )
        try:
            person_id, snapshot = await adapter.async_get_account()
        except ControllerAuthenticationError:
            return "invalid_auth"
        except ControllerRateLimitError:
            return "rate_limited"
        except ControllerInvalidResponseError:
            return "invalid_response"
        except (ControllerProviderError, ValueError):
            return "cannot_connect"
        return person_id, snapshot, identities


class IrrigationOSOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit one Landscape Digital Twin area profile at a time."""

    def __init__(self) -> None:
        self._selected_area_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select the irrigation area to edit."""
        coordinator = self.config_entry.runtime_data
        area_choices = {
            area.area_id: area.vendor_name or area.name
            for area in coordinator.data.configured_areas
        }
        if not area_choices:
            return self.async_abort(reason="no_areas")

        if user_input is not None:
            self._selected_area_id = str(user_input[CONF_AREA_ID])
            return await self.async_step_area()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_AREA_ID): vol.In(area_choices)}),
        )

    async def async_step_area(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit the selected area profile."""
        if self._selected_area_id is None:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        existing_profiles = self.config_entry.options.get(CONF_AREA_PROFILES, {})
        if not isinstance(existing_profiles, dict):
            existing_profiles = {}
        existing = existing_profiles.get(self._selected_area_id, {})
        if not isinstance(existing, dict):
            existing = {}

        if user_input is not None:
            try:
                normalized = _normalize_profile_input(user_input)
            except ValueError:
                errors["base"] = "invalid_profile"
            else:
                profiles = {str(key): value for key, value in existing_profiles.items()}
                profiles[self._selected_area_id] = normalized
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options, CONF_AREA_PROFILES: profiles},
                )

        profile = self.config_entry.runtime_data.landscape.get_area(self._selected_area_id)
        return self.async_show_form(
            step_id="area",
            data_schema=_area_schema(existing, profile),
            errors=errors,
            description_placeholders={"area_name": profile.display_name.value},
        )


def _area_schema(existing: dict[str, Any], profile: Any) -> vol.Schema:
    """Return the editable Landscape Digital Twin schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_DISPLAY_NAME,
                default=existing.get(CONF_DISPLAY_NAME, profile.display_name.value),
            ): str,
            vol.Required(
                CONF_PLANT_TYPE,
                default=existing.get(CONF_PLANT_TYPE, profile.plant_type.value.value),
            ): vol.In([item.value for item in PlantType]),
            vol.Optional(
                CONF_PLANT_DESCRIPTION,
                default=existing.get(CONF_PLANT_DESCRIPTION, profile.plant_description.value or ""),
            ): str,
            vol.Required(
                CONF_IRRIGATION_METHOD,
                default=existing.get(CONF_IRRIGATION_METHOD, profile.irrigation_method.value.value),
            ): vol.In([item.value for item in IrrigationMethod]),
            vol.Required(
                CONF_SUN_EXPOSURE,
                default=existing.get(CONF_SUN_EXPOSURE, profile.sun_exposure.value.value),
            ): vol.In([item.value for item in SunExposure]),
            vol.Optional(
                CONF_SLOPE_PERCENT,
                default=existing.get(
                    CONF_SLOPE_PERCENT,
                    "" if profile.slope_percent.value is None else profile.slope_percent.value,
                ),
            ): vol.Any("", vol.Coerce(float)),
            vol.Required(
                CONF_SOIL_TEXTURE,
                default=existing.get(CONF_SOIL_TEXTURE, profile.soil_texture.value.value),
            ): vol.In([item.value for item in SoilTexture]),
            vol.Optional(
                CONF_SOIL_DESCRIPTION,
                default=existing.get(CONF_SOIL_DESCRIPTION, profile.soil_description.value or ""),
            ): str,
            vol.Optional(
                CONF_ROOT_DEPTH_INCHES,
                default=existing.get(
                    CONF_ROOT_DEPTH_INCHES,
                    ""
                    if profile.root_depth_inches.value is None
                    else profile.root_depth_inches.value,
                ),
            ): vol.Any("", vol.Coerce(float)),
            vol.Optional(
                CONF_APPLICATION_RATE,
                default=existing.get(
                    CONF_APPLICATION_RATE,
                    ""
                    if profile.application_rate_inches_per_hour.value is None
                    else profile.application_rate_inches_per_hour.value,
                ),
            ): vol.Any("", vol.Coerce(float)),
            vol.Optional(
                CONF_DISTRIBUTION_EFFICIENCY,
                default=existing.get(
                    CONF_DISTRIBUTION_EFFICIENCY,
                    ""
                    if profile.distribution_efficiency.value is None
                    else profile.distribution_efficiency.value,
                ),
            ): vol.Any("", vol.Coerce(float)),
            vol.Required(
                CONF_PROFILE_CONFIDENCE,
                default=existing.get(CONF_PROFILE_CONFIDENCE, 100),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        }
    )


def _normalize_profile_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize persisted user profile overrides."""
    normalized = dict(user_input)
    confidence = int(normalized.pop(CONF_PROFILE_CONFIDENCE))
    for field in (
        CONF_DISPLAY_NAME,
        CONF_PLANT_TYPE,
        CONF_PLANT_DESCRIPTION,
        CONF_IRRIGATION_METHOD,
        CONF_SUN_EXPOSURE,
        CONF_SLOPE_PERCENT,
        CONF_SOIL_TEXTURE,
        CONF_SOIL_DESCRIPTION,
        CONF_ROOT_DEPTH_INCHES,
        CONF_APPLICATION_RATE,
        CONF_DISTRIBUTION_EFFICIENCY,
    ):
        normalized[f"{field}_confidence"] = confidence

    _validate_range(normalized, CONF_SLOPE_PERCENT, 0, 100)
    _validate_range(normalized, CONF_ROOT_DEPTH_INCHES, 0.1, 120)
    _validate_range(normalized, CONF_APPLICATION_RATE, 0.01, 20)
    _validate_range(normalized, CONF_DISTRIBUTION_EFFICIENCY, 0.01, 1)
    return normalized


def _validate_range(values: dict[str, Any], field: str, minimum: float, maximum: float) -> None:
    """Validate an optional numeric field."""
    value = values.get(field)
    if value == "":
        values[field] = None
        return
    if value is None:
        return
    number = float(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} is outside its allowed range")
    values[field] = number
