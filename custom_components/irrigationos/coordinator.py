"""Data coordinator for IrrigationOS."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .actual_vs_shadow.manager import ActualVsShadowReconciliationManager
from .adapters.factory import DEFAULT_PROVIDER_FACTORY, ControllerProviderFactory
from .command_acknowledgements.manager import CommandAcknowledgementManager
from .command_receipts.manager import CommandReceiptManager
from .commissioning_report.manager import CommissioningReportManager
from .const import (
    CONF_API_KEY,
    CONF_AREA_PROFILES,
    CONF_CONTROLLER_PROVIDER,
    CONF_IDENTITY_REGISTRY,
    CONF_PERSON_ID,
    DOMAIN,
    EVENT_HEALTH_RECOVERED,
    EVENT_HEALTH_UNHEALTHY,
    UPDATE_INTERVAL_MINUTES,
    VERSION,
)
from .controllers import (
    ControllerAuthenticationError,
    ControllerAvailability,
    ControllerIdentityRegistry,
    ControllerProviderError,
    ControllerRateLimitError,
    ControllerRegistrySnapshot,
)
from .execution_authorization.manager import ExecutionAuthorizationManager
from .health import (
    HEALTH_REEVALUATION_INTERVAL,
    HEALTH_STORE_VERSION,
    HealthAssessment,
    IrrigationOSHealthState,
    evaluate_health,
)
from .integrated_safety_review.manager import IntegratedSafetyReviewManager
from .landscape import LandscapeProfile, build_landscape_profile
from .live_mode_safety.manager import LiveModeSafetyManager
from .manual_override_preservation.manager import ManualOverridePreservationManager
from .observation_history import (
    SessionObservationContext,
    WateringObservationSource,
)
from .observation_history.manager import WateringSessionHistoryManager
from .operational_log import DailyOperationalLog
from .ownership_commissioning.manager import OwnershipCommissioningManager
from .pipeline import PipelineEvaluation, build_pipeline_evaluation
from .replay_readiness.manager import ReplayReadinessManager
from .safety_preemption.manager import SafetyPreemptionManager
from .scientific_inputs import build_scientific_input_snapshot
from .shadow_evaluation import ShadowEvaluationReason
from .shadow_evaluation.manager import ShadowEvaluationManager
from .sunrise_hard_stop.manager import SunriseHardStopManager

if TYPE_CHECKING:
    from .realtime import RealtimeObservationManager

_LOGGER = logging.getLogger(__name__)


class IrrigationOSCoordinator(DataUpdateCoordinator[ControllerRegistrySnapshot]):
    """Coordinate read-only observations, health, and the Landscape Digital Twin."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        provider_factory: ControllerProviderFactory = DEFAULT_PROVIDER_FACTORY,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.landscape = LandscapeProfile(schema_version=1, areas=())
        self.last_successful_refresh: datetime | None = None
        self.pipeline_evaluation: PipelineEvaluation | None = None
        self.refresh_count = 0
        self.realtime: RealtimeObservationManager | None = None
        self.identities = ControllerIdentityRegistry.from_dict(
            entry.data.get(CONF_IDENTITY_REGISTRY)
        )
        self.adapter = provider_factory.create(
            str(entry.data[CONF_CONTROLLER_PROVIDER]),
            async_get_clientsession(hass),
            str(entry.data[CONF_API_KEY]),
            self.identities,
        )

        self._started_at = datetime.now(UTC)
        self._health_snapshot: ControllerRegistrySnapshot | None = None
        self._all_controllers_unavailable_since: datetime | None = None
        self._health_assessment = evaluate_health(
            now=self._started_at,
            started_at=self._started_at,
            last_successful_refresh=None,
            last_update_success=False,
            realtime_healthy=False,
            controller_count=0,
            online_controller_count=0,
            all_controllers_unavailable_since=None,
            pipeline_available=False,
            operational_log_healthy=True,
            persistence_healthy=True,
        )
        self._health_tick_unsubscribe: Callable[[], None] | None = None
        self._health_store = Store[dict[str, Any]](
            hass, HEALTH_STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.health"
        )
        self._persistence_healthy = True
        self._operational_log_healthy = True
        self._polling_healthy = False
        log_root = Path(hass.config.path("irrigationos_logs"))
        local_timezone = ZoneInfo(hass.config.time_zone)
        self.operational_log = DailyOperationalLog(log_root, local_timezone)
        self.observation_history = WateringSessionHistoryManager(
            hass,
            entry.entry_id,
            log_root,
            local_timezone,
        )
        self.shadow_evaluations = ShadowEvaluationManager(
            hass, entry.entry_id, log_root, local_timezone
        )
        self.actual_vs_shadow = ActualVsShadowReconciliationManager(
            hass, entry.entry_id, log_root, local_timezone
        )
        self.commissioning_report = CommissioningReportManager()
        self.command_acknowledgements = CommandAcknowledgementManager(hass, log_root)
        self.command_receipts = CommandReceiptManager(hass, log_root)
        self.execution_authorization = ExecutionAuthorizationManager()
        self.live_mode_safety = LiveModeSafetyManager()
        self.integrated_safety_review = IntegratedSafetyReviewManager(
            self.live_mode_safety.summary
        )
        self.manual_override_preservation = ManualOverridePreservationManager(
            hass, log_root, self.command_acknowledgements
        )
        self.safety_preemption = SafetyPreemptionManager(
            hass, log_root, self.command_acknowledgements
        )
        self.sunrise_hard_stop = SunriseHardStopManager(
            hass, log_root, self.command_acknowledgements
        )
        self.ownership_commissioning = OwnershipCommissioningManager(hass, entry.entry_id)
        self.replay_readiness = ReplayReadinessManager()
        self._shadow_nightly_unsubscribe: Callable[[], None] | None = None
        self._force_next_shadow_reason: ShadowEvaluationReason | None = None
        self._next_observation_context: tuple[
            WateringObservationSource, str | None, str | None
        ] | None = None

        self._health_tracking_since = self._started_at
        self._incident_latched = False
        self._incident_active = False
        self._incident_started_at: datetime | None = None
        self._last_unhealthy_at: datetime | None = None
        self._last_recovery_at: datetime | None = None
        self._last_incident_duration_seconds: int | None = None
        self._incident_reason_codes: tuple[str, ...] = ()
        self._incident_affected_components: tuple[str, ...] = ()

    async def async_initialize_health(self) -> None:
        """Restore persistent health incident history and initialize daily logging."""

        try:
            stored = await self._health_store.async_load()
        except Exception:  # Storage failures must not prevent observation startup.
            stored = None
            self._persistence_healthy = False
            _LOGGER.exception("Unable to load IrrigationOS health incident state")
        if isinstance(stored, dict):
            self._restore_health_state(stored)
        await self._write_operational_event("integration_starting")

    async def async_initialize_ownership_commissioning(self) -> None:
        """Restore explicit operator ownership commissioning decisions."""

        await self.ownership_commissioning.async_initialize()

    async def async_initialize_observation_history(self) -> None:
        """Restore restart-safe command and observation evidence before refresh."""

        await self.command_acknowledgements.async_initialize(now=datetime.now(UTC))
        await self.observation_history.async_initialize()
        await self.shadow_evaluations.async_initialize()
        shadow_records = await self.shadow_evaluations.async_load_records()
        await self.actual_vs_shadow.async_initialize(
            shadow_records,
            self.observation_history.completed_sessions,
            now=datetime.now(UTC),
            observation_quality=None,
        )
        reconciliation_records = await self.actual_vs_shadow.async_load_records()
        self.commissioning_report.initialize(shadow_records, reconciliation_records)
        self.replay_readiness.initialize(
            reconciliation_records, self.commissioning_report.summary
        )

    async def async_start_health_monitoring(self) -> None:
        """Start non-network health reevaluation after realtime setup completes."""

        if self._health_tick_unsubscribe is None:
            self._health_tick_unsubscribe = async_track_time_interval(
                self.hass,
                self._async_health_tick,
                HEALTH_REEVALUATION_INTERVAL,
            )
        await self.async_update_health("startup_complete")
        if self._shadow_nightly_unsubscribe is None:
            self._shadow_nightly_unsubscribe = async_track_time_change(
                self.hass,
                self._async_nightly_shadow_evaluation,
                hour=20,
                minute=0,
                second=0,
            )
        await self._write_operational_event("integration_started")

    async def async_stop_health_monitoring(self) -> None:
        """Stop health reevaluation without creating a false shutdown incident."""

        await self._write_operational_event("integration_stopping")
        if self._health_tick_unsubscribe is not None:
            self._health_tick_unsubscribe()
            self._health_tick_unsubscribe = None
        if self._shadow_nightly_unsubscribe is not None:
            self._shadow_nightly_unsubscribe()
            self._shadow_nightly_unsubscribe = None

    async def _async_update_data(self) -> ControllerRegistrySnapshot:
        observation_hint = self._next_observation_context
        self._next_observation_context = None
        account_id = str(self.entry.data[CONF_PERSON_ID])
        try:
            snapshot = await self.adapter.async_get_snapshot(account_id)
        except ControllerAuthenticationError as err:
            await self._record_refresh_failure("authentication")
            raise ConfigEntryAuthFailed("Controller authentication failed") from err
        except ControllerRateLimitError as err:
            await self._record_refresh_failure("rate_limit")
            detail = (
                f"; retry after {err.retry_after_seconds} seconds"
                if err.retry_after_seconds is not None
                else ""
            )
            raise UpdateFailed(f"Controller rate limit reached{detail}") from err
        except (ControllerProviderError, ValueError) as err:
            await self._record_refresh_failure("controller_provider")
            raise UpdateFailed(str(err)) from err

        self._persist_new_identities()
        overrides = self.entry.options.get(CONF_AREA_PROFILES, {})
        if not isinstance(overrides, dict):
            overrides = {}
        self.landscape = build_landscape_profile(snapshot, _string_key_mapping(overrides))
        self.last_successful_refresh = dt_util.utcnow()
        source, event_type, event_subtype = observation_hint or (
            WateringObservationSource.POLLING,
            None,
            None,
        )
        await self.observation_history.async_reconcile(
            snapshot,
            SessionObservationContext(
                observed_at=snapshot.observation.observed_at.astimezone(UTC),
                source=source,
                realtime_event_type=event_type,
                realtime_event_subtype=event_subtype,
            ),
        )
        weather_entities = tuple(
            (entity_id, state.state, state.attributes)
            for entity_id in self.hass.states.async_entity_ids("weather")
            if (state := self.hass.states.get(entity_id)) is not None
        )
        scientific_inputs = build_scientific_input_snapshot(
            landscape=self.landscape,
            weather_entities=weather_entities,
            evaluated_at=self.last_successful_refresh,
            country_code=self.hass.config.country,
            latitude=self.hass.config.latitude,
            elevation_meters=self.hass.config.elevation,
        )
        try:
            self.pipeline_evaluation = build_pipeline_evaluation(
                snapshot,
                self.landscape,
                scientific_inputs,
                evaluated_at=self.last_successful_refresh,
            )
        except Exception as err:  # Pipeline faults are operational failures, not commands.
            self.pipeline_evaluation = None
            await self._record_refresh_failure("pipeline")
            raise UpdateFailed("IrrigationOS pipeline evaluation failed") from err

        force_shadow_reason = self._force_next_shadow_reason
        self._force_next_shadow_reason = None
        shadow_record = await self.shadow_evaluations.async_consider(
            self.pipeline_evaluation,
            completed_session_count=len(self.observation_history.completed_sessions),
            force_reason=force_shadow_reason,
        )
        reconciliation_records = await self.actual_vs_shadow.async_consider(
            shadow_record=shadow_record,
            completed_sessions=self.observation_history.completed_sessions,
            now=self.last_successful_refresh,
            observation_quality=snapshot.observation.quality,
        )
        self.commissioning_report.consider(
            shadow_record=shadow_record,
            reconciliation_records=reconciliation_records,
        )
        self.replay_readiness.consider(
            reconciliation_records=reconciliation_records,
            commissioning_summary=self.commissioning_report.summary,
        )
        self.refresh_count += 1
        self._polling_healthy = True
        self._health_snapshot = snapshot
        self._update_controller_unavailability(snapshot, self.last_successful_refresh)
        if self.realtime is not None:
            await self.realtime.async_reconcile_controllers(
                tuple(controller.native_id for controller in snapshot.controllers)
            )
        await self.async_update_health("refresh_success", notify_listeners=False)
        await self._write_operational_event("refresh_success")
        return snapshot

    async def _async_nightly_shadow_evaluation(self, now: datetime) -> None:
        """Persist the authoritative 8 PM local shadow evaluation without actuation."""

        del now
        self._force_next_shadow_reason = ShadowEvaluationReason.NIGHTLY
        try:
            await self.async_request_refresh()
        finally:
            if self._force_next_shadow_reason is ShadowEvaluationReason.NIGHTLY:
                self._force_next_shadow_reason = None

    def mark_next_refresh_as_realtime(
        self,
        event_type: str,
        event_subtype: str,
    ) -> None:
        """Attach safe normalized realtime metadata to the next canonical refresh."""

        self._next_observation_context = (
            WateringObservationSource.REALTIME_REFRESH,
            event_type,
            event_subtype,
        )

    async def _record_refresh_failure(self, category: str) -> None:
        self._polling_healthy = False
        await self.async_update_health("refresh_failure")
        await self._write_operational_event(
            "refresh_failure", extra={"failure_category": category}
        )

    async def async_update_health(
        self, trigger: str, *, notify_listeners: bool = True
    ) -> HealthAssessment:
        """Evaluate aggregate health, latch incidents, and publish transitions."""

        now = datetime.now(UTC)
        controller_count, online_controller_count = self._controller_counts()
        realtime_healthy = bool(
            self.realtime is not None
            and self.realtime.enabled
            and self.realtime.remote_health.healthy
        )
        assessment = evaluate_health(
            now=now,
            started_at=self._started_at,
            last_successful_refresh=self.last_successful_refresh,
            last_update_success=self._polling_healthy,
            realtime_healthy=realtime_healthy,
            controller_count=controller_count,
            online_controller_count=online_controller_count,
            all_controllers_unavailable_since=self._all_controllers_unavailable_since,
            pipeline_available=self.pipeline_evaluation is not None,
            operational_log_healthy=self._operational_log_healthy,
            persistence_healthy=self._persistence_healthy,
        )
        previous = self._health_assessment
        self._health_assessment = assessment
        controller_ids = (
            ()
            if self._health_snapshot is None
            else tuple(
                sorted(
                    controller.controller_id
                    for controller in self._health_snapshot.controllers
                )
            )
        )
        self.ownership_commissioning.consider_topology(controller_ids)
        self.execution_authorization.consider(
            evaluated_at=now,
            health_state=assessment.state.value,
            observation_age_seconds=assessment.observation_age_seconds,
            controller_count=assessment.controller_count,
            online_controller_count=assessment.online_controller_count,
            pipeline_available=assessment.pipeline_available,
            readiness_status=self.replay_readiness.summary.readiness_status.value,
            ownership_confirmed=self.ownership_commissioning.summary.ownership_confirmed,
            boundary_review_acknowledged=(
                self.ownership_commissioning.summary.boundary_review_acknowledged
            ),
            active_watering_session_count=len(self.observation_history.active_sessions),
        )
        self.live_mode_safety.consider(
            readiness_status=self.replay_readiness.summary.readiness_status.value,
            execution_authorization_status=self.execution_authorization.summary.status.value,
            ownership_confirmed=self.ownership_commissioning.summary.ownership_confirmed,
            boundary_review_acknowledged=(
                self.ownership_commissioning.summary.boundary_review_acknowledged
            ),
        )
        self.integrated_safety_review.consider(self.live_mode_safety.summary)
        incident_changed = await self._apply_incident_transition(previous, assessment, now)
        state_changed = assessment != previous
        if notify_listeners and (state_changed or incident_changed):
            self.async_update_listeners()
        if assessment.state is not previous.state:
            await self._write_operational_event(
                "health_transition",
                extra={"previous_health_state": previous.state.value, "trigger": trigger},
            )
        return assessment

    async def confirm_controller_ownership(self) -> bool:
        """Persist explicit ownership commissioning without actuating equipment."""

        result = await self.ownership_commissioning.async_confirm_ownership()
        if result:
            await self.async_update_health("ownership_confirmed")
            await self._write_operational_event("controller_ownership_confirmed")
        return result

    async def acknowledge_execution_boundary_review(self) -> bool:
        """Persist manual boundary review acknowledgement without enabling control."""

        result = await self.ownership_commissioning.async_acknowledge_boundary_review()
        if result:
            await self.async_update_health("execution_boundary_review_acknowledged")
            await self._write_operational_event("execution_boundary_review_acknowledged")
        return result

    async def revoke_controller_ownership(self) -> bool:
        """Revoke commissioned ownership and immediately fail closed."""

        result = await self.ownership_commissioning.async_revoke()
        if result:
            await self.async_update_health("ownership_revoked")
            await self._write_operational_event("controller_ownership_revoked")
        return result

    async def reset_health_incident_latch(self) -> bool:
        """Clear recovered incident history without changing irrigation behavior."""

        if self._health_assessment.state is not IrrigationOSHealthState.HEALTHY:
            return False
        self._health_tracking_since = datetime.now(UTC)
        self._incident_latched = False
        self._incident_active = False
        self._incident_started_at = None
        self._last_unhealthy_at = None
        self._last_recovery_at = None
        self._last_incident_duration_seconds = None
        self._incident_reason_codes = ()
        self._incident_affected_components = ()
        await self._persist_health_state()
        self.async_update_listeners()
        await self._write_operational_event("health_incident_reset")
        return True

    @property
    def health_assessment(self) -> HealthAssessment:
        """Return the most recently evaluated aggregate health."""

        return self._health_assessment

    @property
    def health_incident_latched(self) -> bool:
        """Return whether an unhealthy incident remains unacknowledged."""

        return self._incident_latched

    def health_incident_diagnostics(self) -> dict[str, object]:
        """Return persistent health incident history and current state."""

        now = datetime.now(UTC)
        active_duration = (
            None
            if self._incident_started_at is None or not self._incident_active
            else max(0, round((now - self._incident_started_at).total_seconds()))
        )
        return {
            "current_health": self._health_assessment.state.value,
            "current_reason": self._health_assessment.reason,
            "current_reason_codes": list(self._health_assessment.reason_codes),
            "incident_latched": self._incident_latched,
            "incident_active": self._incident_active,
            "tracking_since": self._health_tracking_since.isoformat(),
            "incident_started_at": _iso_or_none(self._incident_started_at),
            "last_unhealthy_at": _iso_or_none(self._last_unhealthy_at),
            "last_recovery_at": _iso_or_none(self._last_recovery_at),
            "incident_duration_seconds": (
                active_duration
                if active_duration is not None
                else self._last_incident_duration_seconds
            ),
            "incident_reason_codes": list(self._incident_reason_codes),
            "incident_affected_components": list(self._incident_affected_components),
        }

    def operational_health_diagnostics(self) -> dict[str, object]:
        """Return aggregate health, incident, and log diagnostics."""

        return {
            "assessment": self._health_assessment.as_dict(),
            "incident": self.health_incident_diagnostics(),
            "daily_log": self.operational_log.diagnostics(),
            "observation_history": self.observation_history.diagnostics(),
        }

    async def _async_health_tick(self, now: datetime) -> None:
        del now
        if not self._persistence_healthy:
            await self._persist_health_state()
        await self.async_update_health("health_tick")

    async def _apply_incident_transition(
        self,
        previous: HealthAssessment,
        current: HealthAssessment,
        now: datetime,
    ) -> bool:
        changed = False
        if current.state is IrrigationOSHealthState.UNHEALTHY:
            self._last_unhealthy_at = now
            if not self._incident_active:
                self._incident_active = True
                self._incident_latched = True
                self._incident_started_at = now
                self._incident_reason_codes = current.reason_codes
                self._incident_affected_components = current.affected_components
                changed = True
                self.hass.bus.async_fire(
                    EVENT_HEALTH_UNHEALTHY,
                    self._health_event_payload(current, now),
                )
            else:
                self._incident_reason_codes = tuple(
                    dict.fromkeys((*self._incident_reason_codes, *current.reason_codes))
                )
                self._incident_affected_components = tuple(
                    dict.fromkeys(
                        (*self._incident_affected_components, *current.affected_components)
                    )
                )
        elif (
            self._incident_active
            and current.state is IrrigationOSHealthState.HEALTHY
        ):
            self._incident_active = False
            self._last_recovery_at = now
            if self._incident_started_at is not None:
                self._last_incident_duration_seconds = max(
                    0, round((now - self._incident_started_at).total_seconds())
                )
            changed = True
            self.hass.bus.async_fire(
                EVENT_HEALTH_RECOVERED,
                self._health_event_payload(current, now),
            )
        if changed or current.state is IrrigationOSHealthState.UNHEALTHY:
            await self._persist_health_state()
        return changed or previous.state is not current.state

    def _health_event_payload(
        self, assessment: HealthAssessment, event_time: datetime
    ) -> dict[str, object]:
        duration = self._last_incident_duration_seconds
        if self._incident_active and self._incident_started_at is not None:
            duration = max(0, round((event_time - self._incident_started_at).total_seconds()))
        return {
            "health_state": assessment.state.value,
            "reason": assessment.reason,
            "reason_codes": list(assessment.reason_codes),
            "affected_components": list(assessment.affected_components),
            "event_time": event_time.isoformat(),
            "incident_started_at": _iso_or_none(self._incident_started_at),
            "incident_duration_seconds": duration,
        }

    async def _write_operational_event(
        self,
        event_type: str,
        *,
        extra: dict[str, object] | None = None,
    ) -> None:
        recorded_at = datetime.now(UTC)
        payload = self._operational_payload(event_type, extra=extra)
        success = await self.hass.async_add_executor_job(
            self.operational_log.record, recorded_at, payload
        )
        was_healthy = self._operational_log_healthy
        self._operational_log_healthy = success
        if not success and was_healthy:
            _LOGGER.warning("IrrigationOS daily operational log write failed")
        elif success and not was_healthy:
            _LOGGER.info("IrrigationOS daily operational logging recovered")

    def _operational_payload(
        self,
        event_type: str,
        *,
        extra: dict[str, object] | None = None,
    ) -> dict[str, object]:
        assessment = self._health_assessment
        pipeline = self.pipeline_evaluation
        realtime = self.realtime
        payload: dict[str, object] = {
            "integration_version": VERSION,
            "event_type": event_type,
            "health_state": assessment.state.value,
            "health_reason": assessment.reason,
            "reason_codes": list(assessment.reason_codes),
            "affected_components": list(assessment.affected_components),
            "observation_age_seconds": assessment.observation_age_seconds,
            "last_successful_refresh_utc": _iso_or_none(self.last_successful_refresh),
            "polling_healthy": assessment.polling_healthy,
            "realtime_healthy": assessment.realtime_healthy,
            "realtime_error_category": (
                None if realtime is None else realtime.remote_health.error_category
            ),
            "realtime_registered_controllers": (
                0 if realtime is None else realtime.remote_health.registered_controllers
            ),
            "realtime_expected_controllers": (
                0 if realtime is None else realtime.remote_health.expected_controllers
            ),
            "controller_count": assessment.controller_count,
            "online_controller_count": assessment.online_controller_count,
            "unavailable_controller_count": assessment.unavailable_controller_count,
            "pipeline_available": assessment.pipeline_available,
            "pipeline_status": None if pipeline is None else pipeline.status.value,
            "pipeline_stage": None if pipeline is None else pipeline.current_stage.value,
            "pipeline_blocker_codes": (
                [] if pipeline is None else list(pipeline.blocker_codes)
            ),
            "incident_latched": self._incident_latched,
            "incident_active": self._incident_active,
            "incident_started_at": _iso_or_none(self._incident_started_at),
        }
        if extra:
            payload.update(extra)
        return payload

    async def _persist_health_state(self) -> None:
        payload: dict[str, Any] = {
            "tracking_since": self._health_tracking_since.isoformat(),
            "incident_latched": self._incident_latched,
            "incident_active": self._incident_active,
            "incident_started_at": _iso_or_none(self._incident_started_at),
            "last_unhealthy_at": _iso_or_none(self._last_unhealthy_at),
            "last_recovery_at": _iso_or_none(self._last_recovery_at),
            "last_incident_duration_seconds": self._last_incident_duration_seconds,
            "incident_reason_codes": list(self._incident_reason_codes),
            "incident_affected_components": list(self._incident_affected_components),
        }
        try:
            await self._health_store.async_save(payload)
            self._persistence_healthy = True
        except Exception:  # Storage failure degrades diagnostics but never irrigation.
            self._persistence_healthy = False
            _LOGGER.exception("Unable to persist IrrigationOS health incident state")

    def _restore_health_state(self, stored: dict[str, Any]) -> None:
        self._health_tracking_since = _parse_datetime(
            stored.get("tracking_since"), self._started_at
        )
        self._incident_latched = bool(stored.get("incident_latched", False))
        self._incident_active = bool(stored.get("incident_active", False))
        self._incident_started_at = _parse_optional_datetime(
            stored.get("incident_started_at")
        )
        self._last_unhealthy_at = _parse_optional_datetime(stored.get("last_unhealthy_at"))
        self._last_recovery_at = _parse_optional_datetime(stored.get("last_recovery_at"))
        duration = stored.get("last_incident_duration_seconds")
        self._last_incident_duration_seconds = (
            int(duration) if isinstance(duration, (int, float)) else None
        )
        reasons = stored.get("incident_reason_codes", [])
        components = stored.get("incident_affected_components", [])
        self._incident_reason_codes = _string_tuple(reasons)
        self._incident_affected_components = _string_tuple(components)

    def _update_controller_unavailability(
        self, snapshot: ControllerRegistrySnapshot, observed_at: datetime
    ) -> None:
        if snapshot.controllers and all(
            controller.availability is not ControllerAvailability.ONLINE
            for controller in snapshot.controllers
        ):
            if self._all_controllers_unavailable_since is None:
                self._all_controllers_unavailable_since = observed_at
        else:
            self._all_controllers_unavailable_since = None

    def _controller_counts(self) -> tuple[int, int]:
        snapshot = self._health_snapshot
        if snapshot is None:
            return 0, 0
        total = len(snapshot.controllers)
        online = sum(
            controller.availability is ControllerAvailability.ONLINE
            for controller in snapshot.controllers
        )
        return total, online

    def _persist_new_identities(self) -> None:
        if not self.identities.changed:
            return
        data = {**self.entry.data, CONF_IDENTITY_REGISTRY: self.identities.as_dict()}
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        self.identities.mark_saved()


def _string_key_mapping(value: dict[Any, Any]) -> dict[str, Any]:
    """Return a mapping with string keys for persisted config-entry options."""
    return {str(key): item for key, item in value.items()}


def _iso_or_none(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _parse_optional_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _parse_datetime(value: object, default: datetime) -> datetime:
    return _parse_optional_datetime(value) or default


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))
