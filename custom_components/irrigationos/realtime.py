"""Provider-neutral Home Assistant webhook lifecycle for realtime observations."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlsplit

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import EVENT_HOMEASSISTANT_STOP, Event, HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_API_KEY,
    CONF_CLOUDHOOK_URL,
    CONF_WEBHOOK_AUTH,
    CONF_WEBHOOK_ID,
    DOMAIN,
    UPDATE_INTERVAL_MINUTES,
)
from .controllers import RealtimeObservationAdapter, RealtimeRegistrationHealth

if TYPE_CHECKING:
    from .coordinator import IrrigationOSCoordinator

_LOGGER = logging.getLogger(__name__)

MAX_DEDUPLICATION_IDS: Final = 256
MAX_WEBHOOK_BYTES: Final = 256 * 1024
REMOTE_ISSUE_ID: Final = "realtime_observation_unavailable"
SUPPORTED_EVENT_MARKERS: Final = (
    "DEVICE",
    "ZONE",
    "SCHEDULE",
    "RAIN_DELAY",
    "RAIN_SENSOR",
)

type WebhookUrlResolver = Callable[
    [HomeAssistant, ConfigEntry, str], Awaitable[tuple[str | None, str]]
]


class RealtimeObservationManager:
    """Own local delivery, remote subscriptions, and safe event accounting."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: IrrigationOSCoordinator,
        *,
        url_resolver: WebhookUrlResolver | None = None,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._url_resolver = url_resolver or async_resolve_webhook_url
        self._webhook_id = ""
        self._webhook_auth = ""
        self._external_id_prefix = f"homeassistant.irrigationos:{entry.entry_id}:"
        self._external_id = ""
        self._callback_url: str | None = None
        self._controller_native_ids: tuple[str, ...] = ()
        self._registered_locally = False
        self._stop_unsubscribe: Callable[[], None] | None = None
        self._shutdown = False

        self.enabled = False
        self.url_source = "none"
        self.remote_health = RealtimeRegistrationHealth(False, 0, 0, "not configured")
        self.last_received_event: dict[str, str] | None = None
        self.accepted_event_count = 0
        self.rejected_event_count = 0
        self.duplicate_event_count = 0
        self._seen_event_ids: set[str] = set()
        self._event_order: deque[str] = deque()

    async def async_setup(self) -> None:
        """Register local delivery and reconcile remote observation subscriptions."""
        self._ensure_credentials()
        webhook.async_register(
            self._hass,
            DOMAIN,
            "IrrigationOS realtime observation",
            self._webhook_id,
            self._async_handle_webhook,
            local_only=False,
            allowed_methods={"POST"},
        )
        self._registered_locally = True
        self._controller_native_ids = self._controller_ids()
        self._stop_unsubscribe = self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
        )

        callback_url, source = await self._url_resolver(
            self._hass, self._entry, self._webhook_id
        )
        self.url_source = source
        if callback_url is None:
            adapter = self._coordinator.adapter
            if isinstance(adapter, RealtimeObservationAdapter):
                await adapter.async_cleanup_realtime(
                    self._external_id_prefix, self._controller_native_ids
                )
            self.remote_health = RealtimeRegistrationHealth(
                healthy=False,
                registered_controllers=0,
                expected_controllers=len(self._controller_ids()),
                error="no externally usable Home Assistant URL",
            )
            self._create_issue(self.remote_health.error)
            return
        self._callback_url = callback_url

        adapter = self._coordinator.adapter
        if not isinstance(adapter, RealtimeObservationAdapter):
            self.remote_health = RealtimeRegistrationHealth(
                healthy=False,
                registered_controllers=0,
                expected_controllers=len(self._controller_ids()),
                error="provider does not support realtime observation",
            )
            self._create_issue(self.remote_health.error)
            return

        self.remote_health = await adapter.async_reconcile_realtime(
            callback_url,
            self._external_id,
            self._external_id_prefix,
            self._controller_native_ids,
        )
        self.enabled = self.remote_health.healthy
        if self.enabled:
            ir.async_delete_issue(self._hass, DOMAIN, REMOTE_ISSUE_ID)
        else:
            self._create_issue(self.remote_health.error)

    async def async_reconcile_controllers(
        self, controller_native_ids: tuple[str, ...]
    ) -> None:
        """Reconcile subscriptions when polling discovers controller changes."""
        if (
            self._callback_url is None
            or controller_native_ids == self._controller_native_ids
        ):
            return
        adapter = self._coordinator.adapter
        if not isinstance(adapter, RealtimeObservationAdapter):
            return
        removed = tuple(
            item
            for item in self._controller_native_ids
            if item not in controller_native_ids
        )
        cleanup_healthy = True
        if removed:
            cleanup = await adapter.async_cleanup_realtime(
                self._external_id_prefix, removed
            )
            cleanup_healthy = cleanup.healthy
        self._controller_native_ids = controller_native_ids
        self.remote_health = await adapter.async_reconcile_realtime(
            self._callback_url,
            self._external_id,
            self._external_id_prefix,
            controller_native_ids,
        )
        if not cleanup_healthy:
            self.remote_health = RealtimeRegistrationHealth(
                False,
                self.remote_health.registered_controllers,
                self.remote_health.expected_controllers,
                "stale remote subscription cleanup failed",
                "remote_cleanup_failure",
            )
        self.enabled = self.remote_health.healthy
        if self.enabled:
            ir.async_delete_issue(self._hass, DOMAIN, REMOTE_ISSUE_ID)
        else:
            self._create_issue(self.remote_health.error)

    async def async_shutdown(self) -> None:
        """Unregister local delivery and clean up owned remote subscriptions."""
        if self._shutdown:
            return
        self._shutdown = True
        if self._stop_unsubscribe is not None:
            self._stop_unsubscribe()
            self._stop_unsubscribe = None
        adapter = self._coordinator.adapter
        if isinstance(adapter, RealtimeObservationAdapter) and self._external_id_prefix:
            self.remote_health = await adapter.async_cleanup_realtime(
                self._external_id_prefix, self._controller_native_ids
            )
        if self._registered_locally:
            webhook.async_unregister(self._hass, self._webhook_id)
            self._registered_locally = False
        self.enabled = False
        ir.async_delete_issue(self._hass, DOMAIN, REMOTE_ISSUE_ID)

    def diagnostics(self) -> dict[str, Any]:
        """Return URL- and credential-free realtime health diagnostics."""
        return {
            "enabled": self.enabled,
            "url_source": self.url_source,
            "remote_registration": asdict(self.remote_health),
            "last_received_event": self.last_received_event,
            "accepted_event_count": self.accepted_event_count,
            "rejected_event_count": self.rejected_event_count,
            "duplicate_event_count": self.duplicate_event_count,
            "fallback_polling": {
                "enabled": True,
                "interval_minutes": UPDATE_INTERVAL_MINUTES,
                "last_update_success": self._coordinator.last_update_success,
            },
        }

    async def _async_handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        del hass, webhook_id
        if request.content_length is not None and request.content_length > MAX_WEBHOOK_BYTES:
            self.rejected_event_count += 1
            return web.Response(status=413)
        raw = await request.read()
        if not self._valid_signature(raw, request.headers.get("x-signature")):
            self.rejected_event_count += 1
            return web.Response(status=403)
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.rejected_event_count += 1
            return web.Response(status=400)
        if not isinstance(payload, dict) or payload.get("externalId") != self._external_id:
            self.rejected_event_count += 1
            return web.Response(status=403)

        event_type = _event_type(payload)
        event_subtype = _event_subtype(payload)
        if not _is_observation_event(event_type, event_subtype):
            self.rejected_event_count += 1
            return web.Response(status=422)
        event_id = _event_id(payload, raw)
        if event_id in self._seen_event_ids:
            self.duplicate_event_count += 1
            return web.Response(status=204)
        self._remember_event(event_id)
        self.accepted_event_count += 1
        self.last_received_event = {
            "received_at": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "event_subtype": event_subtype,
        }
        await self._coordinator.async_refresh()
        return web.Response(status=204)

    def _ensure_credentials(self) -> None:
        webhook_id = self._entry.data.get(CONF_WEBHOOK_ID)
        webhook_auth = self._entry.data.get(CONF_WEBHOOK_AUTH)
        data = dict(self._entry.data)
        if not isinstance(webhook_id, str) or not webhook_id:
            webhook_id = webhook.async_generate_id()
            data[CONF_WEBHOOK_ID] = webhook_id
        if not isinstance(webhook_auth, str) or not webhook_auth:
            webhook_auth = secrets.token_hex(32)
            data[CONF_WEBHOOK_AUTH] = webhook_auth
        if data != self._entry.data:
            self._hass.config_entries.async_update_entry(self._entry, data=data)
        self._webhook_id = webhook_id
        self._webhook_auth = webhook_auth
        self._external_id = f"{self._external_id_prefix}{webhook_auth}"

    def _controller_ids(self) -> tuple[str, ...]:
        snapshot = self._coordinator.data
        if snapshot is None:
            return ()
        return tuple(controller.native_id for controller in snapshot.controllers)

    def _valid_signature(self, raw: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        expected = hmac.new(
            str(self._entry.data[CONF_API_KEY]).encode(), raw, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip().lower())

    def _remember_event(self, event_id: str) -> None:
        if len(self._event_order) >= MAX_DEDUPLICATION_IDS:
            oldest = self._event_order.popleft()
            self._seen_event_ids.discard(oldest)
        self._event_order.append(event_id)
        self._seen_event_ids.add(event_id)

    def _create_issue(self, reason: str | None) -> None:
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            REMOTE_ISSUE_ID,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="realtime_observation_unavailable",
            translation_placeholders={"reason": reason or "unknown error"},
        )

    async def _async_handle_stop(self, event: Event) -> None:
        del event
        await self.async_shutdown()


