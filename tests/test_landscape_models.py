"""Tests for the controller-agnostic Landscape Digital Twin models."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = ROOT / "custom_components/irrigationos/landscape/models.py"
BUILDER_PATH = ROOT / "custom_components/irrigationos/landscape/builder.py"
OPTIONS_PATH = ROOT / "custom_components/irrigationos/config_flow.py"
SENSOR_PATH = ROOT / "custom_components/irrigationos/sensor.py"

SPEC = importlib.util.spec_from_file_location("irrigationos_landscape_models", MODELS_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

IrrigationAreaProfile = MODULE.IrrigationAreaProfile
IrrigationMethod = MODULE.IrrigationMethod
LandscapeProfile = MODULE.LandscapeProfile
PlantType = MODULE.PlantType
ProfileValue = MODULE.ProfileValue
ProfileValueSource = MODULE.ProfileValueSource
SoilTexture = MODULE.SoilTexture
SunExposure = MODULE.SunExposure


def _profile(**overrides: object) -> Any:
    values = {
        "area_id": "rachio:zone-1",
        "display_name": ProfileValue("Avocado Tree", ProfileValueSource.CONTROLLER, 100),
        "plant_type": ProfileValue(PlantType.TREE, ProfileValueSource.USER, 95),
        "plant_description": ProfileValue("Avocado", ProfileValueSource.USER, 95),
        "irrigation_method": ProfileValue(IrrigationMethod.DRIP, ProfileValueSource.USER, 95),
        "sun_exposure": ProfileValue(SunExposure.FULL_SUN, ProfileValueSource.USER, 90),
        "slope_percent": ProfileValue(8.0, ProfileValueSource.USER, 80),
        "soil_texture": ProfileValue(SoilTexture.CLAY_LOAM, ProfileValueSource.USER, 75),
        "soil_description": ProfileValue("Clay loam", ProfileValueSource.USER, 75),
        "root_depth_inches": ProfileValue(24.0, ProfileValueSource.USER, 90),
        "application_rate_inches_per_hour": ProfileValue(
            0.5, ProfileValueSource.CONTROLLER, 85
        ),
        "distribution_efficiency": ProfileValue(0.8, ProfileValueSource.USER, 85),
    }
    values.update(overrides)
    return IrrigationAreaProfile(**values)


def test_profile_value_validates_confidence() -> None:
    try:
        ProfileValue("value", ProfileValueSource.USER, 101)
    except ValueError as err:
        assert "between 0 and 100" in str(err)
    else:
        raise AssertionError("Out-of-range confidence was accepted")


def test_complete_area_profile_reports_full_completion() -> None:
    profile = _profile()
    assert profile.is_complete is True
    assert profile.completion_percent == 100


def test_unknown_planning_field_marks_profile_incomplete() -> None:
    profile = _profile(
        sun_exposure=ProfileValue(SunExposure.UNKNOWN, ProfileValueSource.UNKNOWN, 0)
    )
    assert profile.is_complete is False
    assert profile.completion_percent == 88


def test_landscape_profile_looks_up_area_and_counts_complete_profiles() -> None:
    profile = _profile()
    landscape = LandscapeProfile(schema_version=1, areas=(profile,))
    assert landscape.get_area("rachio:zone-1") is profile
    assert landscape.complete_area_count == 1


def test_landscape_boundary_is_wired_into_builder_options_and_entities() -> None:
    builder = BUILDER_PATH.read_text(encoding="utf-8")
    options = OPTIONS_PATH.read_text(encoding="utf-8")
    sensor = SENSOR_PATH.read_text(encoding="utf-8")
    assert "build_landscape_profile" in builder
    assert "ProfileValueSource.USER" in builder
    assert "IrrigationOSOptionsFlow" in options
    assert "IrrigationOSLandscapeProfileSensor" in sensor
