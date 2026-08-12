"""Diagnostics for IrrigationOS."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_CLOUDHOOK_URL,
    CONF_IDENTITY_REGISTRY,
    CONF_WEBHOOK_AUTH,
    CONF_WEBHOOK_ID,
)
from .coordinator import IrrigationOSCoordinator
from .diagnostic_data import redact_data

TO_REDACT = {
    CONF_API_KEY,
    CONF_IDENTITY_REGISTRY,
    CONF_CLOUDHOOK_URL,
    CONF_WEBHOOK_AUTH,
    CONF_WEBHOOK_ID,
    "webhook_url",
    "external_id",
    "authorization",
    "signature",
    "x-signature",
    "id",
    "person_id",
    "native_id",
    "controller_native_id",
    "account_id",
    "controller_id",
    "area_id",
    "assessment_id",
    "recommendation_assessment_id",
    "plant_instance_id",
    "location_id",
    "plan_id",
    "schedule_id",
    "execution_plan_id",
    "report_id",
    "request_id",
    "command_id",
    "scheduled_action_id",
    "target_id",
    "serial_number",
    "serialNumber",
    "macAddress",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
) -> dict[str, Any]:
    """Return redacted diagnostics."""
    del hass
    snapshot = asdict(entry.runtime_data.data)
    landscape = asdict(entry.runtime_data.landscape)
    realtime = entry.runtime_data.realtime
    pipeline = entry.runtime_data.pipeline_evaluation
    pipeline_summary = None
    if pipeline is not None:
        pipeline_summary = {
            "algorithm_version": pipeline.algorithm_version,
            "status": pipeline.status.value,
            "current_stage": pipeline.current_stage.value,
            "evaluated_at": pipeline.evaluated_at.isoformat(),
            "configured_area_count": pipeline.configured_area_count,
            "complete_profile_count": pipeline.complete_profile_count,
            "blocker_codes": list(pipeline.blocker_codes),
            "stages": {
                stage.stage.value: {
                    "status": stage.status.value,
                    "reason": stage.reason,
                    "blocker_codes": list(stage.blocker_codes),
                }
                for stage in pipeline.stages
            },
            "output_counts": {
                "water_requirements": len(pipeline.water_requirements),
                "plant_stress": len(pipeline.plant_stress),
                "plant_health": len(pipeline.plant_health),
                "recommendations": len(pipeline.recommendations),
                "planning": len(pipeline.planning),
                "scheduling": len(pipeline.scheduling),
                "execution": len(pipeline.execution),
                "runtime_monitoring": len(pipeline.runtime_monitoring),
            },
        }
    return {
        "entry": redact_data(dict(entry.data), TO_REDACT),
        "coordinator": {
            "last_update_success": entry.runtime_data.last_update_success,
            "last_successful_refresh": (
                entry.runtime_data.last_successful_refresh.isoformat()
                if entry.runtime_data.last_successful_refresh is not None
                else None
            ),
            "refresh_count": entry.runtime_data.refresh_count,
            "last_exception": (
                str(entry.runtime_data.last_exception)
                if entry.runtime_data.last_exception is not None
                else None
            ),
            "data": redact_data(snapshot, TO_REDACT),
            "landscape": redact_data(landscape, TO_REDACT),
            "pipeline_summary": pipeline_summary,
            "pipeline_evaluation": (
                redact_data(asdict(pipeline), TO_REDACT)
                if pipeline is not None
                else None
            ),
            "realtime": (
                redact_data(realtime.diagnostics(), TO_REDACT)
                if realtime is not None
                else None
            ),
            "operational_health": entry.runtime_data.operational_health_diagnostics(),
            "shadow_evaluations": entry.runtime_data.shadow_evaluations.diagnostics(),
            "actual_vs_shadow": entry.runtime_data.actual_vs_shadow.diagnostics(),
            "commissioning_report": entry.runtime_data.commissioning_report.diagnostics(),
            "command_acknowledgements": (
                entry.runtime_data.command_acknowledgements.diagnostics()
            ),
            "command_receipts": entry.runtime_data.command_receipts.diagnostics(),
            "replay_readiness": entry.runtime_data.replay_readiness.diagnostics(),
            "execution_authorization": entry.runtime_data.execution_authorization.diagnostics(),
            "ownership_commissioning": entry.runtime_data.ownership_commissioning.diagnostics(),
            "live_mode_safety": entry.runtime_data.live_mode_safety.diagnostics(),
            "manual_override_preservation": (
                entry.runtime_data.manual_override_preservation.diagnostics()
            ),
            "safety_preemption": entry.runtime_data.safety_preemption.diagnostics(),
            "sunrise_hard_stop": entry.runtime_data.sunrise_hard_stop.diagnostics(),
        },
    }
