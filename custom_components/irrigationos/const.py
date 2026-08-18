"""Constants for IrrigationOS."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "irrigationos"
NAME: Final = "IrrigationOS"
VERSION: Final = "1.0.48"

CONF_API_KEY: Final = "api_key"
CONF_PERSON_ID: Final = "person_id"
CONF_CONTROLLER_PROVIDER: Final = "controller_provider"
CONF_OPERATING_MODE: Final = "operating_mode"
CONF_AREA_PROFILES: Final = "area_profiles"
CONF_AREA_ID: Final = "area_id"
CONF_IDENTITY_REGISTRY: Final = "identity_registry"
CONF_WEBHOOK_ID: Final = "webhook_id"
CONF_WEBHOOK_AUTH: Final = "webhook_auth"
CONF_CLOUDHOOK_URL: Final = "cloudhook_url"
DEFAULT_CONTROLLER_PROVIDER: Final = "rachio"

MODE_OBSERVATION: Final = "observation"
MODE_SIMULATION: Final = "simulation"
MODE_LIVE: Final = "live"
DEFAULT_OPERATING_MODE: Final = MODE_OBSERVATION

PLATFORMS: Final = ["sensor", "binary_sensor", "button"]
UPDATE_INTERVAL_MINUTES: Final = 5

EVENT_HEALTH_UNHEALTHY: Final = "irrigationos_health_unhealthy"
EVENT_HEALTH_RECOVERED: Final = "irrigationos_health_recovered"
