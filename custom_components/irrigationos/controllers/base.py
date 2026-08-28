"""Controller adapter contract for IrrigationOS."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ControllerRegistrySnapshot, RealtimeRegistrationHealth, VendorBinding


class ControllerProviderError(Exception):
    """Base error raised by controller providers."""


class ControllerAuthenticationError(ControllerProviderError):
    """Raised when provider credentials are rejected."""


class ControllerRateLimitError(ControllerProviderError):
    """Raised when a provider rate limit is reached."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ControllerInvalidResponseError(ControllerProviderError):
    """Raised when a provider returns malformed data."""


class ControllerAdapter(Protocol):
    """Protocol implemented by every irrigation controller adapter."""

    provider: str

    async def async_get_account(self) -> tuple[str, ControllerRegistrySnapshot]:
        """Resolve the provider account and return its first snapshot."""
        ...

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        """Return the latest normalized controller registry snapshot."""
        ...


@runtime_checkable
class GuidedObservationAdapter(Protocol):
    """Optional provider boundary for one operator-directed observation run."""

    async def async_start_guided_observation(
        self, *, area_binding: VendorBinding, duration_seconds: int
    ) -> None:
        """Start exactly one selected area for a bounded observation."""
        ...

    async def async_stop_guided_observation(
        self, *, controller_binding: VendorBinding
    ) -> None:
        """Stop the controller used by the current guided observation."""
        ...


@runtime_checkable
class ManualWateringAdapter(Protocol):
    """Optional provider boundary for explicit operator-directed watering."""

    async def async_start_manual_watering(
        self, *, area_binding: VendorBinding, duration_seconds: int
    ) -> None:
        """Start exactly one selected area for a finite manual runtime."""
        ...

    async def async_stop_manual_watering(
        self, *, controller_binding: VendorBinding
    ) -> None:
        """Stop watering using the provider's supported controller boundary."""
        ...


@runtime_checkable
class RealtimeObservationAdapter(Protocol):
    """Optional provider contract for read-only realtime observations."""

    async def async_reconcile_realtime(
        self,
        callback_url: str,
        external_id: str,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        """Idempotently reconcile remote observation subscriptions."""
        ...

    async def async_cleanup_realtime(
        self,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        """Remove remote observation subscriptions owned by this entry."""
        ...
