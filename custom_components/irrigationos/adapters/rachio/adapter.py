"""Rachio implementation of the controller adapter contract."""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from ...controllers import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerIdentityRegistry,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
    ObservationError,
    ObservationMetadata,
    ObservationQuality,
    RealtimeRegistrationHealth,
    VendorBinding,
)
from .api import RachioApiClient, RachioApiError
from .realtime import RachioWebhookRegistrar

PROVIDER: Final = "rachio"
OBSERVATION_FRESHNESS_MINUTES: Final = 10


class RachioControllerAdapter:
    """Normalize Rachio account data into canonical IrrigationOS models."""

    provider = PROVIDER

    def __init__(
        self,
        client: RachioApiClient,
        identities: ControllerIdentityRegistry,
    ) -> None:
        self._client = client
        self._identities = identities
        self._webhooks = RachioWebhookRegistrar(client)

    async def async_reconcile_realtime(
        self,
        callback_url: str,
        external_id: str,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        """Reconcile Rachio notification subscriptions for this entry."""
        return await self._webhooks.async_reconcile(
            callback_url,
            external_id,
            external_id_prefix,
            controller_native_ids,
        )

    async def async_cleanup_realtime(
        self,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        """Remove Rachio notification subscriptions for this entry."""
        return await self._webhooks.async_cleanup(
            external_id_prefix, controller_native_ids
        )

    async def async_get_account(self) -> tuple[str, ControllerRegistrySnapshot]:
        """Resolve the current Rachio account and return its first snapshot."""
        account_id, payload = await self._client.async_get_account()
        return account_id, await self._async_snapshot_from_payload(payload)

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        """Fetch and normalize the latest Rachio account snapshot."""
        payload = await self._client.async_get_person(account_id)
        return await self._async_snapshot_from_payload(payload)

    async def _async_snapshot_from_payload(
        self, payload: dict[str, Any]
    ) -> ControllerRegistrySnapshot:
        observed_at = datetime.now(UTC)
        snapshot = self.from_person_payload(payload, self._identities, observed_at=observed_at)
        results = await asyncio.gather(
            *(
                self._async_enrich_current_watering(controller)
                for controller in snapshot.controllers
            )
        )
        controllers = tuple(controller for controller, _error in results)
        errors = tuple(error for _controller, error in results if error is not None)
        quality = ObservationQuality.PARTIAL if errors else ObservationQuality.CONFIRMED
        return replace(
            snapshot,
            controllers=controllers,
            observation=replace(snapshot.observation, quality=quality, errors=errors),
        )

    async def _async_enrich_current_watering(
        self, controller: IrrigationController
    ) -> tuple[IrrigationController, ObservationError | None]:
        """Enrich watering state while preserving safe endpoint failures."""
        try:
            payload = await self._client.async_get_current_schedule(controller.native_id)
        except RachioApiError as err:
            observed_at = datetime.now(UTC)
            areas = tuple(
                replace(area, state=IrrigationAreaState.UNKNOWN)
                if area.configured and area.enabled
                else area
                for area in controller.areas
            )
            return (
                replace(
                    controller,
                    areas=areas,
                    watering_observation_quality=ObservationQuality.UNAVAILABLE,
                ),
                ObservationError(
                    endpoint="current_schedule",
                    error_type=type(err).__name__,
                    message=str(err),
                    observed_at=observed_at,
                ),
            )

        active_native_ids = _find_zone_ids(payload)
        areas = tuple(
            _with_confirmed_watering_state(area, active_native_ids)
            for area in controller.areas
        )
        return (
            replace(
                controller,
                areas=areas,
                watering_observation_quality=ObservationQuality.CONFIRMED,
            ),
            None,
        )

    @classmethod
    def from_person_payload(
        cls,
        payload: dict[str, Any],
        identities: ControllerIdentityRegistry,
        *,
        observed_at: datetime | None = None,
    ) -> ControllerRegistrySnapshot:
        """Normalize a Rachio person payload without performing enrichment."""
        timestamp = observed_at or datetime.now(UTC)
        account_id = _required_string(payload, "id", "person")
        controllers = tuple(
            _controller_from_api(device, identities)
            for device in payload.get("devices", [])
            if isinstance(device, dict)
        )
        return ControllerRegistrySnapshot(
            provider=PROVIDER,
            account_id=account_id,
            account_name=_optional_string(payload.get("fullName"))
            or _optional_string(payload.get("username")),
            controllers=controllers,
            observation=ObservationMetadata(
                observed_at=timestamp,
                fresh_until=timestamp + timedelta(minutes=OBSERVATION_FRESHNESS_MINUTES),
                source=PROVIDER,
                quality=ObservationQuality.PARTIAL,
            ),
        )


def _controller_from_api(
    payload: dict[str, Any], identities: ControllerIdentityRegistry
) -> IrrigationController:
    native_id = _required_string(payload, "id", "controller")
    controller_id = identities.controller_id_for(PROVIDER, native_id)
    availability = _normalize_availability(payload.get("status"))
    zones = tuple(item for item in payload.get("zones", []) if isinstance(item, dict))
    capacity = _controller_capacity(payload, zones)
    zones_by_slot = _zones_by_slot(zones, capacity)
    areas = tuple(
        _area_from_api(zones_by_slot.get(slot), controller_id, slot)
        for slot in range(1, capacity + 1)
    )
    return IrrigationController(
        controller_id=controller_id,
        binding=VendorBinding(PROVIDER, native_id),
        name=_optional_string(payload.get("name")) or "Irrigation Controller",
        availability=availability,
        enabled=bool(payload.get("on", False)),
        model=_optional_string(payload.get("model")),
        serial_number=_optional_string(payload.get("serialNumber")),
        firmware_version=_optional_string(payload.get("firmwareVersion")),
        latitude=_optional_float(payload.get("latitude")),
        longitude=_optional_float(payload.get("longitude")),
        capacity=capacity,
        watering_observation_quality=ObservationQuality.UNAVAILABLE,
        capabilities=ControllerCapabilities(
            observe_current_watering=True,
            observe_last_watered=True,
        ),
        areas=areas,
    )


def _area_from_api(
    payload: dict[str, Any] | None,
    controller_id: str,
    slot_number: int,
) -> IrrigationArea:
    area_id = ControllerIdentityRegistry.area_id_for(controller_id, slot_number)
    slot_name = f"Zone {slot_number}"
    if payload is None:
        return IrrigationArea(
            area_id=area_id,
            controller_id=controller_id,
            slot_number=slot_number,
            name=slot_name,
            enabled=False,
            configured=False,
            state=IrrigationAreaState.UNUSED,
        )

    native_id = _required_string(payload, "id", "zone")
    enabled = bool(payload.get("enabled", False))
    return IrrigationArea(
        area_id=area_id,
        controller_id=controller_id,
        slot_number=slot_number,
        name=slot_name,
        enabled=enabled,
        configured=True,
        state=IrrigationAreaState.UNKNOWN if enabled else IrrigationAreaState.DISABLED,
        binding=VendorBinding(PROVIDER, native_id),
        vendor_name=_optional_string(payload.get("name")),
        last_watered_epoch_ms=_optional_int(payload.get("lastWateredDate")),
        root_zone_depth_inches=_optional_float(payload.get("rootZoneDepth")),
        efficiency=_optional_float(payload.get("efficiency")),
        soil_name=_nested_name(payload.get("customSoil")),
        crop_name=_nested_name(payload.get("customCrop")),
        nozzle_name=_nested_name(payload.get("customNozzle")),
        nozzle_inches_per_hour=_nested_float(payload.get("customNozzle"), "inchesPerHour"),
    )


def _with_confirmed_watering_state(
    area: IrrigationArea, active_native_ids: set[str]
) -> IrrigationArea:
    if not area.configured:
        return area
    if not area.enabled:
        return replace(area, state=IrrigationAreaState.DISABLED)
    state = (
        IrrigationAreaState.WATERING
        if area.native_id in active_native_ids
        else IrrigationAreaState.IDLE
    )
    return replace(area, state=state)


def _controller_capacity(payload: dict[str, Any], zones: tuple[dict[str, Any], ...]) -> int:
    """Infer permanent slot capacity from explicit fields, model, and configured slots."""
    configured_max = max(
        (_optional_int(zone.get("zoneNumber")) or 0 for zone in zones),
        default=0,
    )
    for key in ("zoneCount", "capacity", "maxZones"):
        explicit = _optional_int(payload.get(key))
        if explicit is not None and explicit > 0:
            return max(explicit, configured_max)
    model = _optional_string(payload.get("model")) or ""
    match = re.search(r"(?:^|[_ -])(\d+)\s*ZONE(?:$|[_ -])", model.upper())
    if match is not None:
        return max(int(match.group(1)), configured_max)
    return max(configured_max, len(zones))


def _zones_by_slot(
    zones: tuple[dict[str, Any], ...], capacity: int
) -> dict[int, dict[str, Any]]:
    """Bind zones to reported physical numbers, then safe unclaimed fallback slots."""
    bound: dict[int, dict[str, Any]] = {}
    unnumbered: list[dict[str, Any]] = []
    for zone in zones:
        slot = _optional_int(zone.get("zoneNumber"))
        if slot is None or slot < 1 or slot > capacity or slot in bound:
            unnumbered.append(zone)
            continue
        bound[slot] = zone
    available = (slot for slot in range(1, capacity + 1) if slot not in bound)
    for zone, slot in zip(unnumbered, available, strict=False):
        bound[slot] = zone
    return bound


def _find_zone_ids(payload: object) -> set[str]:
    """Find zone identifiers in a current-schedule payload without assuming one schema."""
    found: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = key.replace("_", "").lower()
                if normalized == "zoneid" and isinstance(item, str) and item.strip():
                    found.add(item.strip())
                elif normalized == "zone" and isinstance(item, dict):
                    nested_id = item.get("id")
                    if isinstance(nested_id, str) and nested_id.strip():
                        found.add(nested_id.strip())
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return found


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
