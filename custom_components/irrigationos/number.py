"""Manual-watering duration controls for IrrigationOS production zones."""

from __future__ import annotations

import math

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controllers import IrrigationArea
from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSAreaEntity
from .manual_watering import manual_watering_display_name, manual_watering_object_id
from .production_targets import find_production_area, select_production_targets
from .reconciliation import EntityInventory, controller_first


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up restore-backed manual-watering duration entities."""

    del hass
    coordinator = entry.runtime_data
    inventory = EntityInventory()

    def _new_entities() -> list[IrrigationOSManualWateringDurationNumber]:
        candidates: dict[str, IrrigationOSManualWateringDurationNumber] = {}
        for target in select_production_targets(coordinator.data):
            area = find_production_area(coordinator.data, target)
            if area is not None:
                candidates[area.area_id] = IrrigationOSManualWateringDurationNumber(
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


class IrrigationOSManualWateringDurationNumber(IrrigationOSAreaEntity, RestoreNumber):
    """Select a finite manual runtime without affecting irrigation science."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:timer-outline"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 180
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: IrrigationOSCoordinator,
        area: IrrigationArea,
        *,
        controller_slot: int,
    ) -> None:
        super().__init__(coordinator, area)
        self.controller_slot = controller_slot
        self._attr_unique_id = f"{area.area_id}_manual_watering_duration"
        object_id = manual_watering_object_id(
            controller_slot, area.slot_number, "manual_watering_duration"
        )
        self._attr_suggested_object_id = object_id
        self.entity_id = f"number.{object_id}"

    @property
    def name(self) -> str:
        """Return the latest user-facing zone name without changing identity."""

        return (
            f"{manual_watering_display_name(self.coordinator, self.area, self.controller_slot)} "
            "manual watering duration"
        )

    @property
    def native_value(self) -> float:
        """Return the selected whole-minute duration."""

        return self.coordinator.manual_watering_durations.runtime_seconds(
            self.area_id
        ) / 60

    async def async_added_to_hass(self) -> None:
        """Restore the HA-native preference without restoring command authority."""

        await super().async_added_to_hass()
        restored = await self.async_get_last_number_data()
        if restored is None or restored.native_value is None:
            return
        value = float(restored.native_value)
        if math.isfinite(value) and value.is_integer() and 1 <= value <= 180:
            self.coordinator.manual_watering_durations.set_runtime_seconds(
                self.area_id, int(value) * 60
            )

    async def async_set_native_value(self, value: float) -> None:
        """Set a validated whole-minute manual runtime."""

        if not math.isfinite(value) or not value.is_integer() or not 1 <= value <= 180:
            raise ValueError("manual watering duration must be 1 to 180 whole minutes")
        self.coordinator.manual_watering_durations.set_runtime_seconds(
            self.area_id, int(value) * 60
        )
        self.async_write_ha_state()
