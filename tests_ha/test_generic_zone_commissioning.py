from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import voluptuous_serialize
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigationos import config_flow as config_flow_module
from custom_components.irrigationos.config_flow import (
    CONF_COMMISSIONING_BASELINE_ACTION,
    CONF_COMMISSIONING_BASELINE_MINUTES,
    CONF_COMMISSIONING_BOTANICAL_NAME,
    CONF_COMMISSIONING_CAPTURE_DRY_CONFIRMATION,
    CONF_COMMISSIONING_COLLECTED_VOLUME,
    CONF_COMMISSIONING_COLLECTED_VOLUME_UNIT,
    CONF_COMMISSIONING_COLLECTION_DURATION,
    CONF_COMMISSIONING_COMPONENT_COUNT,
    CONF_COMMISSIONING_COMPONENT_IDS,
    CONF_COMMISSIONING_CONTAINER_GALLONS,
    CONF_COMMISSIONING_DEDICATED_EMITTER,
    CONF_COMMISSIONING_DELIVERY_COMPONENT_ID,
    CONF_COMMISSIONING_DELIVERY_COMPONENT_NAME,
    CONF_COMMISSIONING_DELIVERY_PROFILE_ID,
    CONF_COMMISSIONING_DELIVERY_STATUS,
    CONF_COMMISSIONING_DELIVERY_TYPE,
    CONF_COMMISSIONING_DIRECT_IRRIGATION,
    CONF_COMMISSIONING_EMITTER_TYPE,
    CONF_COMMISSIONING_ESTABLISHMENT,
    CONF_COMMISSIONING_FLOW_BASIS,
    CONF_COMMISSIONING_FLOW_EVIDENCE_LEVEL,
    CONF_COMMISSIONING_FLOW_LPH,
    CONF_COMMISSIONING_HEIGHT_FEET,
    CONF_COMMISSIONING_IRRIGATION_ROLE,
    CONF_COMMISSIONING_PLANT_NAME,
    CONF_COMMISSIONING_PLANT_TARGET,
    CONF_COMMISSIONING_PLANTED_DATE,
    CONF_COMMISSIONING_RADIUS_METERS,
    CONF_COMMISSIONING_RECENT_RAIN_MM,
    CONF_COMMISSIONING_REFERENCE_ET0_MM,
    CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS,
    CONF_COMMISSIONING_REFERENCE_TEMP_F,
    CONF_COMMISSIONING_REPLACE_REFERENCE_CONFIRMATION,
    CONF_COMMISSIONING_REVIEW_ACTION,
    CONF_COMMISSIONING_REVIEW_TARGET,
    CONF_COMMISSIONING_TARGET,
    CONF_COMMISSIONING_ZONE_NAME,
    CONF_MANAGE_ZONE_ACTION,
    CONF_OPTIONS_ACTION,
    CONF_RECOMMISSION_CONFIRM,
    CONF_SIMPLE_CONFIRM,
    CONF_SIMPLE_CONTAINER_GALLONS,
    CONF_SIMPLE_DELIVERY_TYPE,
    CONF_SIMPLE_DESCRIPTION,
    CONF_SIMPLE_EMITTER_CLASS,
    CONF_SIMPLE_HEIGHT_FEET,
    CONF_SIMPLE_PLANT_NAME,
    CONF_SIMPLE_PLANTED_DATE,
    CONF_SIMPLE_PLANTS_PER_EMITTER,
    CONF_SIMPLE_SHARING,
    CONF_SIMPLE_SPRAY_PATTERN,
    CONF_SIMPLE_THROW_FEET,
    CONF_ZONE_PHOTO_NOTE,
    CONF_ZONE_PHOTO_RUNNING,
    CONF_ZONE_PHOTOS,
    IrrigationOSOptionsFlow,
    _commissioning_baseline_schema,
    _commissioning_delivery_calibration_schema,
    _commissioning_plant_schema,
    _commissioning_schema,
    _map_commissioning_form,
    _simple_commissioning_schema,
)
from custom_components.irrigationos.const import DOMAIN
from custom_components.irrigationos.guided_observation import (
    ZONE_IDENTIFICATION_DURATION_SECONDS,
    GuidedObservationManager,
    GuidedObservationResult,
    GuidedObservationState,
    GuidedObservationStatus,
)
from custom_components.irrigationos.landscape_intelligence import (
    CanonicalZoneIdentity,
    Confidence,
    EstablishmentState,
    LandscapeEventType,
    PlantAdditionInput,
    UserCalibratedBaseline,
    ZoneDemandSourceMode,
    add_plant_group,
    zone_setup_is_unresolved,
)
from custom_components.irrigationos.landscape_intelligence.manager import (
    LandscapeIntelligenceManager,
)
from custom_components.irrigationos.landscape_intelligence.onboarding import (
    ManualPlantOnboardingInput,
    ZoneOnboardingRequest,
    map_zone_onboarding,
)
from custom_components.irrigationos.water_delivery import (
    DeliveryComponentCalibrationRequest,
    DeliveryEvidenceLevel,
    WaterDeliveryType,
    calibrate_delivery_component,
)
from custom_components.irrigationos.weather import (
    EnvironmentalWeatherFacts,
    HistoricalWeatherObservation,
    ObservationWindow,
    WeatherFact,
    WeatherProvenance,
    WeatherQualityMetadata,
    WeatherQualityStatus,
    WeatherSourceType,
    WeatherVerificationStatus,
)


def _form_choices(result: dict[str, Any], field: str) -> dict[str, str]:
    """Return one set of choices from a rendered form schema."""
    for marker, validator in result["data_schema"].schema.items():
        if marker.schema == field:
            return dict(validator.container)
    raise AssertionError(f"{field} schema is missing")


