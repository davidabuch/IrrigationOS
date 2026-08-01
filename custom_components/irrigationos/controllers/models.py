"""Controller-agnostic domain models for IrrigationOS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ControllerAvailability(StrEnum):
    """Normalized controller availability."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class IrrigationAreaState(StrEnum):
    """Normalized read-only state for an irrigation area."""

    IDLE = "idle"
    WATERING = "watering"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ControllerCapabilities:
    """Capabilities exposed by a controller adapter."""

    observe_controllers: bool = True
    observe_areas: bool = True
    observe_current_watering: bool = False
    observe_last_watered: bool = False
    supports_start_area: bool = False
    supports_stop_area: bool = False
    supports_stop_all: bool = False
    supports_rain_delay: bool = False


@dataclass(frozen=True, slots=True)
class IrrigationArea:
    """Controller-agnostic irrigation delivery area."""

    area_id: str
    controller_id: str
    native_id: str
    name: str
    enabled: bool
    state: IrrigationAreaState
    native_number: int | None = None
    last_watered_epoch_ms: int | None = None
    root_zone_depth_inches: float | None = None
    efficiency: float | None = None
    soil_name: str | None = None
    crop_name: str | None = None
    nozzle_name: str | None = None
    nozzle_inches_per_hour: float | None = None


@dataclass(frozen=True, slots=True)
class IrrigationController:
    """Controller-agnostic irrigation controller."""

    controller_id: str
    native_id: str
    provider: str
    name: str
    availability: ControllerAvailability
    enabled: bool
    model: str | None
    serial_number: str | None
    firmware_version: str | None
    latitude: float | None
    longitude: float | None
    capabilities: ControllerCapabilities
    areas: tuple[IrrigationArea, ...]


@dataclass(frozen=True, slots=True)
class ControllerRegistrySnapshot:
    """Normalized snapshot returned by the active controller adapter."""

    provider: str
    account_id: str
    account_name: str | None
    controllers: tuple[IrrigationController, ...]

    @property
    def areas(self) -> tuple[IrrigationArea, ...]:
        """Return all irrigation areas across all controllers."""
        return tuple(area for controller in self.controllers for area in controller.areas)
