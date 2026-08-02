"""Asynchronous read-only Rachio API client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from ...controllers import (
    ControllerAuthenticationError,
    ControllerInvalidResponseError,
    ControllerProviderError,
    ControllerRateLimitError,
)

BASE_URL: Final = "https://api.rach.io/1/public"
DEFAULT_TIMEOUT_SECONDS: Final = 20


class RachioApiError(ControllerProviderError):
    """Base exception for Rachio API failures."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_category: str = "transport_failure",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic_category = diagnostic_category
        self.http_status = http_status


class RachioAuthenticationError(ControllerAuthenticationError, RachioApiError):
    """Raised when the Rachio API key is rejected."""

    def __init__(self) -> None:
        super().__init__(
            "Rachio rejected the API key",
            diagnostic_category="http_status_failure",
            http_status=401,
        )


class RachioRateLimitError(ControllerRateLimitError, RachioApiError):
    """Raised when the Rachio API rate limit is reached."""

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        super().__init__("Rachio API rate limit reached", retry_after_seconds)
        self.diagnostic_category = "http_status_failure"
        self.http_status = 429


class RachioInvalidResponseError(ControllerInvalidResponseError, RachioApiError):
    """Raised when Rachio returns an unexpected payload."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_category: str = "unexpected_response_shape",
    ) -> None:
        super().__init__(message, diagnostic_category=diagnostic_category)


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

    async def async_get_current_schedule(self, device_id: str) -> dict[str, Any]:
        """Return the schedule currently running on a controller, if any."""
        return await self._async_request("GET", f"/device/{device_id}/current_schedule")

    async def async_get_account(self) -> tuple[str, dict[str, Any]]:
        """Resolve the person id and return the complete account payload."""
        identity = await self.async_get_person_info()
        person_id = identity.get("id")
        if not isinstance(person_id, str) or not person_id.strip():
            raise RachioInvalidResponseError("Rachio identity response did not include a person id")
        return person_id.strip(), await self.async_get_person(person_id.strip())

    async def async_get_webhook_event_types(self) -> list[dict[str, Any]]:
        """Return the webhook event categories supported by Rachio."""
        payload = await self._async_request_json("GET", "/notification/webhook_event_type")
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise RachioInvalidResponseError("Rachio returned invalid webhook event types")
        return payload

    async def async_get_device_webhooks(
        self, device_id: str
    ) -> list[dict[str, Any]]:
        """Return remote webhooks registered for one controller."""
        payload = await self._async_request_json(
            "GET", f"/notification/{device_id}/webhook"
        )
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise RachioInvalidResponseError("Rachio returned invalid webhooks")
        return payload

    async def async_create_webhook(self, payload: dict[str, Any]) -> None:
        """Create one read-only notification subscription."""
        await self._async_request_json("POST", "/notification/webhook", payload)

    async def async_update_webhook(self, payload: dict[str, Any]) -> None:
        """Update one read-only notification subscription."""
        await self._async_request_json("PUT", "/notification/webhook", payload)

    async def async_delete_webhook(self, webhook_id: str) -> None:
        """Delete one notification subscription."""
        await self._async_request_json(
            "DELETE", f"/notification/webhook/{webhook_id}", allow_empty=True
        )

    async def _async_request(self, method: str, path: str) -> dict[str, Any]:
        payload = await self._async_request_json(method, path)
        if not isinstance(payload, dict):
            raise RachioInvalidResponseError("Rachio returned an unexpected response")
        return payload

    async def _async_request_json(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        *,
        allow_empty: bool = False,
    ) -> object | None:
        headers: Mapping[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                method,
                f"{BASE_URL}{path}",
                headers=headers,
                json=json_body,
                timeout=ClientTimeout(total=DEFAULT_TIMEOUT_SECONDS),
            ) as response:
                if response.status in {401, 403}:
                    error = RachioAuthenticationError()
                    error.http_status = response.status
                    raise error
                if response.status == 429:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    raise RachioRateLimitError(retry_after)
                if not 200 <= response.status < 300:
                    raise RachioApiError(
                        f"Rachio API returned HTTP {response.status}",
                        diagnostic_category="http_status_failure",
                        http_status=response.status,
                    )
                if allow_empty and response.status == 204:
                    return None
                content_type = response.headers.get("Content-Type", "").partition(";")[0]
                if content_type.lower().strip() != "application/json":
                    if allow_empty:
                        return None
                    raise RachioInvalidResponseError(
                        "Rachio returned a non-JSON content type",
                        diagnostic_category="invalid_content_type",
                    )
                try:
                    payload = await response.json()
                except (ClientResponseError, ValueError):
                    if allow_empty:
                        return None
                    raise RachioInvalidResponseError(
                        "Rachio returned invalid JSON",
                        diagnostic_category="invalid_json",
                    ) from None
        except RachioApiError:
            raise
        except TimeoutError as err:
            raise RachioApiError(
                "Rachio API request timed out", diagnostic_category="timeout"
            ) from err
        except ClientError as err:
            raise RachioApiError(
                "Unable to communicate with the Rachio API",
                diagnostic_category="transport_failure",
            ) from err

        return payload


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None
