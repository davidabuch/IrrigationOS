"""Home Assistant runtime smoke tests for IrrigationOS v0.4.2."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util.aiohttp import MockRequest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigationos import (
    SUPERVISED_OPERATION_SERVICE_SCHEMA,
    async_migrate_entry,
)
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
    EVENT_HEALTH_RECOVERED,
    EVENT_HEALTH_UNHEALTHY,
    MODE_OBSERVATION,
)
from custom_components.irrigationos.controllers import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerIdentityRegistry,
    ControllerProviderError,
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
from custom_components.irrigationos.first_live_delivery.acceptance import (
    FirstLiveAcceptanceManager,
    build_acceptance_record,
)
from custom_components.irrigationos.health import IrrigationOSHealthState
from custom_components.irrigationos.production_readiness import (
    ProductionReadinessInputs,
    ProductionTarget,
)
from custom_components.irrigationos.quantitative_water_balance import (
    OpeningBalanceState,
    WaterBalanceLedgerEvent,
    WaterBalanceLedgerEventKind,
    WaterBalanceTargetState,
    WaterQuantity,
)
from custom_components.irrigationos.quantitative_water_balance.manager import (
    WATER_BALANCE_LEDGER_STORE_VERSION,
    WaterBalanceLedgerManager,
)
from custom_components.irrigationos.supervised_operation import (
    SupervisedOperationResult,
    SupervisedOperationStatus,
)
from custom_components.irrigationos.unattended_canary import (
    UNATTENDED_CANARY_CONFIRMATION,
    build_canary_acceptance_record,
)


def _area(
    controller_id: str,
    slot: int,
    *,
    configured: bool,
    state: IrrigationAreaState | None = None,
) -> IrrigationArea:
    return IrrigationArea(
        area_id=ControllerIdentityRegistry.area_id_for(controller_id, slot),
        controller_id=controller_id,
        slot_number=slot,
        name=f"Zone {slot}",
        enabled=configured,
        configured=configured,
        state=state or (
            IrrigationAreaState.IDLE if configured else IrrigationAreaState.UNUSED
        ),
        binding=VendorBinding("rachio", f"native-zone-{slot}") if configured else None,
        vendor_name="Orchard" if configured else None,
    )


def _snapshot(
    controller_id: str = "controller_test",
    *,
    slots: int = 2,
    include_controller: bool = True,
    watering_slots: tuple[int, ...] = (),
    observed_at: datetime | None = None,
    availability: ControllerAvailability = ControllerAvailability.ONLINE,
    watering_quality: ObservationQuality = ObservationQuality.CONFIRMED,
) -> ControllerRegistrySnapshot:
    now = observed_at or datetime.now(UTC)
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
        _area(
            controller_id,
            slot,
            configured=slot == 1,
            state=(
                IrrigationAreaState.WATERING
                if slot in watering_slots
                else None
            ),
        )
        for slot in range(1, slots + 1)
    )
    controller = IrrigationController(
        controller_id=controller_id,
        binding=VendorBinding("rachio", "native-controller-1"),
        name="Back Yard",
        availability=availability,
        enabled=True,
        model="GENERATION3_8ZONE",
        serial_number="serial-secret",
        firmware_version="1.0",
        latitude=1.0,
        longitude=2.0,
        capacity=slots,
        watering_observation_quality=watering_quality,
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


def _production_snapshot() -> ControllerRegistrySnapshot:
    snapshot = _snapshot(slots=16)
    controller = snapshot.controllers[0]
    configured_slots = {1, 2, 4, 5}
    areas = tuple(
        _area(
            controller.controller_id,
            slot,
            configured=slot in configured_slots,
        )
        for slot in range(1, 17)
    )
    return replace(
        snapshot,
        controllers=(replace(controller, areas=areas),),
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


def _supervised_acceptance_record(status: str) -> Any:
    now = datetime.now(UTC)
    return build_acceptance_record(
        attempt_id=f"supervised_operation_{status}",
        controller_slot=1,
        area_slot=1,
        requested_runtime_seconds=30,
        observed_watering_at=now,
        observed_idle_at=(
            None if status == "indeterminate" else now + timedelta(seconds=30)
        ),
        refresh_error_count=1,
        concurrent_watering_observed=status == "fail",
        terminal_detail_code=f"supervised_operation_{status}",
    )


def _canary_acceptance_record() -> Any:
    now = datetime.now(UTC)
    return build_canary_acceptance_record(
        canary_id="unattended_canary_test",
        approval_id="unattended_canary_approval_test",
        controller_slot=1,
        area_slot=1,
        requested_runtime_seconds=30,
        observed_watering_at=now,
        observed_idle_at=now + timedelta(seconds=30),
        refresh_error_count=0,
        concurrent_watering_observed=False,
        safety_preemption_observed=False,
        terminal_detail_code="canary_accepted",
    )


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


def test_supervised_service_accepts_three_hours_but_not_more() -> None:
    common = {
        "config_entry_id": "entry",
        "controller_slot": 1,
        "area_slot": 1,
        "confirmation": "RUN SUPERVISED OPERATIONAL WATERING",
    }
    assert SUPERVISED_OPERATION_SERVICE_SCHEMA(
        {**common, "runtime_seconds": 10_800}
    )["runtime_seconds"] == 10_800
    with pytest.raises(vol.Invalid):
        SUPERVISED_OPERATION_SERVICE_SCHEMA(
            {**common, "runtime_seconds": 10_801}
        )


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
    assert entry.version == 3
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
    assert "irrigationos_current_watering_session" in unique_ids
    assert "irrigationos_last_completed_watering_session" in unique_ids
    assert "irrigationos_watering_sessions_today" in unique_ids
    assert "controller_test_status" in unique_ids
    assert "controller_test:slot:1_observation" in unique_ids
    assert "controller_test:slot:2_observation" in unique_ids
    for stage in (
        "observations",
        "knowledge",
        "water_requirement",
        "stress",
        "health",
        "recommendations",
        "planning",
        "scheduling",
        "execution",
        "runtime_monitoring",
    ):
        assert f"irrigationos_pipeline_stage_{stage}" in unique_ids
    assert "controller_test:slot:1_pipeline_output" in unique_ids
    assert "controller_test:slot:2_pipeline_output" in unique_ids
    unused = next(
        item for item in entries if item.unique_id == "controller_test:slot:2_observation"
    )
    assert unused.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    unused_pipeline = next(
        item
        for item in entries
        if item.unique_id == "controller_test:slot:2_pipeline_output"
    )
    assert unused_pipeline.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    adapter.snapshot = _snapshot(slots=3)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert "controller_test:slot:3_observation" in {item.unique_id for item in entries}
    assert "controller_test:slot:3_pipeline_output" in {
        item.unique_id for item in entries
    }

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
    pipeline_summary = diagnostics["coordinator"]["pipeline_summary"]
    assert pipeline_summary is not None
    assert pipeline_summary["algorithm_version"] == "1.0.10"
    assert "runtime_monitoring" in pipeline_summary["stages"]
    assert pipeline_summary["output_counts"]["runtime_monitoring"] >= 1


@pytest.mark.asyncio
async def test_supervised_operation_state_visibility_and_restart_restore(
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
    sensor_id = "sensor.irrigationos_supervised_operation_acceptance"
    binary_id = "binary_sensor.irrigationos_supervised_operation_in_progress"
    acceptance_state = hass.states.get(sensor_id)
    progress_state = hass.states.get(binary_id)
    assert acceptance_state is not None
    assert acceptance_state.state == "not_available"
    assert progress_state is not None
    assert progress_state.state == "off"

    for expected in ("fail", "indeterminate", "pass"):
        record = _supervised_acceptance_record(expected)
        assert record.status.value == expected
        assert await entry.runtime_data.supervised_operation_acceptance.async_record(
            record
        )
        entry.runtime_data.async_update_listeners()
        await hass.async_block_till_done()
        acceptance_state = hass.states.get(sensor_id)
        assert acceptance_state is not None
        assert acceptance_state.state == expected
        assert acceptance_state.attributes["attempt_id"] == record.attempt_id
        assert acceptance_state.attributes["controller_slot"] == 1
        assert acceptance_state.attributes["area_slot"] == 1
        assert acceptance_state.attributes["requested_runtime_seconds"] == 30
        assert acceptance_state.attributes["criteria_total_count"] == 10
        assert acceptance_state.attributes["schema_version"] == 1
        assert acceptance_state.attributes["last_persistence_error"] is None

    entry.runtime_data.supervised_operation.mark_dispatched(
        "supervised_operation_active",
        controller_slot=1,
        area_slot=1,
        runtime_seconds=30,
    )
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    progress_state = hass.states.get(binary_id)
    assert progress_state is not None
    assert progress_state.state == "on"
    assert progress_state.attributes["active_operation_id"] == "supervised_operation_active"
    assert progress_state.attributes["controller_slot"] == 1
    assert progress_state.attributes["area_slot"] == 1
    assert progress_state.attributes["requested_runtime_seconds"] == 30

    entry.runtime_data.supervised_operation.mark_complete("supervised_operation_active")
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(binary_id).state == "off"

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    supervised_diagnostics = diagnostics["coordinator"][
        "supervised_operation_acceptance"
    ]
    assert supervised_diagnostics["status"] == "pass"
    assert "native-zone-1" not in repr(supervised_diagnostics)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == "pass"
    assert hass.states.get(binary_id).state == "off"
    assert entry.runtime_data.supervised_operation.in_progress is False


@pytest.mark.asyncio
async def test_validated_targets_backfill_multiple_restore_and_revoke(
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
    prior_acceptance = FirstLiveAcceptanceManager(hass, entry.entry_id)
    zone_2 = build_acceptance_record(
        attempt_id="first_live_zone_2",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=datetime.now(UTC),
        observed_idle_at=datetime.now(UTC) + timedelta(seconds=30),
        refresh_error_count=0,
        concurrent_watering_observed=False,
        terminal_detail_code="first_live_trial_accepted",
    )
    assert await prior_acceptance.async_record(zone_2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    sensor_id = "sensor.irrigationos_validated_targets"
    state = hass.states.get(sensor_id)
    assert state is not None
    assert state.state == "1"
    assert state.attributes["validated_targets"][0]["controller_slot"] == 1
    assert state.attributes["validated_targets"][0]["area_slot"] == 2

    zone_1 = build_acceptance_record(
        attempt_id="first_live_zone_1",
        controller_slot=1,
        area_slot=1,
        requested_runtime_seconds=30,
        observed_watering_at=datetime.now(UTC),
        observed_idle_at=datetime.now(UTC) + timedelta(seconds=30),
        refresh_error_count=0,
        concurrent_watering_observed=False,
        terminal_detail_code="first_live_trial_accepted",
    )
    assert await entry.runtime_data.validated_targets.async_register(zone_1)
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get(sensor_id)
    assert state is not None
    assert state.state == "2"
    assert [
        (item["controller_slot"], item["area_slot"])
        for item in state.attributes["validated_targets"]
    ] == [(1, 1), (1, 2)]
    assert "native-zone" not in repr(state.attributes)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == "2"
    assert entry.runtime_data.supervised_operation.in_progress is False
    assert entry.runtime_data.live_commissioning.summary.operator_approval_present is False

    assert await entry.runtime_data.validated_targets.async_revoke(1, 1)
    assert not entry.runtime_data.validated_targets.contains(1, 1)
    assert entry.runtime_data.validated_targets.contains(1, 2)


@pytest.mark.asyncio
async def test_production_readiness_entities_use_only_configured_targets_and_restart_safe(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_production_snapshot())
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

    coordinator = entry.runtime_data
    coordinator.update_production_readiness()
    summary = coordinator.production_readiness.summary
    assert [target.area_slot for target in summary.production_targets] == [1, 2, 4, 5]
    assert summary.state.value == "not_ready"
    recommendation = hass.states.get("sensor.irrigationos_production_recommendations")
    assert recommendation is not None
    assert recommendation.state == "insufficient_evidence"
    assert recommendation.attributes["execution_authorized"] is False
    assert len(recommendation.attributes["recommendations"]) == 4
    aggregate_balance = hass.states.get(
        "sensor.irrigationos_quantitative_water_balances"
    )
    assert aggregate_balance is not None
    assert aggregate_balance.state == "insufficient_evidence"
    assert aggregate_balance.attributes["production_target_count"] == 4
    assert len(aggregate_balance.attributes["targets"]) == 4
    assert "balances" not in aggregate_balance.attributes
    assert "evidence" not in aggregate_balance.attributes
    aggregate_payload = json.dumps(dict(aggregate_balance.attributes), default=str)
    assert len(aggregate_payload.encode("utf-8")) < 8192
    for slot in (1, 2, 4, 5):
        area_recommendation = hass.states.get(
            f"sensor.zone_{slot}_production_recommendation"
        )
        assert area_recommendation is not None
        assert area_recommendation.state == "insufficient_evidence"
        assert area_recommendation.attributes["irrigation_depth"] is None
        assert area_recommendation.attributes["estimated_runtime_seconds"] is None
        assert area_recommendation.attributes["scheduling_window"] is None
        assert area_recommendation.attributes["execution_authorized"] is False
        assert "native-zone" not in repr(area_recommendation.attributes)
        area_balance = hass.states.get(f"sensor.zone_{slot}_water_balance")
        assert area_balance is not None
        assert area_balance.state == "insufficient_evidence"
        assert area_balance.attributes["actual_net_deficit_mm"] is None
        assert area_balance.attributes["execution_authorized"] is False
        assert "native-zone" not in repr(area_balance.attributes)
    assert hass.states.get("sensor.zone_3_water_balance") is None
    assert hass.states.get("sensor.zone_6_water_balance") is None

    targets = tuple(ProductionTarget(1, slot) for slot in (1, 2, 4, 5))
    coordinator.production_readiness.consider(
        ProductionReadinessInputs(
            evaluated_at=datetime.now(UTC),
            health_state="HEALTHY",
            observation_age_seconds=1,
            cloud_connection_healthy=True,
            realtime_observation_healthy=True,
            ownership_confirmed=True,
            boundary_review_acknowledged=True,
            topology_matches=True,
            ownership_persistence_healthy=True,
            production_targets=targets,
            validated_targets=targets,
            validated_target_persistence_healthy=True,
            first_live_persistence_healthy=True,
            supervised_operation_persistence_healthy=True,
            aggregate_persistence_healthy=True,
            operational_log_healthy=True,
            active_external_watering_count=0,
            supervised_operation_in_progress=False,
            safety_prerequisites_met=True,
        )
    )
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    sensor = hass.states.get("sensor.irrigationos_production_readiness")
    binary = hass.states.get("binary_sensor.irrigationos_production_ready")
    assert sensor is not None
    assert sensor.state == "ready_for_supervised_production"
    assert sensor.attributes["production_target_count"] == 4
    assert sensor.attributes["validated_production_target_count"] == 4
    assert [item["area_slot"] for item in sensor.attributes["production_targets"]] == [
        1,
        2,
        4,
        5,
    ]
    assert "native-zone" not in repr(sensor.attributes)
    assert binary is not None
    assert binary.state == "on"

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    readiness_diagnostics = diagnostics["coordinator"]["production_readiness"]
    assert "native-zone" not in repr(readiness_diagnostics)
    assert readiness_diagnostics["live_control_authorized"] is False

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.irrigationos_production_readiness").state == (
        "not_ready"
    )
    assert hass.states.get("binary_sensor.irrigationos_production_ready").state == "off"
    assert entry.runtime_data.supervised_operation.in_progress is False


@pytest.mark.asyncio
async def test_manual_zone_platforms_use_non_contiguous_stable_targets(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _production_snapshot()
    controller = snapshot.controllers[0]
    snapshot = replace(
        snapshot,
        controllers=(
            replace(
                controller,
                areas=tuple(
                    replace(area, vendor_name=None)
                    if area.slot_number == 4
                    else area
                    for area in controller.areas
                ),
            ),
        ),
    )
    adapter = MutableAdapter(snapshot)
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
    entries = {
        item.unique_id: item
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    for slot in (1, 2, 4, 5):
        area_id = f"controller_test:slot:{slot}"
        valve = hass.states.get(f"valve.zone_{slot}_manual_watering")
        duration = hass.states.get(f"number.zone_{slot}_manual_watering_duration")
        assert valve is not None
        assert valve.state == "closed"
        assert duration is not None
        assert duration.state == "15.0"
        assert duration.attributes["min"] == 1
        assert duration.attributes["max"] == 180
        assert duration.attributes["step"] == 1
        assert entries[f"{area_id}_manual_watering_valve"].entity_id == valve.entity_id
        assert entries[f"{area_id}_manual_watering_duration"].entity_id == duration.entity_id
    assert hass.states.get("valve.zone_3_manual_watering") is None
    assert hass.states.get("number.zone_3_manual_watering_duration") is None
    assert hass.states.get("valve.zone_1_manual_watering").attributes[
        "friendly_name"
    ] == "Zone 1 manual watering"
    assert hass.states.get("valve.zone_2_manual_watering").attributes[
        "friendly_name"
    ] == "Orchard manual watering"
    assert hass.states.get("valve.zone_4_manual_watering").attributes[
        "friendly_name"
    ] == "Zone 4 manual watering"

    current = adapter.snapshot.controllers[0]
    adapter.snapshot = replace(
        adapter.snapshot,
        controllers=(
            replace(
                current,
                areas=tuple(
                    replace(area, state=IrrigationAreaState.WATERING)
                    if area.slot_number == 1
                    else area
                    for area in current.areas
                ),
            ),
        ),
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("valve.zone_1_manual_watering").state == "open"

    stale_at = datetime.now(UTC) - timedelta(hours=1)
    adapter.snapshot = replace(
        adapter.snapshot,
        observation=replace(
            adapter.snapshot.observation,
            observed_at=stale_at,
            fresh_until=stale_at + timedelta(minutes=10),
        ),
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("valve.zone_1_manual_watering").state == STATE_UNAVAILABLE

    valve_entry = entries["controller_test:slot:1_manual_watering_valve"]
    original_unique_id = valve_entry.unique_id
    profile = entry.runtime_data.landscape_intelligence.get_zone_by_slots(1, 1)
    assert profile is not None
    assert await entry.runtime_data.landscape_intelligence.async_update_zone(
        replace(profile, display_name="Front Entry Planters")
    )
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    renamed = hass.states.get("valve.zone_1_manual_watering")
    assert renamed is not None
    assert renamed.attributes["friendly_name"] == "Front Entry Planters manual watering"
    renamed_duration = hass.states.get("number.zone_1_manual_watering_duration")
    assert renamed_duration is not None
    assert renamed_duration.attributes["friendly_name"] == (
        "Front Entry Planters manual watering duration"
    )
    assert entries["controller_test:slot:1_manual_watering_valve"].unique_id == original_unique_id


@pytest.mark.asyncio
async def test_manual_duration_drives_valve_runtime_and_restores(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_production_snapshot())
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

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.zone_1_manual_watering_duration",
            "value": 15,
        },
        blocking=True,
    )
    calls: list[int] = []

    async def _start(
        coordinator: object,
        *,
        controller_slot: int,
        area_slot: int,
        runtime_seconds: int,
    ) -> SupervisedOperationResult:
        del coordinator
        assert (controller_slot, area_slot) == (1, 1)
        calls.append(runtime_seconds)
        return SupervisedOperationResult(
            status=SupervisedOperationStatus.START_DISPATCHED,
            blocker_codes=(),
            operation_id="manual-test",
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
        )

    monkeypatch.setattr(
        "custom_components.irrigationos.valve.async_run_manual_operation", _start
    )
    await hass.services.async_call(
        "valve",
        "open_valve",
        {"entity_id": "valve.zone_1_manual_watering"},
        blocking=True,
    )
    assert calls == [900]
    aggregate = hass.states.get("sensor.irrigationos_quantitative_water_balances")
    assert aggregate is not None
    assert aggregate.attributes["execution_authorized"] is False
    assert entry.runtime_data.execution_authorization.summary.live_control_authorized is False

    stop_calls: list[tuple[int, int]] = []

    async def _stop(
        coordinator: object, *, controller_slot: int, area_slot: int
    ) -> SupervisedOperationResult:
        del coordinator
        stop_calls.append((controller_slot, area_slot))
        return SupervisedOperationResult(
            status=SupervisedOperationStatus.STOP_DISPATCHED,
            blocker_codes=(),
            operation_id="manual-test",
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=900,
        )

    monkeypatch.setattr(
        "custom_components.irrigationos.valve.async_stop_manual_operation", _stop
    )
    await hass.services.async_call(
        "valve",
        "close_valve",
        {"entity_id": "valve.zone_1_manual_watering"},
        blocking=True,
    )
    assert stop_calls == [(1, 1)]

    async def _unconfirmed_stop(
        coordinator: object, *, controller_slot: int, area_slot: int
    ) -> SupervisedOperationResult:
        del coordinator
        return SupervisedOperationResult(
            status=SupervisedOperationStatus.STOP_UNCONFIRMED,
            blocker_codes=("stop_outcome_not_observed",),
            operation_id="manual-test",
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=900,
        )

    monkeypatch.setattr(
        "custom_components.irrigationos.valve.async_stop_manual_operation",
        _unconfirmed_stop,
    )
    with pytest.raises(HomeAssistantError, match="stop_outcome_not_observed"):
        await hass.services.async_call(
            "valve",
            "close_valve",
            {"entity_id": "valve.zone_1_manual_watering"},
            blocking=True,
        )

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.zone_1_manual_watering_duration",
            "value": 37,
        },
        blocking=True,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    restored = hass.states.get("number.zone_1_manual_watering_duration")
    assert restored is not None
    assert restored.state == "37.0"


@pytest.mark.asyncio
async def test_water_balance_ledger_persists_and_corruption_fails_closed(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_id = "water_balance_test"
    manager = WaterBalanceLedgerManager(hass, entry_id)
    await manager.async_initialize()
    now = datetime.now(UTC)
    event = WaterBalanceLedgerEvent(
        event_id="water_balance.deferral.test",
        kind=WaterBalanceLedgerEventKind.FORECAST_DEFERRAL,
        target=ProductionTarget(1, 4),
        forecast_id="weather.forecast.test",
        recorded_at=now,
        accounted_through=now,
        forecast_window_start=now + timedelta(hours=1),
        forecast_window_end=now + timedelta(hours=12),
        deferred_deficit_mm=WaterQuantity.millimeters(5),
        carry_forward_deficit_mm=WaterQuantity.millimeters(5),
    )
    assert await manager.async_append(event)
    assert await manager.async_append(event)
    restored = WaterBalanceLedgerManager(hass, entry_id)
    await restored.async_initialize()
    assert restored.events == (event,)
    assert restored.diagnostics()["execution_authorized"] is False

    target_state = WaterBalanceTargetState(
        target=ProductionTarget(1, 4),
        recorded_at=now + timedelta(days=1),
        window_start=now,
        accounted_through=now + timedelta(days=1),
        state=OpeningBalanceState.DURABLE_CARRY_FORWARD,
        deficit_mm=WaterQuantity.millimeters(8),
        reason_code="durable_water_balance_carry_forward",
    )
    assert await restored.async_commit(target_states=(target_state,))
    round_trip = WaterBalanceLedgerManager(hass, entry_id)
    await round_trip.async_initialize()
    assert round_trip.events == (event,)
    assert round_trip.target_states == (target_state,)

    legacy_id = "water_balance_legacy_v1064"
    legacy_store = Store[dict[str, Any]](
        hass,
        WATER_BALANCE_LEDGER_STORE_VERSION,
        f"irrigationos.{legacy_id}.water_balance_ledger",
    )
    legacy_event = event.to_dict()
    legacy_event["schema_version"] = 1
    await legacy_store.async_save({"events": [legacy_event]})
    migrated = WaterBalanceLedgerManager(hass, legacy_id)
    await migrated.async_initialize()
    assert migrated.healthy is True
    assert migrated.events[0].event_id == event.event_id
    assert migrated.events[0].carry_forward_deficit_mm == event.carry_forward_deficit_mm
    assert migrated.events[0].schema_version == 2
    assert migrated.target_states == ()
    assert all(item.kind.value.startswith("forecast_") for item in migrated.events)

    invalidated = WaterBalanceTargetState(
        target=target_state.target,
        state=OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION,
        window_start=target_state.accounted_through,
        accounted_through=target_state.accounted_through + timedelta(hours=1),
        recorded_at=target_state.accounted_through + timedelta(hours=1),
        invalidated_session_ids=("watering.session.native",),
        reason_code="water_balance_invalidated_by_unquantified_irrigation",
    )
    assert await round_trip.async_commit(target_states=(invalidated,))
    invalidated_restart = WaterBalanceLedgerManager(hass, entry_id)
    await invalidated_restart.async_initialize()
    assert invalidated_restart.target_states == (invalidated,)
    assert invalidated_restart.target_states[0].deficit_mm is None
    assert invalidated_restart.events == (event,)

    failing = WaterBalanceLedgerManager(hass, "water_balance_save_failure")
    await failing.async_initialize()

    async def _fail_save(_: object) -> None:
        raise OSError("simulated Store failure")

    monkeypatch.setattr(failing._store, "async_save", _fail_save)
    assert await failing.async_commit(target_states=(target_state,)) is False
    assert failing.events == ()
    assert failing.target_states == ()
    assert failing.healthy is False
    assert failing.last_error == "water_balance_ledger_save_failed"

    corrupt_id = "water_balance_corrupt"
    store = Store[dict[str, Any]](
        hass,
        WATER_BALANCE_LEDGER_STORE_VERSION,
        f"irrigationos.{corrupt_id}.water_balance_ledger",
    )
    await store.async_save({"events": [{"invalid": True}]})
    corrupted = WaterBalanceLedgerManager(hass, corrupt_id)
    await corrupted.async_initialize()
    assert corrupted.healthy is False
    assert corrupted.events == ()
    assert corrupted.last_error == "water_balance_ledger_invalid"


@pytest.mark.asyncio
async def test_water_balance_current_state_is_bounded_atomic_and_refresh_idempotent(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = WaterBalanceLedgerManager(hass, "water_balance_bounded")
    await manager.async_initialize()
    now = datetime.now(UTC)
    states = tuple(
        WaterBalanceTargetState(
            target=ProductionTarget(1, slot),
            state=OpeningBalanceState.DURABLE_CARRY_FORWARD,
            window_start=now,
            accounted_through=now + timedelta(hours=1),
            recorded_at=now + timedelta(hours=1),
            deficit_mm=WaterQuantity.millimeters(float(slot)),
            reason_code="durable_water_balance_carry_forward",
        )
        for slot in (1, 2, 4, 5)
    )
    writes = 0
    original_save = manager._store.async_save

    async def _counted_save(payload: dict[str, Any]) -> None:
        nonlocal writes
        writes += 1
        await original_save(payload)

    monkeypatch.setattr(manager._store, "async_save", _counted_save)
    assert await manager.async_commit(target_states=states)
    assert writes == 1
    assert len(manager.target_states) == 4

    for _ in range(365 * 24 * 12):
        assert await manager.async_commit(target_states=states)

    assert writes == 1
    assert len(manager.target_states) == 4

    advanced = tuple(
        WaterBalanceTargetState(
            target=state.target,
            state=OpeningBalanceState.DURABLE_CARRY_FORWARD,
            window_start=state.accounted_through,
            accounted_through=state.accounted_through + timedelta(hours=1),
            recorded_at=state.accounted_through + timedelta(hours=1),
            deficit_mm=state.deficit_mm,
            reason_code="durable_water_balance_carry_forward",
        )
        for state in states
    )
    assert await manager.async_commit(target_states=advanced)
    assert writes == 2
    assert await manager.async_commit(target_states=advanced)
    assert writes == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("relationship", ["gap", "overlap", "replay"])
async def test_water_balance_target_state_rejects_nonadjacent_boundaries(
    hass: HomeAssistant,
    relationship: str,
) -> None:
    manager = WaterBalanceLedgerManager(hass, f"water_balance_{relationship}")
    await manager.async_initialize()
    now = datetime.now(UTC)
    initial = WaterBalanceTargetState(
        target=ProductionTarget(1, 1),
        state=OpeningBalanceState.DURABLE_CARRY_FORWARD,
        window_start=now,
        accounted_through=now + timedelta(hours=1),
        recorded_at=now + timedelta(hours=1),
        deficit_mm=WaterQuantity.millimeters(2),
        reason_code="durable_water_balance_carry_forward",
    )
    assert await manager.async_commit(target_states=(initial,))
    starts = {
        "gap": now + timedelta(hours=2),
        "overlap": now + timedelta(minutes=30),
        "replay": now - timedelta(hours=1),
    }
    ends = {
        "gap": now + timedelta(hours=3),
        "overlap": now + timedelta(hours=2),
        "replay": now + timedelta(minutes=30),
    }
    candidate = WaterBalanceTargetState(
        target=initial.target,
        state=OpeningBalanceState.DURABLE_CARRY_FORWARD,
        window_start=starts[relationship],
        accounted_through=ends[relationship],
        recorded_at=now + timedelta(hours=3),
        deficit_mm=WaterQuantity.millimeters(3),
        reason_code="durable_water_balance_carry_forward",
    )

    assert await manager.async_commit(target_states=(candidate,)) is False
    assert manager.target_states == (initial,)


@pytest.mark.asyncio
async def test_unattended_canary_approval_acceptance_visibility_and_restart_safety(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = MutableAdapter(_production_snapshot())
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

    approval_sensor = "sensor.irrigationos_unattended_canary_approval"
    acceptance_sensor = "sensor.irrigationos_unattended_canary_acceptance"
    progress_binary = "binary_sensor.irrigationos_unattended_canary_in_progress"
    assert hass.states.get(approval_sensor).state == "none"
    assert hass.states.get(acceptance_sensor).state == "not_available"
    assert hass.states.get(progress_binary).state == "off"
    assert hass.services.has_service(DOMAIN, "authorize_unattended_canary")
    assert hass.services.has_service(DOMAIN, "run_unattended_canary")

    validation_record = build_acceptance_record(
        attempt_id="first_live_zone_1",
        controller_slot=1,
        area_slot=1,
        requested_runtime_seconds=30,
        observed_watering_at=datetime.now(UTC),
        observed_idle_at=datetime.now(UTC) + timedelta(seconds=30),
        refresh_error_count=0,
        concurrent_watering_observed=False,
        terminal_detail_code="first_live_trial_accepted",
    )
    assert await entry.runtime_data.validated_targets.async_register(validation_record)
    await hass.services.async_call(
        DOMAIN,
        "authorize_unattended_canary",
        {
            "config_entry_id": entry.entry_id,
            "controller_slot": 1,
            "area_slot": 1,
            "runtime_seconds": 30,
            "confirmation": UNATTENDED_CANARY_CONFIRMATION,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    approval_state = hass.states.get(approval_sensor)
    assert approval_state.state == "approved"
    assert approval_state.attributes["controller_slot"] == 1
    assert approval_state.attributes["area_slot"] == 1
    assert approval_state.attributes["runtime_seconds"] == 30
    assert approval_state.attributes["single_use"] is True
    assert approval_state.attributes["persists_across_restart"] is False
    assert "native-zone" not in repr(approval_state.attributes)

    acceptance_record = _canary_acceptance_record()
    assert await entry.runtime_data.unattended_canary_acceptance.async_record(
        acceptance_record
    )
    entry.runtime_data.unattended_canary.mark_dispatched(
        "unattended_canary_test",
        "unattended_canary_approval_test",
        controller_slot=1,
        area_slot=1,
        runtime_seconds=30,
    )
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(acceptance_sensor).state == "pass"
    assert hass.states.get(progress_binary).state == "on"
    assert "native-zone" not in repr(hass.states.get(acceptance_sensor).attributes)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    canary_diagnostics = diagnostics["coordinator"]["unattended_canary"]
    acceptance_diagnostics = diagnostics["coordinator"][
        "unattended_canary_acceptance"
    ]
    assert "native-zone" not in repr(canary_diagnostics)
    assert "native-zone" not in repr(acceptance_diagnostics)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(approval_sensor).state == "none"
    assert hass.states.get(acceptance_sensor).state == "pass"
    assert hass.states.get(progress_binary).state == "off"
    assert entry.runtime_data.unattended_canary.approval is None
    assert entry.runtime_data.unattended_canary.in_progress is False
    assert entry.runtime_data.production_readiness.summary.live_control_authorized is False


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
    assert entry.version == 3


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
async def test_watering_session_persists_across_restart_and_updates_entities(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An active canonical session survives unload and closes without duplication."""
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

    started_at = datetime.now(UTC)
    adapter.snapshot = _snapshot(watering_slots=(1,), observed_at=started_at)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    active = entry.runtime_data.observation_history.active_sessions
    assert len(active) == 1
    session_id = active[0].session_id
    assert active[0].incomplete is True
    current = hass.states.get("sensor.irrigationos_current_watering_session")
    assert current is not None
    assert current.state == "watering"
    assert current.attributes["active_session_count"] == 1
    assert "native-zone-1" not in repr(current.attributes)
    session_filename = (
        entry.runtime_data.observation_history.session_log.current_file
    )
    assert session_filename is not None
    session_log_text = (
        Path(hass.config.path("irrigationos_logs")) / session_filename
    ).read_text(encoding="utf-8")
    assert '"event_type":"session_started"' in session_log_text
    for secret in (
        "native-controller-1",
        "native-zone-1",
        "person-1",
        "top-secret-api-key",
        entry.data[CONF_WEBHOOK_ID],
        entry.data[CONF_WEBHOOK_AUTH],
        "serial-secret",
    ):
        assert secret not in session_log_text

    await entry.runtime_data.async_refresh()
    assert len(entry.runtime_data.observation_history.active_sessions) == 1
    assert entry.runtime_data.observation_history.active_sessions[0].session_id == session_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    restored = entry.runtime_data.observation_history.active_sessions
    assert len(restored) == 1
    assert restored[0].session_id == session_id
    assert restored[0].reconstructed_after_restart is True
    assert restored[0].incomplete is True

    stopped_at = started_at + timedelta(minutes=10)
    adapter.snapshot = _snapshot(observed_at=stopped_at)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.observation_history.active_sessions == ()
    completed = entry.runtime_data.observation_history.last_completed_session
    assert completed is not None
    assert completed.session_id == session_id
    assert completed.duration_seconds == 600
    assert completed.reconstructed_after_restart is True
    current = hass.states.get("sensor.irrigationos_current_watering_session")
    last = hass.states.get("sensor.irrigationos_last_completed_watering_session")
    today = hass.states.get("sensor.irrigationos_watering_sessions_today")
    assert current is not None and current.state == "idle"
    assert last is not None and last.state == "completed"
    assert last.attributes["session_id"] == session_id
    assert today is not None and int(today.state) >= 1
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    history = diagnostics["coordinator"]["operational_health"][
        "observation_history"
    ]
    assert history["active_session_count"] == 0
    assert history["last_completed_session"]["session_id"] == session_id
    assert "native-zone-1" not in repr(history)


