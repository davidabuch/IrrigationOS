"""Pure migration helpers for the v0.4.1 canonical controller model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import CONF_AREA_PROFILES, CONF_IDENTITY_REGISTRY
from .controllers import ControllerIdentityRegistry, ControllerRegistrySnapshot


@dataclass(frozen=True, slots=True)
class CanonicalIdentityMigration:
    """Config and registry changes required for a v0.4.0 entry."""

    data: dict[str, Any]
    options: dict[str, Any]
    entity_unique_ids: dict[str, str]
    device_identifiers: dict[str, str]


def build_v040_migration(
    data: dict[str, Any],
    options: dict[str, Any],
    snapshot: ControllerRegistrySnapshot,
    identities: ControllerIdentityRegistry,
) -> CanonicalIdentityMigration:
    """Map vendor-derived v0.4.0 identities to canonical controller slots."""
    device_identifiers: dict[str, str] = {}
    entity_unique_ids: dict[str, str] = {}
    old_area_to_new: dict[str, str] = {}

    for controller in snapshot.controllers:
        old_controller_id = (
            f"{controller.binding.provider}:{controller.binding.native_id}"
        )
        device_identifiers[old_controller_id] = controller.controller_id
        for suffix in ("status", "online"):
            entity_unique_ids[f"{old_controller_id}_{suffix}"] = (
                f"{controller.controller_id}_{suffix}"
            )

        for area in controller.areas:
            if area.binding is None:
                continue
            old_area_id = f"{area.binding.provider}:{area.binding.native_id}"
            old_area_to_new[old_area_id] = area.area_id
            device_identifiers[old_area_id] = area.area_id
            for suffix in ("observation", "landscape_profile", "enabled"):
                entity_unique_ids[f"{old_area_id}_{suffix}"] = f"{area.area_id}_{suffix}"

    migrated_profiles: dict[str, Any] = {}
    raw_profiles = options.get(CONF_AREA_PROFILES, {})
    if isinstance(raw_profiles, dict):
        for raw_key, value in raw_profiles.items():
            old_key = str(raw_key)
            migrated_profiles[old_area_to_new.get(old_key, old_key)] = value

    new_options = dict(options)
    new_options[CONF_AREA_PROFILES] = migrated_profiles
    new_data = dict(data)
    new_data[CONF_IDENTITY_REGISTRY] = identities.as_dict()
    return CanonicalIdentityMigration(
        data=new_data,
        options=new_options,
        entity_unique_ids=entity_unique_ids,
        device_identifiers=device_identifiers,
    )


def migrate_unique_id(unique_id: str, mapping: dict[str, str]) -> str:
    """Return a migrated entity unique ID when one is known."""
    return mapping.get(unique_id, unique_id)
