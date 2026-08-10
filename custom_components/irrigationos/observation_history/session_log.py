"""Safe daily JSONL watering-session evidence export."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SESSION_LOG_RETENTION_DAYS = 30


class DailyWateringSessionLog:
    """Write safe canonical session evidence to local-day files."""

    def __init__(self, root: Path, timezone: ZoneInfo) -> None:
        self.root = root
        self.timezone = timezone
        self.last_successful_write: datetime | None = None
        self.last_error: str | None = None
        self.write_error_count = 0
        self.record_count = 0
        self.current_file: str | None = None
        self._last_cleanup_date: date | None = None

    def record(self, recorded_at: datetime, payload: dict[str, Any]) -> bool:
        """Append one safe record and enforce independent 30-day retention."""

        try:
            utc_time = recorded_at.astimezone(UTC)
            local_time = utc_time.astimezone(self.timezone)
            self.root.mkdir(parents=True, exist_ok=True)
            cleanup_healthy = self._cleanup(local_time.date())
            filename = f"irrigationos_sessions_{local_time.date().isoformat()}.jsonl"
            path = self.root / filename
            record = {
                "timestamp_local": local_time.isoformat(),
                "timestamp_utc": utc_time.isoformat(),
                **payload,
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
            self.current_file = filename
            self.last_successful_write = utc_time
            if cleanup_healthy:
                self.last_error = None
            self.record_count += 1
            return cleanup_healthy
        except (OSError, TypeError, ValueError):
            self.last_error = "daily_session_log_write_failed"
            self.write_error_count += 1
            return False

    def diagnostics(self) -> dict[str, object]:
        """Return safe session-log health diagnostics."""

        return {
            "directory": str(self.root),
            "current_file": self.current_file,
            "retention_days": SESSION_LOG_RETENTION_DAYS,
            "record_count": self.record_count,
            "write_error_count": self.write_error_count,
            "last_error": self.last_error,
            "last_successful_write": (
                None
                if self.last_successful_write is None
                else self.last_successful_write.isoformat()
            ),
        }

    def _cleanup(self, local_date: date) -> bool:
        if self._last_cleanup_date == local_date:
            return self.last_error != "daily_session_log_retention_failed"
        self._last_cleanup_date = local_date
        oldest_kept = local_date - timedelta(days=SESSION_LOG_RETENTION_DAYS - 1)
        healthy = True
        for path in self.root.glob("irrigationos_sessions_????-??-??.jsonl"):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_sessions_")
                )
            except ValueError:
                continue
            if file_date < oldest_kept:
                try:
                    path.unlink()
                except OSError:
                    self.last_error = "daily_session_log_retention_failed"
                    self.write_error_count += 1
                    healthy = False
        return healthy