@pytest.mark.asyncio
async def test_realtime_refresh_records_session_without_false_ownership(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deduplicated realtime refreshes discover state but never invent attribution."""
    async def standard_url(*_args: object) -> tuple[str, str]:
        return "https://ha.example.com/api/webhook/stable", "standard"

    monkeypatch.setattr(realtime_module, "async_resolve_webhook_url", standard_url)
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=3)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.realtime
    webhook_id = entry.data[CONF_WEBHOOK_ID]

    adapter.snapshot = _snapshot(watering_slots=(1,))
    raw, signature = _signed_event(entry, "session-start", "ZONE_STARTED")
    response = await manager._async_handle_webhook(
        hass, webhook_id, _mock_webhook_request(raw, signature)
    )
    assert response.status == 204
    active = entry.runtime_data.observation_history.active_sessions
    assert len(active) == 1
    assert active[0].observation_source.value == "realtime_refresh"
    assert active[0].attribution.value == "external_unknown"
    assert active[0].incomplete is False

    response = await manager._async_handle_webhook(
        hass, webhook_id, _mock_webhook_request(raw, signature)
    )
    assert response.status == 204
    assert len(entry.runtime_data.observation_history.active_sessions) == 1
    assert manager.duplicate_event_count == 1

    adapter.snapshot = _snapshot()
    stop_raw, stop_signature = _signed_event(entry, "session-stop", "ZONE_STOPPED")
    response = await manager._async_handle_webhook(
        hass, webhook_id, _mock_webhook_request(stop_raw, stop_signature)
    )
    assert response.status == 204
    completed = entry.runtime_data.observation_history.last_completed_session
    assert completed is not None
    assert completed.attribution.value == "external_unknown"
    assert completed.attribution.value not in {"provider_schedule", "manual", "irrigationos"}
    assert completed.incomplete is False


@pytest.mark.asyncio
async def test_offline_snapshot_marks_active_session_uncertain_without_closure(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HA lifecycle preserves an active session through controller unavailability."""
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=3)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    adapter.snapshot = _snapshot(watering_slots=(1,))
    await entry.runtime_data.async_refresh()
    session_id = entry.runtime_data.observation_history.active_sessions[0].session_id
    adapter.snapshot = _snapshot(availability=ControllerAvailability.OFFLINE)
    await entry.runtime_data.async_refresh()
    active = entry.runtime_data.observation_history.active_sessions
    assert len(active) == 1
    assert active[0].session_id == session_id
    assert active[0].incomplete is True
    assert active[0].observation_quality is ObservationQuality.PARTIAL

    adapter.snapshot = _snapshot()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.observation_history.active_sessions == ()
    assert entry.runtime_data.observation_history.last_completed_session is not None


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


