"""Rachio-specific remote webhook subscription reconciliation."""

from __future__ import annotations

from typing import Any, Final

from ...controllers import RealtimeRegistrationHealth
from .api import RachioApiClient, RachioApiError

OBSERVATION_EVENT_TYPES: Final = frozenset(
    {
        "DEVICE_STATUS_EVENT",
        "ZONE_STATUS_EVENT",
        "RAIN_DELAY_EVENT",
        "RAIN_SENSOR_DETECTION_EVENT",
        "SCHEDULE_STATUS_EVENT",
    }
)
_EVENT_NAME_FIELDS: Final = ("name", "eventType", "type")


class _EventCatalogError(RachioApiError):
    """Safe event-catalog failure with sanitized discovery metadata."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_category: str,
        count: int,
        field_names: tuple[str, ...],
        names: tuple[str, ...],
    ) -> None:
        super().__init__(message, diagnostic_category=diagnostic_category)
        self.discovered_event_type_count = count
        self.discovered_event_type_field_names = field_names
        self.discovered_event_type_names = names


class RachioWebhookRegistrar:
    """Own only IrrigationOS notification subscriptions on Rachio devices."""

    def __init__(self, client: RachioApiClient) -> None:
        self._client = client

    async def async_reconcile(
        self,
        callback_url: str,
        external_id: str,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        """Ensure exactly one current subscription exists per controller."""
        expected = len(controller_native_ids)
        if expected == 0:
            return RealtimeRegistrationHealth(True, 0, 0)
        try:
            event_types = await self._selected_event_types()
        except RachioApiError as err:
            return _failed_health(
                expected,
                "event type discovery failed",
                err.diagnostic_category,
                err.http_status,
                discovered_event_type_count=getattr(
                    err, "discovered_event_type_count", None
                ),
                discovered_event_type_field_names=getattr(
                    err, "discovered_event_type_field_names", ()
                ),
                discovered_event_type_names=getattr(
                    err, "discovered_event_type_names", ()
                ),
            )

        registered = 0
        failure: RachioApiError | None = None
        for controller_native_id in controller_native_ids:
            try:
                webhooks = await self._client.async_get_device_webhooks(
                    controller_native_id
                )
                owned = [
                    item
                    for item in webhooks
                    if str(item.get("externalId", "")).startswith(external_id_prefix)
                ]
                current = next(
                    (
                        item
                        for item in owned
                        if item.get("externalId") == external_id
                    ),
                    owned[0] if owned else None,
                )
                for duplicate in owned:
                    if duplicate is current:
                        continue
                    await self._delete(duplicate)

                payload = {
                    "device": {"id": controller_native_id},
                    "externalId": external_id,
                    "url": callback_url,
                    "eventTypes": event_types,
                }
                if current is None:
                    await self._client.async_create_webhook(payload)
                else:
                    webhook_id = _webhook_id(current)
                    if not _registration_matches(
                        current, callback_url, external_id, event_types
                    ):
                        await self._client.async_update_webhook(
                            {**payload, "id": webhook_id}
                        )
                registered += 1
            except RachioApiError as err:
                failure = failure or err

        return RealtimeRegistrationHealth(
            healthy=failure is None and registered == expected,
            registered_controllers=registered,
            expected_controllers=expected,
            error=(
                "remote subscription reconciliation failed"
                if failure is not None
                else None
            ),
            error_category=(
                failure.diagnostic_category if failure is not None else None
            ),
            http_status=failure.http_status if failure is not None else None,
        )

    async def async_cleanup(
        self,
        external_id_prefix: str,
        controller_native_ids: tuple[str, ...],
    ) -> RealtimeRegistrationHealth:
        """Remove subscriptions owned by this config entry."""
        expected = len(controller_native_ids)
        cleaned = 0
        failure: RachioApiError | None = None
        for controller_native_id in controller_native_ids:
            try:
                webhooks = await self._client.async_get_device_webhooks(
                    controller_native_id
                )
                for item in webhooks:
                    if str(item.get("externalId", "")).startswith(
                        external_id_prefix
                    ):
                        await self._delete(item)
                cleaned += 1
            except RachioApiError as err:
                failure = failure or err
        return RealtimeRegistrationHealth(
            healthy=failure is None and cleaned == expected,
            registered_controllers=0,
            expected_controllers=expected,
            error="remote subscription cleanup failed" if failure is not None else None,
            error_category=(
                failure.diagnostic_category if failure is not None else None
            ),
            http_status=failure.http_status if failure is not None else None,
        )

    async def _selected_event_types(self) -> list[dict[str, str]]:
        available = await self._client.async_get_webhook_event_types()
        field_names, names = _catalog_summary(available)
        if not available:
            raise _EventCatalogError(
                "Rachio returned no webhook event types",
                diagnostic_category="zero_event_types_returned",
                count=0,
                field_names=field_names,
                names=names,
            )

        selected: list[dict[str, str]] = []
        for item in available:
            event_id = _optional_identifier(item.get("id"))
            event_name = _event_type_name(item)
            if event_id is not None and event_name in OBSERVATION_EVENT_TYPES:
                selected.append({"id": event_id})

        if not selected:
            raise _EventCatalogError(
                "Rachio exposed no desired observation webhook event types",
                diagnostic_category="zero_desired_event_names_matched",
                count=len(available),
                field_names=field_names,
                names=names,
            )
        return selected

    async def _delete(self, webhook: dict[str, Any]) -> None:
        await self._client.async_delete_webhook(_webhook_id(webhook))


def _catalog_summary(
    available: list[dict[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return credential-free event catalog metadata for diagnostics."""
    field_names = tuple(
        sorted({str(key) for item in available for key in item if str(key) != "id"})
    )
    names = tuple(
        sorted(
            {
                value
                for item in available
                for field in _EVENT_NAME_FIELDS
                if (value := _optional_string(item.get(field))) is not None
            }
        )
    )
    return field_names, names


