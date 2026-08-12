"""Narrow Rachio transport primitive for a future supervised first-live trial."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from aiohttp import ClientError, ClientSession, ClientTimeout

RACHIO_PUBLIC_BASE_URL: Final = "https://api.rach.io/1/public"
FIRST_LIVE_NETWORK_TIMEOUT_SECONDS: Final = 20
MAX_TRANSPORT_RUNTIME_SECONDS: Final = 120


class FirstLiveTransportError(RuntimeError):
    """Raised when the narrow physical delivery transport fails."""


class RachioFirstLiveTransport:
    """Expose only bounded zone start and device-wide emergency stop operations."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        token = api_key.strip()
        if not token:
            raise ValueError("Rachio API key must not be blank")
        self._session = session
        self._api_key = token

    async def async_start_zone(
        self,
        *,
        zone_id: str,
        runtime_seconds: int,
    ) -> None:
        """Start exactly one native Rachio zone for a bounded duration."""

        target = zone_id.strip()
        if not target:
            raise ValueError("zone_id must not be blank")
        if not 1 <= runtime_seconds <= MAX_TRANSPORT_RUNTIME_SECONDS:
            raise ValueError("runtime_seconds must be between 1 and 120")
        await self._async_put(
            "/zone/start",
            {"id": target, "duration": runtime_seconds},
        )

    async def async_emergency_stop(self, *, device_id: str) -> None:
        """Stop all watering on the selected Rachio controller."""

        target = device_id.strip()
        if not target:
            raise ValueError("device_id must not be blank")
        await self._async_put("/device/stop_water", {"id": target})

    async def _async_put(self, path: str, payload: dict[str, object]) -> None:
        headers: Mapping[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                "PUT",
                f"{RACHIO_PUBLIC_BASE_URL}{path}",
                headers=headers,
                json=payload,
                timeout=ClientTimeout(total=FIRST_LIVE_NETWORK_TIMEOUT_SECONDS),
            ) as response:
                if not 200 <= response.status < 300:
                    raise FirstLiveTransportError(
                        f"Rachio first-live transport returned HTTP {response.status}"
                    )
        except FirstLiveTransportError:
            raise
        except TimeoutError as err:
            raise FirstLiveTransportError("Rachio first-live transport timed out") from err
        except ClientError as err:
            raise FirstLiveTransportError(
                "Unable to communicate with Rachio first-live transport"
            ) from err
