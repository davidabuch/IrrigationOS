"""Controller registry helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .base import ControllerAdapter


@dataclass(frozen=True, slots=True)
class ControllerAdapterRegistration:
    """Registered adapter metadata."""

    provider: str
    adapter: ControllerAdapter


class ControllerAdapterRegistry:
    """Small runtime registry for controller adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ControllerAdapter] = {}

    def register(self, adapter: ControllerAdapter) -> None:
        """Register an adapter by provider name."""
        provider = adapter.provider.strip().lower()
        if not provider:
            raise ValueError("Controller adapter provider cannot be blank")
        if provider in self._adapters:
            raise ValueError(f"Controller adapter already registered: {provider}")
        self._adapters[provider] = adapter

    def get(self, provider: str) -> ControllerAdapter:
        """Return a registered adapter."""
        normalized = provider.strip().lower()
        try:
            return self._adapters[normalized]
        except KeyError as err:
            raise KeyError(f"Unknown controller adapter: {normalized}") from err

    @property
    def providers(self) -> tuple[str, ...]:
        """Return registered provider names."""
        return tuple(sorted(self._adapters))
