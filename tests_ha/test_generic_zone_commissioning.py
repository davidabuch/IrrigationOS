from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant

from custom_components.irrigationos.config_flow import (
    CONF_COMMISSIONING_BOTANICAL_NAME,
    CONF_COMMISSIONING_COMPONENT_IDS,
    CONF_COMMISSIONING_CONTAINER_GALLONS,
    CONF_COMMISSIONING_DELIVERY_PROFILE_ID,
    CONF_COMMISSIONING_ESTABLISHMENT,
    CONF_COMMISSIONING_HEIGHT_FEET,
    CONF_COMMISSIONING_PLANT_NAME,
    CONF_COMMISSIONING_PLANTED_DATE,
    CONF_COMMISSIONING_ZONE_NAME,
    _map_commissioning_form,
)
from custom_components.irrigationos.landscape_intelligence import (
    CanonicalZoneIdentity,
    Confidence,
    EstablishmentState,
    ZoneDemandSourceMode,
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
    assert store.value["commissioning_store_schema_version"] == 2
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
async def test_diagnostics_are_canonical_compact_and_confidence_preserved(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "diagnostics")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize(initial_observed_at=NOW)
    assert await manager.async_add_zone(_zone2())

    summary = manager.diagnostics()["commissioning_summary"]
    assert summary["store_schema_version"] == 2
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
