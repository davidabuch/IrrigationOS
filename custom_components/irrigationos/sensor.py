"""Sensor platform for IrrigationOS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_OBSERVATION
from .controllers import IrrigationArea, IrrigationController
from .coordinator import IrrigationOSCoordinator
from .entity import (
    IrrigationOSAreaEntity,
    IrrigationOSControllerEntity,
    IrrigationOSEntity,
    IrrigationOSLandscapeAreaEntity,
)
from .observation_history.models import safe_session_summary
from .pipeline import PIPELINE_ALGORITHM_VERSION, PipelineStage
from .production_targets import find_production_area, select_production_targets
from .reconciliation import EntityInventory, controller_first
from .supervised_operation.acceptance import (
    SUPERVISED_OPERATION_ACCEPTANCE_RECORD_SCHEMA_VERSION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IrrigationOS sensors."""
    del hass
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        IrrigationOSStatusSensor(coordinator),
        IrrigationOSHealthSensor(coordinator),
        IrrigationOSCurrentWateringSessionSensor(coordinator),
        IrrigationOSLastCompletedWateringSessionSensor(coordinator),
        IrrigationOSWateringSessionsTodaySensor(coordinator),
        IrrigationOSProviderSensor(coordinator),
        IrrigationOSControllerCountSensor(coordinator),
        IrrigationOSAreaCountSensor(coordinator),
        IrrigationOSLandscapeStatusSensor(coordinator),
        IrrigationOSLastRefreshSensor(coordinator),
        IrrigationOSDiscoverySummarySensor(coordinator),
        IrrigationOSPipelineStatusSensor(coordinator),
        IrrigationOSPipelineStageSensor(coordinator),
        IrrigationOSPipelineVersionSensor(coordinator),
        IrrigationOSPipelineLastEvaluationSensor(coordinator),
        IrrigationOSScientificInputStatusSensor(coordinator),
        IrrigationOSWeatherSourceSensor(coordinator),
        IrrigationOSCommissioningSummarySensor(coordinator),
        IrrigationOSControlReadinessSensor(coordinator),
        IrrigationOSExecutionAuthorizationSensor(coordinator),
        IrrigationOSControllerOwnershipSensor(coordinator),
        IrrigationOSLiveModeSafetySensor(coordinator),
        IrrigationOSIntegratedSafetyReviewSensor(coordinator),
        IrrigationOSLiveCommissioningSensor(coordinator),
        IrrigationOSFirstLiveAcceptanceSensor(coordinator),
        IrrigationOSValidatedTargetsSensor(coordinator),
        IrrigationOSProductionReadinessSensor(coordinator),
        IrrigationOSProductionRecommendationsSensor(coordinator),
        IrrigationOSUnattendedCanaryApprovalSensor(coordinator),
        IrrigationOSUnattendedCanaryAcceptanceSensor(coordinator),
        IrrigationOSSupervisedOperationAcceptanceSensor(coordinator),
        *(
            IrrigationOSPipelineStageStatusSensor(coordinator, stage)
            for stage in PipelineStage
        ),
    ]
    inventory = EntityInventory()
    entities.extend(_new_dynamic_entities(coordinator, inventory))
    async_add_entities(entities)

    def _async_reconcile() -> None:
        additions = _new_dynamic_entities(coordinator, inventory)
        if additions:
            async_add_entities(additions)

    entry.async_on_unload(coordinator.async_add_listener(_async_reconcile))


def _new_dynamic_entities(
    coordinator: IrrigationOSCoordinator,
    inventory: EntityInventory,
) -> list[SensorEntity]:
    """Create sensors for newly discovered canonical objects and slots."""
    candidates: dict[str, SensorEntity] = {}
    for controller in coordinator.data.controllers:
        candidates[f"controller:{controller.controller_id}"] = (
            IrrigationOSControllerStatusSensor(coordinator, controller)
        )
    for area in coordinator.data.areas:
        candidates[f"area:{area.area_id}"] = IrrigationOSAreaSummarySensor(
            coordinator, area
        )
        candidates[f"pipeline:{area.area_id}"] = IrrigationOSAreaPipelineSensor(
            coordinator, area
        )
        if area.configured and _has_landscape_profile(coordinator, area.area_id):
            candidates[f"landscape:{area.area_id}"] = IrrigationOSLandscapeProfileSensor(
                coordinator, area
            )
    for target in select_production_targets(coordinator.data):
        production_area = find_production_area(coordinator.data, target)
        if production_area is not None:
            candidates[f"production_recommendation:{production_area.area_id}"] = (
                IrrigationOSAreaProductionRecommendationSensor(
                    coordinator, production_area, target.controller_slot
                )
            )
    result = inventory.reconcile(set(candidates))
    return [candidates[key] for key in controller_first(result.added)]


