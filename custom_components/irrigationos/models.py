"""Compatibility exports for IrrigationOS domain models."""

from __future__ import annotations

from .controllers.models import (
    ControllerAvailability,
    ControllerCapabilities,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    IrrigationController,
    ObservationError,
    ObservationMetadata,
    ObservationQuality,
    VendorBinding,
)

__all__ = [
    "ControllerAvailability",
    "ControllerCapabilities",
    "ControllerRegistrySnapshot",
    "IrrigationArea",
    "IrrigationAreaState",
    "IrrigationController",
    "ObservationError",
    "ObservationMetadata",
    "ObservationQuality",
    "VendorBinding",
]
