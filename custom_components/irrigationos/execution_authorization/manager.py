"""In-memory fail-closed execution authorization evidence manager."""

from __future__ import annotations

from datetime import UTC, datetime

from .engine import build_execution_authorization_summary


class ExecutionAuthorizationManager:
    """Maintain derived safety-gate evidence; positive authorization is never persisted."""

    def __init__(self) -> None:
        self.summary = build_execution_authorization_summary(
            evaluated_at=datetime.now(UTC),
            health_state="INITIALIZING",
            observation_age_seconds=None,
            controller_count=0,
            online_controller_count=0,
            pipeline_available=False,
            readiness_status="insufficient_evidence",
            ownership_confirmed=False,
            active_watering_session_count=0,
        )

    def consider(
        self,
        *,
        evaluated_at: datetime,
        health_state: str,
        observation_age_seconds: int | None,
        controller_count: int,
        online_controller_count: int,
        pipeline_available: bool,
        readiness_status: str,
        active_watering_session_count: int,
    ) -> None:
        """Recompute fail-closed gates from current evidence."""

        self.summary = build_execution_authorization_summary(
            evaluated_at=evaluated_at,
            health_state=health_state,
            observation_age_seconds=observation_age_seconds,
            controller_count=controller_count,
            online_controller_count=online_controller_count,
            pipeline_available=pipeline_available,
            readiness_status=readiness_status,
            ownership_confirmed=False,
            active_watering_session_count=active_watering_session_count,
        )

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe derived authorization evidence."""

        return self.summary.to_dict()
