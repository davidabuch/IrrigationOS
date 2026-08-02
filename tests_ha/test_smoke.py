"""Home Assistant runtime smoke tests for IrrigationOS v0.4.1."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigationos import async_migrate_entry
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
    VendorBinding,
)
from custom_components.irrigationos.diagnostics import async_get_config_entry_diagnostics


def _area(
    controller_id: str,
    slot: int,
    *,
    configured: bool,
) -> IrrigationArea:
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


def _snapshot(
    controller_id: str = "controller_test",
    *,
    slots: int = 2,
    include_controller: bool = True,
) -> ControllerRegistrySnapshot:
    now = datetime.now(UTC)
    observation = ObservationMetadata(
        observed_at=now,
        fresh_until=now + timedelta(minutes=10),
        source="rachio",
        quality=ObservationQuality.CONFIRMED,
    )
    if not include_controller:
        return ControllerRegistrySnapshot(
            provider="rachio",
            account_id="person-1",
            account_name="Test Account",
            controllers=(),
            observation=observation,
        )
    areas = tuple(
        _area(controller_id, slot, configured=slot == 1)
        for slot in range(1, slots + 1)
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
        capacity=slots,
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
        observation=observation,
    )


class MutableAdapter:
    """Return mutable snapshots through the real coordinator contract."""

    provider = "rachio"

    def __init__(self, snapshot: ControllerRegistrySnapshot) -> None:
        self.snapshot = snapshot

    async def async_get_account(self) -> tuple[str, ControllerRegistrySnapshot]:
        return "person-1", self.snapshot

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        assert account_id == "person-1"
        return self.snapshot


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


@pytest.mark.asyncio
async def test_fresh_config_flow_discovery(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    def create_adapter(
        _provider: str,
        _session: object,
        _api_key: str,
        identities: ControllerIdentityRegistry,
    ) -> MutableAdapter:
        controller_id = identities.controller_id_for(
            "rachio", "native-controller-1"
        )
        return MutableAdapter(_snapshot(controller_id))

    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", create_adapter)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "top-secret-api-key", CONF_NAME: "IrrigationOS"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.version == 2
    assert entry.data[CONF_IDENTITY_REGISTRY]["controllers"][
        "rachio:native-controller-1"
    ].startswith("controller_")
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_runtime_inventory_and_diagnostics(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
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
    assert "non existing `via_device`" not in caplog.text

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    unique_ids = {item.unique_id for item in entries}
    assert "controller_test_status" in unique_ids
    assert "controller_test:slot:1_observation" in unique_ids
    assert "controller_test:slot:2_observation" in unique_ids
    unused = next(
        item for item in entries if item.unique_id == "controller_test:slot:2_observation"
    )
    assert unused.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    adapter.snapshot = _snapshot(slots=3)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert "controller_test:slot:3_observation" in {item.unique_id for item in entries}

    configured = next(
        item for item in entries if item.unique_id == "controller_test:slot:1_observation"
    )
    adapter.snapshot = _snapshot(include_controller=False)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    removed_state = hass.states.get(configured.entity_id)
    assert removed_state is not None
    assert removed_state.state == STATE_UNAVAILABLE

    adapter.snapshot = _snapshot()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    diagnostic_text = repr(diagnostics)
    assert "top-secret-api-key" not in diagnostic_text
    assert "native-controller-1" not in diagnostic_text
    assert "native-zone-1" not in diagnostic_text
    observation = diagnostics["coordinator"]["data"]["observation"]
    assert observation["source"] == "rachio"
    assert "observed_at" in observation


@pytest.mark.asyncio
async def test_v040_registry_and_landscape_migration(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MigrationAdapter(MutableAdapter):
        def __init__(self, identities: ControllerIdentityRegistry) -> None:
            controller_id = identities.controller_id_for(
                "rachio", "native-controller-1"
            )
            super().__init__(_snapshot(controller_id))

    monkeypatch.setattr(
        DEFAULT_PROVIDER_FACTORY,
        "create",
        lambda _provider, _session, _api_key, identities: MigrationAdapter(identities),
    )
    old_data = _entry_data()
    old_data.pop(CONF_IDENTITY_REGISTRY)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=old_data,
        options={
            CONF_AREA_PROFILES: {
                "rachio:native-zone-1": {"display_name": "My Orchard"}
            }
        },
        version=1,
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    old_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "rachio:native-zone-1_observation",
        config_entry=entry,
    )
    device_registry = dr.async_get(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "rachio:native-zone-1")},
        name="Old Zone",
    )

    assert await async_migrate_entry(hass, entry)
    canonical_controller_id = entry.data[CONF_IDENTITY_REGISTRY]["controllers"][
        "rachio:native-controller-1"
    ]
    canonical_area_id = f"{canonical_controller_id}:slot:1"
    migrated_entity = entity_registry.async_get(old_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.entity_id == old_entity.entity_id
    assert migrated_entity.unique_id == f"{canonical_area_id}_observation"
    migrated_device = device_registry.async_get(old_device.id)
    assert migrated_device is not None
    assert (DOMAIN, canonical_area_id) in migrated_device.identifiers
    assert entry.options[CONF_AREA_PROFILES][canonical_area_id]["display_name"] == (
        "My Orchard"
    )
    assert entry.version == 2