async def async_resolve_webhook_url(
    hass: HomeAssistant, entry: ConfigEntry, webhook_id: str
) -> tuple[str | None, str]:
    """Prefer an active cloudhook, then a standard external HA webhook URL."""
    cloudhook_url = await _async_cloudhook_url(hass, entry, webhook_id)
    if cloudhook_url is not None and _is_remotely_usable_url(cloudhook_url):
        return cloudhook_url, "cloudhook"
    try:
        standard_url = webhook.async_generate_url(
            hass,
            webhook_id,
            allow_internal=False,
            allow_external=True,
            allow_ip=False,
            prefer_external=True,
        )
    except Exception:  # Home Assistant URL helper errors vary across releases.
        return None, "none"
    if _is_remotely_usable_url(standard_url):
        return standard_url, "standard"
    return None, "none"


async def _async_cloudhook_url(
    hass: HomeAssistant, entry: ConfigEntry, webhook_id: str
) -> str | None:
    """Return a cloudhook only when Home Assistant Cloud is actively subscribed."""
    try:
        from homeassistant.components import cloud

        if not cloud.async_active_subscription(hass):
            return None
        existing = entry.data.get(CONF_CLOUDHOOK_URL)
        if isinstance(existing, str) and existing:
            return existing
        cloudhook_url = await cloud.async_create_cloudhook(hass, webhook_id)
    except Exception:  # Cloud is optional; standard URL and polling remain available.
        _LOGGER.debug("Home Assistant Cloud hook unavailable")
        return None
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CLOUDHOOK_URL: cloudhook_url}
    )
    return cloudhook_url


