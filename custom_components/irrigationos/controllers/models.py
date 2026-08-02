"""Controller-agnostic domain models for IrrigationOS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class ControllerAvailability(StrEnum):
    """Normalized controller availability."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class IrrigationAreaState(StrEnum):
    """Normalized read-only state for an irrigation slot."""

    IDLE = "idle"
    WATERING = "watering"
    DISABLED = "disabled"
    UNUSED = "unused"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ObservationQuality(StrEnum):
    """Confidence in an observation source."""

    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class VendorBinding:
    """Replaceable binding from a canonical object to a provider object."""

    provider: str
    native_id: str


@dataclass(frozen=True, slots=True)
class ObservationError:
    """Safe endpoint-specific observation failure."""

    endpoint: str
    error_type: str
    message: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ObservationMetadata:
    """Freshness, source quality, and partial failures for a snapshot."""

    observed_at: datetime
    fresh_until: datetime
    source: str
    quality: ObservationQuality
    errors: tuple[ObservationError, ...] = ()

    def is_fresh(self, at: datetime | None = None) -> bool:
        """Return whether the observation remains within its freshness window."""
        current = at or datetime.now(UTC)
        return current <= self.fresh_until


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
    """Permanent controller slot with an optional provider-zone binding."""

    area_id: str
    controller_id: str
    slot_number: int
    name: str
    enabled: bool
    configured: bool
    state: IrrigationAreaState
    binding: VendorBinding | None = None
    vendor_name: str | None = None
    last_watered_epoch_ms: int | None = None
    root_zone_depth_inches: float | None = None
    efficiency: float | None = None
    soil_name: str | None = None
    crop_name: str | None = None
    nozzle_name: str | None = None
    nozzle_inches_per_hour: float | None = None

    @property
    def native_id(self) -> str | None:
        """Return the replaceable provider identifier, when configured."""
        return self.binding.native_id if self.binding is not None else None

    @property
    def native_number(self) -> int:
        """Compatibility alias for the canonical slot number."""
        return self.slot_number


@dataclass(frozen=True, slots=True)
class IrrigationController:
    """Canonical irrigation controller with permanent delivery slots."""

    controller_id: str
    binding: VendorBinding
    name: str
    availability: ControllerAvailability
    enabled: bool
    model: str | None
    serial_number: str | None
    firmware_version: str | None
    latitude: float | None
    longitude: float | None
    capacity: int
    watering_observation_quality: ObservationQuality
    capabilities: ControllerCapabilities
    areas: tuple[IrrigationArea, ...]

    @property
    def provider(self) -> str:
        """Return the bound provider name."""
        return self.binding.provider

    @property
    def native_id(self) -> str:
        """Return the replaceable provider identifier."""
        return self.binding.native_id


@dataclass(frozen=True, slots=True)
class ControllerRegistrySnapshot:
    """Normalized snapshot returned by the active controller adapter."""

    provider: str
    account_id: str
    account_name: str | None
    controllers: tuple[IrrigationController, ...]
    observation: ObservationMetadata

    @property
    def areas(self) -> tuple[IrrigationArea, ...]:
        """Return every permanent slot across all controllers."""
        return tuple(area for controller in self.controllers for area in controller.areas)

    @property
    def configured_areas(self) -> tuple[IrrigationArea, ...]:
        """Return slots currently bound to provider zones."""
        return tuple(area for area in self.areas if area.configured)


@dataclass(frozen=True, slots=True)
class RealtimeRegistrationHealth:
    """Provider-neutral result of remote realtime subscription reconciliation."""

    healthy: bool
    registered_controllers: int
    expected_controllers: int
    error: str | None = None
    error_category: str | None = None
    http_status: int | None = None
