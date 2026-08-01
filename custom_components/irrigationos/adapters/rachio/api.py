"""Minimal asynchronous Rachio API client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from aiohttp import ClientError, ClientSession, ClientTimeout

BASE_URL: Final = "https://api.rach.io/1/public"
DEFAULT_TIMEOUT_SECONDS: Final = 20


class RachioApiError(Exception):
    """Base exception for Rachio API failures."""


class RachioAuthenticationError(RachioApiError):
    """Raised when the Rachio API key is rejected."""


class RachioApiClient:
    """Small client used by Config Flow and the future Rachio adapter."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key.strip()

    async def async_get_person_info(self) -> dict[str, Any]:
        """Validate the API key and return the Rachio person identity."""
        return await self._async_request("GET", "/person/info")

    async def async_get_person(self, person_id: str) -> dict[str, Any]:
        """Return controllers and account data for a person."""
        return await self._async_request("GET", f"/person/{person_id}")

    async def _async_request(self, method: str, path: str) -> dict[str, Any]:
        headers: Mapping[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        try:
            async with self._session.request(
                method,
                f"{BASE_URL}{path}",
                headers=headers,
                timeout=ClientTimeout(total=DEFAULT_TIMEOUT_SECONDS),
            ) as response:
                if response.status in {401, 403}:
                    raise RachioAuthenticationError("Rachio rejected the API key")
                if response.status >= 400:
                    body = (await response.text())[:250]
                    raise RachioApiError(f"Rachio API returned HTTP {response.status}: {body}")
                payload = await response.json()
        except RachioApiError:
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            raise RachioApiError("Unable to communicate with the Rachio API") from err

        if not isinstance(payload, dict):
            raise RachioApiError("Rachio returned an unexpected response")
        return payload