def _manage_zone_actions(result: dict[str, Any]) -> dict[str, str]:
    """Return the manage-zone choices from the rendered form schema."""
    return _form_choices(result, CONF_MANAGE_ZONE_ACTION)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_simple_commissioning_review_confirms_canonical_evidence(
    hass: HomeAssistant,
) -> None:
    """The simple path hides canonical IDs and atomically publishes after confirmation."""
    voluptuous_serialize.convert(
        _simple_commissioning_schema(), custom_serializer=cv.custom_serializer
    )
    manager = LandscapeIntelligenceManager(hass, "simple-commissioning")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow._commissioning_controller_slot = 1
    flow._commissioning_area_slot = 7
    flow._commissioning_area_name = "Front planter"

    result = await flow.async_step_commissioning_simple_input(
        {
            CONF_SIMPLE_DESCRIPTION: (
                "Podocarpus planted last year from 5-gallon pots; one blue "
                "two-sided microjet serves two plants."
            ),
            CONF_SIMPLE_PLANT_NAME: "Podocarpus",
            CONF_SIMPLE_PLANTED_DATE: "2025-08-24",
            CONF_SIMPLE_CONTAINER_GALLONS: 5,
            CONF_SIMPLE_HEIGHT_FEET: 6,
            CONF_SIMPLE_DELIVERY_TYPE: "microjet",
            CONF_SIMPLE_EMITTER_CLASS: "blue",
            CONF_SIMPLE_THROW_FEET: 3.5,
            CONF_SIMPLE_SPRAY_PATTERN: "part_circle",
            CONF_SIMPLE_SHARING: "shared",
            CONF_SIMPLE_PLANTS_PER_EMITTER: 2,
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "commissioning_simple_review"
    assert "zone.7" not in result["description_placeholders"]["understood"]
    confirmed = await flow.async_step_commissioning_simple_review(
        {CONF_SIMPLE_CONFIRM: True}
    )
    assert confirmed["type"] == "create_entry"
    saved = manager.get_zone("property.primary", "zone.7")
    assert saved is not None
    assert saved.landscape_profile.plant_groups[0].common_name == "Podocarpus"
    assert manager.delivery_profiles[0].components[0].measured_flow_liters_per_hour.value is None
    assert not saved.execution_authorized
    assert not saved.live_control_authorized


@pytest.mark.asyncio
async def test_simple_commissioning_persistence_failure_publishes_nothing(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "simple-failure")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow._commissioning_controller_slot = 1
    flow._commissioning_area_slot = 8
    flow._commissioning_area_name = "Back planter"
    await flow.async_step_commissioning_simple_input(
        {
            CONF_SIMPLE_DESCRIPTION: "Shrubs with shared spray",
            CONF_SIMPLE_PLANT_NAME: "Shrubs",
            CONF_SIMPLE_PLANTED_DATE: "",
            CONF_SIMPLE_CONTAINER_GALLONS: "",
            CONF_SIMPLE_HEIGHT_FEET: "",
            CONF_SIMPLE_DELIVERY_TYPE: "spray",
            CONF_SIMPLE_EMITTER_CLASS: "",
            CONF_SIMPLE_THROW_FEET: "",
            CONF_SIMPLE_SPRAY_PATTERN: "unknown",
            CONF_SIMPLE_SHARING: "shared",
            CONF_SIMPLE_PLANTS_PER_EMITTER: "",
        }
    )
    store.fail_save = True
    result = await flow.async_step_commissioning_simple_review(
        {CONF_SIMPLE_CONFIRM: True}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "commissioning_persistence_failed"}
    assert manager.get_zone("property.primary", "zone.8") is None
    assert not any(item.area_id == "zone.8" for item in manager.delivery_profiles)


@pytest.mark.asyncio
async def test_zone_photo_references_are_private_atomic_and_ha_serializable(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "zone-photos")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow._manage_controller_slot = 1
    flow._manage_area_slot = 1

    form = await flow.async_step_manage_zone_photos()
    assert voluptuous_serialize.convert(
        form["data_schema"], custom_serializer=cv.custom_serializer
    )
    result = await flow.async_step_manage_zone_photos(
        {
            CONF_ZONE_PHOTOS: [
                {"media_content_id": "media-source://media_source/local/zone1.jpg"},
                {"media_content_id": "media-source://media_source/local/zone1-running.jpg"},
            ],
            CONF_ZONE_PHOTO_NOTE: "Wide view",
            CONF_ZONE_PHOTO_RUNNING: True,
        }
    )
    assert result["step_id"] == "manage_zone_review"
    photos = manager.photos_for_zone("property.primary", "zone.1")
    assert len(photos) == 2
    assert all(photo.zone_running_context for photo in photos)
    assert all(
        photo.content_reference
        and not photo.content_reference.startswith("data:")
        for photo in photos
    )
    assert store.value is not None
    assert all("private-zone" not in str(item) for item in store.value["photo_evidence"])


@pytest.mark.asyncio
async def test_all_zone_management_forms_cross_ha_serialization_boundary(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "manage-zone-forms")
    manager._store = _Store(None)  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    area = SimpleNamespace(
        configured=True,
        enabled=True,
        binding=object(),
        slot_number=1,
        vendor_name="Zone 1",
        name="Zone 1",
    )
    runtime = SimpleNamespace(
        landscape_intelligence=manager,
        data=SimpleNamespace(controllers=(SimpleNamespace(areas=(area,)),)),
        guided_observation=GuidedObservationManager(),
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    zones = await flow.async_step_manage_zones()
    zone = await flow.async_step_manage_zones(
        {CONF_COMMISSIONING_TARGET: "1|1"}
    )
    name = await flow.async_step_manage_zone_name()
    review = await flow.async_step_manage_zone_review()
    for result in (zones, zone, name, review):
        assert voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        ) is not None


@pytest.mark.asyncio
async def test_manage_zones_prefers_friendly_name_and_keeps_uncommissioned_target(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "zone-home-list")
    manager._store = _Store(None)  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    zone1 = manager.get_zone("property.primary", "zone.1")
    assert zone1 is not None
    assert await manager.async_update_zone(
        replace(zone1, display_name="Front Entry Planters")
    )
    areas = (
        SimpleNamespace(
            configured=True,
            enabled=True,
            binding=object(),
            slot_number=1,
            vendor_name="Native Front",
            name="Zone 1",
        ),
        SimpleNamespace(
            configured=True,
            enabled=True,
            binding=object(),
            slot_number=2,
            vendor_name="Back Lawn",
            name="Zone 2",
        ),
    )
    runtime = SimpleNamespace(
        landscape_intelligence=manager,
        data=SimpleNamespace(controllers=(SimpleNamespace(areas=areas),)),
        guided_observation=GuidedObservationManager(),
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    zones = await flow.async_step_manage_zones()
    choices = _form_choices(zones, CONF_COMMISSIONING_TARGET)
    assert choices["1|1"].startswith("Front Entry Planters — ")
    assert choices["1|2"] == "Back Lawn — Not set up"

    commissioned = await flow.async_step_manage_zones(
        {CONF_COMMISSIONING_TARGET: "1|1"}
    )
    commissioned_actions = _manage_zone_actions(commissioned)
    assert commissioned_actions["rename"] == "Rename zone"
    assert commissioned_actions["edit"] == "Edit setup"
    assert commissioned_actions["add_plant"] == "Add another plant"

    uncommissioned = await flow.async_step_manage_zones(
        {CONF_COMMISSIONING_TARGET: "1|2"}
    )
    uncommissioned_actions = _manage_zone_actions(uncommissioned)
    assert uncommissioned_actions["setup"] == "Name / Set up this zone"
    assert "rename" not in uncommissioned_actions
    assert "add_plant" not in uncommissioned_actions
    name_form = await flow.async_step_manage_zone(
        {CONF_MANAGE_ZONE_ACTION: "setup"}
    )
    assert name_form["step_id"] == "manage_zone_name"
    assert name_form["data_schema"]({})[CONF_COMMISSIONING_ZONE_NAME] == "Back Lawn"
    setup = await flow.async_step_manage_zone_name(
        {CONF_COMMISSIONING_ZONE_NAME: "  East Lawn  "}
    )
    assert setup["step_id"] == "commissioning_simple_input"
    assert flow._commissioning_area_name == "East Lawn"


@pytest.mark.asyncio
async def test_zone_rename_is_durable_and_preserves_identity_and_evidence(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "zone-rename")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    original = manager.get_zone("property.primary", "zone.1")
    assert original is not None
    delivery = calibrate_delivery_component(
        DeliveryComponentCalibrationRequest(
            "zone1.delivery.microjet",
            "zone.1",
            "zone1.component.fig",
            "Fig microjet",
            WaterDeliveryType.MICROJET,
            1,
            DeliveryEvidenceLevel.UNKNOWN,
            NOW,
        )
    )
    assert await manager.async_update_zone_and_delivery_profile(original, delivery)
    binding = object()
    area = SimpleNamespace(
        configured=True,
        enabled=True,
        binding=binding,
        slot_number=1,
        vendor_name="Native Zone 1",
        name="Zone 1",
    )
    runtime = SimpleNamespace(
        landscape_intelligence=manager,
        data=SimpleNamespace(controllers=(SimpleNamespace(areas=(area,)),)),
        guided_observation=GuidedObservationManager(),
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    await flow.async_step_manage_zones({CONF_COMMISSIONING_TARGET: "1|1"})
    await flow.async_step_manage_zone_photos(
        {
            CONF_ZONE_PHOTOS: {
                "media_content_id": "media-source://media_source/local/zone1.jpg"
            },
            CONF_ZONE_PHOTO_NOTE: "Before rename",
            CONF_ZONE_PHOTO_RUNNING: False,
        }
    )
    before = manager.get_zone("property.primary", "zone.1")
    assert before is not None
    before_delivery = manager.delivery_profiles
    before_photos = manager.photos_for_zone("property.primary", "zone.1")

    name_form = await flow.async_step_manage_zone(
        {CONF_MANAGE_ZONE_ACTION: "rename"}
    )
    assert name_form["step_id"] == "manage_zone_name"
    assert name_form["data_schema"]({})[CONF_COMMISSIONING_ZONE_NAME] == "Zone 1"
    blank = await flow.async_step_manage_zone_name(
        {CONF_COMMISSIONING_ZONE_NAME: "   "}
    )
    assert blank["errors"] == {
        CONF_COMMISSIONING_ZONE_NAME: "invalid_zone_name"
    }
    renamed_home = await flow.async_step_manage_zone_name(
        {CONF_COMMISSIONING_ZONE_NAME: "  Front Entry Planters  "}
    )
    assert renamed_home["step_id"] == "manage_zone"
    assert renamed_home["description_placeholders"]["zone_name"] == (
        "Front Entry Planters"
    )

    renamed = manager.get_zone("property.primary", "zone.1")
    assert renamed == replace(before, display_name="Front Entry Planters")
    assert renamed.identity == original.identity
    assert renamed.landscape_profile == original.landscape_profile
    assert renamed.plant_details == original.plant_details
    assert renamed.delivery_links == original.delivery_links
    assert manager.delivery_profiles == before_delivery
    assert manager.photos_for_zone("property.primary", "zone.1") == before_photos
    assert area.binding is binding
    assert area.vendor_name == "Native Zone 1"

    store.fail_save = True
    failed = await flow.async_step_manage_zone_name(
        {CONF_COMMISSIONING_ZONE_NAME: "Unsaved name"}
    )
    assert failed["errors"] == {"base": "commissioning_persistence_failed"}
    assert manager.get_zone("property.primary", "zone.1") == renamed
    store.fail_save = False

    choices = _form_choices(
        await flow.async_step_manage_zones(), CONF_COMMISSIONING_TARGET
    )
    assert choices["1|1"].startswith("Front Entry Planters — ")
    restored = LandscapeIntelligenceManager(hass, "zone-rename-restored")
    restored._store = store  # type: ignore[assignment]
    await restored.async_initialize(initial_observed_at=NOW + timedelta(minutes=1))
    restored_zone = restored.get_zone("property.primary", "zone.1")
    assert restored_zone is not None
    assert restored_zone.display_name == "Front Entry Planters"
    assert restored_zone.identity == original.identity
    assert restored.delivery_profiles == before_delivery
    assert restored.photos_for_zone("property.primary", "zone.1") == before_photos


@pytest.mark.asyncio
async def test_zone_home_add_plant_reuses_simple_canonical_merge(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "zone-home-add-plant")
    manager._store = _Store(None)  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())
    area = SimpleNamespace(
        configured=True,
        enabled=True,
        binding=object(),
        slot_number=2,
        vendor_name="Native Zone 2",
        name="Zone 2",
    )
    runtime = SimpleNamespace(
        landscape_intelligence=manager,
        data=SimpleNamespace(controllers=(SimpleNamespace(areas=(area,)),)),
        guided_observation=GuidedObservationManager(),
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    home = await flow.async_step_manage_zones(
        {CONF_COMMISSIONING_TARGET: "1|2"}
    )
    assert _manage_zone_actions(home)["add_plant"] == "Add another plant"
    add_form = await flow.async_step_manage_zone(
        {CONF_MANAGE_ZONE_ACTION: "add_plant"}
    )
    assert add_form["step_id"] == "commissioning_simple_input"
    review = await flow.async_step_commissioning_simple_input(
        {
            CONF_SIMPLE_DESCRIPTION: "A newly planted Hass avocado",
            CONF_SIMPLE_PLANT_NAME: "Hass avocado",
            CONF_SIMPLE_PLANTED_DATE: "2026-08-17",
            CONF_SIMPLE_CONTAINER_GALLONS: 5,
            CONF_SIMPLE_HEIGHT_FEET: 4,
            CONF_SIMPLE_DELIVERY_TYPE: "unknown",
            CONF_SIMPLE_EMITTER_CLASS: "",
            CONF_SIMPLE_THROW_FEET: "",
            CONF_SIMPLE_SPRAY_PATTERN: "unknown",
            CONF_SIMPLE_SHARING: "unknown",
            CONF_SIMPLE_PLANTS_PER_EMITTER: "",
        }
    )
    assert review["step_id"] == "commissioning_simple_review"
    saved = await flow.async_step_commissioning_simple_review(
        {CONF_SIMPLE_CONFIRM: True}
    )
    assert saved["type"] == "create_entry"
    updated = manager.get_zone("property.primary", "zone.2")
    assert updated is not None
    assert tuple(
        plant.common_name for plant in updated.landscape_profile.plant_groups
    ) == ("Podocarpus", "Hass avocado")
    assert updated.landscape_events[-1].plant_snapshot.plant_group.common_name == (
        "Hass avocado"
    )


@pytest.mark.asyncio
async def test_zone_home_recommission_is_confirmed_atomic_and_reuses_setup(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "zone-recommission")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    original = manager.get_zone("property.primary", "zone.1")
    assert original is not None
    original = replace(original, display_name="Front Planters")
    delivery = calibrate_delivery_component(
        DeliveryComponentCalibrationRequest(
            "zone1.delivery.microjet",
            "zone.1",
            "zone1.component.fig",
            "Fig microjet",
            WaterDeliveryType.MICROJET,
            1,
            DeliveryEvidenceLevel.UNKNOWN,
            NOW,
        )
    )
    assert await manager.async_update_zone_and_delivery_profile(original, delivery)
    assert await manager.async_add_zone(_zone2())
    area_binding = object()
    areas = (
        SimpleNamespace(
            configured=True,
            enabled=True,
            binding=area_binding,
            slot_number=1,
            vendor_name="Native Zone 1",
            name="Zone 1",
        ),
        SimpleNamespace(
            configured=True,
            enabled=True,
            binding=object(),
            slot_number=2,
            vendor_name="Native Zone 2",
            name="Zone 2",
        ),
    )
    runtime = SimpleNamespace(
        landscape_intelligence=manager,
        data=SimpleNamespace(controllers=(SimpleNamespace(areas=areas),)),
        guided_observation=GuidedObservationManager(),
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    await flow.async_step_manage_zones({CONF_COMMISSIONING_TARGET: "1|1"})
    await flow.async_step_manage_zone_photos(
        {
            CONF_ZONE_PHOTOS: {
                "media_content_id": "media-source://media_source/local/zone1-before.jpg"
            },
            CONF_ZONE_PHOTO_NOTE: "Before recommissioning",
            CONF_ZONE_PHOTO_RUNNING: False,
        }
    )
    before = manager.get_zone("property.primary", "zone.1")
    zone2_before = manager.get_zone("property.primary", "zone.2")
    photos_before = manager.photos_for_zone("property.primary", "zone.1")
    profiles_before = manager.delivery_profiles
    assert before is not None
    assert zone2_before is not None
    saves_before = len(store.saved)

    async def unexpected_command(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("recommissioning must not issue watering commands")

    monkeypatch.setattr(
        config_flow_module, "async_start_guided_observation", unexpected_command
    )
    monkeypatch.setattr(
        config_flow_module, "async_stop_guided_observation", unexpected_command
    )

    home = await flow.async_step_manage_zone()
    assert _manage_zone_actions(home)["recommission"] == "Start over / Recommission"
    confirm = await flow.async_step_manage_zone(
        {CONF_MANAGE_ZONE_ACTION: "recommission"}
    )
    assert confirm["step_id"] == "manage_zone_recommission"
    assert voluptuous_serialize.convert(
        confirm["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert manager.get_zone("property.primary", "zone.1") == before
    assert len(store.saved) == saves_before

    cancelled = await flow.async_step_manage_zone_recommission(
        {CONF_RECOMMISSION_CONFIRM: False}
    )
    assert cancelled["step_id"] == "manage_zone"
    assert manager.get_zone("property.primary", "zone.1") == before
    assert len(store.saved) == saves_before

    store.fail_save = True
    failed = await flow.async_step_manage_zone_recommission(
        {CONF_RECOMMISSION_CONFIRM: True}
    )
    assert failed["errors"] == {"base": "commissioning_persistence_failed"}
    assert manager.get_zone("property.primary", "zone.1") == before
    assert store.value == store.saved[-1]
    assert len(store.saved) == saves_before

    store.fail_save = False
    completed = await flow.async_step_manage_zone_recommission(
        {CONF_RECOMMISSION_CONFIRM: True}
    )
    assert completed["step_id"] == "manage_zone"
    assert len(store.saved) == saves_before + 1
    reset = manager.get_zone("property.primary", "zone.1")
    assert reset is not None
    assert reset.identity == before.identity
    assert reset.display_name == "Front Planters"
    assert reset.landscape_profile.plant_groups == ()
    assert reset.plant_details == ()
    assert reset.delivery_links == ()
    assert zone_setup_is_unresolved(reset)
    assert reset.landscape_events[-1].event_type is LandscapeEventType.ZONE_RECOMMISSIONED
    assert reset.landscape_events[-1].setup_snapshot is not None
    assert manager.get_zone("property.primary", "zone.2") == zone2_before
    assert manager.delivery_profiles == profiles_before
    assert manager.photos_for_zone("property.primary", "zone.1") == photos_before
    assert areas[0].binding is area_binding
    assert reset.execution_authorized is False
    assert reset.live_control_authorized is False

    reset_actions = _manage_zone_actions(completed)
    assert reset_actions["setup"] == "Set up this zone"
    assert "recommission" not in reset_actions
    assert "add_plant" not in reset_actions
    choices = _form_choices(
        await flow.async_step_manage_zones(), CONF_COMMISSIONING_TARGET
    )
    assert choices["1|1"] == "Front Planters — Not set up"

    await flow.async_step_manage_zones({CONF_COMMISSIONING_TARGET: "1|1"})
    setup = await flow.async_step_manage_zone({CONF_MANAGE_ZONE_ACTION: "setup"})
    assert setup["step_id"] == "commissioning_simple_input"
    review = await flow.async_step_commissioning_simple_input(
        {
            CONF_SIMPLE_DESCRIPTION: "A newly planted Hass avocado",
            CONF_SIMPLE_PLANT_NAME: "Hass avocado",
            CONF_SIMPLE_PLANTED_DATE: "2026-08-17",
            CONF_SIMPLE_CONTAINER_GALLONS: 5,
            CONF_SIMPLE_HEIGHT_FEET: 4,
            CONF_SIMPLE_DELIVERY_TYPE: "unknown",
            CONF_SIMPLE_EMITTER_CLASS: "",
            CONF_SIMPLE_THROW_FEET: "",
            CONF_SIMPLE_SPRAY_PATTERN: "unknown",
            CONF_SIMPLE_SHARING: "unknown",
            CONF_SIMPLE_PLANTS_PER_EMITTER: "",
        }
    )
    assert review["step_id"] == "commissioning_simple_review"
    saved = await flow.async_step_commissioning_simple_review(
        {CONF_SIMPLE_CONFIRM: True}
    )
    assert saved["type"] == "create_entry"
    recommissioned = manager.get_zone("property.primary", "zone.1")
    assert recommissioned is not None
    assert recommissioned.identity == before.identity
    assert recommissioned.display_name == "Front Planters"
    assert recommissioned.landscape_profile.profile_status == "onboarded"
    assert tuple(
        plant.common_name for plant in recommissioned.landscape_profile.plant_groups
    ) == ("Hass avocado",)
    assert any(
        event.event_type is LandscapeEventType.ZONE_RECOMMISSIONED
        for event in recommissioned.landscape_events
    )


@pytest.mark.asyncio
async def test_manage_zone_identification_runs_30_seconds_stops_and_repeats(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "identify-zone-flow")
    manager._store = _Store(None)  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    guided = GuidedObservationManager()
    runtime = SimpleNamespace(
        landscape_intelligence=manager,
        guided_observation=guided,
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow._manage_controller_slot = 1
    flow._manage_area_slot = 1
    flow._commissioning_area_name = "Zone 1"
    starts: list[int] = []
    stops: list[tuple[int, int]] = []

    async def start(
        coordinator: Any,
        *,
        controller_slot: int,
        area_slot: int,
        duration_seconds: int,
    ) -> GuidedObservationResult:
        assert coordinator is runtime
        starts.append(duration_seconds)
        guided.mark_starting(controller_slot, area_slot, duration_seconds)
        return GuidedObservationResult(
            GuidedObservationStatus.ACCEPTED, controller_slot, area_slot
        )

    async def stop(
        coordinator: Any, *, controller_slot: int, area_slot: int
    ) -> GuidedObservationResult:
        assert coordinator is runtime
        stops.append((controller_slot, area_slot))
        guided.snapshot = replace(
            guided.snapshot, state=GuidedObservationState.COMPLETED
        )
        return GuidedObservationResult(
            GuidedObservationStatus.ACCEPTED, controller_slot, area_slot
        )

    monkeypatch.setattr(
        config_flow_module, "async_start_guided_observation", start
    )
    monkeypatch.setattr(
        config_flow_module, "async_stop_guided_observation", stop
    )

    inactive = await flow.async_step_manage_zone()
    inactive_actions = _manage_zone_actions(inactive)
    assert inactive_actions["run"] == "Identify Zone 1 — water for 30 seconds"

    active = await flow.async_step_manage_zone(
        {CONF_MANAGE_ZONE_ACTION: "run"}
    )
    assert starts == [ZONE_IDENTIFICATION_DURATION_SECONDS]
    assert guided.snapshot.requested_duration_seconds == 30
    assert _manage_zone_actions(active)["stop"] == "Stop watering Zone 1"

    completed = await flow.async_step_manage_zone(
        {CONF_MANAGE_ZONE_ACTION: "stop"}
    )
    assert stops == [(1, 1)]
    assert _manage_zone_actions(completed)["run"] == (
        "Identify Zone 1 — water for 30 seconds"
    )


@pytest.mark.asyncio
async def test_existing_zone_simple_update_preserves_identity_and_history(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "simple-revisit")
    manager._store = _Store(None)  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    before = manager.get_zone("property.primary", "zone.1")
    assert before is not None
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id
    flow._commissioning_controller_slot = 1
    flow._commissioning_area_slot = 1
    flow._commissioning_area_name = "Zone 1"
    flow._manage_plant_group_id = "podocarpus"
    original_event_count = len(before.landscape_events)

    review = await flow.async_step_commissioning_simple_input(
        {
            CONF_SIMPLE_DESCRIPTION: "The Podocarpus are now about 6 feet tall.",
            CONF_SIMPLE_PLANT_NAME: "Podocarpus",
            CONF_SIMPLE_PLANTED_DATE: "2025-08-25",
            CONF_SIMPLE_CONTAINER_GALLONS: 5,
            CONF_SIMPLE_HEIGHT_FEET: 6,
            CONF_SIMPLE_DELIVERY_TYPE: "microjet",
            CONF_SIMPLE_EMITTER_CLASS: "blue",
            CONF_SIMPLE_THROW_FEET: 3.5,
            CONF_SIMPLE_SPRAY_PATTERN: "part_circle",
            CONF_SIMPLE_SHARING: "shared",
            CONF_SIMPLE_PLANTS_PER_EMITTER: 2,
        }
    )
    assert review["step_id"] == "commissioning_simple_review"
    saved = await flow.async_step_commissioning_simple_review(
        {CONF_SIMPLE_CONFIRM: True}
    )
    assert saved["type"] == "create_entry"
    after = manager.get_zone("property.primary", "zone.1")
    assert after is not None
    assert len(manager.commissioned_zones) == 1
    assert len(after.landscape_events) == original_event_count + 1
    podocarpus = next(
        item for item in after.plant_details if item.plant_group_id == "podocarpus"
    )
    assert podocarpus.current_height_meters == pytest.approx(1.8288)


class _Store:
    def __init__(self, value: dict[str, Any] | None, *, fail_save: bool = False) -> None:
        self.value = value
        self.fail_save = fail_save
        self.saved: list[dict[str, Any]] = []

    async def async_load(self) -> dict[str, Any] | None:
        return self.value

    async def async_save(self, value: dict[str, Any]) -> None:
        if self.fail_save:
            raise OSError("synthetic persistence failure")
        self.saved.append(value)
        self.value = value


def _zone2() -> Any:
    return map_zone_onboarding(
        ZoneOnboardingRequest(
            CanonicalZoneIdentity("property.primary", "zone.2", 1, 2),
            "Podocarpus screen",
            ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
            NOW,
            manual_plants=(
                ManualPlantOnboardingInput(
                    "podocarpus",
                    "Podocarpus",
                    "Podocarpus spp.",
                    EstablishmentState.ESTABLISHING,
                    NOW,
                    planted_at=NOW - timedelta(days=365),
                    source_container_gallons=5,
                    current_height_meters=1.8288,
                ),
            ),
        )
    )


def _baseline_zone() -> Any:
    return map_zone_onboarding(
        ZoneOnboardingRequest(
            CanonicalZoneIdentity("property.primary", "zone.4", 1, 4),
            "Baseline lawn",
            ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
            NOW - timedelta(days=30),
            calibrated_baseline=UserCalibratedBaseline(
                720,
                (75 - 32) * 5 / 9,
                0,
                "representative dry day",
                NOW - timedelta(days=30),
                Confidence.HIGH,
            ),
        )
    )


def _weather_fact(value: object, observed_at: datetime) -> Any:
    return WeatherFact(
        value=value,
        confidence=0.9,
        provenance=WeatherProvenance(
            "normalized.synthetic.station", WeatherSourceType.STATION
        ),
        verification_status=WeatherVerificationStatus.PROVIDER_VALIDATED,
        observed_at=observed_at,
        quality=WeatherQualityMetadata(WeatherQualityStatus.GOOD),
    )


def _baseline_observations() -> ObservationWindow:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=24)
    observations = []
    for index in range(24):
        observed_at = start + timedelta(hours=index)
        unknown = WeatherFact(
            value=None,
            confidence=0,
            provenance=WeatherProvenance("synthetic", WeatherSourceType.OTHER),
            verification_status=WeatherVerificationStatus.UNVERIFIED,
            observed_at=observed_at,
            quality=WeatherQualityMetadata(
                WeatherQualityStatus.UNAVAILABLE, reason="not used"
            ),
        )
        values = {
            name: unknown for name in EnvironmentalWeatherFacts.__dataclass_fields__
        }
        values["reference_evapotranspiration_mm"] = _weather_fact(0.2, observed_at)
        values["precipitation_mm"] = _weather_fact(0.0, observed_at)
        values["air_temperature_celsius"] = _weather_fact(23.7, observed_at)
        observations.append(
            HistoricalWeatherObservation(
                f"observation.{index}",
                "location.synthetic",
                observed_at,
                observed_at + timedelta(minutes=1),
                EnvironmentalWeatherFacts(**values),
            )
        )
    return ObservationWindow(
        "window.synthetic",
        "location.synthetic",
        start,
        end,
        tuple(observations),
    )


@pytest.mark.asyncio
async def test_legacy_schema_one_zone1_store_migrates_additively(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "existing")
    old_zone1 = {"profile_status": "commissioned", "legacy_marker": "preserve"}
    store = _Store({"schema_version": 1, "zone_1": old_zone1})
    manager._store = store  # type: ignore[assignment]

    await manager.async_initialize(initial_observed_at=NOW)

    assert len(store.saved) == 1
    assert store.value is not None
    assert store.value["commissioning_store_schema_version"] == 8
    assert store.value["zone_1"] == old_zone1
    assert manager.zone1.area_slot == 1
    assert tuple(zone.identity.area_slot for zone in manager.commissioned_zones) == (1,)


@pytest.mark.asyncio
async def test_generic_zone_crud_round_trip_and_tombstone(hass: HomeAssistant) -> None:
    first = LandscapeIntelligenceManager(hass, "roundtrip")
    store = _Store(None)
    first._store = store  # type: ignore[assignment]
    await first.async_initialize(initial_observed_at=NOW)

    zone2 = _zone2()
    assert await first.async_add_zone(zone2)
    assert first.get_zone("property.primary", "zone.2") == zone2
    assert first.get_zone_by_slots(1, 2) == zone2
    assert not await first.async_add_zone(zone2)

    second = LandscapeIntelligenceManager(hass, "roundtrip-restored")
    second._store = store  # type: ignore[assignment]
    await second.async_initialize(initial_observed_at=NOW)
    assert second.get_zone("property.primary", "zone.2") == zone2

    assert await second.async_deactivate_zone(
        "property.primary",
        "zone.2",
        deactivated_at=NOW + timedelta(days=1),
        reason="user_deactivated",
    )
    assert second.get_zone("property.primary", "zone.2") is None
    assert second.deactivated_zones[0].profile == zone2
    assert not await second.async_deactivate_zone(
        "property.primary",
        "zone.1",
        deactivated_at=NOW + timedelta(days=1),
        reason="not_allowed",
    )


@pytest.mark.asyncio
async def test_persistence_failure_does_not_expose_new_zone(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "failure")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    store.fail_save = True

    assert not await manager.async_add_zone(_zone2())
    assert manager.get_zone("property.primary", "zone.2") is None
    assert manager.last_persistence_error == "commissioning_store_save_failed"
    assert manager.zone1.area_slot == 1


@pytest.mark.asyncio
async def test_failed_edit_preserves_durable_and_in_memory_profile(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "edit-failure")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())
    original = manager.get_zone("property.primary", "zone.2")
    assert original is not None
    durable_before = store.value
    candidate = add_plant_group(
        original,
        PlantAdditionInput(
            "event.zone2.companion.add",
            ManualPlantOnboardingInput(
                "zone.2.plant.2",
                "Companion shrub",
                None,
                EstablishmentState.ESTABLISHED,
                NOW + timedelta(minutes=1),
            ),
            NOW + timedelta(minutes=1),
        ),
    )
    store.fail_save = True

    assert not await manager.async_update_zone(candidate)
    assert manager.get_zone("property.primary", "zone.2") == original
    assert store.value == durable_before


@pytest.mark.asyncio
async def test_diagnostics_are_canonical_compact_and_confidence_preserved(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "diagnostics")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())

    summary = manager.diagnostics()["commissioning_summary"]
    assert summary["store_schema_version"] == 8
    assert summary["commissioned_zone_count"] == 2
    assert summary["legacy_zone_1_compatible"] is True
    assert summary["zones"][1]["identity"] == {
        "property_id": "property.primary",
        "zone_id": "zone.2",
        "controller_slot": 1,
        "area_slot": 2,
    }
    assert "controller_id" not in repr(summary)
    assert "native_id" not in repr(summary)
    zone_summary = manager.compact_summary(2)
    assert zone_summary is not None
    assert zone_summary["commissioning_assessment_status"] == "purpose_ready"
    assert zone_summary["commissioning_ready_purpose_count"] >= 1
    assert zone_summary["commissioning_follow_up_count"] >= 1
    assert "commissioning_assessment" in summary["zones"][1]
    assert len(repr(zone_summary)) < 2048
    assert _zone2().plant_details[0].confidence is Confidence.HIGH


def test_options_form_maps_zone_two_to_installed_canonical_identity() -> None:
    profile = _map_commissioning_form(
        {
            CONF_COMMISSIONING_ZONE_NAME: "Podocarpus screen",
            CONF_COMMISSIONING_PLANT_NAME: "Podocarpus",
            CONF_COMMISSIONING_BOTANICAL_NAME: "Podocarpus spp.",
            CONF_COMMISSIONING_ESTABLISHMENT: EstablishmentState.ESTABLISHING.value,
            CONF_COMMISSIONING_PLANTED_DATE: "2025-08-24",
            CONF_COMMISSIONING_CONTAINER_GALLONS: 5,
            CONF_COMMISSIONING_HEIGHT_FEET: 6,
            CONF_COMMISSIONING_DELIVERY_PROFILE_ID: "delivery.zone.2",
            CONF_COMMISSIONING_COMPONENT_IDS: "emitter.1, emitter.2",
        },
        controller_slot=1,
        area_slot=2,
        mode=ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
        now=NOW,
        timezone=ZoneInfo("America/Los_Angeles"),
    )

    assert profile.identity == CanonicalZoneIdentity(
        "property.primary", "zone.2", 1, 2
    )
    assert profile.plant_details[0].current_height_meters == pytest.approx(1.8288)
    assert profile.delivery_links[0].delivery_profile_id == "delivery.zone.2"
    assert not profile.execution_authorized
    assert not profile.live_control_authorized


@pytest.mark.asyncio
async def test_options_review_flow_adds_second_plant_without_replacing_first(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "options-review")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    selected = await flow.async_step_commissioning_review_select(
        {CONF_COMMISSIONING_REVIEW_TARGET: "property.primary|zone.2"}
    )
    assert selected["type"] == "form"
    assert selected["step_id"] == "commissioning_review"
    summary = selected["description_placeholders"]["review_summary"]
    assert "Commissioning status: purpose_ready" in summary
    assert "delivery_quantification: not_ready" in summary
    assert "document_irrigation_delivery" in summary
    add_form = await flow.async_step_commissioning_review(
        {CONF_COMMISSIONING_REVIEW_ACTION: "add_plant"}
    )
    assert add_form["step_id"] == "commissioning_add_plant"
    result = await flow.async_step_commissioning_add_plant(
        {
            CONF_COMMISSIONING_PLANT_NAME: "Hass avocado",
            CONF_COMMISSIONING_BOTANICAL_NAME: "Persea americana Hass",
            CONF_COMMISSIONING_ESTABLISHMENT: EstablishmentState.NEWLY_PLANTED.value,
            CONF_COMMISSIONING_IRRIGATION_ROLE: "primary_target",
            CONF_COMMISSIONING_PLANTED_DATE: "2026-08-17",
            CONF_COMMISSIONING_CONTAINER_GALLONS: 5,
            CONF_COMMISSIONING_HEIGHT_FEET: 4,
            CONF_COMMISSIONING_DIRECT_IRRIGATION: True,
            CONF_COMMISSIONING_DEDICATED_EMITTER: False,
            CONF_COMMISSIONING_EMITTER_TYPE: "",
            CONF_COMMISSIONING_DELIVERY_STATUS: "unresolved",
            CONF_COMMISSIONING_DELIVERY_PROFILE_ID: "",
            CONF_COMMISSIONING_COMPONENT_IDS: "",
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "commissioning_review"
    updated = manager.get_zone("property.primary", "zone.2")
    assert updated is not None
    assert tuple(
        plant.common_name for plant in updated.landscape_profile.plant_groups
    ) == ("Podocarpus", "Hass avocado")
    assert updated.landscape_events[-1].plant_snapshot.plant_group.common_name == (
        "Hass avocado"
    )
    await flow.async_step_commissioning_review(
        {CONF_COMMISSIONING_REVIEW_ACTION: "edit_delivery"}
    )
    delivery_form = await flow.async_step_commissioning_plant_select(
        {CONF_COMMISSIONING_PLANT_TARGET: "zone.2.plant.1"}
    )
    assert delivery_form["step_id"] == "commissioning_delivery"
    delivered = await flow.async_step_commissioning_delivery(
        {
            CONF_COMMISSIONING_DELIVERY_STATUS: "documented",
            CONF_COMMISSIONING_DELIVERY_PROFILE_ID: "delivery.zone.2.avocado",
            CONF_COMMISSIONING_COMPONENT_IDS: "component.avocado.1",
            CONF_COMMISSIONING_DEDICATED_EMITTER: True,
        }
    )
    assert delivered["step_id"] == "commissioning_review"
    final = manager.get_zone("property.primary", "zone.2")
    assert final is not None
    avocado_link = next(
        link
        for link in final.delivery_links
        if link.plant_group_id == "zone.2.plant.1"
    )
    assert avocado_link.delivery_profile_id == "delivery.zone.2.avocado"


@pytest.mark.asyncio
async def test_options_flow_guides_dry_baseline_reference_capture(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "baseline-capture")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_baseline_zone())
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(
        landscape_intelligence=manager,
        weather_evidence=SimpleNamespace(observations=_baseline_observations()),
    )
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    await flow.async_step_commissioning_review_select(
        {CONF_COMMISSIONING_REVIEW_TARGET: "property.primary|zone.4"}
    )
    form = await flow.async_step_commissioning_review(
        {CONF_COMMISSIONING_REVIEW_ACTION: "capture_baseline_reference"}
    )
    assert form["step_id"] == "commissioning_baseline_reference"
    result = await flow.async_step_commissioning_baseline_reference(
        {
            CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS: 24,
            CONF_COMMISSIONING_CAPTURE_DRY_CONFIRMATION: True,
            CONF_COMMISSIONING_REPLACE_REFERENCE_CONFIRMATION: False,
        }
    )
    assert result["step_id"] == "commissioning_review"
    updated = manager.get_zone("property.primary", "zone.4")
    assert updated is not None
    reference = updated.demand_sources[0].calibrated_baseline.environmental_reference
    assert reference.reference_et0_mm == pytest.approx(4.8)
    assert reference.capture_method.value == "observed_environment_capture"
    assert updated.execution_authorized is False

    await flow.async_step_commissioning_review(
        {CONF_COMMISSIONING_REVIEW_ACTION: "edit_baseline"}
    )
    unchanged = await flow.async_step_commissioning_baseline(
        {
            CONF_COMMISSIONING_BASELINE_ACTION: "set",
            CONF_COMMISSIONING_BASELINE_MINUTES: 12,
            CONF_COMMISSIONING_REFERENCE_TEMP_F: 75,
            CONF_COMMISSIONING_RECENT_RAIN_MM: 0,
            CONF_COMMISSIONING_REFERENCE_ET0_MM: reference.reference_et0_mm,
            CONF_COMMISSIONING_REFERENCE_PERIOD_HOURS: 24,
        }
    )
    assert unchanged["step_id"] == "commissioning_review"
    preserved = manager.get_zone("property.primary", "zone.4")
    preserved_baseline = preserved.demand_sources[0].calibrated_baseline
    assert preserved_baseline.environmental_reference == reference
    assert preserved_baseline.reference_history == ()


@pytest.mark.asyncio
async def test_options_flow_calibrates_measured_shared_delivery_atomically(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "delivery-calibration")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)
    flow = IrrigationOSOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    await flow.async_step_commissioning_review_select(
        {CONF_COMMISSIONING_REVIEW_TARGET: "property.primary|zone.2"}
    )
    await flow.async_step_commissioning_review(
        {CONF_COMMISSIONING_REVIEW_ACTION: "calibrate_delivery"}
    )
    form = await flow.async_step_commissioning_plant_select(
        {CONF_COMMISSIONING_PLANT_TARGET: "podocarpus"}
    )
    assert form["step_id"] == "commissioning_delivery_calibration"
    result = await flow.async_step_commissioning_delivery_calibration(
        {
            CONF_COMMISSIONING_DELIVERY_PROFILE_ID: "delivery.zone.2",
            CONF_COMMISSIONING_DELIVERY_COMPONENT_ID: "component.microjet.shared.1",
            CONF_COMMISSIONING_DELIVERY_COMPONENT_NAME: "Shared microjet",
            CONF_COMMISSIONING_DELIVERY_TYPE: "microjet",
            CONF_COMMISSIONING_COMPONENT_COUNT: 1,
            CONF_COMMISSIONING_FLOW_EVIDENCE_LEVEL: "measured",
            CONF_COMMISSIONING_FLOW_BASIS: "component_total",
            CONF_COMMISSIONING_FLOW_LPH: "",
            CONF_COMMISSIONING_COLLECTED_VOLUME: 1,
            CONF_COMMISSIONING_COLLECTED_VOLUME_UNIT: "us_gallons",
            CONF_COMMISSIONING_COLLECTION_DURATION: 300,
            CONF_COMMISSIONING_RADIUS_METERS: 0.9144,
            CONF_COMMISSIONING_DEDICATED_EMITTER: False,
        }
    )
    assert result["step_id"] == "commissioning_review"
    delivery = manager.get_delivery_profile("delivery.zone.2")
    assert delivery is not None
    assert delivery.components[0].measured_flow_liters_per_hour.value == pytest.approx(
        45.424941408
    )
    updated = manager.get_zone("property.primary", "zone.2")
    assert updated is not None
    assert updated.delivery_links[0].component_ids == (
        "component.microjet.shared.1",
    )
    assert updated.delivery_links[0].dedicated_delivery is False
    assert updated.execution_authorized is False
    assert store.value["water_delivery_profiles"][0] == delivery.to_dict()


@pytest.mark.asyncio
async def test_delivery_calibration_save_failure_publishes_neither_zone_nor_profile(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "delivery-save-failure")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())
    original = manager.get_zone("property.primary", "zone.2")
    assert original is not None
    delivery = calibrate_delivery_component(
        DeliveryComponentCalibrationRequest(
            "delivery.zone.2",
            "zone.2",
            "component.microjet.1",
            "Microjet",
            WaterDeliveryType.MICROJET,
            1,
            DeliveryEvidenceLevel.UNKNOWN,
            NOW,
        )
    )
    store.fail_save = True

    assert not await manager.async_update_zone_and_delivery_profile(original, delivery)
    assert manager.get_zone("property.primary", "zone.2") == original
    assert manager.delivery_profiles == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("review_action", "expected_step"),
    [
        ("calibrate_delivery", "commissioning_delivery_calibration"),
        ("edit_delivery", "commissioning_delivery"),
    ],
)
async def test_framework_options_flow_accepts_zone1_plant_selection(
    hass: HomeAssistant,
    review_action: str,
    expected_step: str,
) -> None:
    """Exercise HA's schema validation rather than calling flow methods directly."""
    manager = LandscapeIntelligenceManager(hass, f"selector-{review_action}")
    manager._store = _Store(None)  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(landscape_intelligence=manager)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_OPTIONS_ACTION: "commissioning_review"}
    )
    assert result["step_id"] == "commissioning_review_select"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_COMMISSIONING_REVIEW_TARGET: "property.primary|zone.1"},
    )
    assert result["step_id"] == "commissioning_review"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMMISSIONING_REVIEW_ACTION: review_action}
    )
    assert result["step_id"] == "commissioning_plant_select"
    assert result["data_schema"](
        {CONF_COMMISSIONING_PLANT_TARGET: "podocarpus"}
    ) == {CONF_COMMISSIONING_PLANT_TARGET: "podocarpus"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_COMMISSIONING_PLANT_TARGET: "podocarpus"},
    )
    assert result["step_id"] == expected_step
    serialized_schema = voluptuous_serialize.convert(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert serialized_schema


@pytest.mark.parametrize(
    "schema",
    [
        _commissioning_delivery_calibration_schema(None),
        _commissioning_baseline_schema(None),
        _commissioning_plant_schema(),
        _commissioning_schema(
            ZoneDemandSourceMode.MANUAL_PLANT_PROFILE, "Manual zone"
        ),
        _commissioning_schema(
            ZoneDemandSourceMode.USER_CALIBRATED_BASELINE, "Baseline zone"
        ),
        _commissioning_schema(ZoneDemandSourceMode.HYBRID, "Hybrid zone"),
    ],
)
def test_commissioning_optional_numeric_forms_serialize_for_ha(schema: Any) -> None:
    """Keep every commissioning numeric form inside HA's serialization contract."""
    serialized_schema = voluptuous_serialize.convert(
        schema, custom_serializer=cv.custom_serializer
    )

    assert serialized_schema
