"""Controller adapter contract for IrrigationOS."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ControllerRegistrySnapshot, RealtimeRegistrationHealth


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
