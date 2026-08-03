"""Behavioral tests for the read-only Rachio API client."""

from __future__ import annotations

from typing import Any

import pytest
from aiohttp import ClientConnectionError

from tests.helpers import load_integration_module

MODULE = load_integration_module("adapters.rachio.api")
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
        *,
        json_error: ValueError | None = None,
    ) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {"Content-Type": "application/json"}
        self.json_error = json_error

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self) -> object:
        if self.json_error is not None:
            raise self.json_error
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


@pytest.mark.asyncio
async def test_notification_subscription_endpoints_and_payloads() -> None:
    session = FakeSession(
        [
            FakeResponse(200, [{"id": "zone", "name": "ZONE_STATUS_EVENT"}]),
            FakeResponse(200, []),
            FakeResponse(200, {"id": "hook-1"}),
            FakeResponse(200, {"id": "hook-1"}),
            FakeResponse(204, None),
        ]
    )
    client = RachioApiClient(session, "token")
    payload = {
        "device": {"id": "device-1"},
        "externalId": "entry-auth",
        "url": "https://ha.example.com/api/webhook/stable",
        "eventTypes": [{"id": "zone"}],
    }

    assert await client.async_get_webhook_event_types() == [
        {"id": "zone", "name": "ZONE_STATUS_EVENT"}
    ]
    assert await client.async_get_device_webhooks("device-1") == []
    await client.async_create_webhook(payload)
    await client.async_update_webhook({**payload, "id": "hook-1"})
    await client.async_delete_webhook("hook-1")

    assert [item["method"] for item in session.requests] == [
        "GET",
        "GET",
        "POST",
        "PUT",
        "DELETE",
    ]
    assert session.requests[2]["json"] == payload
    assert session.requests[4]["url"].endswith("/notification/webhook/hook-1")


@pytest.mark.asyncio
async def test_event_type_discovery_sends_rachiopy_headers() -> None:
    session = FakeSession(
        [FakeResponse(200, [{"id": "zone", "name": "ZONE_STATUS_EVENT"}])]
    )
    client = RachioApiClient(session, "top-secret-token")

    event_types = await client.async_get_webhook_event_types()

    assert event_types == [{"id": "zone", "name": "ZONE_STATUS_EVENT"}]
    assert session.requests[0]["headers"] == {
        "Authorization": "Bearer top-secret-token",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_event_type_discovery_reports_safe_http_status() -> None:
    session = FakeSession([FakeResponse(503, {"private": "body"})])
    client = RachioApiClient(session, "top-secret-token")

    with pytest.raises(MODULE.RachioApiError) as caught:
        await client.async_get_webhook_event_types()

    assert caught.value.diagnostic_category == "http_status_failure"
    assert caught.value.http_status == 503
    assert "private" not in str(caught.value)
    assert "top-secret-token" not in str(caught.value)


@pytest.mark.asyncio
async def test_event_type_discovery_reports_invalid_content_type() -> None:
    session = FakeSession(
        [FakeResponse(200, "not inspected", {"Content-Type": "text/html"})]
    )
    client = RachioApiClient(session, "token")

    with pytest.raises(RachioInvalidResponseError) as caught:
        await client.async_get_webhook_event_types()

    assert caught.value.diagnostic_category == "invalid_content_type"


@pytest.mark.asyncio
async def test_event_type_discovery_reports_invalid_json() -> None:
    session = FakeSession(
        [FakeResponse(200, None, json_error=ValueError("private response body"))]
    )
    client = RachioApiClient(session, "token")

    with pytest.raises(RachioInvalidResponseError) as caught:
        await client.async_get_webhook_event_types()

    assert caught.value.diagnostic_category == "invalid_json"
    assert "private response body" not in str(caught.value)


@pytest.mark.asyncio
async def test_event_type_discovery_reports_unexpected_shape() -> None:
    session = FakeSession([FakeResponse(200, {"eventTypes": []})])
    client = RachioApiClient(session, "token")

    with pytest.raises(RachioInvalidResponseError) as caught:
        await client.async_get_webhook_event_types()

    assert caught.value.diagnostic_category == "unexpected_response_shape"


class FailingSession:
    """Raise a transport-layer failure before a response exists."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def request(self, *_args: object, **_kwargs: object) -> None:
        raise self.error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_category"),
    [
        (TimeoutError(), "timeout"),
        (ClientConnectionError(), "transport_failure"),
    ],
)
async def test_event_type_discovery_reports_transport_category(
    error: Exception, expected_category: str
) -> None:
    client = RachioApiClient(FailingSession(error), "token")

    with pytest.raises(MODULE.RachioApiError) as caught:
        await client.async_get_webhook_event_types()

    assert caught.value.diagnostic_category == expected_category
