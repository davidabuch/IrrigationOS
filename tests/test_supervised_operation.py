"""Tests for the bounded supervised operational watering boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from custom_components.irrigationos.controllers.models import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
    ObservationMetadata,
    ObservationQuality,
    VendorBinding,
)
from custom_components.irrigationos.first_live_delivery.acceptance import (
    FirstLiveAcceptanceStatus,
)
from custom_components.irrigationos.health import IrrigationOSHealthState
from custom_components.irrigationos.supervised_operation.audit import (
    JsonlSupervisedOperationAuditSink,
    build_audit_event,
    new_operation_id,
)
from custom_components.irrigationos.supervised_operation.operator import (
    SUPERVISED_OPERATION_CONFIRMATION,
    evaluate_supervised_operation_blockers,
)


def _coordinator(*, accepted_slot: int = 2, active_sessions: tuple[object, ...] = ()) -> Any:
    now = datetime.now(UTC)
    area = IrrigationArea(
        area_id="canonical-area-2",
        controller_id="canonical-controller-1",
        slot_number=2,
        name="Area 2",
        enabled=True,
        configured=True,
        state=IrrigationAreaState.IDLE,
        binding=VendorBinding(provider="rachio", native_id="native-zone-secret"),
        vendor_name="Zone 2",
    )
    controller = IrrigationController(
        controller_id="canonical-controller-1",
        binding=VendorBinding(provider="rachio", native_id="native-controller-secret"),
        name="Controller",
        availability=ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number=None,
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=16,
        watering_observation_quality=ObservationQuality.CONFIRMED,
        capabilities=ControllerCapabilities(observe_current_watering=True),
        areas=(area,),
    )
    snapshot = ControllerRegistrySnapshot(
        provider="rachio",
        account_id="account",
        account_name=None,
        controllers=(controller,),
        observation=ObservationMetadata(
            observed_at=now,
            fresh_until=now + timedelta(minutes=5),
            source="polling",
            quality=ObservationQuality.CONFIRMED,
        ),
    )
    return SimpleNamespace(
        data=snapshot,
        health_assessment=SimpleNamespace(state=IrrigationOSHealthState.HEALTHY),
        ownership_commissioning=SimpleNamespace(
            summary=SimpleNamespace(
                ownership_confirmed=True,
                boundary_review_acknowledged=True,
            )
        ),
        observation_history=SimpleNamespace(active_sessions=active_sessions),
        live_commissioning=SimpleNamespace(
            summary=SimpleNamespace(supervised_safety_prerequisites_met=True)
        ),
        first_live_acceptance=SimpleNamespace(
            status=FirstLiveAcceptanceStatus.PASS,
            latest=SimpleNamespace(controller_slot=1, area_slot=accepted_slot),
            last_persistence_error=None,
        ),
    )


def _blockers(coordinator: Any, **overrides: object) -> tuple[str, ...]:
    values: dict[str, object] = {
        "controller_slot": 1,
        "area_slot": 2,
        "runtime_seconds": 30,
        "confirmation": SUPERVISED_OPERATION_CONFIRMATION,
    }
    values.update(overrides)
    return evaluate_supervised_operation_blockers(coordinator, **values)  # type: ignore[arg-type]


def test_supervised_operation_happy_path_has_no_blockers() -> None:
    assert _blockers(_coordinator()) == ()


def test_supervised_operation_requires_exact_confirmation() -> None:
    blockers = _blockers(_coordinator(), confirmation="RUN SOMETHING ELSE")
    assert "operator_confirmation_mismatch" in blockers


def test_supervised_operation_requires_accepted_first_live_evidence() -> None:
    coordinator = _coordinator()
    coordinator.first_live_acceptance.status = FirstLiveAcceptanceStatus.NOT_AVAILABLE
    blockers = _blockers(coordinator)
    assert "accepted_first_live_evidence_required" in blockers


def test_supervised_operation_is_limited_to_validated_target() -> None:
    blockers = _blockers(_coordinator(accepted_slot=3))
    assert "target_not_first_live_validated" in blockers



def test_supervised_operation_requires_current_integrated_safety() -> None:
    coordinator = _coordinator()
    coordinator.live_commissioning.summary.supervised_safety_prerequisites_met = False
    blockers = _blockers(coordinator)
    assert "supervised_safety_prerequisites_not_met" in blockers

def test_supervised_operation_blocks_existing_watering() -> None:
    blockers = _blockers(_coordinator(active_sessions=(object(),)))
    assert "active_watering_conflict" in blockers


def test_supervised_operation_audit_is_privacy_safe(tmp_path: Path) -> None:
    path = tmp_path / "supervised_operation_audit.jsonl"
    operation_id = new_operation_id()
    sink = JsonlSupervisedOperationAuditSink(path)
    event = build_audit_event(
        operation_id=operation_id,
        event_type="dispatch_intent",
        recorded_at=datetime.now(UTC),
        controller_slot=1,
        area_slot=2,
        runtime_seconds=30,
        detail_code="supervised_operational_start",
    )
    assert asyncio.run(sink.async_record(event)) is True
    content = path.read_text(encoding="utf-8")
    assert operation_id in content
    assert "native-zone-secret" not in content
    assert "native-controller-secret" not in content
