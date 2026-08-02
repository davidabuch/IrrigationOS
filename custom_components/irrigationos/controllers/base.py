"""Controller adapter contract for IrrigationOS."""

from __future__ import annotations

from typing import Protocol

from .models import ControllerRegistrySnapshot


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
