"""Behavioral tests for v0.4.1 migration and runtime composition."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tests.helpers import load_integration_module

CONTROLLERS = load_integration_module("controllers")
ADAPTER = load_integration_module("adapters.rachio.adapter")
FACTORY = load_integration_module("adapters.factory")
MIGRATION = load_integration_module("migration")
RECONCILIATION = load_integration_module("reconciliation")
DIAGNOSTICS = load_integration_module("diagnostic_data")

ControllerIdentityRegistry = CONTROLLERS.ControllerIdentityRegistry
RachioControllerAdapter = ADAPTER.RachioControllerAdapter


def _snapshot() -> tuple[Any, Any]:
    identities = ControllerIdentityRegistry()
    snapshot = RachioControllerAdapter.from_person_payload(
        {
            "id": "person-1",
            "devices": [
                {
                    "id": "device-1",
                    "name": "Home",
                    "model": "GENERATION3_4ZONE",
                    "zones": [
                        {
                            "id": "zone-1",
                            "zoneNumber": 1,
                            "name": "Trees",
                            "enabled": True,
                        }
                    ],
                }
            ],
        },
        identities,
    )
    return snapshot, identities


def test_v040_migration_preserves_profiles_and_registry_identity() -> None:
    snapshot, identities = _snapshot()
    migration = MIGRATION.build_v040_migration(
        {"api_key": "secret", "person_id": "person-1"},
        {"area_profiles": {"rachio:zone-1": {"display_name": "Orchard"}}},
        snapshot,
        identities,
    )
    controller = snapshot.controllers[0]
    area = snapshot.areas[0]

    assert migration.data["identity_registry"] == identities.as_dict()
    assert migration.options["area_profiles"][area.area_id]["display_name"] == "Orchard"
    assert migration.entity_unique_ids["rachio:device-1_status"] == (
        f"{controller.controller_id}_status"
    )
    assert migration.entity_unique_ids["rachio:zone-1_observation"] == (
        f"{area.area_id}_observation"
    )
    assert migration.device_identifiers["rachio:zone-1"] == area.area_id


def test_dynamic_inventory_reports_additions_and_removals_without_forgetting_identity() -> None:
    inventory = RECONCILIATION.EntityInventory()
    first = inventory.reconcile({"controller:a", "area:a:slot:1"})
    second = inventory.reconcile({"controller:a", "area:a:slot:1", "area:a:slot:2"})
    third = inventory.reconcile({"controller:a", "area:a:slot:2"})
    rediscovered = inventory.reconcile(
        {"controller:a", "area:a:slot:1", "area:a:slot:2"}
    )

    assert first.added == {"controller:a", "area:a:slot:1"}
    assert second.added == {"area:a:slot:2"}
    assert third.missing == {"area:a:slot:1"}
    assert rediscovered.added == frozenset()


def test_provider_factory_composes_rachio_adapter() -> None:
    adapter = FACTORY.DEFAULT_PROVIDER_FACTORY.create(
        "rachio", object(), "api-key", ControllerIdentityRegistry()
    )
    assert isinstance(adapter, RachioControllerAdapter)
    assert adapter.provider == "rachio"


def test_diagnostics_redact_bindings_but_preserve_observation_metadata() -> None:
    snapshot, _identities = _snapshot()
    redacted = DIAGNOSTICS.redact_data(
        asdict(snapshot),
        {"api_key", "account_id", "native_id", "controller_id", "area_id"},
    )

    assert redacted["account_id"] == DIAGNOSTICS.REDACTED
    assert redacted["controllers"][0]["binding"]["native_id"] == DIAGNOSTICS.REDACTED
    assert redacted["controllers"][0]["areas"][0]["area_id"] == DIAGNOSTICS.REDACTED
    assert redacted["observation"]["observed_at"] == snapshot.observation.observed_at
    assert redacted["observation"]["source"] == "rachio"
    assert redacted["observation"]["quality"] == snapshot.observation.quality

    entry_data = DIAGNOSTICS.redact_data(
        {
            "api_key": "secret",
            "identity_registry": {
                "controllers": {"rachio:device-1": "controller_safe"}
            },
        },
        {"api_key", "identity_registry"},
    )
    assert entry_data["api_key"] == DIAGNOSTICS.REDACTED
    assert entry_data["identity_registry"] == DIAGNOSTICS.REDACTED