def _has_landscape_profile(
    coordinator: IrrigationOSCoordinator, area_id: str
) -> bool:
    """Return whether the current landscape contains the canonical area profile."""

    return any(profile.area_id == area_id for profile in coordinator.landscape.areas)


class IrrigationOSCommissioningSummarySensor(IrrigationOSEntity, SensorEntity):
    """Expose aggregate shadow commissioning evidence without authorizing control."""

    _attr_name = "Commissioning summary"
    _attr_unique_id = "irrigationos_commissioning_summary"
    entity_id = "sensor.irrigationos_commissioning_summary"
    _attr_icon = "mdi:clipboard-check-outline"

    @property
    def available(self) -> bool:
        """Remain available while evidence is still being collected."""

        return True

    @property
    def native_value(self) -> str:
        """Return the current evidence-review state."""

        return self.coordinator.commissioning_report.summary.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return privacy-safe aggregate commissioning metrics."""

        return self.coordinator.commissioning_report.summary.to_dict()


class IrrigationOSControlReadinessSensor(IrrigationOSEntity, SensorEntity):
    """Expose replay-backed readiness evidence without enabling control."""

    _attr_name = "Control readiness evidence"
    _attr_unique_id = "irrigationos_control_readiness_evidence"
    entity_id = "sensor.irrigationos_control_readiness_evidence"
    _attr_icon = "mdi:shield-check-outline"

    @property
    def available(self) -> bool:
        """Remain available while replay evidence accumulates."""

        return True

    @property
    def native_value(self) -> str:
        """Return the current evidence-based readiness state."""

        return self.coordinator.replay_readiness.summary.readiness_status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return replay metrics and explicit promotion criteria."""

        return self.coordinator.replay_readiness.summary.to_dict()


class IrrigationOSControllerOwnershipSensor(IrrigationOSEntity, SensorEntity):
    """Expose explicit controller ownership commissioning evidence."""

    _attr_name = "Controller ownership commissioning"
    _attr_unique_id = "irrigationos_controller_ownership_commissioning"
    entity_id = "sensor.irrigationos_controller_ownership_commissioning"
    _attr_icon = "mdi:account-key-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.ownership_commissioning.summary.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.ownership_commissioning.summary.to_dict()


