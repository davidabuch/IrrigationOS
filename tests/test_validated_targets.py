"""Tests for the durable canonical validated-target registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.helpers import load_integration_module

acceptance = load_integration_module("first_live_delivery.acceptance")
registry_module = load_integration_module("first_live_delivery.validated_targets")

FirstLiveAcceptanceStatus = acceptance.FirstLiveAcceptanceStatus
ValidatedTargetRecord = registry_module.ValidatedTargetRecord
ValidatedTargetRegistry = registry_module.ValidatedTargetRegistry

NOW = datetime(2026, 8, 13, 14, 0, tzinfo=UTC)


class _Store:
    def __init__(self, stored: dict[str, Any] | None = None, *, fail: bool = False) -> None:
        self.stored = stored
        self.fail = fail
        self.save_count = 0

    async def async_load(self) -> dict[str, Any] | None:
        if self.fail:
            raise OSError("store unavailable")
        return self.stored

    async def async_save(self, value: dict[str, Any]) -> None:
        self.save_count += 1
        if self.fail:
            raise OSError("store unavailable")
        self.stored = value


def _registry(store: _Store) -> Any:
    registry = ValidatedTargetRegistry.__new__(ValidatedTargetRegistry)
    registry._store = store
    registry._targets = ()
    registry._migration_completed = False
    registry.last_persistence_error = None
    return registry


def _acceptance(
    *,
    controller_slot: int = 1,
    area_slot: int = 2,
    outcome: str = "pass",
    attempt_id: str | None = None,
) -> Any:
    observed_watering_at = NOW
    observed_idle_at: datetime | None = NOW + timedelta(seconds=30)
    concurrent_watering = False
    if outcome == "fail":
        concurrent_watering = True
    elif outcome == "indeterminate":
        observed_idle_at = None
    record = acceptance.build_acceptance_record(
        attempt_id=attempt_id or f"first_live_{controller_slot}_{area_slot}_{outcome}",
        controller_slot=controller_slot,
        area_slot=area_slot,
        requested_runtime_seconds=30,
        observed_watering_at=observed_watering_at,
        observed_idle_at=observed_idle_at,
        refresh_error_count=0,
        concurrent_watering_observed=concurrent_watering,
        terminal_detail_code=f"first_live_{outcome}",
    )
    assert record.status.value == outcome
    return record


async def test_empty_registry_initializes_without_eligibility() -> None:
    registry = _registry(_Store())
    await registry.async_initialize(None)
    assert registry.targets == ()
    assert registry.contains(1, 2) is False
    assert registry.diagnostics()["validated_target_count"] == 0


async def test_only_pass_adds_target() -> None:
    registry = _registry(_Store())
    await registry.async_initialize(None)
    assert await registry.async_register(_acceptance(outcome="fail")) is False
    assert await registry.async_register(_acceptance(outcome="indeterminate")) is False
    assert registry.targets == ()

    assert await registry.async_register(_acceptance()) is True
    assert registry.contains(1, 2) is True
    assert registry.targets[0].acceptance_status is FirstLiveAcceptanceStatus.PASS


async def test_duplicate_pass_refreshes_without_duplicate() -> None:
    registry = _registry(_Store())
    assert await registry.async_register(_acceptance(attempt_id="first_live_original"))
    assert await registry.async_register(_acceptance(attempt_id="first_live_refreshed"))
    assert len(registry.targets) == 1
    assert registry.targets[0].source_attempt_id == "first_live_refreshed"


async def test_multiple_targets_coexist_in_canonical_order() -> None:
    registry = _registry(_Store())
    assert await registry.async_register(_acceptance(area_slot=2))
    assert await registry.async_register(_acceptance(area_slot=1))
    assert [target.key for target in registry.targets] == [(1, 1), (1, 2)]
    assert registry.contains(1, 1)
    assert registry.contains(1, 2)
    assert not registry.contains(1, 3)


async def test_restart_restores_all_targets_and_migration_is_idempotent() -> None:
    store = _Store()
    original = _registry(store)
    await original.async_initialize(_acceptance(area_slot=2))
    assert await original.async_register(_acceptance(area_slot=1))

    restarted = _registry(store)
    await restarted.async_initialize(_acceptance(area_slot=3))
    assert [target.key for target in restarted.targets] == [(1, 1), (1, 2)]
    assert store.save_count == 2


@pytest.mark.parametrize("outcome", ["fail", "indeterminate"])
async def test_migration_does_not_seed_nonpass(outcome: str) -> None:
    registry = _registry(_Store())
    await registry.async_initialize(_acceptance(outcome=outcome))
    assert registry.targets == ()


async def test_migration_seeds_latest_v1040_pass_once() -> None:
    store = _Store()
    registry = _registry(store)
    passed = _acceptance(area_slot=2)
    await registry.async_initialize(passed)
    assert registry.contains(1, 2)
    assert store.stored is not None
    assert store.stored["migration_completed"] is True

    restarted = _registry(store)
    await restarted.async_initialize(_acceptance(area_slot=1))
    assert [target.key for target in restarted.targets] == [(1, 2)]


async def test_persistence_failure_preserves_previously_durable_targets() -> None:
    store = _Store()
    registry = _registry(store)
    assert await registry.async_register(_acceptance(area_slot=2))
    store.fail = True
    assert await registry.async_register(_acceptance(area_slot=1)) is False
    assert registry.contains(1, 2)
    assert not registry.contains(1, 1)
    assert store.stored is not None
    assert len(store.stored["targets"]) == 1
    assert registry.last_persistence_error == "validated_target_registry_save_failed"
    assert registry.diagnostics()["last_persistence_error"] == (
        "validated_target_registry_save_failed"
    )


async def test_revocation_removes_only_exact_target() -> None:
    registry = _registry(_Store())
    assert await registry.async_register(_acceptance(area_slot=1))
    assert await registry.async_register(_acceptance(area_slot=2))
    assert await registry.async_revoke(1, 1)
    assert not registry.contains(1, 1)
    assert registry.contains(1, 2)


def test_record_rejects_nonpass_and_serializes_no_provider_ids() -> None:
    passed = _acceptance()
    target = ValidatedTargetRecord.from_acceptance(passed)
    serialized = repr(target.to_dict())
    assert "native-zone" not in serialized
    assert "native-controller" not in serialized
    with pytest.raises(ValueError, match="only PASS"):
        ValidatedTargetRecord.from_acceptance(_acceptance(outcome="fail"))
    with pytest.raises(ValueError, match="privacy-safe"):
        ValidatedTargetRecord.from_acceptance(
            _acceptance(attempt_id="native-zone-provider-123")
        )
