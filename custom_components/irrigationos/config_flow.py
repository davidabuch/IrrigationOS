"""Config and options flows for IrrigationOS."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

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
from .first_live_delivery.operator import (
    FIRST_LIVE_OPERATOR_CONFIRMATION,
    async_run_supervised_first_live_trial,
)
from .landscape import (
    EstablishmentStage,
    IrrigationMethod,
    PlantType,
    SoilTexture,
    SunExposure,
)
from .landscape_intelligence import (
    CanonicalZoneIdentity,
    Confidence,
    DeliveryLinkStatus,
    IrrigationDeliveryLink,
    UserCalibratedBaseline,
    ZoneDemandSourceMode,
)
from .landscape_intelligence import (
    EstablishmentState as CommissioningEstablishmentState,
)
from .landscape_intelligence.onboarding import (
    ApprovedVisualPlantFinding,
    ManualPlantOnboardingInput,
    ZoneOnboardingRequest,
    map_zone_onboarding,
)

CONF_DISPLAY_NAME = "display_name"
CONF_PLANT_TYPE = "plant_type"
CONF_PLANT_DESCRIPTION = "plant_description"
CONF_ESTABLISHMENT_STAGE = "establishment_stage"
CONF_IRRIGATION_METHOD = "irrigation_method"
CONF_SUN_EXPOSURE = "sun_exposure"
CONF_SLOPE_PERCENT = "slope_percent"
CONF_SOIL_TEXTURE = "soil_texture"
CONF_SOIL_DESCRIPTION = "soil_description"
CONF_ROOT_DEPTH_INCHES = "root_depth_inches"
CONF_APPLICATION_RATE = "application_rate_inches_per_hour"
CONF_DISTRIBUTION_EFFICIENCY = "distribution_efficiency"
CONF_PROFILE_CONFIDENCE = "profile_confidence_percent"
CONF_OPTIONS_ACTION = "action"
CONF_FIRST_LIVE_TARGET = "first_live_target"
CONF_FIRST_LIVE_RUNTIME = "first_live_runtime_seconds"
CONF_FIRST_LIVE_CONFIRMATION = "first_live_confirmation"
CONF_COMMISSIONING_TARGET = "commissioning_target"
CONF_COMMISSIONING_MODE = "commissioning_mode"
CONF_COMMISSIONING_ZONE_NAME = "commissioning_zone_name"
CONF_COMMISSIONING_PLANT_NAME = "commissioning_plant_name"
CONF_COMMISSIONING_BOTANICAL_NAME = "commissioning_botanical_name"
CONF_COMMISSIONING_ESTABLISHMENT = "commissioning_establishment"
CONF_COMMISSIONING_PLANTED_DATE = "commissioning_planted_date"
CONF_COMMISSIONING_CONTAINER_GALLONS = "commissioning_container_gallons"
CONF_COMMISSIONING_HEIGHT_FEET = "commissioning_height_feet"
CONF_COMMISSIONING_DELIVERY_PROFILE_ID = "commissioning_delivery_profile_id"
CONF_COMMISSIONING_COMPONENT_IDS = "commissioning_component_ids"
CONF_COMMISSIONING_BASELINE_MINUTES = "commissioning_baseline_minutes"
CONF_COMMISSIONING_REFERENCE_TEMP_F = "commissioning_reference_temperature_f"
CONF_COMMISSIONING_RECENT_RAIN_MM = "commissioning_recent_rain_mm"
CONF_COMMISSIONING_ASSESSMENT_ID = "commissioning_assessment_id"
CONF_COMMISSIONING_EVIDENCE_IDS = "commissioning_evidence_ids"
CONF_COMMISSIONING_AI_PLANT_NAME = "commissioning_ai_plant_name"
CONF_COMMISSIONING_AI_BOTANICAL_NAME = "commissioning_ai_botanical_name"
CONF_COMMISSIONING_AI_CONFIDENCE = "commissioning_ai_confidence"
CONF_COMMISSIONING_VISIBLE_IRRIGATION = "commissioning_visible_irrigation"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=NAME): str,
    }
)


class IrrigationOSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle IrrigationOS configuration."""

    VERSION = 3

    def __init__(self) -> None:
        self._pending_data: dict[str, Any] | None = None
        self._pending_title = NAME
        self._discovery_summary: dict[str, str] = {}

    @staticmethod
    @callback  # type: ignore[untyped-decorator, unused-ignore]
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
    """Edit landscape profiles or run one supervised first-live trial."""

    def __init__(self) -> None:
        self._selected_area_id: str | None = None
        self._commissioning_controller_slot: int | None = None
        self._commissioning_area_slot: int | None = None
        self._commissioning_area_name: str | None = None
        self._commissioning_mode: ZoneDemandSourceMode | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose the interactive options workflow."""

        if user_input is not None:
            action = str(user_input[CONF_OPTIONS_ACTION])
            if action == "landscape":
                return await self.async_step_landscape()
            if action == "commissioning":
                return await self.async_step_commissioning()
            return await self.async_step_first_live_trial()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPTIONS_ACTION): vol.In(
                        {
                            "landscape": "Edit Landscape Digital Twin",
                            "commissioning": "Commission generic zone knowledge",
                            "first_live_trial": "Run supervised first-live watering trial",
                        }
                    )
                }
            ),
        )

    async def async_step_commissioning(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select one canonical target and generic onboarding mode."""
        choices: dict[str, str] = {}
        manager = self.config_entry.runtime_data.landscape_intelligence
        for controller_slot, controller in enumerate(
            self.config_entry.runtime_data.data.controllers, start=1
        ):
            for area in controller.areas:
                if (
                    area.configured
                    and area.enabled
                    and area.binding is not None
                    and manager.get_zone_by_slots(
                        controller_slot, area.slot_number
                    )
                    is None
                ):
                    key = f"{controller_slot}|{area.slot_number}"
                    choices[key] = area.vendor_name or area.name
        if not choices:
            return self.async_abort(reason="no_areas")
        if user_input is not None:
            controller_text, area_text = str(
                user_input[CONF_COMMISSIONING_TARGET]
            ).split("|", 1)
            self._commissioning_controller_slot = int(controller_text)
            self._commissioning_area_slot = int(area_text)
            self._commissioning_area_name = choices[
                str(user_input[CONF_COMMISSIONING_TARGET])
            ]
            self._commissioning_mode = ZoneDemandSourceMode(
                str(user_input[CONF_COMMISSIONING_MODE])
            )
            return await self.async_step_commissioning_input()
        return self.async_show_form(
            step_id="commissioning",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COMMISSIONING_TARGET): vol.In(choices),
                    vol.Required(CONF_COMMISSIONING_MODE): vol.In(
                        [item.value for item in ZoneDemandSourceMode]
                    ),
                }
            ),
        )

    async def async_step_commissioning_input(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Map approved onboarding input and persist it before reload."""
        if (
            self._commissioning_controller_slot is None
            or self._commissioning_area_slot is None
            or self._commissioning_mode is None
        ):
            return await self.async_step_commissioning()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                profile = _map_commissioning_form(
                    user_input,
                    controller_slot=self._commissioning_controller_slot,
                    area_slot=self._commissioning_area_slot,
                    mode=self._commissioning_mode,
                    now=datetime.now(UTC),
                    timezone=ZoneInfo(self.hass.config.time_zone),
                )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_input"
            else:
                manager = self.config_entry.runtime_data.landscape_intelligence
                saved = await manager.async_add_zone(
                    profile,
                )
                if saved:
                    return self.async_create_entry(
                        title="",
                        data=dict(self.config_entry.options),
                    )
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_input",
            data_schema=_commissioning_schema(
                self._commissioning_mode,
                self._commissioning_area_name or f"Zone {self._commissioning_area_slot}",
            ),
            errors=errors,
        )

    async def async_step_landscape(
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
            step_id="landscape",
            data_schema=vol.Schema({vol.Required(CONF_AREA_ID): vol.In(area_choices)}),
        )

    async def async_step_first_live_trial(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Run one explicitly confirmed supervised physical watering trial."""

        coordinator = self.config_entry.runtime_data
        choices: dict[str, str] = {}
        for controller in coordinator.data.controllers:
            for area in controller.areas:
                if area.configured and area.enabled and area.binding is not None:
                    key = f"{controller.controller_id}|{area.slot_number}"
                    choices[key] = f"{controller.name} - {area.vendor_name or area.name}"
        if not choices:
            return self.async_abort(reason="no_first_live_targets")

        errors: dict[str, str] = {}
        placeholders = {
            "confirmation_phrase": FIRST_LIVE_OPERATOR_CONFIRMATION,
            "commissioning_status": coordinator.live_commissioning.summary.status.value,
        }
        if user_input is not None:
            confirmation = str(user_input[CONF_FIRST_LIVE_CONFIRMATION])
            if confirmation.strip() != FIRST_LIVE_OPERATOR_CONFIRMATION:
                errors["base"] = "first_live_confirmation_mismatch"
            else:
                target = str(user_input[CONF_FIRST_LIVE_TARGET])
                controller_id, area_slot_text = target.rsplit("|", 1)
                try:
                    result = await async_run_supervised_first_live_trial(
                        coordinator,
                        controller_id=controller_id,
                        area_slot=int(area_slot_text),
                        runtime_seconds=int(user_input[CONF_FIRST_LIVE_RUNTIME]),
                        confirmation=confirmation,
                    )
                except ValueError:
                    errors["base"] = "first_live_trial_invalid"
                else:
                    return self.async_abort(
                        reason=f"first_live_trial_{result.status.value}",
                        description_placeholders={
                            "blockers": ", ".join(result.blocker_codes) or "none",
                            "runtime_seconds": str(result.runtime_seconds),
                        },
                    )

        return self.async_show_form(
            step_id="first_live_trial",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FIRST_LIVE_TARGET): vol.In(choices),
                    vol.Required(CONF_FIRST_LIVE_RUNTIME, default=30): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=120)
                    ),
                    vol.Required(CONF_FIRST_LIVE_CONFIRMATION): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_area(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit the selected area profile."""
        if self._selected_area_id is None:
            return await self.async_step_landscape()

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
        CONF_ESTABLISHMENT_STAGE,
                default=existing.get(CONF_PLANT_DESCRIPTION, profile.plant_description.value or ""),
            ): str,
            vol.Required(
                CONF_ESTABLISHMENT_STAGE,
                default=existing.get(
                    CONF_ESTABLISHMENT_STAGE,
                    profile.establishment_stage.value.value,
                ),
            ): vol.In([item.value for item in EstablishmentStage]),
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
        CONF_ESTABLISHMENT_STAGE,
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


def _commissioning_schema(
    mode: ZoneDemandSourceMode,
    default_name: str,
) -> vol.Schema:
    """Return the bounded generic onboarding form for one demand-source mode."""
    fields: dict[vol.Marker, Any] = {
        vol.Required(CONF_COMMISSIONING_ZONE_NAME, default=default_name): str,
    }
    if mode in {
        ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
        ZoneDemandSourceMode.HYBRID,
    }:
        fields.update(
            {
                vol.Required(CONF_COMMISSIONING_PLANT_NAME): str,
                vol.Optional(CONF_COMMISSIONING_BOTANICAL_NAME, default=""): str,
                vol.Required(
                    CONF_COMMISSIONING_ESTABLISHMENT,
                    default=CommissioningEstablishmentState.UNKNOWN.value,
                ): vol.In([item.value for item in CommissioningEstablishmentState]),
                vol.Optional(CONF_COMMISSIONING_PLANTED_DATE, default=""): str,
                vol.Optional(CONF_COMMISSIONING_CONTAINER_GALLONS, default=""): vol.Any(
                    "", vol.Coerce(float)
                ),
                vol.Optional(CONF_COMMISSIONING_HEIGHT_FEET, default=""): vol.Any(
                    "", vol.Coerce(float)
                ),
            }
        )
    if mode is ZoneDemandSourceMode.USER_CALIBRATED_BASELINE:
        fields.update(
            {
                vol.Required(CONF_COMMISSIONING_BASELINE_MINUTES, default=12): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=1440)
                ),
                vol.Required(CONF_COMMISSIONING_REFERENCE_TEMP_F, default=75): vol.Coerce(
                    float
                ),
                vol.Required(CONF_COMMISSIONING_RECENT_RAIN_MM, default=0): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
            }
        )
    if mode in {
        ZoneDemandSourceMode.PHOTO_AI_DERIVED,
        ZoneDemandSourceMode.HYBRID,
    }:
        fields.update(
            {
                vol.Required(CONF_COMMISSIONING_ASSESSMENT_ID): str,
                vol.Required(CONF_COMMISSIONING_EVIDENCE_IDS): str,
                vol.Required(CONF_COMMISSIONING_AI_PLANT_NAME): str,
                vol.Optional(CONF_COMMISSIONING_AI_BOTANICAL_NAME, default=""): str,
                vol.Required(
                    CONF_COMMISSIONING_AI_CONFIDENCE,
                    default=Confidence.MODERATE.value,
                ): vol.In([item.value for item in Confidence]),
                vol.Optional(CONF_COMMISSIONING_VISIBLE_IRRIGATION, default=""): str,
            }
        )
    if mode is not ZoneDemandSourceMode.USER_CALIBRATED_BASELINE:
        fields.update(
            {
                vol.Optional(CONF_COMMISSIONING_DELIVERY_PROFILE_ID, default=""): str,
                vol.Optional(CONF_COMMISSIONING_COMPONENT_IDS, default=""): str,
            }
        )
    return vol.Schema(fields)


def _optional_form_text(values: dict[str, Any], key: str) -> str | None:
    value = str(values.get(key, "")).strip()
    return value or None


def _form_ids(values: dict[str, Any], key: str) -> tuple[str, ...]:
    value = str(values.get(key, ""))
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _optional_form_float(values: dict[str, Any], key: str) -> float | None:
    value = values.get(key)
    if value in {None, ""}:
        return None
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ValueError(f"{key} must be numeric")
    number = float(value)
    if number <= 0:
        raise ValueError(f"{key} must be positive")
    return number


def _planting_datetime(
    values: dict[str, Any],
    timezone: ZoneInfo,
) -> datetime | None:
    value = _optional_form_text(values, CONF_COMMISSIONING_PLANTED_DATE)
    if value is None:
        return None
    return datetime.combine(date.fromisoformat(value), time.min, tzinfo=timezone)


def _map_commissioning_form(
    values: dict[str, Any],
    *,
    controller_slot: int,
    area_slot: int,
    mode: ZoneDemandSourceMode,
    now: datetime,
    timezone: ZoneInfo,
) -> Any:
    """Map one Home Assistant form into the provider-neutral onboarding contract."""
    zone_id = (
        f"zone.{area_slot}"
        if controller_slot == 1
        else f"zone.{controller_slot}.{area_slot}"
    )
    plant_group_id = f"{zone_id}.plant.primary"
    manual: tuple[ManualPlantOnboardingInput, ...] = ()
    visual: tuple[ApprovedVisualPlantFinding, ...] = ()
    baseline: UserCalibratedBaseline | None = None
    delivery_links: tuple[IrrigationDeliveryLink, ...] = ()

    if mode in {
        ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
        ZoneDemandSourceMode.HYBRID,
    }:
        manual = (
            ManualPlantOnboardingInput(
                plant_group_id=plant_group_id,
                common_name=str(values[CONF_COMMISSIONING_PLANT_NAME]).strip(),
                botanical_name=_optional_form_text(
                    values, CONF_COMMISSIONING_BOTANICAL_NAME
                ),
                establishment_state=CommissioningEstablishmentState(
                    str(values[CONF_COMMISSIONING_ESTABLISHMENT])
                ),
                observed_at=now,
                planted_at=_planting_datetime(values, timezone),
                source_container_gallons=_optional_form_float(
                    values, CONF_COMMISSIONING_CONTAINER_GALLONS
                ),
                current_height_meters=(
                    None
                    if (
                        height := _optional_form_float(
                            values, CONF_COMMISSIONING_HEIGHT_FEET
                        )
                    )
                    is None
                    else height * 0.3048
                ),
            ),
        )
    if mode is ZoneDemandSourceMode.USER_CALIBRATED_BASELINE:
        baseline = UserCalibratedBaseline(
            runtime_seconds=int(values[CONF_COMMISSIONING_BASELINE_MINUTES]) * 60,
            reference_air_temperature_celsius=(
                float(values[CONF_COMMISSIONING_REFERENCE_TEMP_F]) - 32
            )
            * 5
            / 9,
            reference_recent_precipitation_mm=float(
                values[CONF_COMMISSIONING_RECENT_RAIN_MM]
            ),
            reference_condition="user-confirmed dry-day reference condition",
            calibrated_at=now,
            confidence=Confidence.HIGH,
        )
    if mode in {
        ZoneDemandSourceMode.PHOTO_AI_DERIVED,
        ZoneDemandSourceMode.HYBRID,
    }:
        visual = (
            ApprovedVisualPlantFinding(
                plant_group_id=plant_group_id,
                assessment_id=str(values[CONF_COMMISSIONING_ASSESSMENT_ID]).strip(),
                evidence_ids=_form_ids(values, CONF_COMMISSIONING_EVIDENCE_IDS),
                likely_common_name=str(
                    values[CONF_COMMISSIONING_AI_PLANT_NAME]
                ).strip(),
                likely_botanical_name=_optional_form_text(
                    values, CONF_COMMISSIONING_AI_BOTANICAL_NAME
                ),
                confidence=Confidence(
                    str(values[CONF_COMMISSIONING_AI_CONFIDENCE])
                ),
                establishment_state=(
                    manual[0].establishment_state
                    if manual
                    else CommissioningEstablishmentState.UNKNOWN
                ),
                approved_at=now,
                visible_irrigation_method=_optional_form_text(
                    values, CONF_COMMISSIONING_VISIBLE_IRRIGATION
                ),
                delivery_profile_id=_optional_form_text(
                    values, CONF_COMMISSIONING_DELIVERY_PROFILE_ID
                ),
                delivery_component_ids=_form_ids(
                    values, CONF_COMMISSIONING_COMPONENT_IDS
                ),
            ),
        )
    delivery_profile_id = _optional_form_text(
        values, CONF_COMMISSIONING_DELIVERY_PROFILE_ID
    )
    if manual and delivery_profile_id is not None:
        delivery_links = (
            IrrigationDeliveryLink(
                f"{plant_group_id}.delivery",
                plant_group_id,
                DeliveryLinkStatus.DOCUMENTED,
                delivery_profile_id,
                _form_ids(values, CONF_COMMISSIONING_COMPONENT_IDS),
                None,
            ),
        )
    return map_zone_onboarding(
        ZoneOnboardingRequest(
            identity=CanonicalZoneIdentity(
                "property.primary", zone_id, controller_slot, area_slot
            ),
            display_name=str(values[CONF_COMMISSIONING_ZONE_NAME]).strip(),
            mode=mode,
            observed_at=now,
            manual_plants=manual,
            visual_findings=visual,
            calibrated_baseline=baseline,
            delivery_links=delivery_links,
        )
    )
