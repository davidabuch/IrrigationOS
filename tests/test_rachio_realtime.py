"""Behavioral tests for idempotent Rachio notification subscriptions."""

from __future__ import annotations

from typing import Any

import pytest

from tests.helpers import load_integration_module

MODULE = load_integration_module("adapters.rachio.realtime")
RachioWebhookRegistrar = MODULE.RachioWebhookRegistrar


class FakeWebhookApi:
    """Stateful subset of the Rachio notification API."""

    def __init__(self) -> None:
        self.webhooks: dict[str, list[dict[str, Any]]] = {"device-1": []}
        self.created = 0
        self.updated = 0
        self.deleted = 0
        self.event_types = [
            {"id": "zone", "name": "ZONE_STATUS_EVENT"},
            {"id": "device", "name": "DEVICE_STATUS_EVENT"},
            {"id": "schedule", "name": "SCHEDULE_STATUS_EVENT"},
            {"id": "ignored", "name": "SHARED_SCHEDULE_EVENT"},
        ]

    async def async_get_webhook_event_types(self) -> list[dict[str, str]]:
        return self.event_types

    async def async_get_device_webhooks(
        self, device_id: str
    ) -> list[dict[str, Any]]:
        return [dict(item) for item in self.webhooks[device_id]]

    async def async_create_webhook(self, payload: dict[str, Any]) -> None:
        self.created += 1
        device_id = payload["device"]["id"]
        self.webhooks[device_id].append({**payload, "id": f"hook-{self.created}"})

    async def async_update_webhook(self, payload: dict[str, Any]) -> None:
        self.updated += 1
        device_id = payload["device"]["id"]
        self.webhooks[device_id] = [
            dict(payload) if item["id"] == payload["id"] else item
            for item in self.webhooks[device_id]
        ]

    async def async_delete_webhook(self, webhook_id: str) -> None:
        self.deleted += 1
        for device_id, hooks in self.webhooks.items():
            self.webhooks[device_id] = [
                item for item in hooks if item["id"] != webhook_id
            ]


@pytest.mark.asyncio
async def test_reconcile_is_idempotent_and_cleanup_is_entry_scoped() -> None:
    api = FakeWebhookApi()
    registrar = RachioWebhookRegistrar(api)
    prefix = "homeassistant.irrigationos:entry-1:"
    external_id = f"{prefix}secret"

    first = await registrar.async_reconcile(
        "https://ha.example.com/api/webhook/stable",
        external_id,
        prefix,
        ("device-1",),
    )
    second = await registrar.async_reconcile(
        "https://ha.example.com/api/webhook/stable",
        external_id,
        prefix,
        ("device-1",),
    )

    assert first.healthy and second.healthy
    assert api.created == 1
    assert api.updated == 0
    assert len(api.webhooks["device-1"]) == 1
    assert api.webhooks["device-1"][0]["eventTypes"] == [
        {"id": "zone"},
        {"id": "device"},
        {"id": "schedule"},
    ]

    api.webhooks["device-1"].append(
        {
            "id": "stale-owned-hook",
            "externalId": f"{prefix}old-secret",
            "url": "https://old.example.com",
            "eventTypes": [],
        }
    )
    api.webhooks["device-1"].append(
        {
            "id": "foreign-hook",
            "externalId": "another-application",
            "url": "https://foreign.example.com",
            "eventTypes": [],
        }
    )
    reconciled = await registrar.async_reconcile(
        "https://ha.example.com/api/webhook/stable",
        external_id,
        prefix,
        ("device-1",),
    )
    assert reconciled.healthy
    assert {item["id"] for item in api.webhooks["device-1"]} == {
        "hook-1",
        "foreign-hook",
    }

    cleaned = await registrar.async_cleanup(prefix, ("device-1",))
    assert cleaned.healthy
    assert [item["id"] for item in api.webhooks["device-1"]] == ["foreign-hook"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_types", "expected_category"),
    [
        ([], "zero_event_types_returned"),
        (
            [{"id": "unwanted", "name": "SHARED_SCHEDULE_EVENT"}],
            "zero_desired_event_names_matched",
        ),
    ],
)
async def test_discovery_catalog_failures_are_structured(
    event_types: list[dict[str, str]], expected_category: str
) -> None:
    api = FakeWebhookApi()
    api.event_types = event_types
    registrar = RachioWebhookRegistrar(api)

    health = await registrar.async_reconcile(
        "https://ha.example.com/api/webhook/stable",
        "homeassistant.irrigationos:entry:secret",
        "homeassistant.irrigationos:entry:",
        ("device-1",),
    )

    assert not health.healthy
    assert health.registered_controllers == 0
    assert health.expected_controllers == 1
    assert health.error_category == expected_category
    assert api.created == 0