class IrrigationOSExecutionAuthorizationSensor(IrrigationOSEntity, SensorEntity):
    """Expose fail-closed execution authorization safety evidence."""

    _attr_name = "Execution authorization"
    _attr_unique_id = "irrigationos_execution_authorization"
    entity_id = "sensor.irrigationos_execution_authorization"
    _attr_icon = "mdi:shield-lock-outline"

    @property
    def available(self) -> bool:
        """Remain available while safety prerequisites are incomplete."""

        return True

    @property
    def native_value(self) -> str:
        """Return the current fail-closed authorization state."""

        return self.coordinator.execution_authorization.summary.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return deterministic gates and blockers without enabling control."""

        return self.coordinator.execution_authorization.summary.to_dict()


class IrrigationOSLiveModeSafetySensor(IrrigationOSEntity, SensorEntity):
    """Expose the separate pre-Live safety architecture boundary."""

    _attr_name = "Live mode safety architecture"
    _attr_unique_id = "irrigationos_live_mode_safety_architecture"
    entity_id = "sensor.irrigationos_live_mode_safety_architecture"
    _attr_icon = "mdi:shield-alert-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.live_mode_safety.summary.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.live_mode_safety.summary.to_dict()


class IrrigationOSIntegratedSafetyReviewSensor(IrrigationOSEntity, SensorEntity):
    """Expose integrated six-safeguard commissioning validation evidence."""

    _attr_name = "Integrated live safety review"
    _attr_unique_id = "irrigationos_integrated_live_safety_review"
    entity_id = "sensor.irrigationos_integrated_live_safety_review"
    _attr_icon = "mdi:shield-check-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.integrated_safety_review.summary.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.integrated_safety_review.summary.to_dict()


class IrrigationOSLiveCommissioningSensor(IrrigationOSEntity, SensorEntity):
    """Expose bounded first-live commissioning eligibility without actuation."""

    _attr_name = "Live commissioning protocol"
    _attr_unique_id = "irrigationos_live_commissioning_protocol"
    entity_id = "sensor.irrigationos_live_commissioning_protocol"
    _attr_icon = "mdi:clipboard-check-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.live_commissioning.summary.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.live_commissioning.summary.to_dict()


class IrrigationOSFirstLiveAcceptanceSensor(IrrigationOSEntity, SensorEntity):
    """Expose the latest persistent structured supervised-trial result."""

    _attr_name = "First live trial acceptance"
    _attr_unique_id = "irrigationos_first_live_trial_acceptance"
    entity_id = "sensor.irrigationos_first_live_trial_acceptance"
    _attr_icon = "mdi:clipboard-check-multiple-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.first_live_acceptance.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latest = self.coordinator.first_live_acceptance.latest
        if latest is None:
            return {
                "status": self.coordinator.first_live_acceptance.status.value,
                "last_persistence_error": (
                    self.coordinator.first_live_acceptance.last_persistence_error
                ),
            }
        return latest.to_dict()


class IrrigationOSSupervisedOperationAcceptanceSensor(IrrigationOSEntity, SensorEntity):
    """Expose the latest persistent supervised operational result."""

    _attr_name = "Supervised operation acceptance"
    _attr_unique_id = "irrigationos_supervised_operation_acceptance"
    entity_id = "sensor.irrigationos_supervised_operation_acceptance"
    _attr_icon = "mdi:clipboard-check-multiple-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.supervised_operation_acceptance.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        manager = self.coordinator.supervised_operation_acceptance
        latest = manager.latest
        if latest is None:
            return {
                "schema_version": SUPERVISED_OPERATION_ACCEPTANCE_RECORD_SCHEMA_VERSION,
                "last_persistence_error": manager.last_persistence_error,
            }
        attributes = latest.to_dict()
        attributes["last_persistence_error"] = manager.last_persistence_error
        return attributes


class IrrigationOSValidatedTargetsSensor(IrrigationOSEntity, SensorEntity):
    """Expose durable privacy-safe first-live validated target evidence."""

    _attr_name = "Validated targets"
    _attr_unique_id = "irrigationos_validated_targets"
    entity_id = "sensor.irrigationos_validated_targets"
    _attr_icon = "mdi:check-decagram-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> int:
        return len(self.coordinator.validated_targets.targets)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.validated_targets.diagnostics()


class IrrigationOSProductionReadinessSensor(IrrigationOSEntity, SensorEntity):
    """Expose fail-closed advisory production readiness without authority."""

    _attr_name = "Production readiness"
    _attr_unique_id = "irrigationos_production_readiness"
    entity_id = "sensor.irrigationos_production_readiness"
    _attr_icon = "mdi:shield-check-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.production_readiness.summary.state.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.production_readiness.summary.to_dict()


class IrrigationOSProductionRecommendationsSensor(IrrigationOSEntity, SensorEntity):
    """Expose the current transient recommendation set without authority."""

    _attr_name = "Production recommendations"
    _attr_unique_id = "irrigationos_production_recommendations"
    entity_id = "sensor.irrigationos_production_recommendations"
    _attr_icon = "mdi:clipboard-text-search-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.production_recommendations.state.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.production_recommendations.to_dict()


class IrrigationOSUnattendedCanaryApprovalSensor(IrrigationOSEntity, SensorEntity):
    """Expose one restart-ephemeral single-use approval."""

    _attr_name = "Unattended canary approval"
    _attr_unique_id = "irrigationos_unattended_canary_approval"
    entity_id = "sensor.irrigationos_unattended_canary_approval"
    _attr_icon = "mdi:shield-key-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.unattended_canary.approval_state().value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        diagnostics = self.coordinator.unattended_canary.approval_diagnostics()
        approval = diagnostics["approval"]
        if isinstance(approval, dict):
            return dict(approval)
        return {
            "single_use": True,
            "persists_across_restart": False,
        }


class IrrigationOSUnattendedCanaryAcceptanceSensor(
    IrrigationOSEntity, SensorEntity
):
    """Expose latest persisted terminal canary acceptance."""

    _attr_name = "Unattended canary acceptance"
    _attr_unique_id = "irrigationos_unattended_canary_acceptance"
    entity_id = "sensor.irrigationos_unattended_canary_acceptance"
    _attr_icon = "mdi:clipboard-check-outline"

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.unattended_canary_acceptance.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        manager = self.coordinator.unattended_canary_acceptance
        attributes = {} if manager.latest is None else manager.latest.to_dict()
        attributes["last_persistence_error"] = manager.last_persistence_error
        return attributes


class IrrigationOSCurrentWateringSessionSensor(IrrigationOSEntity, SensorEntity):
    """Expose a compact summary of currently observed watering sessions."""

    _attr_name = "Current watering session"
    _attr_unique_id = "irrigationos_current_watering_session"
    entity_id = "sensor.irrigationos_current_watering_session"
    _attr_icon = "mdi:sprinkler-variant"

    @property
    def available(self) -> bool:
        """Remain available through temporary controller observation gaps."""

        return True

    @property
    def native_value(self) -> str:
        """Return whether any canonical slot is currently observed watering."""

        return (
            "watering"
            if self.coordinator.observation_history.active_sessions
            else "idle"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return vendor-ID-free active-session summaries."""

        sessions = self.coordinator.observation_history.active_sessions
        return {
            "active_session_count": len(sessions),
            "active_slots": [session.slot_number for session in sessions],
            "sessions": [safe_session_summary(session) for session in sessions],
        }


