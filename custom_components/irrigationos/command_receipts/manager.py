"""Immutable local command intent and receipt evidence manager."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant

from .engine import build_command_intent, build_not_dispatched_receipt
from .models import CommandAttribution, CommandIntent, CommandIntentAction, CommandReceipt

COMMAND_RECEIPT_RETENTION_DAYS = 30


class CommandReceiptManager:
    """Record future command intent evidence without any dispatch capability."""

    def __init__(self, hass: HomeAssistant, root: Path) -> None:
        self._hass = hass
        self._root = root
        self.intent_count = 0
        self.receipt_count = 0
        self.last_intent: CommandIntent | None = None
        self.last_receipt: CommandReceipt | None = None
        self.last_error: str | None = None
        self._last_cleanup_date: date | None = None

    async def async_record_intent(
        self,
        *,
        created_at: datetime,
        attribution: CommandAttribution,
        action: CommandIntentAction,
        controller_id: str,
        zone_id: str | None,
        requested_runtime_seconds: int | None,
        reason_code: str,
    ) -> tuple[CommandIntent, CommandReceipt]:
        """Persist intent plus explicit not-dispatched receipt."""

        intent = build_command_intent(
            created_at=created_at,
            attribution=attribution,
            action=action,
            controller_id=controller_id,
            zone_id=zone_id,
            requested_runtime_seconds=requested_runtime_seconds,
            reason_code=reason_code,
        )
        receipt = build_not_dispatched_receipt(intent, recorded_at=created_at)
        success = await self._hass.async_add_executor_job(self._write_pair, intent, receipt)
        if success:
            self.intent_count += 1
            self.receipt_count += 1
            self.last_intent = intent
            self.last_receipt = receipt
        return intent, receipt

    def _write_pair(self, intent: CommandIntent, receipt: CommandReceipt) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            local_date = receipt.recorded_at_utc.date()
            self._cleanup(local_date)
            path = self._root / (
                f"irrigationos_command_receipts_{local_date.isoformat()}.jsonl"
            )
            with path.open("a", encoding="utf-8") as handle:
                payload = {"intent": intent.to_dict(), "receipt": receipt.to_dict()}
                handle.write(
                    json.dumps(
                        payload, sort_keys=True, separators=(",", ":")
                    )
                    + "\n"
                )
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "command_receipt_log_write_failed"
            return False

    def _cleanup(self, today: date) -> None:
        if self._last_cleanup_date == today:
            return
        self._last_cleanup_date = today
        oldest = today - timedelta(days=COMMAND_RECEIPT_RETENTION_DAYS - 1)
        for path in self._root.glob("irrigationos_command_receipts_????-??-??.jsonl"):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_command_receipts_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    def diagnostics(self) -> dict[str, object]:
        return {
            "intent_count": self.intent_count,
            "receipt_count": self.receipt_count,
            "last_command_id": (
                None if self.last_intent is None else self.last_intent.command_id
            ),
            "last_receipt_outcome": (
                None
                if self.last_receipt is None
                else self.last_receipt.outcome.value
            ),
            "dispatch_capability": False,
            "last_error": self.last_error,
        }
