"""Constants for IrrigationOS."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "irrigationos"
NAME: Final = "IrrigationOS"
VERSION: Final = "0.4.0"

CONF_API_KEY: Final = "api_key"
CONF_PERSON_ID: Final = "person_id"
CONF_CONTROLLER_PROVIDER: Final = "controller_provider"
CONF_OPERATING_MODE: Final = "operating_mode"
CONF_AREA_PROFILES: Final = "area_profiles"
CONF_AREA_ID: Final = "area_id"

MODE_OBSERVATION: Final = "observation"
MODE_SIMULATION: Final = "simulation"
MODE_LIVE: Final = "live"
DEFAULT_OPERATING_MODE: Final = MODE_OBSERVATION

PLATFORMS: Final = ["sensor", "binary_sensor"]
UPDATE_INTERVAL_MINUTES: Final = 5
