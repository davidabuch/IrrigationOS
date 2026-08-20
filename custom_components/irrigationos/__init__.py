"""IrrigationOS integration setup."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .adapters.factory import DEFAULT_PROVIDER_FACTORY
from .const import (
    CONF_API_KEY,
    CONF_CONTROLLER_PROVIDER,
    CONF_IDENTITY_REGISTRY,
    CONF_PERSON_ID,
    DEFAULT_CONTROLLER_PROVIDER,
    DOMAIN,
    PLATFORMS,
)
from .controllers import ControllerIdentityRegistry
from .coordinator import IrrigationOSCoordinator
from .migration import build_v040_migration
from .realtime import RealtimeObservationManager, async_delete_cloudhook
from .supervised_operation import (
    SERVICE_RUN_SUPERVISED_OPERATION,
    SupervisedOperationStatus,
    async_run_supervised_operation,
)
from .unattended_canary import (
    SERVICE_AUTHORIZE_UNATTENDED_CANARY,
    SERVICE_RUN_UNATTENDED_CANARY,
    UNATTENDED_CANARY_DEFAULT_RUNTIME_SECONDS,
    UnattendedCanaryAuthorizationStatus,
    UnattendedCanaryRunStatus,
    async_authorize_unattended_canary,
    async_run_unattended_canary,
)

type IrrigationOSConfigEntry = ConfigEntry[IrrigationOSCoordinator]

_LOGGER = logging.getLogger(__name__)

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_CONTROLLER_SLOT = "controller_slot"
ATTR_AREA_SLOT = "area_slot"
ATTR_RUNTIME_SECONDS = "runtime_seconds"
ATTR_CONFIRMATION = "confirmation"

SUPERVISED_OPERATION_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_CONTROLLER_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_AREA_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_RUNTIME_SECONDS, default=30): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=120)
        ),
        vol.Required(ATTR_CONFIRMATION): str,
    }
)

UNATTENDED_CANARY_APPROVAL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_CONTROLLER_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_AREA_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            ATTR_RUNTIME_SECONDS, default=UNATTENDED_CANARY_DEFAULT_RUNTIME_SECONDS
        ): vol.All(vol.Coerce(int), vol.Range(min=15, max=60)),
        vol.Required(ATTR_CONFIRMATION): str,
    }
)

UNATTENDED_CANARY_RUN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_CONTROLLER_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(ATTR_AREA_SLOT): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            ATTR_RUNTIME_SECONDS, default=UNATTENDED_CANARY_DEFAULT_RUNTIME_SECONDS
        ): vol.All(vol.Coerce(int), vol.Range(min=15, max=60)),
    }
)

GLOBAL_ENTITY_ID_MIGRATIONS = {
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


async def async_setup_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> bool:
    """Set up IrrigationOS from a config entry."""
    coordinator = IrrigationOSCoordinator(hass, entry)
    await coordinator.async_initialize_health()
    await coordinator.async_initialize_landscape_intelligence()
    await coordinator.async_initialize_ownership_commissioning()
    await coordinator.async_initialize_observation_history()
    await coordinator.async_config_entry_first_refresh()
    coordinator.realtime = RealtimeObservationManager(hass, entry, coordinator)
    await coordinator.realtime.async_setup()
    await coordinator.async_start_health_monitoring()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_supervised_operation_service(hass)
    _async_register_unattended_canary_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> bool:
    """Unload an IrrigationOS config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop_health_monitoring()
        await entry.runtime_data.observation_history.async_shutdown()
        if entry.runtime_data.realtime is not None:
            await entry.runtime_data.realtime.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> None:
    """Remove the optional cloudhook when the entry is permanently deleted."""
    await async_delete_cloudhook(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate canonical identities and global Home Assistant entity IDs."""
    if entry.version >= 3:
        return True

    entity_registry = er.async_get(hass)
    if entry.version < 2:
        identities = ControllerIdentityRegistry.from_dict(
            entry.data.get(CONF_IDENTITY_REGISTRY)
        )
        adapter = DEFAULT_PROVIDER_FACTORY.create(
            str(entry.data.get(CONF_CONTROLLER_PROVIDER, DEFAULT_CONTROLLER_PROVIDER)),
            async_get_clientsession(hass),
            str(entry.data[CONF_API_KEY]),
            identities,
        )
        snapshot = await adapter.async_get_snapshot(str(entry.data[CONF_PERSON_ID]))
        migration = build_v040_migration(
            dict(entry.data), dict(entry.options), snapshot, identities
        )

        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            migrated = migration.entity_unique_ids.get(entity.unique_id)
            if migrated is not None and migrated != entity.unique_id:
                entity_registry.async_update_entity(
                    entity.entity_id, new_unique_id=migrated
                )

        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            migrated_identifiers = {
                (
                    domain,
                    migration.device_identifiers.get(identifier, identifier)
                    if domain == DOMAIN
                    else identifier,
                )
                for domain, identifier in device.identifiers
            }
            if migrated_identifiers != device.identifiers:
                device_registry.async_update_device(
                    device.id, new_identifiers=migrated_identifiers
                )

        hass.config_entries.async_update_entry(
            entry,
            data=migration.data,
            options=migration.options,
        )

    _migrate_global_entity_ids(entity_registry, entry.entry_id)
    hass.config_entries.async_update_entry(entry, version=3)
    return True


def _async_register_supervised_operation_service(hass: HomeAssistant) -> None:
    """Register the explicit manual operational command boundary exactly once."""

    if hass.services.has_service(DOMAIN, SERVICE_RUN_SUPERVISED_OPERATION):
        return

    async def _async_handle(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        target_entry = hass.config_entries.async_get_entry(entry_id)
        if target_entry is None or target_entry.domain != DOMAIN:
            raise HomeAssistantError("IrrigationOS config entry was not found")
        try:
            coordinator = target_entry.runtime_data
        except RuntimeError as err:
            raise HomeAssistantError("IrrigationOS config entry is not loaded") from err
        if not isinstance(coordinator, IrrigationOSCoordinator):
            raise HomeAssistantError("IrrigationOS runtime data is unavailable")

        result = await async_run_supervised_operation(
            coordinator,
            controller_slot=int(call.data[ATTR_CONTROLLER_SLOT]),
            area_slot=int(call.data[ATTR_AREA_SLOT]),
            runtime_seconds=int(call.data[ATTR_RUNTIME_SECONDS]),
            confirmation=str(call.data[ATTR_CONFIRMATION]),
        )
        if result.status is not SupervisedOperationStatus.START_DISPATCHED:
            blockers = ", ".join(result.blocker_codes) or result.status.value
            raise HomeAssistantError(f"Supervised operation blocked: {blockers}")

    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_SUPERVISED_OPERATION,
        _async_handle,
        schema=SUPERVISED_OPERATION_SERVICE_SCHEMA,
    )


def _async_register_unattended_canary_services(hass: HomeAssistant) -> None:
    """Register separate approval and one-shot execution boundaries."""

    async def _coordinator(call: ServiceCall) -> IrrigationOSCoordinator:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        target_entry = hass.config_entries.async_get_entry(entry_id)
        if target_entry is None or target_entry.domain != DOMAIN:
            raise HomeAssistantError("IrrigationOS config entry was not found")
        try:
            coordinator = target_entry.runtime_data
        except RuntimeError as err:
            raise HomeAssistantError("IrrigationOS config entry is not loaded") from err
        if not isinstance(coordinator, IrrigationOSCoordinator):
            raise HomeAssistantError("IrrigationOS runtime data is unavailable")
        return coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_AUTHORIZE_UNATTENDED_CANARY):

        async def _async_authorize(call: ServiceCall) -> None:
            coordinator = await _coordinator(call)
            result = await async_authorize_unattended_canary(
                coordinator,
                controller_slot=int(call.data[ATTR_CONTROLLER_SLOT]),
                area_slot=int(call.data[ATTR_AREA_SLOT]),
                runtime_seconds=int(call.data[ATTR_RUNTIME_SECONDS]),
                confirmation=str(call.data[ATTR_CONFIRMATION]),
            )
            if result.status is not UnattendedCanaryAuthorizationStatus.APPROVED:
                blockers = ", ".join(result.blocker_codes) or result.status.value
                raise HomeAssistantError(f"Canary approval blocked: {blockers}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_AUTHORIZE_UNATTENDED_CANARY,
            _async_authorize,
            schema=UNATTENDED_CANARY_APPROVAL_SERVICE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RUN_UNATTENDED_CANARY):

        async def _async_run(call: ServiceCall) -> None:
            coordinator = await _coordinator(call)
            result = await async_run_unattended_canary(
                coordinator,
                controller_slot=int(call.data[ATTR_CONTROLLER_SLOT]),
                area_slot=int(call.data[ATTR_AREA_SLOT]),
                runtime_seconds=int(call.data[ATTR_RUNTIME_SECONDS]),
            )
            if result.status is not UnattendedCanaryRunStatus.START_DISPATCHED:
                blockers = ", ".join(result.blocker_codes) or result.status.value
                raise HomeAssistantError(f"Unattended canary blocked: {blockers}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_RUN_UNATTENDED_CANARY,
            _async_run,
            schema=UNATTENDED_CANARY_RUN_SERVICE_SCHEMA,
        )


def _migrate_global_entity_ids(
    entity_registry: er.EntityRegistry, entry_id: str
) -> None:
    """Rename only known default global IDs while preserving registry entries."""
    for entity in er.async_entries_for_config_entry(entity_registry, entry_id):
        migration = GLOBAL_ENTITY_ID_MIGRATIONS.get(entity.unique_id)
        if migration is None:
            continue
        old_entity_id, new_entity_id = migration
        if entity.entity_id != old_entity_id:
            continue
        if entity_registry.async_get(new_entity_id) is not None:
            _LOGGER.warning(
                "Cannot migrate IrrigationOS entity %s because %s already exists",
                old_entity_id,
                new_entity_id,
            )
            continue
        entity_registry.async_update_entity(
            old_entity_id,
            new_entity_id=new_entity_id,
        )
