"""Home Assistant regression tests for stable IrrigationOS zone identity."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigationos.adapters.factory import DEFAULT_PROVIDER_FACTORY
from custom_components.irrigationos.const import (
    CONF_API_KEY,
    CONF_AREA_PROFILES,
    CONF_CONTROLLER_PROVIDER,
    CONF_IDENTITY_REGISTRY,
    CONF_OPERATING_MODE,
    CONF_PERSON_ID,
    DOMAIN,
    MODE_OBSERVATION,
)
from custom_components.irrigationos.controllers import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerIdentityRegistry,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
    ObservationMetadata,
    ObservationQuality,
    RealtimeRegistrationHealth,
    VendorBinding,
)

GLOBAL_ENTITY_IDS = {
    "irrigationos_status": ("sensor.status", "sensor.irrigationos_status"),
    "irrigationos_controller_provider": (
        "sensor.controller_provider",
        "sensor.irrigationos_controller_provider",
    ),
    "irrigationos_controller_count": (
        "sensor.controller_count",
        "sensor.irrigationos_controller_count",
    ),
    "irrigationos_area_count": (
        "sensor.irrigation_area_count",
        "sensor.irrigationos_area_count",
    ),
    "irrigationos_landscape_profile_status": (
        "sensor.landscape_profile_status",
        "sensor.irrigationos_landscape_profile_status",
    ),
    "irrigationos_last_successful_refresh": (
        "sensor.last_successful_refresh",
        "sensor.irrigationos_last_successful_refresh",
    ),
    "irrigationos_discovery_summary": (
        "sensor.discovery_summary",
        "sensor.irrigationos_discovery_summary",
    ),
    "irrigationos_cloud_connection": (
        "binary_sensor.cloud_connection",
        "binary_sensor.irrigationos_cloud_connection",
    ),
    "irrigationos_realtime_observation": (
        "binary_sensor.realtime_observation",
        "binary_sensor.irrigationos_realtime_observation",
    ),
    "irrigationos_polling_fallback": (
        "binary_sensor.polling_fallback",
        "binary_sensor.irrigationos_polling_fallback",
    ),
    "irrigationos_watering_active": (
        "binary_sensor.watering_active",
        "binary_sensor.irrigationos_watering_active",
    ),
}


def _area(controller_id: str, slot: int, *, configured: bool) -> IrrigationArea:
    return IrrigationArea(
        area_id=ControllerIdentityRegistry.area_id_for(controller_id, slot),
        controller_id=controller_id,
        slot_number=slot,
        name=f"Zone {slot}",
        enabled=configured,
        configured=configured,
        state=IrrigationAreaState.IDLE if configured else IrrigationAreaState.UNUSED,
        binding=VendorBinding("rachio", f"native-zone-{slot}") if configured else None,
        vendor_name="Orchard" if configured else None,
    )


def _snapshot(controller_id: str = "controller_test") -> ControllerRegistrySnapshot:
    now = datetime.now(UTC)
    areas = (
        _area(controller_id, 1, configured=True),
        _area(controller_id, 2, configured=False),
    )
    controller = IrrigationController(
        controller_id=controller_id,
        binding=VendorBinding("rachio", "native-controller-1"),
        name="Back Yard",
        availability=ControllerAvailability.ONLINE,
        enabled=True,
        model="GENERATION3_8ZONE",
        serial_number="serial-secret",
        firmware_version="1.0",
        latitude=1.0,
        longitude=2.0,
        capacity=2,
        watering_observation_quality=ObservationQuality.CONFIRMED,
        capabilities=ControllerCapabilities(
            observe_current_watering=True,
            observe_last_watered=True,
        ),
        areas=areas,
    )
    return ControllerRegistrySnapshot(
        provider="rachio",
        account_id="person-1",
        account_name="Test Account",
        controllers=(controller,),
        observation=ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=10),
            source="rachio",
            quality=ObservationQuality.CONFIRMED,
        ),
    )


class MutableAdapter:
    """Return mutable snapshots through the integration adapter contract."""

    provider = "rachio"

    def __init__(self, snapshot: ControllerRegistrySnapshot) -> None:
        self.snapshot = snapshot

    async def async_get_account(self) -> tuple[str, ControllerRegistrySnapshot]:
        return "person-1", self.snapshot

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        assert account_id == "person-1"
        return self.snapshot

    async def async_reconcile_realtime(
        self,
        callback_url: str,
        external_id: str,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        del callback_url, external_id, external_id_prefix
        return RealtimeRegistrationHealth(
            True, len(controller_native_ids), len(controller_native_ids)
        )

    async def async_cleanup_realtime(
        self,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        del external_id_prefix
        return RealtimeRegistrationHealth(True, 0, len(controller_native_ids))


def _entry_data() -> dict[str, Any]:
    return {
        CONF_API_KEY: "top-secret-api-key",
        CONF_PERSON_ID: "person-1",
        CONF_CONTROLLER_PROVIDER: "rachio",
        CONF_OPERATING_MODE: MODE_OBSERVATION,
        CONF_IDENTITY_REGISTRY: {
            "controllers": {"rachio:native-controller-1": "controller_test"}
        },
    }


def _zone_entry(
    registry: er.EntityRegistry,
    entry_id: str,
) -> er.RegistryEntry:
    return next(
        item
        for item in er.async_entries_for_config_entry(registry, entry_id)
        if item.unique_id == "controller_test:slot:1_observation"
    )


@pytest.mark.asyncio
async def test_zone_name_priority_and_identity_survive_reload(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=_entry_data(),
        version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    original = _zone_entry(entity_registry, entry.entry_id)
    original_entity_id = original.entity_id
    original_unique_id = original.unique_id
    original_count = len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))

    assert original.entity_id == "sensor.zone_1_observation"
    zone_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "controller_test:slot:1")}
    )
    assert zone_device is not None
    assert zone_device.name == "Zone 1"

    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_AREA_PROFILES: {
                "controller_test:slot:1": {"display_name": "Avocado Tree"}
            }
        },
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    renamed = _zone_entry(entity_registry, entry.entry_id)
    assert renamed.entity_id == original_entity_id
    assert renamed.unique_id == original_unique_id
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == original_count
    zone_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "controller_test:slot:1")}
    )
    assert zone_device is not None
    assert zone_device.name == "Avocado Tree"

    controller = adapter.snapshot.controllers[0]
    renamed_vendor_area = replace(controller.areas[0], vendor_name="Renamed in Rachio")
    adapter.snapshot = replace(
        adapter.snapshot,
        controllers=(
            replace(
                controller,
                areas=(renamed_vendor_area, controller.areas[1]),
            ),
        ),
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    after_vendor_rename = _zone_entry(entity_registry, entry.entry_id)
    assert after_vendor_rename.entity_id == original_entity_id
    assert after_vendor_rename.unique_id == original_unique_id
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == original_count
    zone_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "controller_test:slot:1")}
    )
    assert zone_device is not None
    assert zone_device.name == "Avocado Tree"
    state = hass.states.get(original_entity_id)
    assert state is not None
    assert state.attributes["vendor_name"] == "Renamed in Rachio"


@pytest.mark.asyncio
async def test_fresh_install_uses_namespaced_global_entity_ids(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=_entry_data(),
        version=3,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries_by_unique_id = {
        item.unique_id: item
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    for unique_id, (old_entity_id, expected_entity_id) in GLOBAL_ENTITY_IDS.items():
        assert entries_by_unique_id[unique_id].entity_id == expected_entity_id
        assert registry.async_get(old_entity_id) is None

    assert _zone_entry(registry, entry.entry_id).entity_id == (
        "sensor.zone_1_observation"
    )
    assert entries_by_unique_id["controller_test:slot:1_enabled"].entity_id == (
        "binary_sensor.zone_1_enabled"
    )


@pytest.mark.asyncio
async def test_upgrade_renames_global_registry_entries_in_place(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=_entry_data(),
        version=2,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    original_registry_ids: dict[str, str] = {}
    for unique_id, (old_entity_id, _expected_entity_id) in GLOBAL_ENTITY_IDS.items():
        domain, object_id = old_entity_id.split(".", maxsplit=1)
        old_entry = registry.async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            config_entry=entry,
            suggested_object_id=object_id,
        )
        assert old_entry.entity_id == old_entity_id
        original_registry_ids[unique_id] = old_entry.id

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    entries_by_unique_id = {item.unique_id: item for item in entries}
    for unique_id, (old_entity_id, expected_entity_id) in GLOBAL_ENTITY_IDS.items():
        migrated = entries_by_unique_id[unique_id]
        assert migrated.entity_id == expected_entity_id
        assert migrated.unique_id == unique_id
        assert migrated.id == original_registry_ids[unique_id]
        assert registry.async_get(old_entity_id) is None
        assert sum(item.unique_id == unique_id for item in entries) == 1


@pytest.mark.asyncio
async def test_watering_active_exposes_control_center_attributes(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=_entry_data(),
        version=3,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    controller = adapter.snapshot.controllers[0]
    watering_area = replace(
        controller.areas[0], state=IrrigationAreaState.WATERING
    )
    adapter.snapshot = replace(
        adapter.snapshot,
        controllers=(
            replace(
                controller,
                areas=(watering_area, controller.areas[1]),
            ),
        ),
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.irrigationos_watering_active")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["active_zone_count"] == 1
    assert state.attributes["active_zone_slots"] == [1]
    assert state.attributes["active_zone_names"] == ["Zone 1"]
    assert state.attributes["active_zone_vendor_names"] == ["Orchard"]
