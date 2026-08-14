"""Regression tests for realtime observation lifecycle cleanup."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.irrigationos import realtime as realtime_module
from custom_components.irrigationos.const import (
    CONF_API_KEY,
    CONF_WEBHOOK_AUTH,
    CONF_WEBHOOK_ID,
)
from custom_components.irrigationos.controllers import RealtimeRegistrationHealth
from custom_components.irrigationos.realtime import RealtimeObservationManager


class _Bus:
    def __init__(self) -> None:
        self.listen_count = 0
        self.unsubscribe_count = 0

    def async_listen_once(self, _event_type: str, _listener: Any) -> Any:
        self.listen_count += 1

        def _unsubscribe() -> None:
            self.unsubscribe_count += 1

        return _unsubscribe


class _Adapter:
    def __init__(self, *, fail_cleanup: bool = False) -> None:
        self.cleanup_count = 0
        self.fail_cleanup = fail_cleanup

    async def async_reconcile_realtime(self, *_args: Any) -> RealtimeRegistrationHealth:
        return RealtimeRegistrationHealth(True, 0, 0, None)

    async def async_cleanup_realtime(self, *_args: Any) -> RealtimeRegistrationHealth:
        self.cleanup_count += 1
        if self.fail_cleanup:
            raise RuntimeError("remote cleanup failed")
        return RealtimeRegistrationHealth(True, 0, 0, None)


async def _no_external_url(*_args: Any) -> tuple[None, str]:
    return None, "none"


async def _url_resolution_failure(*_args: Any) -> tuple[None, str]:
    raise RuntimeError("URL resolution failed")


def _manager(adapter: object | None = None) -> tuple[RealtimeObservationManager, _Bus]:
    bus = _Bus()
    hass = SimpleNamespace(bus=bus)
    entry = SimpleNamespace(
        entry_id="entry-test",
        data={
            CONF_API_KEY: "token-secret",
            CONF_WEBHOOK_ID: "webhook-secret",
            CONF_WEBHOOK_AUTH: "authorization-secret",
        },
    )
    coordinator = SimpleNamespace(
        adapter=adapter or object(),
        data=None,
        last_update_success=True,
    )
    manager = RealtimeObservationManager(
        hass, entry, coordinator, url_resolver=_no_external_url
    )
    manager._ensure_credentials()
    return manager, bus


@pytest.mark.asyncio
async def test_stop_callback_does_not_unsubscribe_one_shot_listener_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bus = _manager()
    manager._stop_unsubscribe = bus.async_listen_once("stop", object())
    monkeypatch.setattr(realtime_module.ir, "async_delete_issue", lambda *_args: None)

    await manager._async_handle_stop(SimpleNamespace())
    await manager.async_shutdown()

    assert bus.unsubscribe_count == 0


@pytest.mark.asyncio
async def test_unload_then_stop_unsubscribes_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bus = _manager()
    manager._stop_unsubscribe = bus.async_listen_once("stop", object())
    monkeypatch.setattr(realtime_module.ir, "async_delete_issue", lambda *_args: None)

    await manager.async_shutdown()
    await manager._async_handle_stop(SimpleNamespace())

    assert bus.unsubscribe_count == 1


@pytest.mark.asyncio
async def test_remote_cleanup_failure_still_unregisters_local_webhook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _Adapter(fail_cleanup=True)
    manager, _bus = _manager(adapter)
    manager._registered_locally = True
    unregistered: list[str] = []
    monkeypatch.setattr(
        realtime_module.webhook,
        "async_unregister",
        lambda _hass, webhook_id: unregistered.append(webhook_id),
    )
    monkeypatch.setattr(realtime_module.ir, "async_delete_issue", lambda *_args: None)

    await manager.async_shutdown()
    await manager.async_shutdown()

    assert adapter.cleanup_count == 1
    assert unregistered == ["webhook-secret"]


@pytest.mark.asyncio
async def test_repeated_setup_does_not_duplicate_local_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bus = _manager()
    registered: list[str] = []
    unregistered: list[str] = []
    monkeypatch.setattr(
        realtime_module.webhook,
        "async_register",
        lambda _hass, _domain, _name, webhook_id, _handler, **_kwargs: (
            registered.append(webhook_id)
        ),
    )
    monkeypatch.setattr(
        realtime_module.webhook,
        "async_unregister",
        lambda _hass, webhook_id: unregistered.append(webhook_id),
    )
    monkeypatch.setattr(
        realtime_module.ir, "async_create_issue", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(realtime_module.ir, "async_delete_issue", lambda *_args: None)

    await manager.async_setup()
    await manager.async_setup()
    await manager.async_shutdown()

    assert registered == ["webhook-secret"]
    assert bus.listen_count == 1
    assert bus.unsubscribe_count == 1
    assert unregistered == ["webhook-secret"]


@pytest.mark.asyncio
async def test_setup_failure_rolls_back_local_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bus = _manager()
    manager._url_resolver = _url_resolution_failure
    registered: list[str] = []
    unregistered: list[str] = []
    monkeypatch.setattr(
        realtime_module.webhook,
        "async_register",
        lambda _hass, _domain, _name, webhook_id, _handler, **_kwargs: (
            registered.append(webhook_id)
        ),
    )
    monkeypatch.setattr(
        realtime_module.webhook,
        "async_unregister",
        lambda _hass, webhook_id: unregistered.append(webhook_id),
    )
    monkeypatch.setattr(realtime_module.ir, "async_delete_issue", lambda *_args: None)

    with pytest.raises(RuntimeError, match="URL resolution failed"):
        await manager.async_setup()

    assert registered == ["webhook-secret"]
    assert unregistered == ["webhook-secret"]
    assert bus.unsubscribe_count == 1
