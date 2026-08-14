"""Tests for terminal unattended-canary acceptance persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.helpers import load_integration_module

acceptance = load_integration_module("unattended_canary.acceptance")

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
    manager = acceptance.UnattendedCanaryAcceptanceManager.__new__(
        acceptance.UnattendedCanaryAcceptanceManager
    )
    manager._store = store
    manager.latest = None
    manager.last_persistence_error = None
    return manager


def _record(
    *,
    observed_watering: bool = True,
    observed_idle: bool = True,
    concurrent: bool = False,
    safety_preemption: bool = False,
    start_acknowledged: bool = True,
) -> Any:
    watering_at = NOW if observed_watering else None
    idle_at = (
        NOW + timedelta(seconds=30)
        if observed_watering and observed_idle
        else None
    )
    return acceptance.build_canary_acceptance_record(
        canary_id="unattended_canary_test",
        approval_id="unattended_canary_approval_test",
        controller_slot=1,
        area_slot=2,
        requested_runtime_seconds=30,
        observed_watering_at=watering_at,
        observed_idle_at=idle_at,
        refresh_error_count=0,
        concurrent_watering_observed=concurrent,
        safety_preemption_observed=safety_preemption,
        terminal_detail_code="test_terminal",
        start_acknowledged=start_acknowledged,
        recorded_at=NOW,
    )


def test_acceptance_pass_fail_indeterminate_and_all_criteria() -> None:
    passed = _record()
    failed = _record(concurrent=True)
    indeterminate = _record(observed_idle=False)
    timeout = _record(observed_watering=False, observed_idle=False)
    preempted = _record(safety_preemption=True)
    assert passed.status is acceptance.UnattendedCanaryAcceptanceStatus.PASS
    assert failed.status is acceptance.UnattendedCanaryAcceptanceStatus.FAIL
    assert indeterminate.status is (
        acceptance.UnattendedCanaryAcceptanceStatus.INDETERMINATE
    )
    assert timeout.status is acceptance.UnattendedCanaryAcceptanceStatus.FAIL
    assert preempted.status is acceptance.UnattendedCanaryAcceptanceStatus.FAIL
    assert {criterion.code for criterion in passed.criteria} >= {
        "explicit_approval_recorded",
        "approval_matched_exact_target",
        "approval_matched_runtime",
        "production_readiness_passed",
        "command_intent_recorded",
        "approval_consumed",
        "target_preflight_observed",
        "start_acknowledged",
        "target_watering_observed",
        "runtime_within_canary_ceiling",
        "target_returned_idle",
        "no_concurrent_watering_observed",
        "no_safety_preemption",
        "post_run_reconciliation_passed",
        "terminal_acceptance_audit_recorded",
    }


def test_acceptance_serialization_is_deterministic_and_privacy_safe() -> None:
    record = _record()
    payload = record.to_dict()
    assert acceptance.UnattendedCanaryAcceptanceRecord.from_dict(payload) == record
    assert payload == record.to_dict()
    assert payload["criteria_passed_count"] == payload["criteria_total_count"]
    assert "native" not in repr(payload).lower()


async def test_no_prior_record_and_restart_restore_latest_terminal_result() -> None:
    store = _Store()
    manager = _manager(store)
    await manager.async_initialize()
    assert manager.status is acceptance.UnattendedCanaryAcceptanceStatus.NOT_AVAILABLE

    record = _record()
    assert await manager.async_record(record)
    restarted = _manager(store)
    await restarted.async_initialize()
    assert restarted.latest == record
    assert restarted.status is acceptance.UnattendedCanaryAcceptanceStatus.PASS
    assert not hasattr(restarted, "active_canary_id")


async def test_persistence_failure_is_fail_safe_and_visible() -> None:
    manager = _manager(_Store(fail=True))
    assert not await manager.async_record(_record())
    assert manager.latest is None
    assert manager.status is acceptance.UnattendedCanaryAcceptanceStatus.NOT_AVAILABLE
    assert manager.last_persistence_error == (
        "unattended_canary_acceptance_save_failed"
    )


async def test_malformed_restore_fails_closed() -> None:
    manager = _manager(_Store({"status": "pass"}))
    await manager.async_initialize()
    assert manager.latest is None
    assert manager.last_persistence_error == (
        "unattended_canary_acceptance_restore_failed"
    )
