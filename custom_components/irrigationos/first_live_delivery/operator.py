"""Interactive Home Assistant operator boundary for one supervised live trial."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import CONF_API_KEY
from ..coordinator import IrrigationOSCoordinator
from .audit import JsonlFirstLiveTrialAuditSink
from .executor import FirstLiveTrialExecutionResult, FirstLiveTrialExecutor
from .models import FirstLiveDeliveryRequest
from .monitor import async_monitor_first_live_acceptance
from .rachio import RachioFirstLiveTransport

FIRST_LIVE_OPERATOR_CONFIRMATION = "RUN SUPERVISED FIRST LIVE TRIAL"
FIRST_LIVE_OPERATOR_REVISION = 1


async def async_run_supervised_first_live_trial(
    coordinator: IrrigationOSCoordinator,
    *,
    controller_id: str,
    area_slot: int,
    runtime_seconds: int,
    confirmation: str,
) -> FirstLiveTrialExecutionResult:
    """Run one interactive trial after a fresh commissioning re-evaluation."""

    if confirmation.strip() != FIRST_LIVE_OPERATOR_CONFIRMATION:
        raise ValueError("operator_confirmation_mismatch")

    controller_slot = _controller_slot(coordinator, controller_id)
    approved_at = datetime.now(UTC)
    coordinator.live_commissioning.set_supervised_commissioning_window(open_window=True)
    coordinator.live_commissioning.approve_trial(
        controller_id=controller_id,
        controller_slot=controller_slot,
        area_slot=area_slot,
        requested_runtime_seconds=runtime_seconds,
        approved_at=approved_at,
        supervised_daytime=True,
    )
    try:
        await coordinator.async_request_refresh()
        request = FirstLiveDeliveryRequest(
            controller_id=controller_id,
            controller_slot=controller_slot,
            area_slot=area_slot,
            runtime_seconds=runtime_seconds,
            requested_at=datetime.now(UTC),
        )
        log_path = Path(
            coordinator.hass.config.path(
                "irrigationos_logs",
                "first_live_trial_audit.jsonl",
            )
        )
        executor = FirstLiveTrialExecutor(
            commissioning=coordinator.live_commissioning,
            transport=RachioFirstLiveTransport(
                async_get_clientsession(coordinator.hass),
                str(coordinator.entry.data[CONF_API_KEY]),
            ),
            audit_sink=JsonlFirstLiveTrialAuditSink(log_path),
        )
        result = await executor.async_execute(request=request, snapshot=coordinator.data)
        if result.status.value == "start_dispatched" and result.attempt_id is not None:
            coordinator.hass.async_create_task(
                async_monitor_first_live_acceptance(
                    coordinator=coordinator,
                    audit_sink=JsonlFirstLiveTrialAuditSink(log_path),
                    acceptance=coordinator.first_live_acceptance,
                    validated_targets=coordinator.validated_targets,
                    attempt_id=result.attempt_id,
                    controller_id=controller_id,
                    controller_slot=controller_slot,
                    area_slot=area_slot,
                    runtime_seconds=runtime_seconds,
                    dispatched_at=request.requested_at,
                ),
                "IrrigationOS supervised first-live acceptance monitor",
            )
        return result
    finally:
        coordinator.live_commissioning.revoke_approval()


def _controller_slot(coordinator: IrrigationOSCoordinator, controller_id: str) -> int:
    for index, controller in enumerate(coordinator.data.controllers, start=1):
        if controller.controller_id == controller_id:
            return index
    raise ValueError("controller_not_observed")
