"""Controller adapter contract for IrrigationOS."""

from __future__ import annotations

from typing import Protocol

from .models import ControllerRegistrySnapshot


class ControllerAdapter(Protocol):
    """Protocol implemented by every irrigation controller adapter."""

    provider: str

    async def async_get_snapshot(self, account_id: str) -> ControllerRegistrySnapshot:
        """Return the latest normalized controller registry snapshot."""
        ...
