"""Behavioral tests for canonical watering-session observation history."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tests.helpers import load_integration_module

CONTROLLERS = load_integration_module("controllers.models")
MODELS = load_integration_module("observation_history.models")
RECONCILIATION = load_integration_module("observation_history.reconciliation")
SESSION_LOG = load_integration_module("observation_history.session_log")

START = datetime(2026, 8, 9, 23, 55, tzinfo=UTC)


def _snapshot(
    observed_at: datetime,
    states: tuple[Any, ...],
    *,
    availability: Any = None,
    watering_quality: Any = None,
    snapshot_quality: Any = None,
) -> Any:
    areas = tuple(
        CONTROLLERS.IrrigationArea(
            area_id=f"controller_test:slot:{slot}",
            controller_id="controller_test",
            slot_number=slot,
            name=f"Zone {slot}",
            enabled=True,
            configured=True,
            state=state,
            binding=CONTROLLERS.VendorBinding("test", f"provider-zone-{slot}"),
            vendor_name=f"Safe Area {slot}",
        )
        for slot, state in enumerate(states, start=1)
    )
    controller = CONTROLLERS.IrrigationController(
        controller_id="controller_test",
        binding=CONTROLLERS.VendorBinding("test", "provider-controller-secret"),
        name="Test Controller",
        availability=availability or CONTROLLERS.ControllerAvailability.ONLINE,
        enabled=True,
        model=None,
        serial_number="serial-secret",
        firmware_version=None,
        latitude=None,
        longitude=None,
        capacity=len(areas),
        watering_observation_quality=(
            watering_quality or CONTROLLERS.ObservationQuality.CONFIRMED
        ),
        capabilities=CONTROLLERS.ControllerCapabilities(observe_current_watering=True),
        areas=areas,
    )
    return CONTROLLERS.ControllerRegistrySnapshot(
        provider="test",
        account_id="provider-account-secret",
        account_name=None,
        controllers=(controller,),
        observation=CONTROLLERS.ObservationMetadata(
            observed_at=observed_at,
            fresh_until=observed_at + timedelta(minutes=10),
            source="test",
            quality=snapshot_quality or CONTROLLERS.ObservationQuality.CONFIRMED,
        ),
    )


def _context(
    observed_at: datetime,
    source: Any = None,
) -> Any:
    return RECONCILIATION.SessionObservationContext(
        observed_at=observed_at,
        source=source or MODELS.WateringObservationSource.POLLING,
    )


def _open_session(
    *,
    source: Any = None,
) -> tuple[Any, Any]:
    reconciler = RECONCILIATION.WateringSessionReconciler()
    events = reconciler.reconcile(
        _snapshot(START, (CONTROLLERS.IrrigationAreaState.WATERING,)),
        _context(START, source),
    )
    assert len(events) == 1
    return reconciler, events[0].session


def test_idle_watering_watering_idle_reconciles_one_session() -> None:
    """Transitions open, update, and close one stable logical session."""
    reconciler = RECONCILIATION.WateringSessionReconciler()
    assert reconciler.reconcile(
        _snapshot(START, (CONTROLLERS.IrrigationAreaState.IDLE,)),
        _context(START),
    ) == ()

    started_at = START + timedelta(minutes=5)
    started = reconciler.reconcile(
        _snapshot(started_at, (CONTROLLERS.IrrigationAreaState.WATERING,)),
        _context(started_at),
    )
    assert started[0].event_type is MODELS.WateringSessionEventType.SESSION_STARTED
    session_id = started[0].session.session_id
    assert len(reconciler.active_sessions) == 1

    updated_at = START + timedelta(minutes=10)
    updated = reconciler.reconcile(
        _snapshot(updated_at, (CONTROLLERS.IrrigationAreaState.WATERING,)),
        _context(updated_at),
    )
    assert updated[0].event_type is MODELS.WateringSessionEventType.SESSION_UPDATED
    assert updated[0].session.session_id == session_id
    assert len(reconciler.active_sessions) == 1

    stopped_at = START + timedelta(minutes=15)
    closed = reconciler.reconcile(
        _snapshot(stopped_at, (CONTROLLERS.IrrigationAreaState.IDLE,)),
        _context(stopped_at),
    )
    assert closed[0].event_type is MODELS.WateringSessionEventType.SESSION_CLOSED
    assert closed[0].session.session_id == session_id
    assert closed[0].session.duration_seconds == 600
    assert closed[0].session.ended_at == stopped_at
    assert reconciler.active_sessions == ()
    assert len(reconciler.completed_sessions) == 1


def test_simultaneous_zones_keep_independent_sessions() -> None:
    """Concurrent canonical slots never overwrite or merge each other."""
    reconciler = RECONCILIATION.WateringSessionReconciler()
    events = reconciler.reconcile(
        _snapshot(
            START,
            (
                CONTROLLERS.IrrigationAreaState.WATERING,
                CONTROLLERS.IrrigationAreaState.WATERING,
            ),
        ),
        _context(START),
    )
    assert len(events) == 2
    assert {session.slot_number for session in reconciler.active_sessions} == {1, 2}
    assert len({session.session_id for session in reconciler.active_sessions}) == 2


def test_polling_and_realtime_preserve_precision_without_false_attribution() -> None:
    """Observation source changes precision but never invents watering ownership."""
    _polling_reconciler, polling = _open_session()
    assert polling.timestamp_precision is MODELS.WateringTimestampPrecision.POLLING_WINDOW
    assert polling.incomplete is True
    assert polling.attribution is MODELS.WateringAttribution.EXTERNAL_UNKNOWN
    assert polling.attribution_confidence == 0
    assert "polling_boundary_inexact" in polling.attribution_evidence

    _realtime_reconciler, realtime = _open_session(
        source=MODELS.WateringObservationSource.REALTIME_REFRESH
    )
    assert realtime.timestamp_precision is MODELS.WateringTimestampPrecision.EVENT_BOUNDED
    assert realtime.incomplete is False
    assert realtime.attribution is MODELS.WateringAttribution.EXTERNAL_UNKNOWN
    assert "realtime_event_not_ownership_evidence" in realtime.attribution_evidence
    assert realtime.attribution is not MODELS.WateringAttribution.PROVIDER_SCHEDULE
    assert realtime.attribution is not MODELS.WateringAttribution.MANUAL
    assert realtime.attribution is not MODELS.WateringAttribution.IRRIGATIONOS


@pytest.mark.parametrize(
    ("availability", "quality", "state"),
    (
        (
            CONTROLLERS.ControllerAvailability.ONLINE,
            CONTROLLERS.ObservationQuality.UNAVAILABLE,
            CONTROLLERS.IrrigationAreaState.UNKNOWN,
        ),
        (
            CONTROLLERS.ControllerAvailability.OFFLINE,
            CONTROLLERS.ObservationQuality.CONFIRMED,
            CONTROLLERS.IrrigationAreaState.IDLE,
        ),
    ),
)
def test_unavailable_or_offline_observation_does_not_falsely_close(
    availability: Any,
    quality: Any,
    state: Any,
) -> None:
    """Only a trustworthy non-watering observation can close an active session."""
    reconciler, session = _open_session()
    events = reconciler.reconcile(
        _snapshot(
            START + timedelta(minutes=5),
            (state,),
            availability=availability,
            watering_quality=quality,
        ),
        _context(START + timedelta(minutes=5)),
    )
    assert events[0].event_type is MODELS.WateringSessionEventType.SESSION_RECONCILED
    assert reconciler.active_sessions[0].session_id == session.session_id
    assert reconciler.active_sessions[0].incomplete is True
    assert reconciler.active_sessions[0].observation_quality is (
        CONTROLLERS.ObservationQuality.PARTIAL
    )


def test_missing_controller_preserves_active_session_as_uncertain() -> None:
    """Removed or unavailable hardware cannot create a false stop boundary."""
    reconciler, session = _open_session()
    observed_at = START + timedelta(minutes=5)
    empty = CONTROLLERS.ControllerRegistrySnapshot(
        provider="test",
        account_id="secret",
        account_name=None,
        controllers=(),
        observation=CONTROLLERS.ObservationMetadata(
            observed_at=observed_at,
            fresh_until=observed_at + timedelta(minutes=10),
            source="test",
            quality=CONTROLLERS.ObservationQuality.PARTIAL,
        ),
    )
    reconciler.reconcile(empty, _context(observed_at))
    assert reconciler.active_sessions[0].session_id == session.session_id
    assert reconciler.active_sessions[0].incomplete is True


def test_restart_reconstruction_continues_or_closes_same_session() -> None:
    """Persisted active evidence survives restart without duplicate logical sessions."""
    _original, session = _open_session()
    restored = session.reconstructed()
    continued = RECONCILIATION.WateringSessionReconciler(active_sessions=(restored,))
    event = continued.reconcile(
        _snapshot(
            START + timedelta(minutes=5),
            (CONTROLLERS.IrrigationAreaState.WATERING,),
        ),
        _context(START + timedelta(minutes=5)),
    )[0]
    assert event.event_type is MODELS.WateringSessionEventType.SESSION_RECONCILED
    assert event.session.session_id == session.session_id
    assert event.session.reconstructed_after_restart is True
    assert len(continued.active_sessions) == 1

    stopped = RECONCILIATION.WateringSessionReconciler(active_sessions=(restored,))
    closed = stopped.reconcile(
        _snapshot(
            START + timedelta(minutes=5),
            (CONTROLLERS.IrrigationAreaState.IDLE,),
        ),
        _context(START + timedelta(minutes=5)),
    )[0].session
    assert closed.session_id == session.session_id
    assert closed.reconstructed_after_restart is True
    assert closed.incomplete is True
    assert stopped.active_sessions == ()


def test_session_model_is_immutable_and_persistence_round_trips() -> None:
    """Canonical session snapshots restore deterministically without vendor payloads."""
    _reconciler, session = _open_session()
    assert MODELS.WateringSession.from_dict(session.to_dict()) == session
    assert session.to_dict() == session.to_dict()
    with pytest.raises(FrozenInstanceError):
        session.__setattr__("area_name", "Changed")


def test_active_session_crosses_local_midnight_without_splitting() -> None:
    """Local calendar rollover never creates a second logical session."""
    started_at = datetime(2026, 8, 10, 6, 55, tzinfo=UTC)  # 23:55 PDT
    reconciler = RECONCILIATION.WateringSessionReconciler()
    started = reconciler.reconcile(
        _snapshot(started_at, (CONTROLLERS.IrrigationAreaState.WATERING,)),
        _context(started_at),
    )[0].session
    after_midnight = started_at + timedelta(minutes=10)
    reconciler.reconcile(
        _snapshot(after_midnight, (CONTROLLERS.IrrigationAreaState.WATERING,)),
        _context(after_midnight),
    )
    assert len(reconciler.active_sessions) == 1
    assert reconciler.active_sessions[0].session_id == started.session_id
    closed_at = started_at + timedelta(minutes=15)
    closed = reconciler.reconcile(
        _snapshot(closed_at, (CONTROLLERS.IrrigationAreaState.IDLE,)),
        _context(closed_at),
    )[0].session
    assert closed.session_id == started.session_id
    assert closed.duration_seconds == 900


def test_session_log_rolls_local_midnight_and_retains_thirty_days(
    tmp_path: Path,
) -> None:
    """Session evidence uses independent local-day files and 30-day cleanup."""
    root = tmp_path / "irrigationos_logs"
    root.mkdir()
    old = root / "irrigationos_sessions_2026-07-01.jsonl"
    kept = root / "irrigationos_sessions_2026-07-12.jsonl"
    health_log = root / "irrigationos_2026-07-01.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    kept.write_text("{}\n", encoding="utf-8")
    health_log.write_text("{}\n", encoding="utf-8")
    recorder = SESSION_LOG.DailyWateringSessionLog(
        root, ZoneInfo("America/Los_Angeles")
    )
    payload = {
        "event_type": "session_started",
        "session_id": "session.safe",
        "slot_number": 1,
        "area_name": "Safe Area",
    }
    assert recorder.record(datetime(2026, 8, 10, 6, 59, tzinfo=UTC), payload)
    assert recorder.record(datetime(2026, 8, 10, 7, 1, tzinfo=UTC), payload)
    first = root / "irrigationos_sessions_2026-08-09.jsonl"
    second = root / "irrigationos_sessions_2026-08-10.jsonl"
    assert first.is_file()
    assert second.is_file()
    record = json.loads(first.read_text(encoding="utf-8").splitlines()[0])
    assert record["timestamp_local"].startswith("2026-08-09T23:59")
    assert not old.exists()
    assert kept.exists()
    assert health_log.exists()


def test_safe_session_evidence_has_no_sensitive_provider_identifiers(
    tmp_path: Path,
) -> None:
    """Canonical summaries and session JSONL omit all native provider identifiers."""
    _reconciler, session = _open_session()
    summary = MODELS.safe_session_summary(session)
    assert "controller_id" not in summary
    assert "area_id" not in summary
    serialized = json.dumps(summary, sort_keys=True)
    for secret in (
        "provider-zone",
        "provider-controller",
        "provider-account",
        "serial-secret",
        "api_key",
        "webhook",
        "signature",
    ):
        assert secret not in serialized


def test_observation_history_has_no_actuation_path() -> None:
    """Session/history modules remain strictly observational."""
    root = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "irrigationos"
        / "observation_history"
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    for forbidden in (
        "async_start_area",
        "async_stop_area",
        "async_stop_all",
        "async_set_rain_delay",
        "hass.services.async_call",
        "controller_command",
    ):
        assert forbidden not in source