async def async_delete_cloudhook(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the optional cloudhook when the config entry is permanently removed."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        return
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not isinstance(webhook_id, str) or not webhook_id:
        return
    try:
        from homeassistant.components import cloud

        await cloud.async_delete_cloudhook(hass, webhook_id)
    except Exception:
        _LOGGER.debug("Unable to delete optional Home Assistant Cloud hook")


def _is_remotely_usable_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme != "https" or not host:
            return False
        if host == "localhost" or host.endswith(".local"):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return "." in host
        return not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        )
    except ValueError:
        return False


def _event_type(payload: dict[str, Any]) -> str:
    value = payload.get("type", payload.get("eventType", ""))
    return str(value).strip().upper()


def _event_subtype(payload: dict[str, Any]) -> str:
    value = payload.get("subType", payload.get("eventSubType", ""))
    return str(value).strip().upper()


def _is_observation_event(event_type: str, event_subtype: str) -> bool:
    combined = f"{event_type} {event_subtype}"
    return bool(event_type) and any(marker in combined for marker in SUPPORTED_EVENT_MARKERS)


def _event_id(payload: dict[str, Any], raw: bytes) -> str:
    value = payload.get("eventId", payload.get("id"))
    if isinstance(value, str) and value:
        return value
    return hashlib.sha256(raw).hexdigest()
