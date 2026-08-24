from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from homeassistant.core import HomeAssistant

from custom_components.irrigationos.landscape_intelligence.manager import (
    LandscapeIntelligenceManager,
)


class _Store:
    def __init__(self, value: dict[str, Any] | None) -> None:
        self.value = value
        self.saved: list[dict[str, Any]] = []

    async def async_load(self) -> dict[str, Any] | None:
        return self.value

    async def async_save(self, value: dict[str, Any]) -> None:
        self.saved.append(value)


@pytest.mark.asyncio
async def test_existing_schema_one_zone1_store_is_preserved(hass: HomeAssistant) -> None:
    manager = LandscapeIntelligenceManager(hass, "existing")
    old_payload = {"schema_version": 1, "zone_1": {"profile_status": "commissioned"}}
    store = _Store(old_payload)
    manager._store = store  # type: ignore[assignment]

    await manager.async_initialize(
        initial_observed_at=datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    )

    assert store.saved == []
    assert manager.zone1.area_slot == 1
    assert tuple(zone.identity.area_slot for zone in manager.commissioned_zones) == (1,)


@pytest.mark.asyncio
async def test_new_store_retains_legacy_payload_and_adds_generic_zone(
    hass: HomeAssistant,
) -> None:
    manager = LandscapeIntelligenceManager(hass, "new")
    store = _Store(None)
    manager._store = store  # type: ignore[assignment]

    await manager.async_initialize(
        initial_observed_at=datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    )

    assert len(store.saved) == 1
    payload = store.saved[0]
    assert payload["schema_version"] == 1
    assert payload["zone_1"]["area_slot"] == 1
    assert payload["commissioned_zones"][0]["identity"] == {
        "property_id": "property.primary",
        "zone_id": "zone.1",
        "controller_slot": 1,
        "area_slot": 1,
    }
