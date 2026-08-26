"""Config and options flows for IrrigationOS."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
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
from .guided_observation import (
    GuidedObservationState,
    async_start_guided_observation,
    async_stop_guided_observation,
)
from .landscape import (
    EstablishmentStage,
    IrrigationMethod,
    PlantType,
    SoilTexture,
    SunExposure,
)
from .landscape_intelligence import (
    BaselineEnvironmentalReference,
    BaselineEnvironmentalScalingAssessment,
    BaselineReferenceSource,
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    Confidence,
    ConflictResolutionInput,
    ConversationalCommissioningIntake,
    ConversationalCommissioningProposal,
    DeliveryLinkStatus,
    DeliverySharing,
    IrrigationDeliveryLink,
    IrrigationRole,
    LandscapeChangeEvent,
    LandscapeEventType,
    LandscapePlantSnapshot,
    PlantAdditionInput,
    PlantCommissioningDetails,
    PlantEditInput,
    PlantGroup,
    PlantRemovalInput,
    SimpleDeliveryDescription,
    SimplePlantDescription,
    UserCalibratedBaseline,
    ZoneDemandSourceMode,
    add_plant_group,
    apply_baseline_reference_capture,
    assess_commissioning,
    build_commissioning_review,
    build_conversational_commissioning_proposal,
    capture_baseline_environmental_reference,
    edit_plant_group,
    remove_calibrated_baseline,
    remove_plant_group,
    resolve_identity_conflict,
    set_calibrated_baseline,
    update_delivery_link,
)
from .landscape_intelligence import (
    EstablishmentState as CommissioningEstablishmentState,
)
from .landscape_intelligence.baseline_reference import (
    SUPPORTED_REFERENCE_PERIOD_HOURS,
    BaselineReferenceCaptureStatus,
    CaptureBaselineReferenceRequest,
)
from .landscape_intelligence.onboarding import (
    ApprovedVisualPlantFinding,
    ManualPlantOnboardingInput,
    ZoneOnboardingRequest,
    map_zone_onboarding,
)
from .visual_assessment import (
    PhotoEvidence,
    PhotoEvidenceType,
    PhotoSource,
    PrivacyClassification,
    RetentionPolicy,
)
from .water_delivery import (
    DeliveryComponentCalibrationRequest,
    DeliveryEvidenceLevel,
    FlowBasis,
    MeasurementUnit,
    SprayPattern,
    WaterDeliveryProfile,
    WaterDeliveryType,
    calibrate_delivery_component,
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
CONF_COMMISSIONING_REFERENCE_ET0_MM = "commissioning_reference_et0_mm"
CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS = "commissioning_reference_period_hours"
CONF_COMMISSIONING_ASSESSMENT_ID = "commissioning_assessment_id"
CONF_COMMISSIONING_EVIDENCE_IDS = "commissioning_evidence_ids"
CONF_COMMISSIONING_AI_PLANT_NAME = "commissioning_ai_plant_name"
CONF_COMMISSIONING_AI_BOTANICAL_NAME = "commissioning_ai_botanical_name"
CONF_COMMISSIONING_AI_CONFIDENCE = "commissioning_ai_confidence"
CONF_COMMISSIONING_VISIBLE_IRRIGATION = "commissioning_visible_irrigation"
CONF_COMMISSIONING_REVIEW_TARGET = "commissioning_review_target"
CONF_COMMISSIONING_REVIEW_ACTION = "commissioning_review_action"
CONF_COMMISSIONING_PLANT_TARGET = "commissioning_plant_target"
CONF_COMMISSIONING_IRRIGATION_ROLE = "commissioning_irrigation_role"
CONF_COMMISSIONING_DIRECT_IRRIGATION = "commissioning_direct_irrigation"
CONF_COMMISSIONING_DEDICATED_EMITTER = "commissioning_dedicated_emitter"
CONF_COMMISSIONING_EMITTER_TYPE = "commissioning_emitter_type"
CONF_COMMISSIONING_REMOVE_CONFIRMATION = "commissioning_remove_confirmation"
CONF_COMMISSIONING_DELIVERY_STATUS = "commissioning_delivery_status"
CONF_COMMISSIONING_BASELINE_ACTION = "commissioning_baseline_action"
CONF_COMMISSIONING_CONFLICT_TARGET = "commissioning_conflict_target"
CONF_COMMISSIONING_RESOLUTION_COMMON_NAME = "commissioning_resolution_common_name"
CONF_COMMISSIONING_RESOLUTION_BOTANICAL_NAME = (
    "commissioning_resolution_botanical_name"
)
CONF_COMMISSIONING_RESOLUTION_NOTE = "commissioning_resolution_note"
CONF_COMMISSIONING_CAPTURE_DRY_CONFIRMATION = (
    "commissioning_capture_dry_confirmation"
)
CONF_COMMISSIONING_REPLACE_REFERENCE_CONFIRMATION = (
    "commissioning_replace_reference_confirmation"
)
CONF_COMMISSIONING_DELIVERY_COMPONENT_ID = "commissioning_delivery_component_id"
CONF_COMMISSIONING_DELIVERY_COMPONENT_NAME = "commissioning_delivery_component_name"
CONF_COMMISSIONING_DELIVERY_TYPE = "commissioning_delivery_type"
CONF_COMMISSIONING_COMPONENT_COUNT = "commissioning_component_count"
CONF_COMMISSIONING_FLOW_EVIDENCE_LEVEL = "commissioning_flow_evidence_level"
CONF_COMMISSIONING_FLOW_BASIS = "commissioning_flow_basis"
CONF_COMMISSIONING_FLOW_LPH = "commissioning_flow_liters_per_hour"
CONF_COMMISSIONING_COLLECTED_VOLUME = "commissioning_collected_volume"
CONF_COMMISSIONING_COLLECTED_VOLUME_UNIT = (
    "commissioning_collected_volume_unit"
)
CONF_COMMISSIONING_COLLECTION_DURATION = "commissioning_collection_duration_seconds"
CONF_COMMISSIONING_RADIUS_METERS = "commissioning_radius_meters"
CONF_SIMPLE_DESCRIPTION = "simple_description"
CONF_SIMPLE_PLANT_NAME = "simple_plant_name"
CONF_SIMPLE_PLANTED_DATE = "simple_planted_date"
CONF_SIMPLE_CONTAINER_GALLONS = "simple_container_gallons"
CONF_SIMPLE_HEIGHT_FEET = "simple_height_feet"
CONF_SIMPLE_DELIVERY_TYPE = "simple_delivery_type"
CONF_SIMPLE_EMITTER_CLASS = "simple_emitter_class"
CONF_SIMPLE_THROW_FEET = "simple_throw_feet"
CONF_SIMPLE_SPRAY_PATTERN = "simple_spray_pattern"
CONF_SIMPLE_SHARING = "simple_sharing"
CONF_SIMPLE_PLANTS_PER_EMITTER = "simple_plants_per_emitter"
CONF_SIMPLE_CONFIRM = "simple_confirm"
CONF_MANAGE_ZONE_ACTION = "manage_zone_action"
CONF_MANAGE_PLANT = "manage_plant"
CONF_ZONE_PHOTOS = "zone_photos"
CONF_ZONE_PHOTO_NOTE = "zone_photo_note"
CONF_ZONE_PHOTO_RUNNING = "zone_photo_running"

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
        self._review_property_id: str | None = None
        self._review_zone_id: str | None = None
        self._review_plant_group_id: str | None = None
        self._review_plant_action: str | None = None
        self._review_conflict_id: str | None = None
        self._simple_proposal: ConversationalCommissioningProposal | None = None
        self._manage_controller_slot: int | None = None
        self._manage_area_slot: int | None = None
        self._manage_plant_group_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose the interactive options workflow."""

        if user_input is not None:
            action = str(user_input[CONF_OPTIONS_ACTION])
            if action == "manage_zones":
                return await self.async_step_manage_zones()
            if action == "landscape":
                return await self.async_step_landscape()
            if action == "commissioning":
                return await self.async_step_commissioning()
            if action == "commissioning_simple":
                return await self.async_step_commissioning_simple()
            if action == "commissioning_review":
                return await self.async_step_commissioning_review_select()
            return await self.async_step_first_live_trial()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPTIONS_ACTION): vol.In(
                        {
                            "manage_zones": "Manage zones",
                            "landscape": "Edit Landscape Digital Twin",
                            "commissioning": "Commission generic zone knowledge",
                            "commissioning_simple": "Simple guided zone setup",
                            "commissioning_review": "Review or edit commissioned zones",
                            "first_live_trial": "Run supervised first-live watering trial",
                        }
                    )
                }
            ),
        )

    async def async_step_manage_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show every configured zone through one permanent simple entry point."""
        choices: dict[str, str] = {}
        manager = self.config_entry.runtime_data.landscape_intelligence
        for controller_slot, controller in enumerate(
            self.config_entry.runtime_data.data.controllers, start=1
        ):
            for area in controller.areas:
                if not area.configured or area.binding is None:
                    continue
                profile = manager.get_zone_by_slots(controller_slot, area.slot_number)
                status = _plain_zone_status(profile)
                choices[f"{controller_slot}|{area.slot_number}"] = (
                    f"{area.vendor_name or area.name} — {status}"
                )
        if not choices:
            return self.async_abort(reason="no_areas")
        if user_input is not None:
            controller, area = str(user_input[CONF_COMMISSIONING_TARGET]).split("|", 1)
            self._manage_controller_slot = int(controller)
            self._manage_area_slot = int(area)
            self._commissioning_controller_slot = int(controller)
            self._commissioning_area_slot = int(area)
            selected_label = choices[str(user_input[CONF_COMMISSIONING_TARGET])]
            self._commissioning_area_name = selected_label.split(" — ", 1)[0]
            return await self.async_step_manage_zone()
        return self.async_show_form(
            step_id="manage_zones",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_TARGET): vol.In(choices)}
            ),
        )

    async def async_step_manage_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Offer plain-language actions for one selected zone."""
        if self._manage_controller_slot is None or self._manage_area_slot is None:
            return await self.async_step_manage_zones()
        coordinator = self.config_entry.runtime_data
        manager = coordinator.landscape_intelligence
        profile = manager.get_zone_by_slots(
            self._manage_controller_slot, self._manage_area_slot
        )
        run = coordinator.guided_observation.snapshot
        active_here = (
            run.controller_slot == self._manage_controller_slot
            and run.area_slot == self._manage_area_slot
            and run.state in {
                GuidedObservationState.STARTING,
                GuidedObservationState.RUNNING,
                GuidedObservationState.STOPPING,
                GuidedObservationState.UNCERTAIN,
            }
        )
        actions = {
            "tell": (
                "Tell IrrigationOS about this zone"
                if profile is None
                else "Update plants and irrigation"
            ),
            "photos": "Take or add photos",
            "stop" if active_here else "run": (
                f"Stop {self._commissioning_area_name}" if active_here
                else f"Run {self._commissioning_area_name} for 3 minutes"
            ),
            "review": "Review what IrrigationOS understands",
            "advanced": "Advanced",
            "done": "Done",
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            action = str(user_input[CONF_MANAGE_ZONE_ACTION])
            if action == "tell":
                if profile is not None and len(profile.landscape_profile.plant_groups) > 1:
                    return await self.async_step_manage_zone_plant()
                if profile is not None and profile.landscape_profile.plant_groups:
                    self._manage_plant_group_id = (
                        profile.landscape_profile.plant_groups[0].plant_group_id
                    )
                return await self.async_step_commissioning_simple_input()
            if action == "photos":
                return await self.async_step_manage_zone_photos()
            if action == "review":
                return await self.async_step_manage_zone_review()
            if action == "advanced":
                if profile is None:
                    return await self.async_step_commissioning()
                self._review_property_id = profile.identity.property_id
                self._review_zone_id = profile.identity.zone_id
                return await self.async_step_commissioning_review()
            if action == "done":
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
            result = (
                await async_stop_guided_observation(
                    coordinator,
                    controller_slot=self._manage_controller_slot,
                    area_slot=self._manage_area_slot,
                )
                if action == "stop"
                else await async_start_guided_observation(
                    coordinator,
                    controller_slot=self._manage_controller_slot,
                    area_slot=self._manage_area_slot,
                )
            )
            if result.blocker_codes:
                errors["base"] = result.blocker_codes[0]
            else:
                return await self.async_step_manage_zone()
        return self.async_show_form(
            step_id="manage_zone",
            data_schema=vol.Schema(
                {vol.Required(CONF_MANAGE_ZONE_ACTION): vol.In(actions)}
            ),
            errors=errors,
            description_placeholders={
                "zone_name": self._commissioning_area_name or "Zone",
                "status": _plain_zone_status(profile),
            },
        )

    async def async_step_manage_zone_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select an existing plant by plain name before a simple update."""
        manager = self.config_entry.runtime_data.landscape_intelligence
        profile = manager.get_zone_by_slots(
            self._manage_controller_slot or 0, self._manage_area_slot or 0
        )
        if profile is None:
            return await self.async_step_commissioning_simple_input()
        choices = {
            plant.plant_group_id: plant.common_name
            for plant in profile.landscape_profile.plant_groups
        }
        choices["__add_new__"] = "Add another plant group"
        if user_input is not None:
            self._manage_plant_group_id = str(user_input[CONF_MANAGE_PLANT])
            return await self.async_step_commissioning_simple_input()
        return self.async_show_form(
            step_id="manage_zone_plant",
            data_schema=vol.Schema({vol.Required(CONF_MANAGE_PLANT): vol.In(choices)}),
        )

    async def async_step_manage_zone_photos(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Persist only opaque HA media references, never image bytes."""
        errors: dict[str, str] = {}
        if user_input is not None:
            manager = self.config_entry.runtime_data.landscape_intelligence
            profile = manager.get_zone_by_slots(
                self._manage_controller_slot or 0, self._manage_area_slot or 0
            )
            property_id = "property.primary" if profile is None else profile.identity.property_id
            zone_id = (
                f"zone.{self._manage_area_slot}"
                if profile is None
                else profile.identity.zone_id
            )
            raw = user_input[CONF_ZONE_PHOTOS]
            selected = raw if isinstance(raw, list) else [raw]
            photos = tuple(
                PhotoEvidence(
                    evidence_id=f"photo.{uuid4().hex}",
                    area_id=zone_id,
                    property_id=property_id,
                    evidence_type=(
                        PhotoEvidenceType.RUNNING_CONDITION
                        if bool(user_input.get(CONF_ZONE_PHOTO_RUNNING, False))
                        else PhotoEvidenceType.AREA_OVERVIEW
                    ),
                    captured_at=datetime.now(UTC),
                    source=PhotoSource.USER_SELECTED,
                    privacy_classification=PrivacyClassification.PRIVATE,
                    retention_policy=RetentionPolicy.UNTIL_DELETED,
                    content_reference=_media_content_id(item),
                    user_note=_optional_form_text(user_input, CONF_ZONE_PHOTO_NOTE),
                    zone_running_context=bool(
                        user_input.get(CONF_ZONE_PHOTO_RUNNING, False)
                    ),
                )
                for item in selected
            )
            if await manager.async_add_photo_evidence(photos):
                return await self.async_step_manage_zone_review()
            errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="manage_zone_photos",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE_PHOTOS): selector.MediaSelector(
                        selector.MediaSelectorConfig(accept=["image/*"], multiple=True)
                    ),
                    vol.Optional(CONF_ZONE_PHOTO_NOTE, default=""): str,
                    vol.Required(CONF_ZONE_PHOTO_RUNNING, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_manage_zone_review(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show a compact plain-language reconstruction from canonical state."""
        del user_input
        manager = self.config_entry.runtime_data.landscape_intelligence
        profile = manager.get_zone_by_slots(
            self._manage_controller_slot or 0, self._manage_area_slot or 0
        )
        if profile is None:
            summary = "IrrigationOS does not have landscape details for this zone yet."
            questions = "Tell IrrigationOS what you know about the plants and irrigation."
        else:
            review = manager.review_zone(profile.identity.property_id, profile.identity.zone_id)
            assert review is not None
            summary = "; ".join(
                f"{item.plant_group.common_name} "
                f"({item.plant_group.establishment_state.value.replace('_', ' ')})"
                for item in review.plants
            ) or "No active plants documented"
            questions = " | ".join(
                item.prompt for item in review.commissioning_assessment.follow_up_requirements[:3]
            ) or "No high-priority questions right now."
            photos = manager.photos_for_zone(profile.identity.property_id, profile.identity.zone_id)
            summary = f"Plants: {summary}. Photos saved: {len(photos)}."
        return self.async_show_form(
            step_id="manage_zone_review",
            data_schema=vol.Schema({}),
            description_placeholders={"understood": summary, "questions": questions},
        )

    async def async_step_commissioning_simple(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select an uncommissioned canonical target for simple guided setup."""
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
                    and manager.get_zone_by_slots(controller_slot, area.slot_number) is None
                ):
                    choices[f"{controller_slot}|{area.slot_number}"] = (
                        area.vendor_name or area.name
                    )
        if not choices:
            return self.async_abort(reason="no_areas")
        if user_input is not None:
            selected = str(user_input[CONF_COMMISSIONING_TARGET])
            controller, area = selected.split("|", 1)
            self._commissioning_controller_slot = int(controller)
            self._commissioning_area_slot = int(area)
            self._commissioning_area_name = choices[selected]
            return await self.async_step_commissioning_simple_input()
        return self.async_show_form(
            step_id="commissioning_simple",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_TARGET): vol.In(choices)}
            ),
        )

    async def async_step_commissioning_simple_input(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect understandable observations and build a reviewable candidate."""
        if self._commissioning_controller_slot is None or self._commissioning_area_slot is None:
            return await self.async_step_commissioning_simple()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                proposal = _map_simple_commissioning_form(
                    user_input,
                    controller_slot=self._commissioning_controller_slot,
                    area_slot=self._commissioning_area_slot,
                    zone_name=self._commissioning_area_name
                    or f"Zone {self._commissioning_area_slot}",
                    now=datetime.now(UTC),
                    timezone=ZoneInfo(self.hass.config.time_zone),
                )
                existing = self.config_entry.runtime_data.landscape_intelligence.get_zone_by_slots(
                    self._commissioning_controller_slot,
                    self._commissioning_area_slot,
                )
                self._simple_proposal = (
                    proposal
                    if existing is None
                    else _merge_simple_update(
                        existing,
                        proposal,
                        datetime.now(UTC),
                        plant_group_id=self._manage_plant_group_id,
                    )
                )
                if existing is not None:
                    self._simple_proposal = _preserve_existing_delivery_calibration(
                        self.config_entry.runtime_data.landscape_intelligence,
                        existing,
                        self._simple_proposal,
                        plant_group_id=self._manage_plant_group_id,
                    )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_input"
            else:
                return await self.async_step_commissioning_simple_review()
        return self.async_show_form(
            step_id="commissioning_simple_input",
            data_schema=_simple_commissioning_schema(
                self.config_entry.runtime_data.landscape_intelligence.get_zone_by_slots(
                    self._commissioning_controller_slot,
                    self._commissioning_area_slot,
                ),
                plant_group_id=self._manage_plant_group_id,
            ),
            errors=errors,
        )

    async def async_step_commissioning_simple_review(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Require explicit confirmation before atomically persisting canonical evidence."""
        proposal = self._simple_proposal
        if proposal is None:
            return await self.async_step_commissioning_simple_input()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not bool(user_input[CONF_SIMPLE_CONFIRM]):
                errors["base"] = "confirmation_required"
            else:
                manager = self.config_entry.runtime_data.landscape_intelligence
                existing = manager.get_zone(
                    proposal.zone_profile.identity.property_id,
                    proposal.zone_profile.identity.zone_id,
                )
                if proposal.delivery_profile is None:
                    saved = (
                        await manager.async_add_zone(proposal.zone_profile)
                        if existing is None
                        else await manager.async_update_zone(proposal.zone_profile)
                    )
                else:
                    saved = (
                        await manager.async_add_zone_and_delivery_profile(
                            proposal.zone_profile, proposal.delivery_profile
                        )
                        if existing is None
                        else await manager.async_update_zone_and_delivery_profile(
                            proposal.zone_profile, proposal.delivery_profile
                        )
                    )
                if saved:
                    return self.async_create_entry(
                        title="", data=dict(self.config_entry.options)
                    )
                errors["base"] = "commissioning_persistence_failed"
        questions = " | ".join(
            item.question for item in proposal.follow_up_questions
        ) or "No additional information is required for this commissioning record."
        return self.async_show_form(
            step_id="commissioning_simple_review",
            data_schema=vol.Schema({vol.Required(CONF_SIMPLE_CONFIRM, default=False): bool}),
            errors=errors,
            description_placeholders={
                "understood": " | ".join(proposal.summary),
                "questions": questions,
                "authority": "Advisory evidence only; watering is not authorized.",
            },
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
                        [
                            item.value
                            for item in ZoneDemandSourceMode
                            if item is not ZoneDemandSourceMode.UNRESOLVED
                        ]
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

    def _selected_review_profile(self) -> CommissionedZoneProfile | None:
        """Return the selected generic profile without provider-native identity."""
        if self._review_property_id is None or self._review_zone_id is None:
            return None
        return self.config_entry.runtime_data.landscape_intelligence.get_zone(
            self._review_property_id,
            self._review_zone_id,
        )

    async def async_step_commissioning_review_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select one durable canonical zone for detailed review."""
        manager = self.config_entry.runtime_data.landscape_intelligence
        choices = {
            f"{zone.identity.property_id}|{zone.identity.zone_id}": (
                f"{zone.display_name} — controller "
                f"{zone.identity.controller_slot or 'unbound'}, area "
                f"{zone.identity.area_slot}"
            )
            for zone in manager.commissioned_zones
        }
        if not choices:
            return self.async_abort(reason="no_commissioned_zones")
        if user_input is not None:
            property_id, zone_id = str(
                user_input[CONF_COMMISSIONING_REVIEW_TARGET]
            ).split("|", 1)
            self._review_property_id = property_id
            self._review_zone_id = zone_id
            return await self.async_step_commissioning_review()
        return self.async_show_form(
            step_id="commissioning_review_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_REVIEW_TARGET): vol.In(choices)}
            ),
        )

    async def async_step_commissioning_review(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Review bounded facts and choose one explicit edit operation."""
        profile = self._selected_review_profile()
        if profile is None:
            return await self.async_step_commissioning_review_select()
        manager = self.config_entry.runtime_data.landscape_intelligence
        review = manager.review_zone(
            profile.identity.property_id, profile.identity.zone_id
        )
        if review is None:
            return await self.async_step_commissioning_review_select()
        actions: dict[str, str] = {
            "add_plant": "Add plant group",
            "edit_baseline": "Review or edit calibrated baseline",
            "finish": "Finish review",
        }
        if review.calibrated_baselines:
            actions["capture_baseline_reference"] = (
                "Capture current conditions as baseline reference"
            )
        if review.plants:
            actions.update(
                {
                    "edit_plant": "Edit plant group",
                    "remove_plant": "Remove plant group",
                    "edit_delivery": "Edit irrigation-delivery link",
                    "calibrate_delivery": "Calibrate irrigation-delivery evidence",
                }
            )
        if review.unresolved_conflicts:
            actions["resolve_conflict"] = "Review or resolve evidence conflict"
        if user_input is not None:
            action = str(user_input[CONF_COMMISSIONING_REVIEW_ACTION])
            if action == "finish":
                return self.async_create_entry(
                    title="", data=dict(self.config_entry.options)
                )
            if action == "add_plant":
                return await self.async_step_commissioning_add_plant()
            if action == "edit_baseline":
                return await self.async_step_commissioning_baseline()
            if action == "capture_baseline_reference":
                return await self.async_step_commissioning_baseline_reference()
            if action == "resolve_conflict":
                return await self.async_step_commissioning_conflict_select()
            self._review_plant_action = action
            return await self.async_step_commissioning_plant_select()
        return self.async_show_form(
            step_id="commissioning_review",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_REVIEW_ACTION): vol.In(actions)}
            ),
            description_placeholders={
                "review_summary": _commissioning_review_summary(
                    profile,
                    manager.baseline_scaling_for(
                        profile.identity.property_id, profile.identity.zone_id
                    ),
                    delivery_profiles=manager.delivery_profiles,
                )
            },
        )

    async def async_step_commissioning_add_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add one user-confirmed plant without replacing existing groups."""
        profile = self._selected_review_profile()
        if profile is None:
            return await self.async_step_commissioning_review_select()
        errors: dict[str, str] = {}
        if user_input is not None:
            now = datetime.now(UTC)
            plant_id = _next_plant_group_id(profile)
            try:
                plant = _manual_plant_from_form(
                    user_input,
                    plant_group_id=plant_id,
                    now=now,
                    timezone=ZoneInfo(self.hass.config.time_zone),
                )
                candidate = add_plant_group(
                    profile,
                    PlantAdditionInput(
                        _commissioning_event_id(profile, "add", now),
                        plant,
                        now,
                        _delivery_link_from_form(user_input, plant_id),
                    ),
                )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_edit"
            else:
                if await self.config_entry.runtime_data.landscape_intelligence.async_update_zone(
                    candidate
                ):
                    return await self.async_step_commissioning_review()
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_add_plant",
            data_schema=_commissioning_plant_schema(),
            errors=errors,
        )

    async def async_step_commissioning_plant_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select one active plant for edit, removal, or delivery review."""
        profile = self._selected_review_profile()
        if profile is None or self._review_plant_action is None:
            return await self.async_step_commissioning_review()
        choices = {
            plant.plant_group_id: plant.common_name
            for plant in profile.landscape_profile.plant_groups
        }
        if not choices:
            return await self.async_step_commissioning_review()
        if user_input is not None:
            self._review_plant_group_id = str(
                user_input[CONF_COMMISSIONING_PLANT_TARGET]
            )
            if self._review_plant_action == "edit_plant":
                return await self.async_step_commissioning_edit_plant()
            if self._review_plant_action == "remove_plant":
                return await self.async_step_commissioning_remove_plant()
            if self._review_plant_action == "calibrate_delivery":
                return await self.async_step_commissioning_delivery_calibration()
            return await self.async_step_commissioning_delivery()
        return self.async_show_form(
            step_id="commissioning_plant_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_PLANT_TARGET): vol.In(choices)}
            ),
        )

    async def async_step_commissioning_edit_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit scientifically relevant plant facts with prior-state history."""
        profile = self._selected_review_profile()
        if profile is None or self._review_plant_group_id is None:
            return await self.async_step_commissioning_plant_select()
        group = next(
            (
                item
                for item in profile.landscape_profile.plant_groups
                if item.plant_group_id == self._review_plant_group_id
            ),
            None,
        )
        details = next(
            (
                item
                for item in profile.plant_details
                if item.plant_group_id == self._review_plant_group_id
            ),
            None,
        )
        delivery = next(
            (
                item
                for item in profile.delivery_links
                if item.plant_group_id == self._review_plant_group_id
            ),
            None,
        )
        if group is None or details is None:
            return await self.async_step_commissioning_review()
        errors: dict[str, str] = {}
        if user_input is not None:
            now = datetime.now(UTC)
            try:
                plant = _manual_plant_from_form(
                    user_input,
                    plant_group_id=group.plant_group_id,
                    now=now,
                    timezone=ZoneInfo(self.hass.config.time_zone),
                )
                candidate = edit_plant_group(
                    profile,
                    PlantEditInput(
                        _commissioning_event_id(profile, "update", now),
                        plant,
                        now,
                    ),
                )
                candidate = update_delivery_link(
                    candidate,
                    _delivery_link_from_form(user_input, group.plant_group_id),
                )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_edit"
            else:
                if await self.config_entry.runtime_data.landscape_intelligence.async_update_zone(
                    candidate
                ):
                    return await self.async_step_commissioning_review()
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_edit_plant",
            data_schema=_commissioning_plant_schema(
                group=group,
                details=details,
                delivery=delivery,
            ),
            errors=errors,
        )

    async def async_step_commissioning_remove_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove one current plant while retaining its immutable snapshot."""
        profile = self._selected_review_profile()
        if profile is None or self._review_plant_group_id is None:
            return await self.async_step_commissioning_plant_select()
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_COMMISSIONING_REMOVE_CONFIRMATION) is not True:
                errors["base"] = "commissioning_removal_not_confirmed"
            else:
                now = datetime.now(UTC)
                try:
                    candidate = remove_plant_group(
                        profile,
                        PlantRemovalInput(
                            _commissioning_event_id(profile, "remove", now),
                            self._review_plant_group_id,
                            now,
                        ),
                    )
                except (KeyError, TypeError, ValueError):
                    errors["base"] = "invalid_commissioning_edit"
                else:
                    manager = self.config_entry.runtime_data.landscape_intelligence
                    if await manager.async_update_zone(candidate):
                        return await self.async_step_commissioning_review()
                    errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_remove_plant",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_REMOVE_CONFIRMATION): bool}
            ),
            errors=errors,
        )

    async def async_step_commissioning_delivery(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Review or replace a plant's canonical delivery association."""
        profile = self._selected_review_profile()
        if profile is None or self._review_plant_group_id is None:
            return await self.async_step_commissioning_plant_select()
        existing = next(
            (
                item
                for item in profile.delivery_links
                if item.plant_group_id == self._review_plant_group_id
            ),
            None,
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                candidate = update_delivery_link(
                    profile,
                    _delivery_link_from_form(
                        user_input,
                        self._review_plant_group_id,
                    ),
                )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_edit"
            else:
                if await self.config_entry.runtime_data.landscape_intelligence.async_update_zone(
                    candidate
                ):
                    return await self.async_step_commissioning_review()
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_delivery",
            data_schema=_commissioning_delivery_schema(existing),
            errors=errors,
        )

    async def async_step_commissioning_baseline(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add, update, or remove user-calibrated baseline evidence."""
        profile = self._selected_review_profile()
        if profile is None:
            return await self.async_step_commissioning_review_select()
        existing = next(
            (
                source.calibrated_baseline
                for source in profile.demand_sources
                if source.calibrated_baseline is not None
            ),
            None,
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                if str(user_input[CONF_COMMISSIONING_BASELINE_ACTION]) == "remove":
                    candidate = remove_calibrated_baseline(profile)
                else:
                    candidate = set_calibrated_baseline(
                        profile,
                        _baseline_from_form(
                            user_input, datetime.now(UTC), existing=existing
                        ),
                    )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_edit"
            else:
                if await self.config_entry.runtime_data.landscape_intelligence.async_update_zone(
                    candidate
                ):
                    return await self.async_step_commissioning_review()
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_baseline",
            data_schema=_commissioning_baseline_schema(existing),
            errors=errors,
        )

    async def async_step_commissioning_baseline_reference(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Capture a dry ET0 reference from current normalized observations."""
        profile = self._selected_review_profile()
        if profile is None:
            return await self.async_step_commissioning_review_select()
        baseline = next(
            (
                source.calibrated_baseline
                for source in profile.demand_sources
                if source.calibrated_baseline is not None
            ),
            None,
        )
        if baseline is None:
            return await self.async_step_commissioning_baseline()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            now = datetime.now(UTC)
            try:
                result = capture_baseline_environmental_reference(
                    profile,
                    assess_commissioning(profile),
                    CaptureBaselineReferenceRequest(
                        identity=profile.identity,
                        expected_baseline_runtime_seconds=baseline.runtime_seconds,
                        period_hours=int(
                            user_input[CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS]
                        ),
                        representative_dry_condition_confirmed=bool(
                            user_input[CONF_COMMISSIONING_CAPTURE_DRY_CONFIRMATION]
                        ),
                        replace_existing_reference_confirmed=bool(
                            user_input[
                                CONF_COMMISSIONING_REPLACE_REFERENCE_CONFIRMATION
                            ]
                        ),
                        captured_at=now,
                    ),
                    observations=(
                        self.config_entry.runtime_data.weather_evidence.observations
                    ),
                )
                if result.status is not BaselineReferenceCaptureStatus.READY:
                    errors["base"] = "baseline_reference_capture_blocked"
                    placeholders["blockers"] = ", ".join(result.blocker_codes)
                else:
                    candidate = apply_baseline_reference_capture(profile, result)
                    if candidate == profile:
                        return await self.async_step_commissioning_review()
                    manager = self.config_entry.runtime_data.landscape_intelligence
                    saved = await manager.async_update_zone(candidate)
                    if saved:
                        return await self.async_step_commissioning_review()
                    errors["base"] = "commissioning_persistence_failed"
            except (KeyError, TypeError, ValueError):
                errors["base"] = "baseline_reference_capture_blocked"
                placeholders["blockers"] = "invalid_capture_request"
        return self.async_show_form(
            step_id="commissioning_baseline_reference",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS, default=24
                    ): vol.In(SUPPORTED_REFERENCE_PERIOD_HOURS),
                    vol.Required(
                        CONF_COMMISSIONING_CAPTURE_DRY_CONFIRMATION, default=False
                    ): bool,
                    vol.Required(
                        CONF_COMMISSIONING_REPLACE_REFERENCE_CONFIRMATION,
                        default=False,
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_commissioning_delivery_calibration(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Capture explicit component evidence and link it atomically to a plant."""
        profile = self._selected_review_profile()
        if profile is None or self._review_plant_group_id is None:
            return await self.async_step_commissioning_plant_select()
        manager = self.config_entry.runtime_data.landscape_intelligence
        existing_link = next(
            (
                item
                for item in profile.delivery_links
                if item.plant_group_id == self._review_plant_group_id
            ),
            None,
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            now = datetime.now(UTC)
            try:
                delivery_profile_id = str(
                    user_input[CONF_COMMISSIONING_DELIVERY_PROFILE_ID]
                ).strip()
                component_id = str(
                    user_input[CONF_COMMISSIONING_DELIVERY_COMPONENT_ID]
                ).strip()
                existing_profile = manager.get_delivery_profile(delivery_profile_id)
                delivery_profile = calibrate_delivery_component(
                    DeliveryComponentCalibrationRequest(
                        profile_id=delivery_profile_id,
                        area_id=profile.identity.zone_id,
                        component_id=component_id,
                        display_name=str(
                            user_input[CONF_COMMISSIONING_DELIVERY_COMPONENT_NAME]
                        ).strip(),
                        delivery_type=WaterDeliveryType(
                            str(user_input[CONF_COMMISSIONING_DELIVERY_TYPE])
                        ),
                        component_count=int(
                            user_input[CONF_COMMISSIONING_COMPONENT_COUNT]
                        ),
                        flow_evidence_level=DeliveryEvidenceLevel(
                            str(user_input[CONF_COMMISSIONING_FLOW_EVIDENCE_LEVEL])
                        ),
                        observed_at=now,
                        flow_basis=FlowBasis(
                            str(user_input[CONF_COMMISSIONING_FLOW_BASIS])
                        ),
                        flow_liters_per_hour=_optional_form_float(
                            user_input, CONF_COMMISSIONING_FLOW_LPH
                        ),
                        collected_volume=_optional_form_float(
                            user_input, CONF_COMMISSIONING_COLLECTED_VOLUME
                        ),
                        collected_volume_unit=(
                            None
                            if not str(
                                user_input.get(
                                    CONF_COMMISSIONING_COLLECTED_VOLUME_UNIT, ""
                                )
                            )
                            else MeasurementUnit(
                                str(
                                    user_input[
                                        CONF_COMMISSIONING_COLLECTED_VOLUME_UNIT
                                    ]
                                )
                            )
                        ),
                        collection_duration_seconds=(
                            None
                            if user_input.get(CONF_COMMISSIONING_COLLECTION_DURATION)
                            in {None, ""}
                            else int(
                                user_input[CONF_COMMISSIONING_COLLECTION_DURATION]
                            )
                        ),
                        radius_meters=_optional_form_float(
                            user_input, CONF_COMMISSIONING_RADIUS_METERS
                        ),
                    ),
                    existing_profile=existing_profile,
                )
                candidate = update_delivery_link(
                    profile,
                    IrrigationDeliveryLink(
                        link_id=f"{self._review_plant_group_id}.delivery",
                        plant_group_id=self._review_plant_group_id,
                        status=DeliveryLinkStatus.DOCUMENTED,
                        delivery_profile_id=delivery_profile.profile_id,
                        component_ids=(component_id,),
                        dedicated_delivery=bool(
                            user_input[CONF_COMMISSIONING_DEDICATED_EMITTER]
                        ),
                    ),
                )
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_delivery_calibration"
            else:
                if await manager.async_update_zone_and_delivery_profile(
                    candidate, delivery_profile
                ):
                    return await self.async_step_commissioning_review()
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_delivery_calibration",
            data_schema=_commissioning_delivery_calibration_schema(existing_link),
            errors=errors,
        )

    async def async_step_commissioning_conflict_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select one unresolved conflict without hiding its candidates."""
        profile = self._selected_review_profile()
        if profile is None:
            return await self.async_step_commissioning_review_select()
        review = build_commissioning_review(profile)
        choices = {
            conflict.conflict_id: " vs. ".join(
                candidate.value for candidate in conflict.candidates
            )
            for conflict in review.unresolved_conflicts
        }
        if not choices:
            return await self.async_step_commissioning_review()
        if user_input is not None:
            self._review_conflict_id = str(
                user_input[CONF_COMMISSIONING_CONFLICT_TARGET]
            )
            return await self.async_step_commissioning_conflict_resolve()
        return self.async_show_form(
            step_id="commissioning_conflict_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_COMMISSIONING_CONFLICT_TARGET): vol.In(choices)}
            ),
        )

    async def async_step_commissioning_conflict_resolve(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Record explicit correction while preserving every original candidate."""
        profile = self._selected_review_profile()
        if profile is None or self._review_conflict_id is None:
            return await self.async_step_commissioning_conflict_select()
        conflict = next(
            (
                item
                for item in profile.conflicts
                if item.conflict_id == self._review_conflict_id
            ),
            None,
        )
        if conflict is None:
            return await self.async_step_commissioning_review()
        group = next(
            item
            for item in profile.landscape_profile.plant_groups
            if item.plant_group_id == conflict.plant_group_id
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            now = datetime.now(UTC)
            try:
                candidate = resolve_identity_conflict(
                    profile,
                    ConflictResolutionInput(
                        resolution_id=_commissioning_event_id(
                            profile, "resolution", now
                        ),
                        event_id=_commissioning_event_id(
                            profile, "correction", now
                        ),
                        conflict_id=conflict.conflict_id,
                        confirmed_common_name=str(
                            user_input[CONF_COMMISSIONING_RESOLUTION_COMMON_NAME]
                        ).strip(),
                        confirmed_botanical_name=_optional_form_text(
                            user_input,
                            CONF_COMMISSIONING_RESOLUTION_BOTANICAL_NAME,
                        ),
                        resolved_at=now,
                        note=_optional_form_text(
                            user_input, CONF_COMMISSIONING_RESOLUTION_NOTE
                        ),
                    ),
                )
            except (KeyError, StopIteration, TypeError, ValueError):
                errors["base"] = "invalid_commissioning_edit"
            else:
                if await self.config_entry.runtime_data.landscape_intelligence.async_update_zone(
                    candidate
                ):
                    return await self.async_step_commissioning_review()
                errors["base"] = "commissioning_persistence_failed"
        return self.async_show_form(
            step_id="commissioning_conflict_resolve",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMMISSIONING_RESOLUTION_COMMON_NAME,
                        default=group.common_name,
                    ): str,
                    vol.Optional(
                        CONF_COMMISSIONING_RESOLUTION_BOTANICAL_NAME,
                        default=group.botanical_name or "",
                    ): str,
                    vol.Optional(CONF_COMMISSIONING_RESOLUTION_NOTE, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "conflict_summary": " | ".join(
                    f"{candidate.source.value}: {candidate.value} "
                    f"({candidate.confidence.value})"
                    for candidate in conflict.candidates
                )
            },
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
                _optional_numeric_field(
                    CONF_COMMISSIONING_CONTAINER_GALLONS
                ): vol.Coerce(float),
                _optional_numeric_field(
                    CONF_COMMISSIONING_HEIGHT_FEET
                ): vol.Coerce(float),
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
                _optional_numeric_field(
                    CONF_COMMISSIONING_REFERENCE_ET0_MM
                ): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
                vol.Required(
                    CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS, default=24
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
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


def _simple_commissioning_schema(
    profile: CommissionedZoneProfile | None = None,
    *,
    plant_group_id: str | None = None,
) -> vol.Schema:
    """Return the serializable plain-language simple commissioning form."""
    plant = (
        None
        if profile is None or not profile.landscape_profile.plant_groups
        else next(
            (
                item
                for item in profile.landscape_profile.plant_groups
                if item.plant_group_id == plant_group_id
            ),
            profile.landscape_profile.plant_groups[0],
        )
    )
    details = (
        None
        if profile is None or plant is None
        else next(
            item
            for item in profile.plant_details
            if item.plant_group_id == plant.plant_group_id
        )
    )
    link = (
        None
        if profile is None or plant is None
        else next(
            (
                item
                for item in profile.delivery_links
                if item.plant_group_id == plant.plant_group_id
            ),
            None,
        )
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_SIMPLE_DESCRIPTION,
                default="Tell IrrigationOS what changed" if profile else "Describe this zone",
            ): str,
            vol.Required(
                CONF_SIMPLE_PLANT_NAME,
                default="" if plant is None else plant.common_name,
            ): str,
            vol.Optional(
                CONF_SIMPLE_PLANTED_DATE,
                default=(
                    ""
                    if details is None or details.planted_at is None
                    else details.planted_at.date().isoformat()
                ),
            ): str,
            vol.Optional(
                CONF_SIMPLE_CONTAINER_GALLONS,
                default=(
                    ""
                    if details is None or details.source_container_gallons is None
                    else details.source_container_gallons
                ),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_SIMPLE_HEIGHT_FEET,
                default=(
                    ""
                    if details is None or details.current_height_meters is None
                    else round(details.current_height_meters / 0.3048, 2)
                ),
            ): vol.Coerce(float),
            vol.Required(
                CONF_SIMPLE_DELIVERY_TYPE, default=WaterDeliveryType.UNKNOWN.value
            ): vol.In([item.value for item in WaterDeliveryType]),
            vol.Optional(CONF_SIMPLE_EMITTER_CLASS, default=""): str,
            _optional_numeric_field(CONF_SIMPLE_THROW_FEET): vol.Coerce(float),
            vol.Required(
                CONF_SIMPLE_SPRAY_PATTERN, default=SprayPattern.UNKNOWN.value
            ): vol.In([item.value for item in SprayPattern]),
            vol.Required(
                CONF_SIMPLE_SHARING,
                default=(
                    DeliverySharing.UNKNOWN.value
                    if link is None or link.dedicated_delivery is None
                    else DeliverySharing.DEDICATED.value
                    if link.dedicated_delivery
                    else DeliverySharing.SHARED.value
                ),
            ): vol.In(
                [item.value for item in DeliverySharing]
            ),
            _optional_numeric_field(CONF_SIMPLE_PLANTS_PER_EMITTER): vol.Coerce(int),
        }
    )


def _map_simple_commissioning_form(
    values: dict[str, Any],
    *,
    controller_slot: int,
    area_slot: int,
    zone_name: str,
    now: datetime,
    timezone: ZoneInfo,
) -> ConversationalCommissioningProposal:
    """Map simple HA fields without exposing or requiring canonical IDs."""
    zone_id = f"zone.{area_slot}" if controller_slot == 1 else f"zone.{controller_slot}.{area_slot}"
    planted_at = _planting_datetime(
        {CONF_COMMISSIONING_PLANTED_DATE: values.get(CONF_SIMPLE_PLANTED_DATE, "")},
        timezone,
    )
    height_feet = _optional_form_float(values, CONF_SIMPLE_HEIGHT_FEET)
    delivery_type = WaterDeliveryType(str(values[CONF_SIMPLE_DELIVERY_TYPE]))
    throw_feet = _optional_form_float(values, CONF_SIMPLE_THROW_FEET)
    plants_per_emitter = values.get(CONF_SIMPLE_PLANTS_PER_EMITTER)
    if plants_per_emitter is None or plants_per_emitter == "":
        plants = None
    else:
        if isinstance(plants_per_emitter, bool) or not isinstance(
            plants_per_emitter, str | int | float
        ):
            raise ValueError("plants per emitter must be numeric")
        plants = int(plants_per_emitter)
        if plants <= 0:
            raise ValueError("plants per emitter must be positive")
    delivery = None
    if delivery_type is not WaterDeliveryType.UNKNOWN:
        delivery = SimpleDeliveryDescription(
            delivery_type,
            now,
            emitter_class=_optional_form_text(values, CONF_SIMPLE_EMITTER_CLASS),
            throw_min_meters=None if throw_feet is None else throw_feet * 0.3048,
            throw_max_meters=None if throw_feet is None else throw_feet * 0.3048,
            spray_pattern=SprayPattern(str(values[CONF_SIMPLE_SPRAY_PATTERN])),
            sharing=DeliverySharing(str(values[CONF_SIMPLE_SHARING])),
            plants_per_emitter=plants,
        )
    return build_conversational_commissioning_proposal(
        ConversationalCommissioningIntake(
            CanonicalZoneIdentity("property.primary", zone_id, controller_slot, area_slot),
            zone_name,
            str(values[CONF_SIMPLE_DESCRIPTION]).strip(),
            now,
            plant=SimplePlantDescription(
                str(values[CONF_SIMPLE_PLANT_NAME]).strip(),
                now,
                planted_at=planted_at,
                source_container_gallons=_optional_form_float(
                    values, CONF_SIMPLE_CONTAINER_GALLONS
                ),
                current_height_meters=None if height_feet is None else height_feet * 0.3048,
                establishment_state=(
                    CommissioningEstablishmentState.ESTABLISHING
                    if planted_at is not None
                    else CommissioningEstablishmentState.UNKNOWN
                ),
            ),
            delivery=delivery,
        )
    )


def _merge_simple_update(
    existing: CommissionedZoneProfile,
    proposal: ConversationalCommissioningProposal,
    effective_at: datetime,
    *,
    plant_group_id: str | None = None,
) -> ConversationalCommissioningProposal:
    """Merge simple evidence into a zone and retain the previous plant snapshot."""
    incoming = proposal.zone_profile.landscape_profile.plant_groups[0]
    incoming_details = proposal.zone_profile.plant_details[0]
    if plant_group_id == "__add_new__":
        incoming_link = (
            None
            if not proposal.zone_profile.delivery_links
            else proposal.zone_profile.delivery_links[0]
        )
        zone = add_plant_group(
            existing,
            PlantAdditionInput(
                event_id=f"event.{uuid4().hex}",
                plant=ManualPlantOnboardingInput(
                    plant_group_id=incoming.plant_group_id,
                    common_name=incoming.common_name,
                    botanical_name=incoming.botanical_name,
                    establishment_state=incoming.establishment_state,
                    observed_at=incoming_details.observed_at,
                    planted_at=incoming_details.planted_at,
                    source_container_gallons=incoming_details.source_container_gallons,
                    current_height_meters=incoming_details.current_height_meters,
                    irrigation_role=incoming.irrigation_role,
                    direct_irrigation=incoming.direct_irrigation,
                    dedicated_emitter=incoming.dedicated_emitter,
                    emitter_type=incoming.emitter_type,
                ),
                effective_at=effective_at,
                delivery_link=incoming_link,
            ),
        )
        return replace(proposal, zone_profile=zone)
    current = next(
        (
            plant
            for plant in existing.landscape_profile.plant_groups
            if (
                plant.plant_group_id == plant_group_id
                if plant_group_id is not None
                else plant.common_name.casefold() == incoming.common_name.casefold()
            )
        ),
        existing.landscape_profile.plant_groups[0],
    )
    current_details = next(
        item
        for item in existing.plant_details
        if item.plant_group_id == current.plant_group_id
    )
    updated_plant = replace(incoming, plant_group_id=current.plant_group_id)
    updated_details = replace(incoming_details, plant_group_id=current.plant_group_id)
    plants = tuple(
        updated_plant if item.plant_group_id == current.plant_group_id else item
        for item in existing.landscape_profile.plant_groups
    )
    details = tuple(
        updated_details if item.plant_group_id == current.plant_group_id else item
        for item in existing.plant_details
    )
    event = LandscapeChangeEvent(
        event_id=f"event.{uuid4().hex}",
        event_type=LandscapeEventType.PLANT_GROUP_UPDATED,
        effective_at=effective_at,
        plant_snapshot=LandscapePlantSnapshot(current, current_details),
    )
    links = existing.delivery_links
    if proposal.zone_profile.delivery_links:
        incoming_link = replace(
            proposal.zone_profile.delivery_links[0],
            plant_group_id=current.plant_group_id,
            link_id=f"{current.plant_group_id}.delivery",
        )
        links = (
            *(item for item in links if item.plant_group_id != current.plant_group_id),
            incoming_link,
        )
    zone = replace(
        existing,
        landscape_profile=replace(existing.landscape_profile, plant_groups=plants),
        plant_details=details,
        delivery_links=tuple(sorted(links, key=lambda item: item.link_id)),
        landscape_events=tuple(
            sorted(
                (*existing.landscape_events, event),
                key=lambda item: (item.effective_at, item.event_id),
            )
        ),
        execution_authorized=False,
        live_control_authorized=False,
    )
    return replace(proposal, zone_profile=zone)


def _plain_zone_status(profile: CommissionedZoneProfile | None) -> str:
    """Return a homeowner-facing setup status from canonical evidence."""
    if profile is None:
        return "Not set up"
    assessment = assess_commissioning(profile)
    resolved = {item.conflict_id for item in profile.conflict_resolutions}
    if any(item.conflict_id not in resolved for item in profile.conflicts):
        return "Needs review"
    if assessment.follow_up_requirements:
        return "Partially set up"
    return "Set up"


def _preserve_existing_delivery_calibration(
    manager: Any,
    existing: CommissionedZoneProfile,
    proposal: ConversationalCommissioningProposal,
    *,
    plant_group_id: str | None,
) -> ConversationalCommissioningProposal:
    """Refine observable delivery facts without replacing stronger calibration."""
    if proposal.delivery_profile is None:
        return proposal
    selected_id = plant_group_id or existing.landscape_profile.plant_groups[0].plant_group_id
    current_link = next(
        (item for item in existing.delivery_links if item.plant_group_id == selected_id),
        None,
    )
    if (
        current_link is None
        or current_link.delivery_profile_id is None
        or not current_link.component_ids
    ):
        return proposal
    current_profile = manager.get_delivery_profile(current_link.delivery_profile_id)
    if current_profile is None:
        return proposal
    current_component = next(
        (
            item
            for item in current_profile.components
            if item.component_id == current_link.component_ids[0]
        ),
        None,
    )
    if current_component is None:
        return proposal
    observed = proposal.delivery_profile.components[0]
    merged_component = replace(
        observed,
        component_id=current_component.component_id,
        area_id=current_component.area_id,
        nominal_flow_liters_per_hour=current_component.nominal_flow_liters_per_hour,
        measured_flow_liters_per_hour=current_component.measured_flow_liters_per_hour,
        application_rate_mm_per_hour=current_component.application_rate_mm_per_hour,
        efficiency=current_component.efficiency,
        pressure_compensation=current_component.pressure_compensation,
        clogging_risk=current_component.clogging_risk,
        calibration_ids=current_component.calibration_ids,
        manufacturer=current_component.manufacturer,
        model=current_component.model,
        approximate_flow_range=(
            observed.approximate_flow_range or current_component.approximate_flow_range
        ),
        visual_assessment_ids=tuple(
            sorted(
                set(current_component.visual_assessment_ids)
                | set(observed.visual_assessment_ids)
            )
        ),
        visual_evidence_ids=tuple(
            sorted(
                set(current_component.visual_evidence_ids)
                | set(observed.visual_evidence_ids)
            )
        ),
    )
    delivery_profile = replace(
        current_profile,
        assessed_at=proposal.delivery_profile.assessed_at,
        components=tuple(
            merged_component if item.component_id == current_component.component_id else item
            for item in current_profile.components
        ),
    )
    proposed_link = next(
        item
        for item in proposal.zone_profile.delivery_links
        if item.plant_group_id == selected_id
    )
    retained_link = replace(
        current_link,
        status=proposed_link.status,
        dedicated_delivery=proposed_link.dedicated_delivery,
    )
    zone = replace(
        proposal.zone_profile,
        delivery_links=tuple(
            retained_link if item.plant_group_id == selected_id else item
            for item in proposal.zone_profile.delivery_links
        ),
    )
    return replace(proposal, zone_profile=zone, delivery_profile=delivery_profile)


def _media_content_id(value: object) -> str:
    """Extract the opaque HA media reference without storing media metadata."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        content_id = value.get("media_content_id")
        if isinstance(content_id, str) and content_id.strip():
            return content_id.strip()
    raise ValueError("photo selection is missing an opaque media reference")


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


def _optional_numeric_field(
    key: str, default: int | float | None = None
) -> vol.Optional:
    """Return a serializable optional numeric marker with an optional default."""
    if default is None:
        return vol.Optional(key)
    return vol.Optional(key, default=default)


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
            environmental_reference=_environmental_reference_from_form(values, now),
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


def _commissioning_plant_schema(
    *,
    group: PlantGroup | None = None,
    details: PlantCommissioningDetails | None = None,
    delivery: IrrigationDeliveryLink | None = None,
) -> vol.Schema:
    """Build the generic plant add/edit form with existing facts as defaults."""
    planted_date = ""
    if details is not None and details.planted_at is not None:
        planted_date = details.planted_at.date().isoformat()
    height_feet: float | None = None
    if details is not None and details.current_height_meters is not None:
        height_feet = details.current_height_meters / 0.3048
    return vol.Schema(
        {
            vol.Required(
                CONF_COMMISSIONING_PLANT_NAME,
                default="" if group is None else group.common_name,
            ): str,
            vol.Optional(
                CONF_COMMISSIONING_BOTANICAL_NAME,
                default="" if group is None else group.botanical_name or "",
            ): str,
            vol.Required(
                CONF_COMMISSIONING_ESTABLISHMENT,
                default=(
                    CommissioningEstablishmentState.UNKNOWN.value
                    if group is None
                    else group.establishment_state.value
                ),
            ): vol.In([item.value for item in CommissioningEstablishmentState]),
            vol.Required(
                CONF_COMMISSIONING_IRRIGATION_ROLE,
                default=(
                    IrrigationRole.PRIMARY_TARGET.value
                    if group is None
                    else group.irrigation_role.value
                ),
            ): vol.In([item.value for item in IrrigationRole]),
            vol.Optional(
                CONF_COMMISSIONING_PLANTED_DATE, default=planted_date
            ): str,
            _optional_numeric_field(
                CONF_COMMISSIONING_CONTAINER_GALLONS,
                None if details is None else details.source_container_gallons,
            ): vol.Coerce(float),
            _optional_numeric_field(
                CONF_COMMISSIONING_HEIGHT_FEET, height_feet
            ): vol.Coerce(float),
            vol.Required(
                CONF_COMMISSIONING_DIRECT_IRRIGATION,
                default=True if group is None else group.direct_irrigation,
            ): bool,
            vol.Required(
                CONF_COMMISSIONING_DEDICATED_EMITTER,
                default=False if group is None else group.dedicated_emitter,
            ): bool,
            vol.Optional(
                CONF_COMMISSIONING_EMITTER_TYPE,
                default="" if group is None else group.emitter_type or "",
            ): str,
            vol.Required(
                CONF_COMMISSIONING_DELIVERY_STATUS,
                default=(
                    DeliveryLinkStatus.UNRESOLVED.value
                    if delivery is None
                    else delivery.status.value
                ),
            ): vol.In([item.value for item in DeliveryLinkStatus]),
            vol.Optional(
                CONF_COMMISSIONING_DELIVERY_PROFILE_ID,
                default=(
                    ""
                    if delivery is None or delivery.delivery_profile_id is None
                    else delivery.delivery_profile_id
                ),
            ): str,
            vol.Optional(
                CONF_COMMISSIONING_COMPONENT_IDS,
                default=(
                    "" if delivery is None else ", ".join(delivery.component_ids)
                ),
            ): str,
        }
    )


def _manual_plant_from_form(
    values: dict[str, Any],
    *,
    plant_group_id: str,
    now: datetime,
    timezone: ZoneInfo,
) -> ManualPlantOnboardingInput:
    """Map plant edit form values without changing evidence implicitly."""
    height = _optional_form_float(values, CONF_COMMISSIONING_HEIGHT_FEET)
    return ManualPlantOnboardingInput(
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
        current_height_meters=None if height is None else height * 0.3048,
        irrigation_role=IrrigationRole(
            str(values[CONF_COMMISSIONING_IRRIGATION_ROLE])
        ),
        direct_irrigation=bool(values[CONF_COMMISSIONING_DIRECT_IRRIGATION]),
        dedicated_emitter=bool(values[CONF_COMMISSIONING_DEDICATED_EMITTER]),
        emitter_type=_optional_form_text(values, CONF_COMMISSIONING_EMITTER_TYPE),
    )


def _delivery_link_from_form(
    values: dict[str, Any],
    plant_group_id: str,
) -> IrrigationDeliveryLink:
    """Map explicit delivery linkage without inventing component properties."""
    status = DeliveryLinkStatus(str(values[CONF_COMMISSIONING_DELIVERY_STATUS]))
    if status is DeliveryLinkStatus.UNRESOLVED:
        return IrrigationDeliveryLink(
            link_id=f"{plant_group_id}.delivery",
            plant_group_id=plant_group_id,
            status=status,
        )
    profile_id = _optional_form_text(
        values, CONF_COMMISSIONING_DELIVERY_PROFILE_ID
    )
    if profile_id is None:
        raise ValueError("documented delivery requires a canonical profile ID")
    return IrrigationDeliveryLink(
        link_id=f"{plant_group_id}.delivery",
        plant_group_id=plant_group_id,
        status=status,
        delivery_profile_id=profile_id,
        component_ids=_form_ids(values, CONF_COMMISSIONING_COMPONENT_IDS),
        dedicated_delivery=(
            bool(values[CONF_COMMISSIONING_DEDICATED_EMITTER])
            if CONF_COMMISSIONING_DEDICATED_EMITTER in values
            else None
        ),
    )


def _commissioning_delivery_schema(
    existing: IrrigationDeliveryLink | None,
) -> vol.Schema:
    """Build a delivery-link-only review form."""
    return vol.Schema(
        {
            vol.Required(
                CONF_COMMISSIONING_DELIVERY_STATUS,
                default=(
                    DeliveryLinkStatus.UNRESOLVED.value
                    if existing is None
                    else existing.status.value
                ),
            ): vol.In([item.value for item in DeliveryLinkStatus]),
            vol.Optional(
                CONF_COMMISSIONING_DELIVERY_PROFILE_ID,
                default=(
                    ""
                    if existing is None or existing.delivery_profile_id is None
                    else existing.delivery_profile_id
                ),
            ): str,
            vol.Optional(
                CONF_COMMISSIONING_COMPONENT_IDS,
                default=(
                    "" if existing is None else ", ".join(existing.component_ids)
                ),
            ): str,
            vol.Required(
                CONF_COMMISSIONING_DEDICATED_EMITTER,
                default=(
                    False
                    if existing is None or existing.dedicated_delivery is None
                    else existing.dedicated_delivery
                ),
            ): bool,
        }
    )


def _baseline_from_form(
    values: dict[str, Any],
    now: datetime,
    *,
    existing: UserCalibratedBaseline | None = None,
) -> UserCalibratedBaseline:
    """Map user calibration and preserve or retire reference evidence explicitly."""
    reference = _environmental_reference_from_form(values, now)
    history = () if existing is None else existing.reference_history
    runtime_seconds = int(values[CONF_COMMISSIONING_BASELINE_MINUTES]) * 60
    reference_temperature = (
        float(values[CONF_COMMISSIONING_REFERENCE_TEMP_F]) - 32
    ) * 5 / 9
    recent_rain = float(values[CONF_COMMISSIONING_RECENT_RAIN_MM])
    if existing is not None and existing.environmental_reference is not None:
        prior_reference = existing.environmental_reference
        unchanged_context = (
            runtime_seconds == existing.runtime_seconds
            and reference_temperature
            == existing.reference_air_temperature_celsius
            and recent_rain == existing.reference_recent_precipitation_mm
        )
        same_explicit_reference = (
            reference is not None
            and reference.reference_et0_mm == prior_reference.reference_et0_mm
            and reference.period_hours == prior_reference.period_hours
        )
        if same_explicit_reference or (reference is None and unchanged_context):
            reference = prior_reference
        elif reference != prior_reference:
            history = (*history, prior_reference)
    return UserCalibratedBaseline(
        runtime_seconds=runtime_seconds,
        reference_air_temperature_celsius=reference_temperature,
        reference_recent_precipitation_mm=recent_rain,
        reference_condition="user-confirmed dry-day reference condition",
        calibrated_at=now,
        confidence=Confidence.HIGH,
        environmental_reference=reference,
        reference_history=history,
    )


def _environmental_reference_from_form(
    values: dict[str, Any], now: datetime
) -> BaselineEnvironmentalReference | None:
    """Map optional explicit ET0 evidence without deriving it from temperature."""
    raw_et0 = values.get(CONF_COMMISSIONING_REFERENCE_ET0_MM, "")
    if raw_et0 in {None, ""}:
        return None
    return BaselineEnvironmentalReference(
        reference_et0_mm=float(raw_et0),
        period_hours=int(values[CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS]),
        observed_at=now,
        source="user-confirmed reference environmental evidence",
        confidence=Confidence.HIGH,
        quality="user_confirmed",
        capture_method=BaselineReferenceSource.MANUALLY_ENTERED_REFERENCE,
        captured_at=now,
    )


def _commissioning_baseline_schema(
    existing: UserCalibratedBaseline | None,
) -> vol.Schema:
    """Build baseline add/edit/remove form without calculation controls."""
    reference_temp_f = 75.0
    if existing is not None:
        reference_temp_f = existing.reference_air_temperature_celsius * 9 / 5 + 32
    return vol.Schema(
        {
            vol.Required(
                CONF_COMMISSIONING_BASELINE_ACTION, default="set"
            ): vol.In({"set": "Add or update baseline", "remove": "Remove baseline"}),
            vol.Required(
                CONF_COMMISSIONING_BASELINE_MINUTES,
                default=(12 if existing is None else existing.runtime_seconds // 60),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
            vol.Required(
                CONF_COMMISSIONING_REFERENCE_TEMP_F,
                default=reference_temp_f,
            ): vol.Coerce(float),
            vol.Required(
                CONF_COMMISSIONING_RECENT_RAIN_MM,
                default=(
                    0
                    if existing is None
                    else existing.reference_recent_precipitation_mm
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0)),
            _optional_numeric_field(
                CONF_COMMISSIONING_REFERENCE_ET0_MM,
                (
                    None
                    if existing is None or existing.environmental_reference is None
                    else existing.environmental_reference.reference_et0_mm
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
            vol.Required(
                CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS,
                default=(
                    24
                    if existing is None or existing.environmental_reference is None
                    else existing.environmental_reference.period_hours
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
        }
    )


def _commissioning_delivery_calibration_schema(
    existing: IrrigationDeliveryLink | None,
) -> vol.Schema:
    """Build one bounded evidence form; blank quantitative fields stay unknown."""
    profile_default = (
        "delivery.profile"
        if existing is None or existing.delivery_profile_id is None
        else existing.delivery_profile_id
    )
    component_default = (
        "delivery.component"
        if existing is None or not existing.component_ids
        else existing.component_ids[0]
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_COMMISSIONING_DELIVERY_PROFILE_ID, default=profile_default
            ): str,
            vol.Required(
                CONF_COMMISSIONING_DELIVERY_COMPONENT_ID,
                default=component_default,
            ): str,
            vol.Required(
                CONF_COMMISSIONING_DELIVERY_COMPONENT_NAME,
                default="Irrigation component",
            ): str,
            vol.Required(
                CONF_COMMISSIONING_DELIVERY_TYPE,
                default=WaterDeliveryType.UNKNOWN.value,
            ): vol.In([item.value for item in WaterDeliveryType]),
            vol.Required(CONF_COMMISSIONING_COMPONENT_COUNT, default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1000)
            ),
            vol.Required(
                CONF_COMMISSIONING_FLOW_EVIDENCE_LEVEL,
                default=DeliveryEvidenceLevel.UNKNOWN.value,
            ): vol.In([item.value for item in DeliveryEvidenceLevel]),
            vol.Required(
                CONF_COMMISSIONING_FLOW_BASIS,
                default=FlowBasis.COMPONENT_TOTAL.value,
            ): vol.In(
                {
                    FlowBasis.COMPONENT_TOTAL.value: "Total for this component group",
                    FlowBasis.PER_EMITTER.value: "Per physical emitter",
                }
            ),
            _optional_numeric_field(CONF_COMMISSIONING_FLOW_LPH): vol.All(
                vol.Coerce(float), vol.Range(min=0.000001)
            ),
            _optional_numeric_field(CONF_COMMISSIONING_COLLECTED_VOLUME): vol.All(
                vol.Coerce(float), vol.Range(min=0.000001)
            ),
            vol.Optional(
                CONF_COMMISSIONING_COLLECTED_VOLUME_UNIT, default=""
            ): vol.In(
                {
                    "": "Not a collected-volume measurement",
                    MeasurementUnit.MILLILITERS.value: "Milliliters",
                    MeasurementUnit.LITERS.value: "Liters",
                    MeasurementUnit.US_GALLONS.value: "US gallons",
                }
            ),
            _optional_numeric_field(CONF_COMMISSIONING_COLLECTION_DURATION): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=86400)
            ),
            _optional_numeric_field(CONF_COMMISSIONING_RADIUS_METERS): vol.All(
                vol.Coerce(float), vol.Range(min=0.000001)
            ),
            vol.Required(
                CONF_COMMISSIONING_DEDICATED_EMITTER,
                default=(
                    False
                    if existing is None or existing.dedicated_delivery is None
                    else existing.dedicated_delivery
                ),
            ): bool,
        }
    )


def _next_plant_group_id(profile: CommissionedZoneProfile) -> str:
    """Allocate a stable slot-like plant ID independent of mutable names."""
    known = {
        group.plant_group_id for group in profile.landscape_profile.plant_groups
    }
    index = 1
    while f"{profile.identity.zone_id}.plant.{index}" in known:
        index += 1
    return f"{profile.identity.zone_id}.plant.{index}"


def _commissioning_event_id(
    profile: CommissionedZoneProfile,
    action: str,
    observed_at: datetime,
) -> str:
    """Create a unique stable audit ID without names or provider identifiers."""
    controller_slot = profile.identity.controller_slot or 0
    stamp = observed_at.strftime("%Y%m%dT%H%M%S%f")
    return (
        f"event.c{controller_slot}.a{profile.identity.area_slot}."
        f"{action}.{stamp}"
    )


def _commissioning_review_summary(
    profile: CommissionedZoneProfile,
    scaling: BaselineEnvironmentalScalingAssessment | None = None,
    *,
    delivery_profiles: tuple[WaterDeliveryProfile, ...] = (),
) -> str:
    """Return bounded human-readable review text for the options flow only."""
    review = build_commissioning_review(
        profile,
        baseline_scaling_assessment=scaling,
        delivery_profiles=delivery_profiles,
    )
    lines = [
        f"{review.display_name} ({profile.identity.property_id}/"
        f"{profile.identity.zone_id})",
        f"Demand modes: {', '.join(mode.value for mode in review.demand_source_modes)}",
        f"Commissioning status: {review.commissioning_assessment.status.value}",
    ]
    for readiness in review.commissioning_assessment.purpose_readiness:
        lines.append(f"{readiness.purpose.value}: {readiness.state.value}")
    for plant in review.plants[:12]:
        link_status = (
            "missing"
            if plant.delivery_link is None
            else plant.delivery_link.status.value
        )
        lines.append(
            f"Plant: {plant.plant_group.common_name}; "
            f"establishment={plant.plant_group.establishment_state.value}; "
            f"source={plant.commissioning_details.source.value}; "
            f"confidence={plant.commissioning_details.confidence.value}; "
            f"delivery={link_status}"
        )
    if review.calibrated_baselines:
        baseline = review.calibrated_baselines[0]
        lines.append(
            f"Baseline: {baseline.runtime_seconds // 60} min at "
            f"{baseline.reference_air_temperature_celsius * 9 / 5 + 32:.1f} °F"
        )
        reference = baseline.environmental_reference
        lines.append(
            "Environmental reference: "
            + (
                "not captured"
                if reference is None
                else f"{reference.reference_et0_mm:.3f} mm ET₀ over "
                f"{reference.period_hours} h; {reference.capture_method.value}; "
                f"quality={reference.quality}"
            )
        )
        lines.append(
            "Environmental scaling: "
            + (
                "not yet evaluated"
                if review.baseline_scaling_assessment is None
                else review.baseline_scaling_assessment.status.value
            )
        )
    lines.append(f"Unresolved conflicts: {len(review.unresolved_conflicts)}")
    lines.append(
        "Advisories: "
        + (", ".join(item.code for item in review.advisories) or "none")
    )
    lines.append(f"Recent landscape events: {len(review.recent_landscape_events)}")
    lines.append(f"Stored delivery profiles: {len(delivery_profiles)}")
    if review.commissioning_assessment.follow_up_requirements:
        lines.append("Next information:")
        lines.extend(
            f"- {item.code}: {item.prompt}"
            for item in review.commissioning_assessment.follow_up_requirements[:8]
        )
    return "\n".join(lines)[:4000]
