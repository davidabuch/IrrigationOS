"""Canonical production-target selection shared by observational consumers."""

from __future__ import annotations

from dataclasses import dataclass

from .controllers import ControllerRegistrySnapshot, IrrigationArea


@dataclass(frozen=True, slots=True, order=True)
class ProductionTarget:
    """One privacy-safe canonical configured irrigation target."""

    controller_slot: int
    area_slot: int

    def __post_init__(self) -> None:
        if self.controller_slot < 1 or self.area_slot < 1:
            raise ValueError("production target slots must be positive")

    def to_dict(self) -> dict[str, int]:
        """Return the canonical public identity without provider identifiers."""

        return {
            "controller_slot": self.controller_slot,
            "area_slot": self.area_slot,
        }


def select_production_targets(
    snapshot: ControllerRegistrySnapshot,
) -> tuple[ProductionTarget, ...]:
    """Select only configured, enabled, and provider-bound canonical targets."""

    return tuple(
        sorted(
            ProductionTarget(controller_slot, area.slot_number)
            for controller_slot, controller in enumerate(snapshot.controllers, start=1)
            for area in controller.areas
            if area.configured and area.enabled and area.binding is not None
        )
    )


def find_production_area(
    snapshot: ControllerRegistrySnapshot, target: ProductionTarget
) -> IrrigationArea | None:
    """Resolve a selected target to its internal canonical area observation."""

    if target.controller_slot > len(snapshot.controllers):
        return None
    controller = snapshot.controllers[target.controller_slot - 1]
    return next(
        (area for area in controller.areas if area.slot_number == target.area_slot),
        None,
    )


__all__ = ["ProductionTarget", "select_production_targets"]
