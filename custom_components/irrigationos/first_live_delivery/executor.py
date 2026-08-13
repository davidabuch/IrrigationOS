"""Commissioned one-shot executor for the first supervised live watering trial."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..controllers.models import (
    ControllerAvailability,
    ControllerRegistrySnapshot,
    IrrigationAreaState,
)
from ..live_commissioning.manager import LiveCommissioningManager
from .audit import FirstLiveTrialAuditSink, build_audit_event, new_attempt_id
from .models import MAX_FIRST_LIVE_DELIVERY_RUNTIME_SECONDS, FirstLiveDeliveryRequest
from .rachio import FirstLiveTransportError, RachioFirstLiveTransport

FIRST_LIVE_TRIAL_EXECUTOR_REVISION = 1
MAX_EXECUTION_PREFLIGHT_AGE_SECONDS = 10.0


class FirstLiveTrialExecutionStatus(StrEnum):
    """Terminal outcome of one supervised first-live dispatch attempt."""

    START_DISPATCHED = "start_dispatched"
    BLOCKED = "blocked"
    TRANSPORT_OUTCOME_UNKNOWN = "transport_outcome_unknown"


@dataclass(frozen=True, slots=True)
class FirstLiveTrialExecutionResult:
    """Privacy-safe result of one one-shot trial execution attempt."""

    status: FirstLiveTrialExecutionStatus
    blocker_codes: tuple[str, ...]
    controller_id: str
    controller_slot: int
    area_slot: int
    runtime_seconds: int
    approval_consumed_before_dispatch: bool
    durable_outcome_recorded: bool
    retry_permitted: bool = False
    attempt_id: str | None = None


class FirstLiveTrialExecutor:
    """Execute at most one approved start after fresh target revalidation."""

    def __init__(
        self,
        *,
        commissioning: LiveCommissioningManager,
        transport: RachioFirstLiveTransport,
        audit_sink: FirstLiveTrialAuditSink,
    ) -> None:
        self._commissioning = commissioning
        self._transport = transport
        self._audit_sink = audit_sink

    async def async_execute(
        self,
        *,
        request: FirstLiveDeliveryRequest,
        snapshot: ControllerRegistrySnapshot,
    ) -> FirstLiveTrialExecutionResult:
        """Consume approval before one transport attempt; never retry automatically."""

        blockers, zone_id = _preflight(request, snapshot, self._commissioning)
        if blockers or zone_id is None:
            return FirstLiveTrialExecutionResult(
                status=FirstLiveTrialExecutionStatus.BLOCKED,
                blocker_codes=tuple(sorted(blockers)),
                controller_id=request.controller_id,
                controller_slot=request.controller_slot,
                area_slot=request.area_slot,
                runtime_seconds=request.runtime_seconds,
                approval_consumed_before_dispatch=False,
                durable_outcome_recorded=False,
            )

        attempt_id = new_attempt_id()
        intent_recorded = await self._audit_sink.async_record(
            build_audit_event(
                attempt_id=attempt_id,
                event_type="dispatch_intent",
                recorded_at=request.requested_at,
                controller_id=request.controller_id,
                controller_slot=request.controller_slot,
                area_slot=request.area_slot,
                runtime_seconds=request.runtime_seconds,
                detail_code="commissioned_first_live_start",
            )
        )
        if not intent_recorded:
            return FirstLiveTrialExecutionResult(
                status=FirstLiveTrialExecutionStatus.BLOCKED,
                blocker_codes=("durable_audit_intent_not_recorded",),
                controller_id=request.controller_id,
                controller_slot=request.controller_slot,
                area_slot=request.area_slot,
                runtime_seconds=request.runtime_seconds,
                approval_consumed_before_dispatch=False,
                durable_outcome_recorded=False,
            )

        # Ambiguous network outcomes must never leave a reusable approval behind.
        self._commissioning.consume_approval()
        try:
            await self._transport.async_start_zone(
                zone_id=zone_id,
                runtime_seconds=request.runtime_seconds,
            )
        except FirstLiveTransportError:
            outcome_recorded = await self._audit_sink.async_record(
                build_audit_event(
                    attempt_id=attempt_id, event_type="transport_outcome",
                    recorded_at=request.requested_at, controller_id=request.controller_id,
                    controller_slot=request.controller_slot, area_slot=request.area_slot,
                    runtime_seconds=request.runtime_seconds,
                    detail_code="transport_outcome_unknown",
                )
            )
            return FirstLiveTrialExecutionResult(
                status=FirstLiveTrialExecutionStatus.TRANSPORT_OUTCOME_UNKNOWN,
                blocker_codes=("transport_outcome_not_confirmed",),
                controller_id=request.controller_id,
                controller_slot=request.controller_slot,
                area_slot=request.area_slot,
                runtime_seconds=request.runtime_seconds,
                approval_consumed_before_dispatch=True,
                durable_outcome_recorded=outcome_recorded,
                attempt_id=attempt_id,
            )

        outcome_recorded = await self._audit_sink.async_record(
            build_audit_event(
                attempt_id=attempt_id, event_type="transport_outcome",
                recorded_at=request.requested_at, controller_id=request.controller_id,
                controller_slot=request.controller_slot, area_slot=request.area_slot,
                runtime_seconds=request.runtime_seconds, detail_code="start_http_accepted",
            )
        )
        return FirstLiveTrialExecutionResult(
            status=FirstLiveTrialExecutionStatus.START_DISPATCHED,
            blocker_codes=(),
            controller_id=request.controller_id,
            controller_slot=request.controller_slot,
            area_slot=request.area_slot,
            runtime_seconds=request.runtime_seconds,
            approval_consumed_before_dispatch=True,
            durable_outcome_recorded=outcome_recorded,
            attempt_id=attempt_id,
        )


def _preflight(
    request: FirstLiveDeliveryRequest,
    snapshot: ControllerRegistrySnapshot,
    commissioning: LiveCommissioningManager,
) -> tuple[set[str], str | None]:
    blockers: set[str] = set()
    summary = commissioning.summary

    if request.requested_at.tzinfo is None or request.requested_at.utcoffset() is None:
        blockers.add("request_timestamp_not_timezone_aware")
    if summary.status.value != "first_live_trial_eligible":
        blockers.add("commissioning_trial_not_eligible")
    if request.requested_at.tzinfo is not None and request.requested_at.utcoffset() is not None:
        preflight_age = (request.requested_at - summary.evaluated_at).total_seconds()
        if preflight_age < 0 or preflight_age > MAX_EXECUTION_PREFLIGHT_AGE_SECONDS:
            blockers.add("commissioning_preflight_not_current")
        if (
            summary.approval_expires_at is None
            or request.requested_at > summary.approval_expires_at
        ):
            blockers.add("commissioning_approval_expired")
    if summary.approval_consumed:
        blockers.add("commissioning_approval_consumed")
    if summary.target_controller_id != request.controller_id:
        blockers.add("approved_controller_mismatch")
    if summary.target_controller_slot != request.controller_slot:
        blockers.add("approved_controller_slot_mismatch")
    if summary.target_area_slot != request.area_slot:
        blockers.add("approved_area_slot_mismatch")
    if summary.requested_runtime_seconds != request.runtime_seconds:
        blockers.add("approved_runtime_mismatch")
    if not 1 <= request.runtime_seconds <= MAX_FIRST_LIVE_DELIVERY_RUNTIME_SECONDS:
        blockers.add("runtime_outside_first_live_delivery_limit")
    if snapshot.provider != "rachio":
        blockers.add("snapshot_provider_not_rachio")
    if not snapshot.observation.is_fresh(request.requested_at):
        blockers.add("controller_snapshot_not_fresh")
    if snapshot.observation.quality.value != "confirmed":
        blockers.add("controller_snapshot_not_confirmed")

    controller = next(
        (item for item in snapshot.controllers if item.controller_id == request.controller_id), None
    )
    if controller is None:
        blockers.add("approved_controller_not_observed")
        return blockers, None
    if controller.availability is not ControllerAvailability.ONLINE:
        blockers.add("approved_controller_not_online")
    if not controller.enabled:
        blockers.add("approved_controller_not_enabled")
    if controller.provider != "rachio":
        blockers.add("approved_controller_provider_mismatch")
    if controller.watering_observation_quality.value != "confirmed":
        blockers.add("controller_watering_state_not_confirmed")

    area = next((item for item in controller.areas if item.slot_number == request.area_slot), None)
    if area is None:
        blockers.add("approved_area_not_observed")
        return blockers, None
    if not area.configured or area.binding is None:
        blockers.add("approved_area_not_configured")
        return blockers, None
    if not area.enabled:
        blockers.add("approved_area_not_enabled")
    if area.binding.provider != "rachio":
        blockers.add("approved_area_provider_mismatch")
    if not area.binding.native_id.strip():
        blockers.add("approved_area_native_binding_invalid")
    if area.state is not IrrigationAreaState.IDLE:
        blockers.add("approved_area_not_confirmed_idle")

    return blockers, area.binding.native_id
