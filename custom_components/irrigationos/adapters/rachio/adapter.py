"""Rachio implementation of the controller adapter contract."""

from __future__ import annotations

from typing import Any, Final

from ...controllers import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
)
from .api import RachioApiClient

PROVIDER: Final = "rachio"


class RachioControllerAdapter:
    """Normalize Rachio account data into IrrigationOS domain models."""

    provider = PROVIDER

    def __init__(self, client: RachioApiClient) -> None:
        self._client = client

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        """Fetch and normalize the latest Rachio account snapshot."""
        payload = await self._client.async_get_person(account_id)
        return self.from_person_payload(payload)

    @classmethod
    def from_person_payload(cls, payload: dict[str, Any]) -> ControllerRegistrySnapshot:
        """Normalize a Rachio person payload."""
        account_id = _required_string(payload, "id", "person")
        controllers = tuple(
            _controller_from_api(device)
            for device in payload.get("devices", [])
            if isinstance(device, dict)
        )
        return ControllerRegistrySnapshot(
            provider=PROVIDER,
            account_id=account_id,
            account_name=_optional_string(payload.get("fullName"))
            or _optional_string(payload.get("username")),
            controllers=controllers,
        )


def _controller_from_api(payload: dict[str, Any]) -> IrrigationController:
    native_id = _required_string(payload, "id", "controller")
    controller_id = f"{PROVIDER}:{native_id}"
    availability = _normalize_availability(payload.get("status"))
    areas = tuple(
        _area_from_api(area, controller_id)
        for area in payload.get("zones", [])
        if isinstance(area, dict)
    )
    return IrrigationController(
        controller_id=controller_id,
        native_id=native_id,
        provider=PROVIDER,
        name=_optional_string(payload.get("name")) or "Rachio Controller",
        availability=availability,
        enabled=bool(payload.get("on", False)),
        model=_optional_string(payload.get("model")),
        serial_number=_optional_string(payload.get("serialNumber")),
        firmware_version=_optional_string(payload.get("firmwareVersion")),
        latitude=_optional_float(payload.get("latitude")),
        longitude=_optional_float(payload.get("longitude")),
        capabilities=ControllerCapabilities(
            observe_current_watering=False,
            observe_last_watered=True,
        ),
        areas=areas,
    )


def _area_from_api(payload: dict[str, Any], controller_id: str) -> IrrigationArea:
    native_id = _required_string(payload, "id", "zone")
    enabled = bool(payload.get("enabled", False))
    state = IrrigationAreaState.IDLE if enabled else IrrigationAreaState.DISABLED
    return IrrigationArea(
        area_id=f"{PROVIDER}:{native_id}",
        controller_id=controller_id,
        native_id=native_id,
        name=_optional_string(payload.get("name")) or f"Zone {payload.get('zoneNumber', '?')}",
        enabled=enabled,
        state=state,
        native_number=_optional_int(payload.get("zoneNumber")),
        last_watered_epoch_ms=_optional_int(payload.get("lastWateredDate")),
        root_zone_depth_inches=_optional_float(payload.get("rootZoneDepth")),
        efficiency=_optional_float(payload.get("efficiency")),
        soil_name=_nested_name(payload.get("customSoil")),
        crop_name=_nested_name(payload.get("customCrop")),
        nozzle_name=_nested_name(payload.get("customNozzle")),
        nozzle_inches_per_hour=_nested_float(payload.get("customNozzle"), "inchesPerHour"),
    )


def _normalize_availability(value: object) -> ControllerAvailability:
    status = _optional_string(value)
    if status is None:
        return ControllerAvailability.UNKNOWN
    normalized = status.upper()
    if normalized == "ONLINE":
        return ControllerAvailability.ONLINE
    if normalized == "OFFLINE":
        return ControllerAvailability.OFFLINE
    return ControllerAvailability.UNKNOWN


def _required_string(payload: dict[str, Any], key: str, object_name: str) -> str:
    value = _optional_string(payload.get(key))
    if value is None:
        raise ValueError(f"Rachio {object_name} payload is missing {key}")
    return value


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _nested_name(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    return _optional_string(value.get("name"))


def _nested_float(value: object, key: str) -> float | None:
    if not isinstance(value, dict):
        return None
    return _optional_float(value.get(key))
