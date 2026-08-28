"""Native Home Assistant valves for explicit IrrigationOS manual watering."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controllers import (
    ControllerAvailability,
    IrrigationArea,
    IrrigationAreaState,
    ObservationQuality,
)
from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSAreaEntity
from .manual_watering import manual_watering_display_name, manual_watering_object_id
from .production_targets import find_production_area, select_production_targets
from .reconciliation import EntityInventory, controller_first
from .supervised_operation import (
    SupervisedOperationStatus,
    async_run_manual_operation,
    async_stop_manual_operation,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up manual-watering valves for selected production targets."""

    del hass
    coordinator = entry.runtime_data
    inventory = EntityInventory()

    def _new_entities() -> list[IrrigationOSManualWateringValve]:
        candidates: dict[str, IrrigationOSManualWateringValve] = {}
        for target in select_production_targets(coordinator.data):
            area = find_production_area(coordinator.data, target)
            if area is not None:
                candidates[area.area_id] = IrrigationOSManualWateringValve(
                    coordinator,
                    area,
                    controller_slot=target.controller_slot,
                )
        result = inventory.reconcile(set(candidates))
        return [candidates[key] for key in controller_first(result.added)]

    async_add_entities(_new_entities())

    def _async_reconcile() -> None:
        additions = _new_entities()
        if additions:
            async_add_entities(additions)

    entry.async_on_unload(coordinator.async_add_listener(_async_reconcile))


class IrrigationOSManualWateringValve(IrrigationOSAreaEntity, ValveEntity):
    """Observation-driven valve with an audited operator-only command boundary."""

    _attr_has_entity_name = False
    _attr_device_class = ValveDeviceClass.WATER
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False
    _attr_icon = "mdi:valve"

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        area: IrrigationArea,
        *,
        controller_slot: int,
    ) -> None:
        super().__init__(coordinator, area)
        self.controller_slot = controller_slot
        self._attr_unique_id = f"{area.area_id}_manual_watering_valve"
        object_id = manual_watering_object_id(
            controller_slot, area.slot_number, "manual_watering"
        )
        self._attr_suggested_object_id = object_id
        self.entity_id = f"valve.{object_id}"

    @property
    def name(self) -> str:
        """Return the latest commissioned/native/fallback name."""

        return (
            f"{manual_watering_display_name(self.coordinator, self.area, self.controller_slot)} "
            "manual watering"
        )

    @property
    def available(self) -> bool:
        """Fail unavailable when the current watering observation is not trustworthy."""

        area = self._current_area()
        controller = next(
            (
                item
                for item in self.coordinator.data.controllers
                if item.controller_id == self.controller_id
            ),
            None,
        )
        now = datetime.now(UTC)
        return bool(
            super().available
            and self.coordinator.last_update_success
            and area is not None
            and area.configured
            and area.enabled
            and area.binding is not None
            and controller is not None
            and controller.enabled
            and controller.availability is ControllerAvailability.ONLINE
            and controller.watering_observation_quality
            is ObservationQuality.CONFIRMED
            and self.coordinator.data.observation.quality
            is ObservationQuality.CONFIRMED
            and self.coordinator.data.observation.is_fresh(now)
        )

    @property
    def is_closed(self) -> bool | None:
        """Expose only observed watering/idle state; never optimistic command state."""

        if not self.available:
            return None
        if self.area.state is IrrigationAreaState.WATERING:
            return False
        if self.area.state is IrrigationAreaState.IDLE:
            return True
        return None

    async def async_open_valve(self) -> None:
        """Treat this HA action as explicit operator approval, preserving all other gates."""

        result = await async_run_manual_operation(
            self.coordinator,
            controller_slot=self.controller_slot,
            area_slot=self.area.slot_number,
            runtime_seconds=self.coordinator.manual_watering_durations.runtime_seconds(
                self.area_id
            ),
        )
        if result.status is not SupervisedOperationStatus.START_DISPATCHED:
            raise HomeAssistantError(
                "Manual watering was not started: "
                + (", ".join(result.blocker_codes) or result.status.value)
            )

    async def async_close_valve(self) -> None:
        """Request the provider-supported controller-wide safe stop."""

        result = await async_stop_manual_operation(
            self.coordinator,
            controller_slot=self.controller_slot,
            area_slot=self.area.slot_number,
        )
        if result.status is not SupervisedOperationStatus.STOP_DISPATCHED:
            raise HomeAssistantError(
                "Manual watering stop was not confirmed: "
                + (", ".join(result.blocker_codes) or result.status.value)
            )
