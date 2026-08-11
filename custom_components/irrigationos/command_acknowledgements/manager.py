"""Local synthetic acknowledgement evidence manager with no dispatch capability."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from homeassistant.core import HomeAssistant

from .engine import (
    begin_acknowledgement_wait,
    evaluate_acknowledgement_timeout,
    parse_acknowledgement_json_lines,
    preempt_acknowledgement,
    reconcile_acknowledgement_history,
    resolve_acknowledgement,
    serialize_acknowledgement_record,
)
from .models import CommandAcknowledgementRecord, CommandAcknowledgementState

COMMAND_ACKNOWLEDGEMENT_RETENTION_DAYS = 30


class CommandAcknowledgementManager:
    """Exercise acknowledgement semantics without any controller dispatch path."""

    def __init__(self, hass: HomeAssistant, root: Path) -> None:
        self._hass = hass
        self._root = root
        self._pending: dict[str, CommandAcknowledgementRecord] = {}
        self.event_count = 0
        self.timeout_count = 0
        self.last_record: CommandAcknowledgementRecord | None = None
        self.last_error: str | None = None
        self.restart_reconciliation_completed = False
        self.restored_pending_count = 0
        self.restart_timeout_count = 0
        self._last_cleanup_date: date | None = None

    async def async_initialize(self, *, now: datetime) -> None:
        """Replay persisted evidence and reconstruct acknowledgement state safely."""

        records = await self._hass.async_add_executor_job(self._load_records)
        self._pending.clear()
        self.restored_pending_count = 0
        self.restart_timeout_count = 0
        self.restart_reconciliation_completed = False
        if records is None:
            return
        pending, timeout_transitions = reconcile_acknowledgement_history(
            records, now=now
        )
        self._pending.update(pending)
        self.restored_pending_count = len(pending)
        for record in timeout_transitions:
            await self._async_record(record)
            self.timeout_count += 1
            self.restart_timeout_count += 1
        self.restart_reconciliation_completed = True

    def is_pending(self, command_id: str) -> bool:
        """Return whether a synthetic acknowledgement window is still active."""

        return command_id in self._pending

    async def async_begin_synthetic_tracking(
        self, *, command_id: str, dispatched_at: datetime
    ) -> CommandAcknowledgementRecord:
        """Start synthetic-only tracking; this method never dispatches a command."""

        record = begin_acknowledgement_wait(
            command_id=command_id, dispatched_at=dispatched_at
        )
        await self._async_record(record)
        self._pending[record.command_id] = record
        return record

    async def async_resolve_synthetic(
        self,
        *,
        command_id: str,
        observed_at: datetime,
        accepted: bool,
        detail_code: str,
    ) -> CommandAcknowledgementRecord:
        """Resolve an existing synthetic acknowledgement window."""

        pending = self._pending.get(command_id)
        if pending is None:
            raise ValueError("pending_acknowledgement_not_found")
        record = resolve_acknowledgement(
            pending,
            observed_at=observed_at,
            accepted=accepted,
            detail_code=detail_code,
        )
        await self._async_record(record)
        self._pending.pop(command_id, None)
        if record.state is CommandAcknowledgementState.TIMED_OUT:
            self.timeout_count += 1
        return record

    async def async_preempt_synthetic(
        self,
        *,
        command_id: str,
        observed_at: datetime,
        detail_code: str,
    ) -> CommandAcknowledgementRecord:
        """Terminate an outstanding synthetic acknowledgement window for safety."""

        pending = self._pending.get(command_id)
        if pending is None:
            raise ValueError("pending_acknowledgement_not_found")
        record = preempt_acknowledgement(
            pending, observed_at=observed_at, detail_code=detail_code
        )
        await self._async_record(record)
        self._pending.pop(command_id, None)
        return record

    async def async_evaluate_timeouts(self, *, now: datetime) -> None:
        """Fail expired synthetic windows closed and persist timeout evidence."""

        for command_id, pending in tuple(self._pending.items()):
            record = evaluate_acknowledgement_timeout(pending, now=now)
            if record is pending:
                continue
            await self._async_record(record)
            self._pending.pop(command_id, None)
            self.timeout_count += 1

    async def _async_record(self, record: CommandAcknowledgementRecord) -> None:
        success = await self._hass.async_add_executor_job(self._write_record, record)
        if success:
            self.event_count += 1
            self.last_record = record

    def _load_records(self) -> tuple[CommandAcknowledgementRecord, ...] | None:
        """Load chronological acknowledgement evidence; malformed data fails closed."""

        records: list[CommandAcknowledgementRecord] = []
        try:
            pattern = "irrigationos_command_acknowledgements_????-??-??.jsonl"
            for path in sorted(self._root.glob(pattern)):
                with path.open("r", encoding="utf-8") as handle:
                    records.extend(parse_acknowledgement_json_lines(handle))
            self.last_error = None
            return tuple(records)
        except (OSError, ValueError):
            self.last_error = "command_acknowledgement_reconciliation_failed"
            return None

    def _write_record(self, record: CommandAcknowledgementRecord) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            local_date = record.recorded_at_utc.date()
            self._cleanup(local_date)
            path = self._root / (
                f"irrigationos_command_acknowledgements_{local_date.isoformat()}.jsonl"
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(serialize_acknowledgement_record(record) + "\n")
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "command_acknowledgement_log_write_failed"
            return False

    def _cleanup(self, today: date) -> None:
        if self._last_cleanup_date == today:
            return
        self._last_cleanup_date = today
        oldest = today - timedelta(days=COMMAND_ACKNOWLEDGEMENT_RETENTION_DAYS - 1)
        for path in self._root.glob(
            "irrigationos_command_acknowledgements_????-??-??.jsonl"
        ):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_command_acknowledgements_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe non-actuating acknowledgement diagnostics."""

        return {
            "event_count": self.event_count,
            "pending_count": len(self._pending),
            "timeout_count": self.timeout_count,
            "last_state": (
                None if self.last_record is None else self.last_record.state.value
            ),
            "synthetic_only": True,
            "dispatch_capability": False,
            "restart_reconciliation": self.restart_reconciliation_completed,
            "restored_pending_count": self.restored_pending_count,
            "restart_timeout_count": self.restart_timeout_count,
            "last_error": self.last_error,
        }
