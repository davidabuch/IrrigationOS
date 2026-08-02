"""IrrigationOS integration setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

type IrrigationOSConfigEntry = ConfigEntry[IrrigationOSCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> bool:
    """Set up IrrigationOS from a config entry."""
    coordinator = IrrigationOSCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.realtime = RealtimeObservationManager(hass, entry, coordinator)
    await coordinator.realtime.async_setup()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> bool:
    """Unload an IrrigationOS config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data.realtime is not None:
        await entry.runtime_data.realtime.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: IrrigationOSConfigEntry) -> None:
    """Remove the optional cloudhook when the entry is permanently deleted."""
    await async_delete_cloudhook(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate vendor-derived v0.4.0 registry identities to canonical slots."""
    if entry.version >= 2:
        return True

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

    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        migrated = migration.entity_unique_ids.get(entity.unique_id)
        if migrated is not None and migrated != entity.unique_id:
            entity_registry.async_update_entity(entity.entity_id, new_unique_id=migrated)

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
        version=2,
    )
    return True
