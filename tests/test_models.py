"""Tests for normalized Rachio observation models."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "irrigationos"
    / "models.py"
)
SPEC = importlib.util.spec_from_file_location("irrigationos_models", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
RachioAccountSnapshot = MODULE.RachioAccountSnapshot


def sample_person_payload() -> dict[str, object]:
    """Return a representative account payload."""
    return {
        "id": "person-1",
        "fullName": "Test User",
        "username": "test",
        "devices": [
            {
                "id": "controller-1",
                "name": "Home",
                "status": "ONLINE",
                "on": False,
                "model": "GENERATION3_8ZONE",
                "serialNumber": "secret-serial",
                "latitude": 34.0,
                "longitude": -118.0,
                "zones": [
                    {
                        "id": "zone-1",
                        "zoneNumber": 1,
                        "name": "Avocado Tree",
                        "enabled": True,
                        "rootZoneDepth": 12,
                        "efficiency": 0.85,
                        "lastWateredDate": 123456789,
                        "customSoil": {"name": "LOAM"},
                        "customCrop": {"name": "Trees"},
                        "customNozzle": {
                            "name": "DRIP",
                            "inchesPerHour": 0.5,
                        },
                    }
                ],
            }
        ],
    }


def test_account_snapshot_normalizes_controllers_and_zones() -> None:
    snapshot = RachioAccountSnapshot.from_person_payload(sample_person_payload())
    assert snapshot.person_id == "person-1"
    assert len(snapshot.controllers) == 1
    assert len(snapshot.zones) == 1
    controller = snapshot.controllers[0]
    zone = snapshot.zones[0]
    assert controller.name == "Home"
    assert controller.status == "ONLINE"
    assert zone.name == "Avocado Tree"
    assert zone.soil_name == "LOAM"
    assert zone.nozzle_inches_per_hour == 0.5


def test_missing_person_id_is_rejected() -> None:
    payload = sample_person_payload()
    payload.pop("id")
    try:
        RachioAccountSnapshot.from_person_payload(payload)
    except ValueError as err:
        assert "person" in str(err)
    else:
        raise AssertionError("Missing person id should be rejected")


def test_malformed_zone_entries_are_ignored() -> None:
    payload = sample_person_payload()
    devices = payload["devices"]
    assert isinstance(devices, list)
    controller = devices[0]
    assert isinstance(controller, dict)
    controller["zones"] = [None, "bad", controller["zones"][0]]
    snapshot = RachioAccountSnapshot.from_person_payload(payload)
    assert len(snapshot.zones) == 1
