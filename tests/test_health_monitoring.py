"""Tests for aggregate IrrigationOS operational health and daily logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tests.helpers import load_integration_module

health = load_integration_module("health")
operational_log = load_integration_module("operational_log")

HealthState = health.IrrigationOSHealthState
STARTUP_HEALTH_GRACE = health.STARTUP_HEALTH_GRACE
STALE_OBSERVATION_THRESHOLD = health.STALE_OBSERVATION_THRESHOLD
CONTROLLER_UNAVAILABLE_THRESHOLD = health.CONTROLLER_UNAVAILABLE_THRESHOLD


def _assessment(
    *,
    now: datetime,
    started_at: datetime,
    last_successful_refresh: datetime | None,
    last_update_success: bool = True,
    realtime_healthy: bool = True,
    controller_count: int = 1,
    online_controller_count: int = 1,
    all_controllers_unavailable_since: datetime | None = None,
    pipeline_available: bool = True,
    operational_log_healthy: bool = True,
    persistence_healthy: bool = True,
) -> Any:
    return health.evaluate_health(
        now=now,
        started_at=started_at,
        last_successful_refresh=last_successful_refresh,
        last_update_success=last_update_success,
        realtime_healthy=realtime_healthy,
        controller_count=controller_count,
        online_controller_count=online_controller_count,
        all_controllers_unavailable_since=all_controllers_unavailable_since,
        pipeline_available=pipeline_available,
        operational_log_healthy=operational_log_healthy,
        persistence_healthy=persistence_healthy,
    )


def test_startup_grace_suppresses_incident_classification() -> None:
    started = datetime(2026, 8, 9, 16, 0, tzinfo=UTC)
    assessment = _assessment(
        now=started + STARTUP_HEALTH_GRACE - timedelta(seconds=1),
        started_at=started,
        last_successful_refresh=None,
        last_update_success=False,
        realtime_healthy=False,
        controller_count=0,
        online_controller_count=0,
        pipeline_available=False,
    )
    assert assessment.state is HealthState.INITIALIZING
    assert assessment.reason_codes == ("startup_grace",)


def test_realtime_failure_with_healthy_polling_is_degraded() -> None:
    now = datetime(2026, 8, 9, 16, 20, tzinfo=UTC)
    assessment = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - timedelta(minutes=2),
        realtime_healthy=False,
    )
    assert assessment.state is HealthState.DEGRADED
    assert assessment.reason_codes == ("realtime_unavailable",)
    assert assessment.polling_healthy is True


def test_single_failed_poll_with_fresh_observation_is_degraded() -> None:
    now = datetime(2026, 8, 9, 16, 20, tzinfo=UTC)
    assessment = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - timedelta(minutes=6),
        last_update_success=False,
    )
    assert assessment.state is HealthState.DEGRADED
    assert "poll_refresh_failed" in assessment.reason_codes


def test_stale_observation_is_unhealthy() -> None:
    now = datetime(2026, 8, 9, 16, 20, tzinfo=UTC)
    assessment = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - STALE_OBSERVATION_THRESHOLD - timedelta(seconds=1),
        last_update_success=False,
        realtime_healthy=False,
    )
    assert assessment.state is HealthState.UNHEALTHY
    assert "observations_stale" in assessment.reason_codes


def test_all_controllers_unavailable_requires_sustained_failure() -> None:
    now = datetime(2026, 8, 9, 16, 20, tzinfo=UTC)
    recent = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - timedelta(minutes=1),
        controller_count=1,
        online_controller_count=0,
        all_controllers_unavailable_since=(
            now - CONTROLLER_UNAVAILABLE_THRESHOLD + timedelta(seconds=1)
        ),
    )
    sustained = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - timedelta(minutes=1),
        controller_count=1,
        online_controller_count=0,
        all_controllers_unavailable_since=now - CONTROLLER_UNAVAILABLE_THRESHOLD,
    )
    assert recent.state is HealthState.DEGRADED
    assert sustained.state is HealthState.UNHEALTHY
    assert "all_controllers_unavailable" in sustained.reason_codes



def test_missing_pipeline_after_trustworthy_observation_is_unhealthy() -> None:
    now = datetime(2026, 8, 9, 16, 20, tzinfo=UTC)
    assessment = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - timedelta(minutes=1),
        last_update_success=False,
        pipeline_available=False,
    )
    assert assessment.state is HealthState.UNHEALTHY
    assert "pipeline_unavailable" in assessment.reason_codes

def test_log_failure_degrades_but_does_not_make_observation_unhealthy() -> None:
    now = datetime(2026, 8, 9, 16, 20, tzinfo=UTC)
    assessment = _assessment(
        now=now,
        started_at=now - timedelta(hours=1),
        last_successful_refresh=now - timedelta(minutes=1),
        operational_log_healthy=False,
    )
    assert assessment.state is HealthState.DEGRADED
    assert assessment.reason_codes == ("operational_log_unavailable",)


def test_daily_operational_log_uses_local_day_and_safe_jsonl(tmp_path: Path) -> None:
    recorder = operational_log.DailyOperationalLog(
        tmp_path / "irrigationos_logs", ZoneInfo("America/Los_Angeles")
    )
    recorded_at = datetime(2026, 8, 10, 6, 30, tzinfo=UTC)
    assert recorder.record(
        recorded_at,
        {
            "integration_version": "1.0.17",
            "event_type": "refresh_success",
            "health_state": "HEALTHY",
            "reason_codes": [],
        },
    )
    expected = tmp_path / "irrigationos_logs" / "irrigationos_2026-08-09.jsonl"
    assert expected.is_file()
    lines = expected.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["timestamp_local"].startswith("2026-08-09T23:30:00-07:00")
    assert payload["timestamp_utc"].startswith("2026-08-10T06:30:00+00:00")
    assert payload["event_type"] == "refresh_success"
    assert "api_key" not in payload


def test_daily_operational_log_retains_only_thirty_local_days(tmp_path: Path) -> None:
    root = tmp_path / "irrigationos_logs"
    root.mkdir()
    old = root / "irrigationos_2026-07-01.jsonl"
    kept = root / "irrigationos_2026-07-12.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    kept.write_text("{}\n", encoding="utf-8")
    recorder = operational_log.DailyOperationalLog(root, ZoneInfo("America/Los_Angeles"))
    assert recorder.record(
        datetime(2026, 8, 10, 7, 0, tzinfo=UTC),
        {"event_type": "retention_test"},
    )
    assert not old.exists()
    assert kept.exists()


def test_health_monitoring_has_no_irrigation_actuation_path() -> None:
    root = Path(__file__).resolve().parents[1] / "custom_components" / "irrigationos"
    source = "\n".join(
        (root / name).read_text(encoding="utf-8")
        for name in ("health.py", "operational_log.py", "button.py")
    )
    for forbidden in (
        "async_start_area",
        "async_stop_area",
        "async_stop_all",
        "async_set_rain_delay",
        "hass.services.async_call",
    ):
        assert forbidden not in source
