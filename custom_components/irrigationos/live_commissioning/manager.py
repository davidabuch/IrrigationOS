"""Ephemeral single-use first-live commissioning protocol manager."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from .engine import build_live_commissioning_summary
from .models import APPROVAL_TTL_SECONDS, FirstLiveTrialApproval, LiveCommissioningSummary


class LiveCommissioningManager:
    """Hold restart-unsafe approval evidence without dispatching controller commands."""

    def __init__(self) -> None:
        self._approval: FirstLiveTrialApproval | None = None
        self._commissioning_window_open = False
        self.summary: LiveCommissioningSummary = build_live_commissioning_summary(
            integrated_review_status="blocked",
            approval=None,
            evaluated_at=datetime.now(UTC),
            health_state="initializing",
            observation_age_seconds=None,
            active_external_watering_count=0,
            commissioning_window_open=False,
        )

    def approve_trial(
        self,
        *,
        controller_id: str,
        controller_slot: int,
        area_slot: int,
        requested_runtime_seconds: int,
        approved_at: datetime,
        supervised_daytime: bool,
    ) -> None:
        """Create one ephemeral approval; intentionally do not persist it."""

        if approved_at.tzinfo is None or approved_at.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")
        self._approval = FirstLiveTrialApproval(
            controller_id=controller_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            requested_runtime_seconds=requested_runtime_seconds,
            approved_at=approved_at,
            expires_at=approved_at + timedelta(seconds=APPROVAL_TTL_SECONDS),
            supervised_daytime=supervised_daytime,
        )

    def set_supervised_commissioning_window(self, *, open_window: bool) -> None:
        """Set an in-memory supervised commissioning window; never persist it."""

        self._commissioning_window_open = bool(open_window)

    def consume_approval(self) -> None:
        """Make the current approval permanently unusable within this process."""

        if self._approval is not None:
            self._approval = replace(self._approval, consumed=True)

    def revoke_approval(self) -> None:
        """Remove any pending approval immediately."""

        self._approval = None
        self._commissioning_window_open = False

    def consider(
        self,
        *,
        integrated_review_status: str,
        evaluated_at: datetime,
        health_state: str,
        observation_age_seconds: float | None,
        active_external_watering_count: int,
    ) -> None:
        """Re-evaluate commissioning eligibility against current safety evidence."""

        self.summary = build_live_commissioning_summary(
            integrated_review_status=integrated_review_status,
            approval=self._approval,
            evaluated_at=evaluated_at,
            health_state=health_state,
            observation_age_seconds=observation_age_seconds,
            active_external_watering_count=active_external_watering_count,
            commissioning_window_open=self._commissioning_window_open,
        )

    def diagnostics(self) -> dict[str, object]:
        """Return operator-safe commissioning evidence."""

        return self.summary.to_dict()
