"""Home Assistant persistence regressions for shadow stability."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

from custom_components.irrigationos.shadow_evaluation.manager import (
    ShadowEvaluationManager,
)


class _CountingStore:
    def __init__(self, stored: dict[str, Any]) -> None:
        self.stored = stored
        self.save_count = 0

    async def async_load(self) -> dict[str, Any]:
        return self.stored

    async def async_save(self, value: dict[str, Any]) -> None:
        self.save_count += 1
        self.stored = value


async def test_unchanged_shadow_metadata_is_not_rewritten(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    stored = {
        "last_decision_fingerprint": "stable-fingerprint",
        "section_hashes": {
            "profile": "profile",
            "scientific": "scientific",
            "observation": "observation",
            "confidence": "confidence",
        },
        "completed_session_count": 4,
    }
    manager = ShadowEvaluationManager(
        hass, "shadow-stability", tmp_path, ZoneInfo("UTC")
    )
    store = _CountingStore(stored)
    manager._store = store  # type: ignore[assignment]
    await manager.async_initialize()

    await manager._async_persist_state()
    assert store.save_count == 0

    manager._completed_session_count = 5
    await manager._async_persist_state()
    assert store.save_count == 1

    await manager._async_persist_state()
    assert store.save_count == 1


async def test_shadow_history_diagnostics_are_computed_during_existing_load(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    path = tmp_path / "irrigationos_shadow_2026-08-17.jsonl"
    line = (
        '{"evaluation_id":"one","reason":"nightly",'
        '"timestamp_utc":"2026-08-17T03:00:00+00:00"}\n'
    )
    path.write_text(line, encoding="utf-8")
    manager = ShadowEvaluationManager(
        hass, "shadow-diagnostics", tmp_path, ZoneInfo("UTC")
    )

    records = await manager.async_load_records()
    diagnostics = manager.diagnostics()

    assert len(records) == 1
    assert diagnostics["shadow_record_count_loaded"] == 1
    assert diagnostics["shadow_log_bytes"] == len(line.encode())
    assert diagnostics["last_shadow_write_reason"] == "nightly"
    assert diagnostics["last_shadow_write_at"] == "2026-08-17T03:00:00+00:00"
