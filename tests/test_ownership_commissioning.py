"""Tests for controller ownership commissioning evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tests.helpers import load_integration_module

ownership = load_integration_module("ownership_commissioning")
OwnershipCommissioningStatus = ownership.OwnershipCommissioningStatus
build_ownership_commissioning_summary = ownership.build_ownership_commissioning_summary
controller_topology_fingerprint = ownership.controller_topology_fingerprint

NOW = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)


def _stored(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "state": "confirmed",
        "controller_ids": ["controller-1"],
        "confirmed_at": NOW.isoformat(),
        "boundary_reviewed_at": None,
        "revoked_at": None,
        "commissioning_revision": 1,
    }
    value.update(overrides)
    return value


def test_uncommissioned_is_fail_closed() -> None:
    summary = build_ownership_commissioning_summary(
        controller_ids=("controller-1",), stored=None
    )
    assert summary.status is OwnershipCommissioningStatus.UNCOMMISSIONED
    assert summary.ownership_confirmed is False
    assert summary.live_control_authorized is False


def test_exact_topology_confirmation_is_effective() -> None:
    summary = build_ownership_commissioning_summary(
        controller_ids=("controller-1",), stored=_stored()
    )
    assert summary.status is OwnershipCommissioningStatus.OWNERSHIP_CONFIRMED
    assert summary.topology_matches is True
    assert summary.ownership_confirmed is True
    assert summary.boundary_review_acknowledged is False


def test_topology_change_invalidates_confirmation() -> None:
    summary = build_ownership_commissioning_summary(
        controller_ids=("controller-1", "controller-2"), stored=_stored()
    )
    assert summary.status is OwnershipCommissioningStatus.STALE_TOPOLOGY
    assert summary.topology_matches is False
    assert summary.ownership_confirmed is False


def test_boundary_review_requires_effective_ownership() -> None:
    reviewed = _stored(boundary_reviewed_at=NOW.isoformat())
    summary = build_ownership_commissioning_summary(
        controller_ids=("controller-1",), stored=reviewed
    )
    assert summary.status is OwnershipCommissioningStatus.BOUNDARY_REVIEW_ACKNOWLEDGED
    assert summary.boundary_review_acknowledged is True
    assert summary.live_control_feature_enabled is False


def test_revocation_overrides_matching_topology() -> None:
    summary = build_ownership_commissioning_summary(
        controller_ids=("controller-1",),
        stored=_stored(state="revoked", confirmed_at=None, revoked_at=NOW.isoformat()),
    )
    assert summary.status is OwnershipCommissioningStatus.REVOKED
    assert summary.ownership_confirmed is False
    assert summary.boundary_review_acknowledged is False


def test_topology_fingerprint_is_order_independent() -> None:
    assert controller_topology_fingerprint(("a", "b")) == controller_topology_fingerprint(
        ("b", "a", "a")
    )


def test_malformed_persisted_controller_ids_fail_closed() -> None:
    summary = build_ownership_commissioning_summary(
        controller_ids=("controller-1",),
        stored=_stored(controller_ids=123),
    )
    assert summary.status is OwnershipCommissioningStatus.STALE_TOPOLOGY
    assert summary.ownership_confirmed is False