class IrrigationOSLastCompletedWateringSessionSensor(
    IrrigationOSEntity, SensorEntity
):
    """Expose the most recently completed observed watering session."""

    _attr_name = "Last completed watering session"
    _attr_unique_id = "irrigationos_last_completed_watering_session"
    entity_id = "sensor.irrigationos_last_completed_watering_session"
    _attr_icon = "mdi:history"

    @property
    def available(self) -> bool:
        """Remain available when no completed session exists yet."""

        return True

    @property
    def native_value(self) -> str:
        """Return a compact completion state."""

        return (
            "completed"
            if self.coordinator.observation_history.last_completed_session is not None
            else "none"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the latest safe completed-session summary."""

        session = self.coordinator.observation_history.last_completed_session
        return {} if session is None else safe_session_summary(session)


class IrrigationOSWateringSessionsTodaySensor(IrrigationOSEntity, SensorEntity):
    """Count sessions observed during the current Home Assistant local day."""

    _attr_name = "Watering sessions today"
    _attr_unique_id = "irrigationos_watering_sessions_today"
    entity_id = "sensor.irrigationos_watering_sessions_today"
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "sessions"

    @property
    def available(self) -> bool:
        """Remain available independently of controller connectivity."""

        return True

    @property
    def native_value(self) -> int:
        """Return the local-day observed-session count."""

        return self.coordinator.observation_history.sessions_today()

class IrrigationOSHealthSensor(IrrigationOSEntity, SensorEntity):
    """Expose aggregate operator-facing health and incident context."""

    _attr_name = "Health"
    _attr_unique_id = "irrigationos_health"
    entity_id = "sensor.irrigationos_health"
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator: IrrigationOSCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Remain available while the integration is loaded, even if polling fails."""

        return True

    @property
    def native_value(self) -> str:
        """Return the aggregate health state."""

        return self.coordinator.health_assessment.state.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safe health, incident, and daily-log context."""

        assessment = self.coordinator.health_assessment
        incident = self.coordinator.health_incident_diagnostics()
        log = self.coordinator.operational_log.diagnostics()
        return {
            "reason": assessment.reason,
            "reason_codes": list(assessment.reason_codes),
            "affected_components": list(assessment.affected_components),
            "startup_grace_active": assessment.startup_grace_active,
            "observation_age_seconds": assessment.observation_age_seconds,
            "polling_healthy": assessment.polling_healthy,
            "realtime_healthy": assessment.realtime_healthy,
            "controller_count": assessment.controller_count,
            "online_controller_count": assessment.online_controller_count,
            "unavailable_controller_count": assessment.unavailable_controller_count,
            "pipeline_available": assessment.pipeline_available,
            "incident_latched": incident["incident_latched"],
            "incident_active": incident["incident_active"],
            "incident_started_at": incident["incident_started_at"],
            "last_unhealthy_at": incident["last_unhealthy_at"],
            "last_recovery_at": incident["last_recovery_at"],
            "incident_duration_seconds": incident["incident_duration_seconds"],
            "daily_log_file": log["current_file"],
            "daily_log_retention_days": log["retention_days"],
            "daily_log_write_error_count": log["write_error_count"],
        }

class IrrigationOSStatusSensor(IrrigationOSEntity, SensorEntity):
    """Show the observation-only system state."""

    _attr_name = "Status"
    _attr_unique_id = "irrigationos_status"
    entity_id = "sensor.irrigationos_status"
    _attr_icon = "mdi:sprinkler-variant"

    @property
    def native_value(self) -> str:
        """Return system state."""
        return MODE_OBSERVATION


class IrrigationOSProviderSensor(IrrigationOSEntity, SensorEntity):
    """Expose the active controller provider."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_name = "Controller provider"
    _attr_unique_id = "irrigationos_controller_provider"
    entity_id = "sensor.irrigationos_controller_provider"
    _attr_icon = "mdi:access-point-network"

    @property
    def native_value(self) -> str:
        """Return provider name."""
        return self.coordinator.data.provider


class IrrigationOSControllerCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered controllers."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_name = "Controller count"
    _attr_unique_id = "irrigationos_controller_count"
    entity_id = "sensor.irrigationos_controller_count"
    _attr_native_unit_of_measurement = "controllers"

    @property
    def native_value(self) -> int:
        """Return controller count."""
        return len(self.coordinator.data.controllers)


class IrrigationOSAreaCountSensor(IrrigationOSEntity, SensorEntity):
    """Count discovered irrigation areas."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_name = "Irrigation area count"
    _attr_unique_id = "irrigationos_area_count"
    entity_id = "sensor.irrigationos_area_count"
    _attr_native_unit_of_measurement = "areas"

    @property
    def native_value(self) -> int:
        """Return irrigation-area count."""
        return len(self.coordinator.data.configured_areas)


class IrrigationOSControllerStatusSensor(IrrigationOSControllerEntity, SensorEntity):
    """Expose a controller's normalized status."""

    _attr_name = "Status"
    _attr_icon = "mdi:access-point-network"

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        controller: IrrigationController,
    ) -> None:
        super().__init__(coordinator, controller)
        self._attr_unique_id = f"{controller.controller_id}_status"

    @property
    def native_value(self) -> str:
        """Return controller availability."""
        return self.controller.availability.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return non-sensitive controller details."""
        controller = self.controller
        return {
            "provider": controller.provider,
            "enabled": controller.enabled,
            "model": controller.model,
            "area_count": len(controller.areas),
            "supports_current_watering": controller.capabilities.observe_current_watering,
            "supports_last_watered": controller.capabilities.observe_last_watered,
            "supports_start_area": controller.capabilities.supports_start_area,
            "supports_stop_area": controller.capabilities.supports_stop_area,
            "capacity": controller.capacity,
            "watering_observation_quality": (
                controller.watering_observation_quality.value
            ),
        }


class IrrigationOSAreaSummarySensor(IrrigationOSAreaEntity, SensorEntity):
    """Expose normalized irrigation-area metadata."""

    _attr_name = "Observation"
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_observation"
        self._attr_suggested_object_id = f"zone_{area.slot_number}_observation"

    @property
    def native_value(self) -> str:
        """Return the normalized area state."""
        return self.area.state.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return read-only area details."""
        area = self.area
        return {
            "native_number": area.native_number,
            "slot_number": area.slot_number,
            "configured": area.configured,
            "vendor_name": area.vendor_name,
            "enabled": area.enabled,
            "last_watered_epoch_ms": area.last_watered_epoch_ms,
            "root_zone_depth_inches": area.root_zone_depth_inches,
            "efficiency": area.efficiency,
            "soil_name": area.soil_name,
            "crop_name": area.crop_name,
            "nozzle_name": area.nozzle_name,
            "nozzle_inches_per_hour": area.nozzle_inches_per_hour,
        }


