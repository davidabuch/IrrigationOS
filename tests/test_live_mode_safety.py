"""Tests for the separate pre-Live safety architecture boundary."""

from __future__ import annotations

from typing import Any

from tests.helpers import load_integration_module

live_mode_safety = load_integration_module("live_mode_safety")
LiveModeSafetyStatus = live_mode_safety.LiveModeSafetyStatus
build_live_mode_safety_summary = live_mode_safety.build_live_mode_safety_summary


def _summary(**overrides: object) -> Any:
    values: dict[str, Any] = {
        "readiness_status": "criteria_met",
        "execution_authorization_status": "manual_review_eligible",
        "ownership_confirmed": True,
        "boundary_review_acknowledged": True,
    }
    values.update(overrides)
    return build_live_mode_safety_summary(**values)


def test_complete_prerequisite_evidence_still_blocks_live_mode() -> None:
    summary = _summary()
    assert summary.status is LiveModeSafetyStatus.ARCHITECTURE_INCOMPLETE
    assert summary.prerequisites_met_count == summary.prerequisites_total_count
    assert summary.safeguards_met_count == 0
    assert summary.live_mode_commissionable is False
    assert summary.live_control_feature_enabled is False
    assert summary.live_control_authorized is False


def test_missing_readiness_is_prerequisite_blocker() -> None:
    summary = _summary(readiness_status="insufficient_evidence")
    assert summary.status is LiveModeSafetyStatus.PREREQUISITES_INCOMPLETE
    assert "control_readiness_criteria_met" in summary.blocker_codes


def test_missing_ownership_is_prerequisite_blocker() -> None:
    summary = _summary(ownership_confirmed=False)
    assert "controller_ownership_confirmed" in summary.blocker_codes


def test_required_safety_architecture_is_explicit() -> None:
    summary = _summary()
    assert set(summary.safeguard_gates) == {
        "command_attribution_and_receipts",
        "acknowledgement_and_timeout_handling",
        "restart_safe_command_reconciliation",
        "safety_preemption_path",
        "sunrise_hard_stop",
        "manual_override_preservation",
    }
    assert all(value is False for value in summary.safeguard_gates.values())


def test_manager_starts_fail_closed() -> None:
    manager_module = load_integration_module("live_mode_safety.manager")
    manager = manager_module.LiveModeSafetyManager()
    assert manager.summary.status is LiveModeSafetyStatus.PREREQUISITES_INCOMPLETE
    assert manager.summary.live_control_authorized is False
