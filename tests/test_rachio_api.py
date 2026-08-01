"""Behavioral tests for the read-only Rachio API client."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "irrigationos"
    / "adapters"
    / "rachio"
    / "api.py"
)
SPEC = importlib.util.spec_from_file_location("irrigationos_rachio_api", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RachioApiClient = MODULE.RachioApiClient
RachioAuthenticationError = MODULE.RachioAuthenticationError
RachioRateLimitError = MODULE.RachioRateLimitError
RachioInvalidResponseError = MODULE.RachioInvalidResponseError


class FakeResponse:
    """Minimal async response context manager."""

    def __init__(
        self,
        status: int,
        payload: object,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {}

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self) -> object:
        return self.payload


class FakeSession:
    """Return queued fake responses and capture requests."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_get_account_resolves_identity_then_person() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"id": "person-1"}),
            FakeResponse(200, {"id": "person-1", "devices": []}),
        ]
    )
    client = RachioApiClient(session, "token")
    person_id, account = await client.async_get_account()
    assert person_id == "person-1"
    assert account["devices"] == []
    assert session.requests[0]["url"].endswith("/person/info")
    assert session.requests[1]["url"].endswith("/person/person-1")
    assert session.requests[0]["headers"]["Authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_authentication_error_does_not_expose_token() -> None:
    session = FakeSession([FakeResponse(401, {})])
    client = RachioApiClient(session, "top-secret-token")
    with pytest.raises(RachioAuthenticationError) as caught:
        await client.async_get_person_info()
    assert "top-secret-token" not in str(caught.value)


@pytest.mark.asyncio
async def test_rate_limit_preserves_retry_after() -> None:
    session = FakeSession([FakeResponse(429, {}, {"Retry-After": "120"})])
    client = RachioApiClient(session, "token")
    with pytest.raises(RachioRateLimitError) as caught:
        await client.async_get_person_info()
    assert caught.value.retry_after_seconds == 120


@pytest.mark.asyncio
async def test_non_object_payload_is_rejected() -> None:
    session = FakeSession([FakeResponse(200, ["unexpected"])])
    client = RachioApiClient(session, "token")
    with pytest.raises(RachioInvalidResponseError):
        await client.async_get_person_info()


@pytest.mark.asyncio
async def test_current_schedule_uses_read_only_device_endpoint() -> None:
    session = FakeSession([FakeResponse(200, {"zoneId": "zone-1"})])
    client = RachioApiClient(session, "token")
    payload = await client.async_get_current_schedule("device-1")
    assert payload["zoneId"] == "zone-1"
    assert session.requests[0]["method"] == "GET"
    assert session.requests[0]["url"].endswith("/device/device-1/current_schedule")
