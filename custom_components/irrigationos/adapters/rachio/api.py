"""Asynchronous read-only Rachio API client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

BASE_URL: Final = "https://api.rach.io/1/public"
DEFAULT_TIMEOUT_SECONDS: Final = 20


class RachioApiError(Exception):
    """Base exception for Rachio API failures."""


class RachioAuthenticationError(RachioApiError):
    """Raised when the Rachio API key is rejected."""


class RachioRateLimitError(RachioApiError):
    """Raised when the Rachio API rate limit is reached."""

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        super().__init__("Rachio API rate limit reached")
        self.retry_after_seconds = retry_after_seconds


class RachioInvalidResponseError(RachioApiError):
    """Raised when Rachio returns an unexpected payload."""


class RachioApiClient:
    """Small API client used by config flow and observation refreshes."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key.strip()

    async def async_get_person_info(self) -> dict[str, Any]:
        """Validate the token and return the current Rachio identity."""
        return await self._async_request("GET", "/person/info")

    async def async_get_person(self, person_id: str) -> dict[str, Any]:
        """Return controllers and zones for the current person."""
        return await self._async_request("GET", f"/person/{person_id}")

    async def async_get_account(self) -> tuple[str, dict[str, Any]]:
        """Resolve the person id and return the complete account payload."""
        identity = await self.async_get_person_info()
        person_id = identity.get("id")
        if not isinstance(person_id, str) or not person_id.strip():
            raise RachioInvalidResponseError("Rachio identity response did not include a person id")
        return person_id.strip(), await self.async_get_person(person_id.strip())

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
                if response.status == 429:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    raise RachioRateLimitError(retry_after)
                if response.status >= 400:
                    raise RachioApiError(f"Rachio API returned HTTP {response.status}")
                try:
                    payload = await response.json()
                except (ClientResponseError, ValueError) as err:
                    raise RachioInvalidResponseError(
                        "Rachio returned invalid JSON"
                    ) from err
        except RachioApiError:
            raise
        except (ClientError, TimeoutError) as err:
            raise RachioApiError("Unable to communicate with the Rachio API") from err

        if not isinstance(payload, dict):
            raise RachioInvalidResponseError("Rachio returned an unexpected response")
        return payload


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None
