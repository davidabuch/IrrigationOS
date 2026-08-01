"""Typed Rachio observation models used by IrrigationOS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RachioZone:
    """A read-only irrigation zone discovered from Rachio."""

    native_id: str
    controller_native_id: str
    name: str
    enabled: bool
    zone_number: int | None
    last_watered_epoch_ms: int | None
    root_zone_depth_inches: float | None
    efficiency: float | None
    soil_name: str | None
    crop_name: str | None
    nozzle_name: str | None
    nozzle_inches_per_hour: float | None

    @classmethod
    def from_api(cls, payload: dict[str, Any], controller_id: str) -> RachioZone:
        """Build a zone from a Rachio API payload."""
        zone_id = _required_string(payload, "id", "zone")
        return cls(
            native_id=zone_id,
            controller_native_id=controller_id,
            name=_optional_string(payload.get("name")) or f"Zone {payload.get('zoneNumber', '?')}",
            enabled=bool(payload.get("enabled", False)),
            zone_number=_optional_int(payload.get("zoneNumber")),
            last_watered_epoch_ms=_optional_int(payload.get("lastWateredDate")),
            root_zone_depth_inches=_optional_float(payload.get("rootZoneDepth")),
            efficiency=_optional_float(payload.get("efficiency")),
            soil_name=_nested_name(payload.get("customSoil")),
            crop_name=_nested_name(payload.get("customCrop")),
            nozzle_name=_nested_name(payload.get("customNozzle")),
            nozzle_inches_per_hour=_nested_float(payload.get("customNozzle"), "inchesPerHour"),
        )


@dataclass(frozen=True, slots=True)
class RachioController:
    """A read-only Rachio controller and its zones."""

    native_id: str
    name: str
    status: str
    on: bool
    model: str | None
    serial_number: str | None
    latitude: float | None
    longitude: float | None
    zones: tuple[RachioZone, ...]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> RachioController:
        """Build a controller from a Rachio API payload."""
        controller_id = _required_string(payload, "id", "controller")
        raw_zones = payload.get("zones", [])
        zones = tuple(
            RachioZone.from_api(zone, controller_id)
            for zone in raw_zones
            if isinstance(zone, dict)
        )
        return cls(
            native_id=controller_id,
            name=_optional_string(payload.get("name")) or "Rachio Controller",
            status=_optional_string(payload.get("status")) or "UNKNOWN",
            on=bool(payload.get("on", False)),
            model=_optional_string(payload.get("model")),
            serial_number=_optional_string(payload.get("serialNumber")),
            latitude=_optional_float(payload.get("latitude")),
            longitude=_optional_float(payload.get("longitude")),
            zones=zones,
        )


@dataclass(frozen=True, slots=True)
class RachioAccountSnapshot:
    """Normalized read-only snapshot of a Rachio account."""

    person_id: str
    full_name: str | None
    username: str | None
    controllers: tuple[RachioController, ...]

    @property
    def zones(self) -> tuple[RachioZone, ...]:
        """Return all zones across all controllers."""
        return tuple(zone for controller in self.controllers for zone in controller.zones)

    @classmethod
    def from_person_payload(cls, payload: dict[str, Any]) -> RachioAccountSnapshot:
        """Build a snapshot from the Rachio person payload."""
        person_id = _required_string(payload, "id", "person")
        raw_devices = payload.get("devices", [])
        controllers = tuple(
            RachioController.from_api(device)
            for device in raw_devices
            if isinstance(device, dict)
        )
        return cls(
            person_id=person_id,
            full_name=_optional_string(payload.get("fullName")),
            username=_optional_string(payload.get("username")),
            controllers=controllers,
        )


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
