"""Operator-facing health evaluation for IrrigationOS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

STARTUP_HEALTH_GRACE = timedelta(minutes=6)
STALE_OBSERVATION_THRESHOLD = timedelta(minutes=12)
CONTROLLER_UNAVAILABLE_THRESHOLD = timedelta(minutes=10)
HEALTH_REEVALUATION_INTERVAL = timedelta(minutes=1)
HEALTH_STORE_VERSION = 1
HEALTH_LOG_RETENTION_DAYS = 30


class IrrigationOSHealthState(StrEnum):
    """Operator-facing aggregate IrrigationOS health state."""

    INITIALIZING = "INITIALIZING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True, slots=True)
class HealthAssessment:
    """Immutable aggregate health assessment."""

    state: IrrigationOSHealthState
    reason: str
    reason_codes: tuple[str, ...]
    affected_components: tuple[str, ...]
    startup_grace_active: bool
    observation_age_seconds: int | None
    polling_healthy: bool
    realtime_healthy: bool
    controller_count: int
    online_controller_count: int
    unavailable_controller_count: int
    pipeline_available: bool
    operational_log_healthy: bool
    persistence_healthy: bool

    def as_dict(self) -> dict[str, object]:
        """Return a serialization-safe health snapshot."""

        return {
            "state": self.state.value,
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "affected_components": list(self.affected_components),
            "startup_grace_active": self.startup_grace_active,
            "observation_age_seconds": self.observation_age_seconds,
            "polling_healthy": self.polling_healthy,
            "realtime_healthy": self.realtime_healthy,
            "controller_count": self.controller_count,
            "online_controller_count": self.online_controller_count,
            "unavailable_controller_count": self.unavailable_controller_count,
            "pipeline_available": self.pipeline_available,
            "operational_log_healthy": self.operational_log_healthy,
            "persistence_healthy": self.persistence_healthy,
        }


def evaluate_health(
    *,
    now: datetime,
    started_at: datetime,
    last_successful_refresh: datetime | None,
    last_update_success: bool,
    realtime_healthy: bool,
    controller_count: int,
    online_controller_count: int,
    all_controllers_unavailable_since: datetime | None,
    pipeline_available: bool,
    operational_log_healthy: bool,
    persistence_healthy: bool,
) -> HealthAssessment:
    """Return aggregate health without mutating coordinator state."""

    startup_grace_active = now < started_at + STARTUP_HEALTH_GRACE
    observation_age_seconds = (
        None
        if last_successful_refresh is None
        else max(0, round((now - last_successful_refresh).total_seconds()))
    )
    unavailable_controller_count = max(0, controller_count - online_controller_count)

    if startup_grace_active:
        return HealthAssessment(
            state=IrrigationOSHealthState.INITIALIZING,
            reason="IrrigationOS is allowing Home Assistant and observation paths to initialize.",
            reason_codes=("startup_grace",),
            affected_components=("lifecycle",),
            startup_grace_active=True,
            observation_age_seconds=observation_age_seconds,
            polling_healthy=bool(last_update_success),
            realtime_healthy=realtime_healthy,
            controller_count=controller_count,
            online_controller_count=online_controller_count,
            unavailable_controller_count=unavailable_controller_count,
            pipeline_available=pipeline_available,
            operational_log_healthy=operational_log_healthy,
            persistence_healthy=persistence_healthy,
        )

    unhealthy_codes: list[str] = []
    unhealthy_components: list[str] = []
    if last_successful_refresh is None:
        unhealthy_codes.append("no_trustworthy_observation")
        unhealthy_components.append("observation")
    elif now - last_successful_refresh > STALE_OBSERVATION_THRESHOLD:
        unhealthy_codes.append("observations_stale")
        unhealthy_components.extend(("observation", "polling"))

    if (
        controller_count > 0
        and online_controller_count == 0
        and all_controllers_unavailable_since is not None
        and now - all_controllers_unavailable_since >= CONTROLLER_UNAVAILABLE_THRESHOLD
    ):
        unhealthy_codes.append("all_controllers_unavailable")
        unhealthy_components.append("controllers")

    if last_successful_refresh is not None and not pipeline_available:
        unhealthy_codes.append("pipeline_unavailable")
        unhealthy_components.append("pipeline")

    if unhealthy_codes:
        return HealthAssessment(
            state=IrrigationOSHealthState.UNHEALTHY,
            reason=_human_reason(unhealthy_codes),
            reason_codes=tuple(dict.fromkeys(unhealthy_codes)),
            affected_components=tuple(dict.fromkeys(unhealthy_components)),
            startup_grace_active=False,
            observation_age_seconds=observation_age_seconds,
            polling_healthy=(
                False if "observations_stale" in unhealthy_codes else last_update_success
            ),
            realtime_healthy=realtime_healthy,
            controller_count=controller_count,
            online_controller_count=online_controller_count,
            unavailable_controller_count=unavailable_controller_count,
            pipeline_available=pipeline_available,
            operational_log_healthy=operational_log_healthy,
            persistence_healthy=persistence_healthy,
        )

    degraded_codes: list[str] = []
    degraded_components: list[str] = []
    if not last_update_success:
        degraded_codes.append("poll_refresh_failed")
        degraded_components.append("polling")
    if not realtime_healthy:
        degraded_codes.append("realtime_unavailable")
        degraded_components.append("realtime")
    if controller_count > 0 and online_controller_count < controller_count:
        degraded_codes.append("controller_partial_unavailable")
        degraded_components.append("controllers")
    if not operational_log_healthy:
        degraded_codes.append("operational_log_unavailable")
        degraded_components.append("logging")
    if not persistence_healthy:
        degraded_codes.append("health_persistence_unavailable")
        degraded_components.append("health_persistence")

    if degraded_codes:
        return HealthAssessment(
            state=IrrigationOSHealthState.DEGRADED,
            reason=_human_reason(degraded_codes),
            reason_codes=tuple(dict.fromkeys(degraded_codes)),
            affected_components=tuple(dict.fromkeys(degraded_components)),
            startup_grace_active=False,
            observation_age_seconds=observation_age_seconds,
            polling_healthy=last_update_success,
            realtime_healthy=realtime_healthy,
            controller_count=controller_count,
            online_controller_count=online_controller_count,
            unavailable_controller_count=unavailable_controller_count,
            pipeline_available=pipeline_available,
            operational_log_healthy=operational_log_healthy,
            persistence_healthy=persistence_healthy,
        )

    return HealthAssessment(
        state=IrrigationOSHealthState.HEALTHY,
        reason="All commissioned IrrigationOS observation paths are healthy.",
        reason_codes=(),
        affected_components=(),
        startup_grace_active=False,
        observation_age_seconds=observation_age_seconds,
        polling_healthy=True,
        realtime_healthy=True,
        controller_count=controller_count,
        online_controller_count=online_controller_count,
        unavailable_controller_count=0,
        pipeline_available=True,
        operational_log_healthy=True,
        persistence_healthy=True,
    )


def _human_reason(reason_codes: list[str]) -> str:
    """Return a concise operator-facing reason for stable reason codes."""

    labels = {
        "no_trustworthy_observation": "No trustworthy controller observation is available",
        "observations_stale": "Controller observations are stale",
        "all_controllers_unavailable": "All configured controllers remain unavailable",
        "pipeline_unavailable": "The synchronized IrrigationOS pipeline is unavailable",
        "poll_refresh_failed": "The latest controller polling refresh failed",
        "realtime_unavailable": "Realtime observation is unavailable; polling fallback is in use",
        "controller_partial_unavailable": "One or more controllers are unavailable",
        "operational_log_unavailable": "Daily operational logging is unavailable",
        "health_persistence_unavailable": "Health incident persistence is unavailable",
    }
    messages = [labels[code] for code in reason_codes if code in labels]
    return "; ".join(messages) if messages else "IrrigationOS health is impaired"
