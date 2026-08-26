"""Controller-agnostic interfaces for IrrigationOS."""

from .base import (
    ControllerAdapter,
    ControllerAuthenticationError,
    ControllerInvalidResponseError,
    ControllerProviderError,
    ControllerRateLimitError,
    GuidedObservationAdapter,
    RealtimeObservationAdapter,
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
    RealtimeRegistrationHealth,
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
    "GuidedObservationAdapter",
    "IrrigationArea",
    "IrrigationAreaState",
    "IrrigationController",
    "ObservationError",
    "ObservationMetadata",
    "ObservationQuality",
    "RealtimeObservationAdapter",
    "RealtimeRegistrationHealth",
    "VendorBinding",
]