class IrrigationOSLandscapeStatusSensor(IrrigationOSEntity, SensorEntity):
    """Expose overall Landscape Digital Twin completion."""

    _attr_name = "Landscape profile status"
    _attr_unique_id = "irrigationos_landscape_profile_status"
    entity_id = "sensor.irrigationos_landscape_profile_status"
    _attr_icon = "mdi:land-plots"

    @property
    def native_value(self) -> str:
        """Return overall landscape profile state."""
        landscape = self.coordinator.landscape
        if not landscape.areas:
            return "unavailable"
        if landscape.complete_area_count == len(landscape.areas):
            return "complete"
        return "incomplete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return aggregate landscape details."""
        landscape = self.coordinator.landscape
        return {
            "schema_version": landscape.schema_version,
            "area_count": len(landscape.areas),
            "complete_area_count": landscape.complete_area_count,
        }


class IrrigationOSLandscapeProfileSensor(
    IrrigationOSLandscapeAreaEntity, SensorEntity
):
    """Expose the canonical landscape profile for an irrigation area."""

    _attr_name = "Landscape profile"
    _attr_icon = "mdi:land-plots"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_landscape_profile"
        self._attr_suggested_object_id = f"zone_{area.slot_number}_landscape_profile"

    @property
    def native_value(self) -> str:
        """Return profile completion state."""
        return "complete" if self.profile.is_complete else "incomplete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile values with provenance and confidence."""
        profile = self.profile
        return {
            "completion_percent": profile.completion_percent,
            "display_name": profile.display_name.value,
            "plant_type": profile.plant_type.value.value,
            "plant_description": profile.plant_description.value,
            "irrigation_method": profile.irrigation_method.value.value,
            "sun_exposure": profile.sun_exposure.value.value,
            "slope_percent": profile.slope_percent.value,
            "soil_texture": profile.soil_texture.value.value,
            "soil_description": profile.soil_description.value,
            "root_depth_inches": profile.root_depth_inches.value,
            "application_rate_inches_per_hour": (
                profile.application_rate_inches_per_hour.value
            ),
            "distribution_efficiency": profile.distribution_efficiency.value,
            "sources": {
                "plant_type": profile.plant_type.source.value,
                "irrigation_method": profile.irrigation_method.source.value,
                "sun_exposure": profile.sun_exposure.source.value,
                "slope_percent": profile.slope_percent.source.value,
                "soil_texture": profile.soil_texture.source.value,
                "root_depth_inches": profile.root_depth_inches.source.value,
                "application_rate": (
                    profile.application_rate_inches_per_hour.source.value
                ),
                "distribution_efficiency": (
                    profile.distribution_efficiency.source.value
                ),
            },
            "confidence": {
                "plant_type": profile.plant_type.confidence_percent,
                "irrigation_method": profile.irrigation_method.confidence_percent,
                "sun_exposure": profile.sun_exposure.confidence_percent,
                "slope_percent": profile.slope_percent.confidence_percent,
                "soil_texture": profile.soil_texture.confidence_percent,
                "root_depth_inches": profile.root_depth_inches.confidence_percent,
                "application_rate": (
                    profile.application_rate_inches_per_hour.confidence_percent
                ),
                "distribution_efficiency": (
                    profile.distribution_efficiency.confidence_percent
                ),
            },
        }