def _pipeline_entity_registry_map(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> dict[str, str]:
    """Return stable pipeline registry IDs for lifecycle assertions."""
    registry = er.async_get(hass)
    return {
        item.unique_id: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.unique_id.startswith("irrigationos_pipeline_")
        or item.unique_id.endswith("_pipeline_output")
    }


@pytest.mark.asyncio
async def test_pipeline_entities_survive_unload_and_restart_without_duplicates(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cold restart keeps pipeline identities, options, and entity IDs stable."""
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    profile_key = "controller_test:slot:1"
    options = {
        CONF_AREA_PROFILES: {
            profile_key: {"display_name": "Persistent Orchard"}
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=_entry_data(),
        options=options,
        version=3,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    first_coordinator = entry.runtime_data
    first_map = _pipeline_entity_registry_map(hass, entry)
    assert first_map
    assert len(first_map) == len(set(first_map.values()))
    persisted_data = dict(entry.data)
    persisted_options = dict(entry.options)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    second_map = _pipeline_entity_registry_map(hass, entry)
    assert entry.runtime_data is not first_coordinator
    assert second_map == first_map
    assert len(second_map) == len(set(second_map.values()))
    assert dict(entry.data) == persisted_data
    assert dict(entry.options) == persisted_options
    registry = er.async_get(hass)
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.unique_id not in second_map or item.disabled_by is not None:
            continue
        assert hass.states.get(item.entity_id) is not None


@pytest.mark.asyncio
async def test_pipeline_entities_survive_config_entry_reload_with_same_ids(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config-entry reload replaces runtime state without duplicating entities."""
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
    before_runtime = entry.runtime_data
    before_map = _pipeline_entity_registry_map(hass, entry)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    after_map = _pipeline_entity_registry_map(hass, entry)
    assert entry.runtime_data is not before_runtime
    assert after_map == before_map
    registry_entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    unique_ids = [item.unique_id for item in registry_entries]
    assert len(unique_ids) == len(set(unique_ids))


@pytest.mark.asyncio
async def test_migrated_entry_starts_with_canonical_pipeline_entities(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A legacy entry can migrate and then start the completed pipeline cleanly."""
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
                "rachio:native-zone-1": {"display_name": "Migrated Orchard"}
            }
        },
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 3
    canonical_controller_id = entry.data[CONF_IDENTITY_REGISTRY]["controllers"][
        "rachio:native-controller-1"
    ]
    canonical_area_id = f"{canonical_controller_id}:slot:1"
    assert canonical_area_id in entry.options[CONF_AREA_PROFILES]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry_map = _pipeline_entity_registry_map(hass, entry)
    assert f"{canonical_area_id}_pipeline_output" in registry_map
    assert "irrigationos_pipeline_stage_runtime_monitoring" in registry_map
    assert entry.runtime_data.pipeline_evaluation is not None


@pytest.mark.asyncio
async def test_health_incident_latches_recovers_persists_and_resets(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health transitions are latched, persisted, logged, and non-actuating."""
    adapter = MutableAdapter(_snapshot())
    monkeypatch.setattr(DEFAULT_PROVIDER_FACTORY, "create", lambda *args: adapter)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IrrigationOS",
        data=_entry_data(),
        version=3,
    )
    entry.add_to_hass(hass)
    unhealthy_events: list[dict[str, Any]] = []
    recovery_events: list[dict[str, Any]] = []
    hass.bus.async_listen(
        EVENT_HEALTH_UNHEALTHY,
        lambda event: unhealthy_events.append(dict(event.data)),
    )
    hass.bus.async_listen(
        EVENT_HEALTH_RECOVERED,
        lambda event: recovery_events.append(dict(event.data)),
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    coordinator._started_at = datetime.now(UTC) - timedelta(minutes=20)
    coordinator._polling_healthy = True
    assert coordinator.realtime is not None
    coordinator.realtime.enabled = True
    coordinator.realtime.remote_health = RealtimeRegistrationHealth(
        healthy=True,
        registered_controllers=1,
        expected_controllers=1,
        error=None,
    )
    await coordinator.async_update_health("test_healthy")
    assert coordinator.health_assessment.state is IrrigationOSHealthState.HEALTHY
    assert hass.states.get("sensor.irrigationos_health").state == "HEALTHY"

    original_snapshot = adapter.async_get_snapshot

    async def _failed_snapshot(_account_id: str) -> ControllerRegistrySnapshot:
        raise ControllerProviderError("temporary provider failure")

    monkeypatch.setattr(adapter, "async_get_snapshot", _failed_snapshot)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.health_assessment.state is IrrigationOSHealthState.DEGRADED
    assert hass.states.get("sensor.irrigationos_health").state == "DEGRADED"
    assert hass.states.get("sensor.irrigationos_health").state != STATE_UNAVAILABLE
    monkeypatch.setattr(adapter, "async_get_snapshot", original_snapshot)

    coordinator.last_successful_refresh = datetime.now(UTC) - timedelta(minutes=13)
    coordinator._polling_healthy = False
    await coordinator.async_update_health("test_stale")
    await hass.async_block_till_done()
    assert coordinator.health_assessment.state is IrrigationOSHealthState.UNHEALTHY
    assert hass.states.get("binary_sensor.irrigationos_health_incident").state == "on"
    assert len(unhealthy_events) == 1

    coordinator.last_successful_refresh = datetime.now(UTC)
    coordinator._polling_healthy = True
    await coordinator.async_update_health("test_recovery")
    await hass.async_block_till_done()
    assert coordinator.health_assessment.state is IrrigationOSHealthState.HEALTHY
    assert hass.states.get("binary_sensor.irrigationos_health_incident").state == "on"
    assert len(recovery_events) == 1

    log_dir = Path(hass.config.path("irrigationos_logs"))
    assert list(log_dir.glob("irrigationos_*.jsonl"))

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.health_incident_latched is True
    assert hass.states.get("binary_sensor.irrigationos_health_incident").state == "on"

    entry.runtime_data._started_at = datetime.now(UTC) - timedelta(minutes=20)
    entry.runtime_data._polling_healthy = True
    await entry.runtime_data.async_update_health("test_post_reload_degraded")
    await hass.async_block_till_done()
    assert entry.runtime_data.health_assessment.state is IrrigationOSHealthState.DEGRADED
    assert entry.runtime_data.health_incident_latched is True
    assert await entry.runtime_data.reset_health_incident_latch() is False
    assert entry.runtime_data.health_incident_latched is True

    assert entry.runtime_data.realtime is not None
    entry.runtime_data.realtime.enabled = True
    entry.runtime_data.realtime.remote_health = RealtimeRegistrationHealth(
        healthy=True,
        registered_controllers=1,
        expected_controllers=1,
        error=None,
    )
    await entry.runtime_data.async_update_health("test_post_reload_healthy")
    await hass.async_block_till_done()
    assert entry.runtime_data.health_assessment.state is IrrigationOSHealthState.HEALTHY
    reset_button = hass.states.get("button.irrigationos_reset_health_incident")
    assert reset_button is not None
    assert reset_button.state != STATE_UNAVAILABLE

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.irrigationos_reset_health_incident"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.health_incident_latched is False
    assert hass.states.get("binary_sensor.irrigationos_health_incident").state == "off"
    assert await entry.runtime_data.reset_health_incident_latch() is True
    assert entry.runtime_data.health_incident_latched is False
