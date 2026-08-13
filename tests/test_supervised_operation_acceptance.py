"""Tests for persistent supervised operational acceptance visibility."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

first_live = load_integration_module("first_live_delivery.acceptance")
supervised = load_integration_module("supervised_operation.acceptance")

FirstLiveAcceptanceStatus = first_live.FirstLiveAcceptanceStatus
SupervisedOperationAcceptanceManager = supervised.SupervisedOperationAcceptanceManager

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class _Store:
    def __init__(self, stored: dict[str, Any] | None = None, *, fail: bool = False) -> None:
        self.stored = stored
        self.fail = fail

    async def async_load(self) -> dict[str, Any] | None:
        if self.fail:
            raise OSError("storage unavailable")
        return self.stored

    async def async_save(self, value: dict[str, Any]) -> None:
        if self.fail:
            raise OSError("storage unavailable")
        self.stored = value


def _manager(store: _Store) -> Any:
    manager = SupervisedOperationAcceptanceManager.__new__(
        SupervisedOperationAcceptanceManager
    )
    manager._store = store
    manager.latest = None
    manager.last_persistence_error = None
    return manager


def _record(status: str) -> Any:
    observed_watering_at = NOW
    observed_idle_at: datetime | None = NOW + timedelta(seconds=30)
    concurrent_watering = False
    if status == "fail":
        concurrent_watering = True
    elif status == "indeterminate":
        observed_idle_at = None
    return first_live.build_acceptance_record(
        attempt_id=f"supervised_operation_{status}",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=observed_watering_at,
        observed_idle_at=observed_idle_at,
        refresh_error_count=0,
        concurrent_watering_observed=concurrent_watering,
        terminal_detail_code=f"supervised_operation_{status}",
    )


async def test_no_prior_supervised_acceptance_is_not_available() -> None:
    manager = _manager(_Store())
    await manager.async_initialize()
    assert manager.status is FirstLiveAcceptanceStatus.NOT_AVAILABLE
    assert manager.diagnostics()["latest"] is None


async def test_pass_fail_and_indeterminate_results_are_preserved() -> None:
    manager = _manager(_Store())
    for expected in ("pass", "fail", "indeterminate"):
        record = _record(expected)
        assert record.status.value == expected
        assert await manager.async_record(record) is True
        assert manager.status.value == expected
        assert manager.latest is record


async def test_latest_acceptance_restores_without_resuming_operation() -> None:
    store = _Store()
    original = _manager(store)
    record = _record("pass")
    assert await original.async_record(record) is True

    restarted = _manager(store)
    await restarted.async_initialize()
    assert restarted.latest == record
    assert restarted.status is FirstLiveAcceptanceStatus.PASS
    assert not hasattr(restarted, "active_operation_id")


async def test_persistence_failure_is_fail_safe_and_visible() -> None:
    manager = _manager(_Store(fail=True))
    assert await manager.async_record(_record("pass")) is False
    assert manager.status is FirstLiveAcceptanceStatus.NOT_AVAILABLE
    assert manager.latest is None
    assert manager.last_persistence_error == "supervised_acceptance_save_failed"
    assert manager.diagnostics()["last_persistence_error"] == (
        "supervised_acceptance_save_failed"
    )


async def test_malformed_restored_acceptance_fails_closed() -> None:
    manager = _manager(_Store({"status": "pass"}))
    await manager.async_initialize()
    assert manager.status is FirstLiveAcceptanceStatus.NOT_AVAILABLE
    assert manager.last_persistence_error == "supervised_acceptance_restore_failed"