class IrrigationOSLastRefreshSensor(IrrigationOSEntity, SensorEntity):
    """Expose the last successful controller refresh."""

    _attr_name = "Last successful refresh"
    _attr_unique_id = "irrigationos_last_successful_refresh"
    entity_id = "sensor.irrigationos_last_successful_refresh"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return the last successful refresh timestamp."""
        return self.coordinator.last_successful_refresh

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return refresh telemetry."""
        return {"refresh_count": self.coordinator.refresh_count}


class IrrigationOSDiscoverySummarySensor(IrrigationOSEntity, SensorEntity):
    """Summarize live controller and irrigation-area discovery."""

    _attr_name = "Discovery summary"
    _attr_unique_id = "irrigationos_discovery_summary"
    entity_id = "sensor.irrigationos_discovery_summary"
    _attr_icon = "mdi:radar"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return a compact discovery state."""
        return "ready" if self.coordinator.data.controllers else "no_controllers"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return discovered names for field validation."""
        return {
            "controller_names": [item.name for item in self.coordinator.data.controllers],
            "area_names": [
                item.vendor_name or item.name
                for item in self.coordinator.data.configured_areas
            ],
            "watering_areas": [
                item.name
                for item in self.coordinator.data.areas
                if item.state.value == "watering"
            ],
            "observed_at": self.coordinator.data.observation.observed_at.isoformat(),
            "fresh_until": self.coordinator.data.observation.fresh_until.isoformat(),
            "source_quality": self.coordinator.data.observation.quality.value,
            "partial_failure_count": len(self.coordinator.data.observation.errors),
        }


class IrrigationOSPipelineStatusSensor(IrrigationOSEntity, SensorEntity):
    """Expose the synchronized pipeline evaluation status."""

    _attr_name = "Pipeline status"
    _attr_unique_id = "irrigationos_pipeline_status"
    entity_id = "sensor.irrigationos_pipeline_status"
    _attr_icon = "mdi:transit-connection-variant"

    @property
    def native_value(self) -> str:
        evaluation = self.coordinator.pipeline_evaluation
        return evaluation.status.value if evaluation is not None else "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return {}
        return {
            "configured_area_count": evaluation.configured_area_count,
            "complete_profile_count": evaluation.complete_profile_count,
            "blocker_codes": list(evaluation.blocker_codes),
        }


class IrrigationOSPipelineStageSensor(IrrigationOSEntity, SensorEntity):
    """Expose the first pipeline stage that is not ready."""

    _attr_name = "Current pipeline stage"
    _attr_unique_id = "irrigationos_pipeline_stage"
    entity_id = "sensor.irrigationos_pipeline_stage"
    _attr_icon = "mdi:timeline-clock-outline"

    @property
    def native_value(self) -> str:
        evaluation = self.coordinator.pipeline_evaluation
        return evaluation.current_stage.value if evaluation is not None else "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return {}
        return {
            item.stage.value: {
                "status": item.status.value,
                "reason": item.reason,
                "blocker_codes": list(item.blocker_codes),
            }
            for item in evaluation.stages
        }


