"""Home Assistant runtime smoke tests for IrrigationOS v0.4.2."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util.aiohttp import MockRequest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigationos import async_migrate_entry
from custom_components.irrigationos import realtime as realtime_module
from custom_components.irrigationos.adapters.factory import DEFAULT_PROVIDER_FACTORY
from custom_components.irrigationos.const import (
    CONF_API_KEY,
    CONF_AREA_PROFILES,
    CONF_CONTROLLER_PROVIDER,
    CONF_IDENTITY_REGISTRY,
    CONF_OPERATING_MODE,
    CONF_PERSON_ID,
    CONF_WEBHOOK_AUTH,
    CONF_WEBHOOK_ID,
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
        self.snapshot_requests = 0
        self.reconcile_calls = 0
        self.cleanup_calls = 0
        self.active_external_ids: set[str] = set()
        self.reconciled_controller_ids: list[tuple[str, ...]] = []
        self.cleaned_controller_ids: list[tuple[str, ...]] = []
        self.registration_health: RealtimeRegistrationHealth | None = None

    async def async_get_account(self) -> tuple[str, ControllerRegistrySnapshot]:
        return "person-1", self.snapshot

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        assert account_id == "person-1"
        self.snapshot_requests += 1
        return self.snapshot

    async def async_reconcile_realtime(
        self,
        callback_url: str,
        external_id: str,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        assert callback_url.startswith("https://")
        assert external_id.startswith(external_id_prefix)
        self.reconcile_calls += 1
        self.reconciled_controller_ids.append(controller_native_ids)
        self.active_external_ids = {external_id}
        if self.registration_health is not None:
            return self.registration_health
        return RealtimeRegistrationHealth(
            True, len(controller_native_ids), len(controller_native_ids)
        )

    async def async_cleanup_realtime(
        self,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        self.cleanup_calls += 1
        self.cleaned_controller_ids.append(controller_native_ids)
        self.active_external_ids = {
            item
            for item in self.active_external_ids
            if not item.startswith(external_id_prefix)
        }
        return RealtimeRegistrationHealth(True, 0, len(controller_native_ids))


def _mock_webhook_request(body: bytes, signature: str) -> MockRequest:
    """Build the same content-length-free request used by HA webhook relays."""
    return MockRequest(
        content=body,
        mock_source="irrigationos-test",
        method="POST",
        headers={"x-signature": signature},
    )


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


def _signed_event(
    entry: MockConfigEntry,
    event_id: str,
    subtype: str,
    *,
    external_id: str | None = None,
) -> tuple[bytes, str]:
    payload = {
        "id": event_id,
        "type": "ZONE_STATUS",
        "subType": subtype,
        "externalId": external_id
        or (
            f"homeassistant.irrigationos:{entry.entry_id}:"
            f"{entry.data[CONF_WEBHOOK_AUTH]}"
        ),
        "deviceId": "native-controller-1",
        "zoneId": "native-zone-1",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(
        str(entry.data[CONF_API_KEY]).encode(), raw, hashlib.sha256
    ).hexdigest()
    return raw, signature


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


@pytest.mark.asyncio
async def test_webhook_url_prefers_cloudhook_then_standard_external_url(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=2)

    async def cloudhook(*_args: object) -> str:
        return "https://hooks.nabu.casa/example"

    monkeypatch.setattr(realtime_module, "_async_cloudhook_url", cloudhook)
    url, source = await realtime_module.async_resolve_webhook_url(
        hass, entry, "stable-id"
    )
    assert url == "https://hooks.nabu.casa/example"
    assert source == "cloudhook"

    async def no_cloudhook(*_args: object) -> None:
        return None

    monkeypatch.setattr(realtime_module, "_async_cloudhook_url", no_cloudhook)
    hass.config.external_url = "https://ha.example.com"
    url, source = await realtime_module.async_resolve_webhook_url(
        hass, entry, "stable-id"
    )
    assert url == "https://ha.example.com/api/webhook/stable-id"
    assert source == "standard"


@pytest.mark.asyncio
async def test_signed_push_via_mock_request_deduplication_reload_and_redaction(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def standard_url(*_args: object) -> tuple[str, str]:
        return "https://ha.example.com/api/webhook/stable", "standard"

    monkeypatch.setattr(
        realtime_module, "async_resolve_webhook_url", standard_url
    )
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

    assert entry.runtime_data.realtime.enabled
    assert adapter.reconcile_calls == 1
    stable_webhook_id = entry.data[CONF_WEBHOOK_ID]
    manager = entry.runtime_data.realtime

    start_raw, start_signature = _signed_event(entry, "event-start", "ZONE_STARTED")
    start_request = _mock_webhook_request(start_raw, start_signature)
    assert not hasattr(start_request, "content_length")
    response = await manager._async_handle_webhook(
        hass, stable_webhook_id, start_request
    )
    assert response.status == 204
    assert entry.runtime_data.realtime.accepted_event_count == 1
    assert adapter.snapshot_requests == 2

    response = await manager._async_handle_webhook(
        hass,
        stable_webhook_id,
        _mock_webhook_request(start_raw, start_signature),
    )
    assert response.status == 204
    assert entry.runtime_data.realtime.duplicate_event_count == 1
    assert adapter.snapshot_requests == 2

    wrong_auth_raw, wrong_auth_signature = _signed_event(
        entry,
        "event-wrong-auth",
        "ZONE_STOPPED",
        external_id="homeassistant.irrigationos:another-entry:wrong",
    )
    response = await manager._async_handle_webhook(
        hass,
        stable_webhook_id,
        _mock_webhook_request(wrong_auth_raw, wrong_auth_signature),
    )
    assert response.status == 403

    response = await manager._async_handle_webhook(
        hass,
        stable_webhook_id,
        _mock_webhook_request(start_raw, "invalid-signature"),
    )
    assert response.status == 403
    assert entry.runtime_data.realtime.rejected_event_count == 2

    stop_raw, stop_signature = _signed_event(entry, "event-stop", "ZONE_STOPPED")
    response = await manager._async_handle_webhook(
        hass,
        stable_webhook_id,
        _mock_webhook_request(stop_raw, stop_signature),
    )
    assert response.status == 204
    assert entry.runtime_data.realtime.accepted_event_count == 2
    assert adapter.snapshot_requests == 3

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    diagnostic_text = repr(diagnostics)
    assert entry.data[CONF_WEBHOOK_AUTH] not in diagnostic_text
    assert entry.data[CONF_WEBHOOK_ID] not in diagnostic_text
    assert "https://ha.example.com/api/webhook/stable" not in diagnostic_text
    realtime = diagnostics["coordinator"]["realtime"]
    assert realtime["url_source"] == "standard"
    assert realtime["fallback_polling"]["interval_minutes"] == 5

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data[CONF_WEBHOOK_ID] == stable_webhook_id
    assert adapter.cleanup_calls == 1
    assert adapter.reconcile_calls == 2
    assert len(adapter.active_external_ids) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert adapter.cleanup_calls == 2
    assert not adapter.active_external_ids


@pytest.mark.asyncio
async def test_no_external_url_keeps_polling_operational(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_external_url(*_args: object) -> tuple[None, str]:
        return None, "none"

    monkeypatch.setattr(
        realtime_module, "async_resolve_webhook_url", no_external_url
    )
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not entry.runtime_data.realtime.enabled
    assert entry.runtime_data.realtime.url_source == "none"
    assert entry.runtime_data.update_interval == timedelta(minutes=5)
    assert adapter.snapshot_requests == 1

    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success
    assert adapter.snapshot_requests == 2


@pytest.mark.asyncio
async def test_polling_reconciles_new_and_removed_controller_webhooks(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def standard_url(*_args: object) -> tuple[str, str]:
        return "https://ha.example.com/api/webhook/stable", "standard"

    monkeypatch.setattr(
        realtime_module, "async_resolve_webhook_url", standard_url
    )
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert adapter.reconciled_controller_ids[-1] == ("native-controller-1",)

    original = adapter.snapshot.controllers[0]
    discovered = replace(
        original,
        controller_id="controller_discovered",
        binding=VendorBinding("rachio", "native-controller-2"),
        name="New Controller",
        areas=(),
        capacity=0,
    )
    adapter.snapshot = replace(
        adapter.snapshot, controllers=(original, discovered)
    )
    await entry.runtime_data.async_refresh()
    assert adapter.reconciled_controller_ids[-1] == (
        "native-controller-1",
        "native-controller-2",
    )

    adapter.snapshot = replace(adapter.snapshot, controllers=(original,))
    await entry.runtime_data.async_refresh()
    assert adapter.cleaned_controller_ids[-1] == ("native-controller-2",)
    assert adapter.reconciled_controller_ids[-1] == ("native-controller-1",)


@pytest.mark.asyncio
async def test_remote_registration_failure_keeps_fallback_polling_active(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def standard_url(*_args: object) -> tuple[str, str]:
        return "https://ha.example.com/api/webhook/stable", "standard"

    monkeypatch.setattr(
        realtime_module, "async_resolve_webhook_url", standard_url
    )
    adapter = MutableAdapter(_snapshot())
    adapter.registration_health = RealtimeRegistrationHealth(
        False,
        0,
        1,
        "event type discovery failed",
        "http_status_failure",
        503,
    )
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    realtime = entry.runtime_data.realtime
    assert not realtime.enabled
    assert realtime.remote_health.error_category == "http_status_failure"
    assert realtime.remote_health.http_status == 503
    assert realtime.diagnostics()["fallback_polling"] == {
        "enabled": True,
        "interval_minutes": 5,
        "last_update_success": True,
    }
    assert entry.runtime_data.update_interval == timedelta(minutes=5)
