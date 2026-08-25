from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigationos.config_flow import (
    CONF_COMMISSIONING_BOTANICAL_NAME,
    CONF_COMMISSIONING_COMPONENT_IDS,
    CONF_COMMISSIONING_CONTAINER_GALLONS,
    CONF_COMMISSIONING_DEDICATED_EMITTER,
    CONF_COMMISSIONING_DELIVERY_PROFILE_ID,
    CONF_COMMISSIONING_DELIVERY_STATUS,
    CONF_COMMISSIONING_DIRECT_IRRIGATION,
    CONF_COMMISSIONING_EMITTER_TYPE,
    CONF_COMMISSIONING_ESTABLISHMENT,
    CONF_COMMISSIONING_HEIGHT_FEET,
    CONF_COMMISSIONING_IRRIGATION_ROLE,
    CONF_COMMISSIONING_PLANT_NAME,
    CONF_COMMISSIONING_PLANT_TARGET,
    CONF_COMMISSIONING_PLANTED_DATE,
    CONF_COMMISSIONING_REVIEW_ACTION,
    CONF_COMMISSIONING_REVIEW_TARGET,
    CONF_COMMISSIONING_ZONE_NAME,
    IrrigationOSOptionsFlow,
    _map_commissioning_form,
)
from custom_components.irrigationos.const import DOMAIN
from custom_components.irrigationos.landscape_intelligence import (
    CanonicalZoneIdentity,
    Confidence,
    EstablishmentState,
    PlantAdditionInput,
    ZoneDemandSourceMode,
    add_plant_group,
)
from custom_components.irrigationos.landscape_intelligence.manager import (
    LandscapeIntelligenceManager,
)
from custom_components.irrigationos.landscape_intelligence.onboarding import (
    ManualPlantOnboardingInput,
    ZoneOnboardingRequest,
    map_zone_onboarding,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


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
    assert store.value["commissioning_store_schema_version"] == 3
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
    assert summary["store_schema_version"] == 3
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
