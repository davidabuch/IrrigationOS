"""Runtime composition for controller providers."""

from __future__ import annotations

from collections.abc import Callable

from aiohttp import ClientSession

from ..controllers import ControllerAdapter, ControllerIdentityRegistry
from ..first_live_delivery.rachio import RachioFirstLiveTransport
from .rachio import PROVIDER as RACHIO_PROVIDER
from .rachio import RachioApiClient, RachioControllerAdapter

AdapterBuilder = Callable[[ClientSession, str, ControllerIdentityRegistry], ControllerAdapter]


class ControllerProviderFactory:
    """Create provider adapters through registered composition roots."""

    def __init__(self) -> None:
        self._builders: dict[str, AdapterBuilder] = {}

    def register(self, provider: str, builder: AdapterBuilder) -> None:
        """Register one provider builder."""
        normalized = provider.strip().lower()
        if not normalized:
            raise ValueError("Provider cannot be blank")
        if normalized in self._builders:
            raise ValueError(f"Provider already registered: {normalized}")
        self._builders[normalized] = builder

    def create(
        self,
        provider: str,
        session: ClientSession,
        api_key: str,
        identities: ControllerIdentityRegistry,
    ) -> ControllerAdapter:
        """Create the configured provider adapter."""
        normalized = provider.strip().lower()
        try:
            builder = self._builders[normalized]
        except KeyError as err:
            raise ValueError(f"Unsupported controller provider: {normalized}") from err
        return builder(session, api_key, identities)


def _build_rachio(
    session: ClientSession,
    api_key: str,
    identities: ControllerIdentityRegistry,
) -> ControllerAdapter:
    return RachioControllerAdapter(
        RachioApiClient(session, api_key),
        identities,
        RachioFirstLiveTransport(session, api_key),
    )


DEFAULT_PROVIDER_FACTORY = ControllerProviderFactory()
DEFAULT_PROVIDER_FACTORY.register(RACHIO_PROVIDER, _build_rachio)
