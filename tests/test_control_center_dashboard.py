"""Contract tests for the observation-only Control Center dashboard."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs/dashboard/irrigationos_control_center.yaml"

GLOBAL_ENTITY_IDS = {
    "sensor.irrigationos_status",
    "sensor.irrigationos_controller_provider",
    "sensor.irrigationos_controller_count",
    "sensor.irrigationos_area_count",
    "sensor.irrigationos_landscape_profile_status",
    "sensor.irrigationos_last_successful_refresh",
    "sensor.irrigationos_discovery_summary",
    "binary_sensor.irrigationos_cloud_connection",
    "binary_sensor.irrigationos_realtime_observation",
    "binary_sensor.irrigationos_polling_fallback",
    "binary_sensor.irrigationos_watering_active",
}


def test_control_center_uses_public_entity_and_watering_attribute_contract() -> None:
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    referenced_entities = set(
        re.findall(r"(?:binary_sensor|sensor)\.[a-z0-9_]+", dashboard)
    )

    assert referenced_entities >= GLOBAL_ENTITY_IDS
    assert "active_zone_count" in dashboard
    assert "active_zone_names" in dashboard
    assert "active_zone_slots" in dashboard
    assert "active_zone_vendor_names" in dashboard
    assert "'friendly_names'" not in dashboard
    assert "'slot_numbers'" not in dashboard
    assert "'vendor_names'" not in dashboard