class IrrigationOSPipelineStageStatusSensor(IrrigationOSEntity, SensorEntity):
    """Expose one stable synchronized pipeline-stage status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:timeline-check-outline"

    def __init__(
        self, coordinator: IrrigationOSCoordinator, stage: PipelineStage
    ) -> None:
        super().__init__(coordinator)
        self.stage = stage
        slug = stage.value
        self._attr_name = f"Pipeline {slug.replace('_', ' ')}"
        self._attr_unique_id = f"irrigationos_pipeline_stage_{slug}"
        self.entity_id = f"sensor.irrigationos_pipeline_stage_{slug}"

    @property
    def native_value(self) -> str:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return "unavailable"
        return evaluation.stage(self.stage).status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return {}
        stage = evaluation.stage(self.stage)
        return {
            "reason": stage.reason,
            "blocker_codes": list(stage.blocker_codes),
            "evaluated_at": evaluation.evaluated_at.isoformat(),
            "pipeline_algorithm_version": evaluation.algorithm_version,
        }


def _area_result_by_id(values: tuple[Any, ...], area_id: str) -> Any | None:
    """Return one immutable per-area pipeline result without recomputation."""
    return next((item for item in values if item.area_id == area_id), None)


class IrrigationOSAreaPipelineSensor(IrrigationOSAreaEntity, SensorEntity):
    """Expose compact science, advisory, and simulation output for one area."""

    _attr_name = "Pipeline output"
    _attr_icon = "mdi:timeline-text-outline"

    def __init__(self, coordinator: IrrigationOSCoordinator, area: IrrigationArea) -> None:
        super().__init__(coordinator, area)
        self._attr_unique_id = f"{area.area_id}_pipeline_output"
        self._attr_suggested_object_id = f"zone_{area.slot_number}_pipeline_output"

    def _output(self) -> tuple[str, dict[str, Any]]:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return "unavailable", {}

        area_id = self.area_id
        water = _area_result_by_id(evaluation.water_requirements, area_id)
        stress = _area_result_by_id(evaluation.plant_stress, area_id)
        health = _area_result_by_id(evaluation.plant_health, area_id)
        recommendation = _area_result_by_id(evaluation.recommendations, area_id)
        planning = _area_result_by_id(evaluation.planning, area_id)
        scheduling = _area_result_by_id(evaluation.scheduling, area_id)
        execution = _area_result_by_id(evaluation.execution, area_id)
        runtime = _area_result_by_id(evaluation.runtime_monitoring, area_id)

        attrs: dict[str, Any] = {
            "evaluated_at": evaluation.evaluated_at.isoformat(),
            "pipeline_algorithm_version": evaluation.algorithm_version,
            "water_requirement_status": (
                water.assessment.status.value
                if water is not None and water.assessment is not None
                else "unavailable"
            ),
            "plant_stress_status": (
                stress.assessment.overall_status.value
                if stress is not None and stress.assessment is not None
                else "unavailable"
            ),
            "plant_health_status": (
                health.assessment.status.value
                if health is not None and health.assessment is not None
                else "unavailable"
            ),
            "recommendation_status": (
                recommendation.assessment.status.value
                if recommendation is not None and recommendation.assessment is not None
                else "unavailable"
            ),
            "planning_status": (
                planning.plan.status.value
                if planning is not None and planning.plan is not None
                else "unavailable"
            ),
            "scheduling_status": (
                scheduling.schedule.status.value
                if scheduling is not None and scheduling.schedule is not None
                else "unavailable"
            ),
            "execution_status": (
                execution.execution_plan.status.value
                if execution is not None and execution.execution_plan is not None
                else "unavailable"
            ),
            "runtime_status": (
                runtime.report.status.value
                if runtime is not None and runtime.report is not None
                else "unavailable"
            ),
            "blocker_codes": sorted(
                {
                    code
                    for item in (
                        water,
                        stress,
                        health,
                        recommendation,
                        planning,
                        scheduling,
                        execution,
                        runtime,
                    )
                    if item is not None
                    for code in item.blocker_codes
                }
            ),
        }
        if recommendation is not None and recommendation.assessment is not None:
            attrs["recommendation_count"] = len(
                recommendation.assessment.recommendations
            )
            attrs["recommendation_assessment_id"] = (
                recommendation.assessment.assessment_id
            )
        if planning is not None and planning.plan is not None:
            attrs["plan_id"] = planning.plan.plan_id
            attrs["plan_action_count"] = len(planning.plan.actions)
        if scheduling is not None and scheduling.schedule is not None:
            attrs["schedule_id"] = scheduling.schedule.schedule_id
            attrs["scheduled_action_count"] = len(scheduling.schedule.actions)
        if execution is not None and execution.execution_plan is not None:
            attrs["execution_plan_id"] = execution.execution_plan.execution_plan_id
            attrs["simulated_command_count"] = len(execution.execution_plan.commands)
        if runtime is not None and runtime.report is not None:
            attrs["runtime_report_id"] = runtime.report.report_id
            attrs["runtime_issue_count"] = len(runtime.report.issues)

        final_status = attrs["runtime_status"]
        if final_status == "unavailable":
            for key in (
                "execution_status",
                "scheduling_status",
                "planning_status",
                "recommendation_status",
                "plant_health_status",
                "plant_stress_status",
                "water_requirement_status",
            ):
                if attrs[key] != "unavailable":
                    final_status = attrs[key]
                    break
        return str(final_status), attrs

    @property
    def native_value(self) -> str:
        return self._output()[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._output()[1]


class IrrigationOSAreaProductionRecommendationSensor(
    IrrigationOSAreaEntity, SensorEntity
):
    """Expose one canonical production-area recommendation."""

    _attr_name = "Production recommendation"
    _attr_icon = "mdi:sprinkler-variant"

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        area: IrrigationArea,
        controller_slot: int,
    ) -> None:
        super().__init__(coordinator, area)
        self.controller_slot = controller_slot
        self._attr_unique_id = f"{area.area_id}_production_recommendation"
        self._attr_suggested_object_id = (
            f"zone_{area.slot_number}_production_recommendation"
        )

    def _recommendation(self) -> Any | None:
        return next(
            (
                item
                for item in self.coordinator.production_recommendations.recommendations
                if item.target.controller_slot == self.controller_slot
                and item.target.area_slot == self.area.slot_number
            ),
            None,
        )

    @property
    def native_value(self) -> str:
        recommendation = self._recommendation()
        return "not_available" if recommendation is None else recommendation.state.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        recommendation = self._recommendation()
        if recommendation is None:
            return {
                "controller_slot": self.controller_slot,
                "area_slot": self.area.slot_number,
                "execution_authorized": False,
            }
        return recommendation.to_dict()


class IrrigationOSPipelineVersionSensor(IrrigationOSEntity, SensorEntity):
    """Expose the pipeline integration algorithm version."""

    _attr_name = "Pipeline version"
    _attr_unique_id = "irrigationos_pipeline_version"
    entity_id = "sensor.irrigationos_pipeline_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:source-branch"

    @property
    def native_value(self) -> str:
        return PIPELINE_ALGORITHM_VERSION


class IrrigationOSPipelineLastEvaluationSensor(IrrigationOSEntity, SensorEntity):
    """Expose the timestamp of the synchronized pipeline evaluation."""

    _attr_name = "Last pipeline evaluation"
    _attr_unique_id = "irrigationos_pipeline_last_evaluation"
    entity_id = "sensor.irrigationos_pipeline_last_evaluation"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        evaluation = self.coordinator.pipeline_evaluation
        return evaluation.evaluated_at if evaluation is not None else None


class IrrigationOSScientificInputStatusSensor(IrrigationOSEntity, SensorEntity):
    """Expose normalized scientific-input readiness."""

    _attr_name = "Scientific input status"
    _attr_unique_id = "irrigationos_scientific_input_status"
    entity_id = "sensor.irrigationos_scientific_input_status"
    _attr_icon = "mdi:flask-outline"

    @property
    def native_value(self) -> str:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return "unavailable"
        return evaluation.scientific_inputs.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None:
            return {}
        inputs = evaluation.scientific_inputs
        return {
            "resolved_area_count": inputs.resolved_area_count,
            "area_count": len(inputs.area_knowledge),
            "blocker_codes": list(inputs.blocker_codes),
        }


class IrrigationOSWeatherSourceSensor(IrrigationOSEntity, SensorEntity):
    """Expose the selected Home Assistant weather source."""

    _attr_name = "Weather source"
    _attr_unique_id = "irrigationos_weather_source"
    entity_id = "sensor.irrigationos_weather_source"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:weather-partly-cloudy"

    @property
    def native_value(self) -> str:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None or evaluation.scientific_inputs.weather is None:
            return "unavailable"
        return evaluation.scientific_inputs.weather.entity_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.coordinator.pipeline_evaluation
        if evaluation is None or evaluation.scientific_inputs.weather is None:
            return {}
        weather = evaluation.scientific_inputs.weather
        return {
            "observed_at": weather.observed_at.isoformat(),
            "condition": weather.condition,
            "temperature_celsius": weather.temperature_celsius,
            "relative_humidity_percent": weather.relative_humidity_percent,
            "pressure_hpa": weather.pressure_hpa,
            "wind_speed_meters_per_second": weather.wind_speed_meters_per_second,
            "wind_bearing_degrees": weather.wind_bearing_degrees,
            "known_fact_count": weather.known_fact_count,
        }
