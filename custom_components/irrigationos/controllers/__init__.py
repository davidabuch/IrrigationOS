"""Controller-agnostic interfaces for IrrigationOS."""

from .base import (
    ControllerAdapter,
    ControllerAuthenticationError,
    ControllerInvalidResponseError,
    ControllerProviderError,
    ControllerRateLimitError,
)
from .identity import ControllerIdentityRegistry
from .models import (
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
from .registry import ControllerAdapterRegistry

__all__ = [
    "ControllerAdapter",
    "ControllerAdapterRegistry",
    "ControllerAuthenticationError",
    "ControllerAvailability",
    "ControllerCapabilities",
    "ControllerIdentityRegistry",
    "ControllerInvalidResponseError",
    "ControllerProviderError",
    "ControllerRateLimitError",
    "ControllerRegistrySnapshot",
    "IrrigationArea",
    "IrrigationAreaState",
    "IrrigationController",
    "ObservationError",
    "ObservationMetadata",
    "ObservationQuality",
    "VendorBinding",
]
