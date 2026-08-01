"""Controller-agnostic interfaces for IrrigationOS."""

from .base import ControllerAdapter
from .models import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
)
from .registry import ControllerAdapterRegistry

__all__ = [
    "ControllerAdapter",
    "ControllerAdapterRegistry",
    "ControllerAvailability",
    "ControllerCapabilities",
    "ControllerRegistrySnapshot",
    "IrrigationArea",
    "IrrigationAreaState",
    "IrrigationController",
]