def _event_type_name(item: dict[str, Any]) -> str | None:
    """Return a normalized legacy Rachio event type name."""
    for field in _EVENT_NAME_FIELDS:
        value = _optional_string(item.get(field))
        if value is None:
            continue
        normalized = value.upper().replace("-", "_").replace(" ", "_")
        if not normalized.endswith("_EVENT"):
            normalized = f"{normalized}_EVENT"
        return normalized
    return None


def _registration_matches(
    webhook: dict[str, Any],
    callback_url: str,
    external_id: str,
    event_types: list[dict[str, str]],
) -> bool:
    existing_ids = {
        item_id
        for item in webhook.get("eventTypes", [])
        if isinstance(item, dict)
        and (item_id := _optional_identifier(item.get("id"))) is not None
    }
    expected_ids = {item["id"] for item in event_types}
    return (
        webhook.get("url") == callback_url
        and webhook.get("externalId") == external_id
        and existing_ids == expected_ids
    )


def _webhook_id(webhook: dict[str, Any]) -> str:
    webhook_id = _optional_identifier(webhook.get("id"))
    if webhook_id is None:
        raise RachioApiError("Rachio webhook did not include an id")
    return webhook_id


def _optional_identifier(value: object) -> str | None:
    """Normalize string or integer Rachio identifiers for API payloads."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    return _optional_string(value)


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _failed_health(
    expected: int,
    error: str,
    error_category: str,
    http_status: int | None = None,
    *,
    discovered_event_type_count: int | None = None,
    discovered_event_type_field_names: tuple[str, ...] = (),
    discovered_event_type_names: tuple[str, ...] = (),
) -> RealtimeRegistrationHealth:
    return RealtimeRegistrationHealth(
        healthy=False,
        registered_controllers=0,
        expected_controllers=expected,
        error=error,
        error_category=error_category,
        http_status=http_status,
        discovered_event_type_count=discovered_event_type_count,
        discovered_event_type_field_names=discovered_event_type_field_names,
        discovered_event_type_names=discovered_event_type_names,
    )
