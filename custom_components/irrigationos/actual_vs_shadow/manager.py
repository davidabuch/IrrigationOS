"""Observation-only actual-vs-shadow reconciliation manager."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..controllers import ObservationQuality
from ..observation_history import WateringSession
from .matching import (
    MATCH_GRACE,
    classify_match,
    extract_scheduled_irrigation_actions,
    parse_time,
)
from .models import (
    ActualVsShadowRecord,
    ReconciliationConfidence,
    ReconciliationKind,
    ReconciliationOutcome,
)

RECONCILIATION_STORE_VERSION = 1
RECONCILIATION_LOG_RETENTION_DAYS = 30
MAX_PROCESSED_IDENTIFIERS = 1000


@dataclass(frozen=True, slots=True)
class _PendingAction:
    evaluation_id: str
    scheduled_action_id: str
    target_id: str
    starts_at: datetime
    ends_at: datetime
    runtime_seconds: int

    @property
    def key(self) -> str:
        return f"{self.evaluation_id}:{self.scheduled_action_id}"

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "scheduled_action_id": self.scheduled_action_id,
            "target_id": self.target_id,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "runtime_seconds": self.runtime_seconds,
        }

    @classmethod
    def from_dict(cls, value: object) -> _PendingAction:
        if not isinstance(value, dict):
            raise ValueError("pending reconciliation action must be a mapping")
        return cls(
            evaluation_id=str(value["evaluation_id"]),
            scheduled_action_id=str(value["scheduled_action_id"]),
            target_id=str(value["target_id"]),
            starts_at=parse_time(value["starts_at"]),
            ends_at=parse_time(value["ends_at"]),
            runtime_seconds=int(value["runtime_seconds"]),
        )


class ActualVsShadowReconciliationManager:
    """Compare immutable shadow intent with observed watering, never actuating."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, root: Path, timezone: ZoneInfo
    ) -> None:
        self._hass = hass
        self._root = root
        self._timezone = timezone
        self._store = Store[dict[str, Any]](
            hass,
            RECONCILIATION_STORE_VERSION,
            f"irrigationos.{entry_id}.actual_vs_shadow",
        )
        self._pending: dict[str, _PendingAction] = {}
        self._processed_sessions: set[str] = set()
        self._processed_actions: set[str] = set()
        self._first_shadow_timestamp: datetime | None = None
        self._last_cleanup_date: date | None = None
        self.record_count = 0
        self.superseded_action_count = 0
        self.last_record: ActualVsShadowRecord | None = None
        self.last_error: str | None = None

    async def async_initialize(
        self,
        shadow_records: tuple[dict[str, Any], ...],
        completed_sessions: tuple[WateringSession, ...],
        *,
        now: datetime,
        observation_quality: ObservationQuality | None = None,
    ) -> None:
        """Restore idempotency state and replay preserved shadow intent safely."""

        try:
            stored = await self._store.async_load()
        except Exception:
            stored = None
            self.last_error = "reconciliation_store_load_failed"
        if isinstance(stored, dict):
            try:
                self._pending = {
                    action.key: action
                    for action in (
                        _PendingAction.from_dict(item)
                        for item in stored.get("pending_actions", [])
                    )
                }
                self._processed_sessions = set(
                    str(value) for value in stored.get("processed_sessions", [])
                )
                self._processed_actions = set(
                    str(value) for value in stored.get("processed_actions", [])
                )
            except (KeyError, TypeError, ValueError):
                self._pending = {}
                self._processed_sessions = set()
                self._processed_actions = set()
                self.last_error = "reconciliation_store_invalid"
        for record in sorted(shadow_records, key=_shadow_timestamp):
            self._ingest_shadow_record(record)
        await self.async_consider(
            shadow_record=None,
            completed_sessions=completed_sessions,
            now=now,
            observation_quality=observation_quality,
        )

    async def async_consider(
        self,
        *,
        shadow_record: object | None,
        completed_sessions: tuple[WateringSession, ...],
        now: datetime,
        observation_quality: ObservationQuality | None,
    ) -> tuple[ActualVsShadowRecord, ...]:
        """Reconcile new intent and completed observations deterministically."""

        if shadow_record is not None:
            record_dict = _shadow_record_dict(shadow_record)
            self._ingest_shadow_record(record_dict)
        created: list[ActualVsShadowRecord] = []
        utc_now = now.astimezone(UTC)
        for session in sorted(completed_sessions, key=lambda item: item.started_at):
            if session.session_id in self._processed_sessions:
                continue
            candidate = self._match_action(session)
            if candidate is not None:
                created.append(self._compare(candidate, session, utc_now))
                self._processed_actions.add(candidate.key)
                self._pending.pop(candidate.key, None)
            elif (
                self._first_shadow_timestamp is None
                or session.started_at < self._first_shadow_timestamp
            ):
                created.append(self._unmatched_without_shadow(session, utc_now))
            else:
                created.append(self._unexpected(session, utc_now))
            self._processed_sessions.add(session.session_id)
        for key, action in tuple(self._pending.items()):
            if key in self._processed_actions:
                self._pending.pop(key, None)
                continue
            if utc_now <= action.ends_at + MATCH_GRACE:
                continue
            created.append(
                self._skipped(action, utc_now, observation_quality=observation_quality)
            )
            self._processed_actions.add(key)
            self._pending.pop(key, None)
        for record in created:
            success = await self._hass.async_add_executor_job(self._write_record, record)
            if success:
                self.record_count += 1
                self.last_record = record
        await self._async_persist()
        return tuple(created)

    def _ingest_shadow_record(self, record: dict[str, Any]) -> None:
        timestamp = _shadow_timestamp(record)
        evaluation_id = str(record.get("evaluation_id", ""))
        if not evaluation_id or timestamp is None:
            return
        if self._first_shadow_timestamp is None or timestamp < self._first_shadow_timestamp:
            self._first_shadow_timestamp = timestamp
        # A later evaluation supersedes only earlier actions that have not started yet.
        for key, action in tuple(self._pending.items()):
            if action.starts_at >= timestamp and action.evaluation_id != evaluation_id:
                self._pending.pop(key, None)
                self.superseded_action_count += 1
        for raw in extract_scheduled_irrigation_actions(record):
            action = _PendingAction(**raw)
            if action.key not in self._processed_actions:
                self._pending[action.key] = action

    def _match_action(self, session: WateringSession) -> _PendingAction | None:
        candidates = [
            action
            for action in self._pending.values()
            if action.target_id == session.area_id
            and action.starts_at - MATCH_GRACE
            <= session.started_at
            <= action.ends_at + MATCH_GRACE
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda action: (
                abs((session.started_at - action.starts_at).total_seconds()),
                action.key,
            ),
        )

    def _compare(
        self, action: _PendingAction, session: WateringSession, now: datetime
    ) -> ActualVsShadowRecord:
        classified = classify_match(
            planned_start=action.starts_at,
            planned_runtime_seconds=action.runtime_seconds,
            observed_start=session.started_at,
            observed_runtime_seconds=session.duration_seconds,
            incomplete=session.incomplete,
            observation_quality=session.observation_quality.value,
            timestamp_precision=session.timestamp_precision.value,
        )
        return self._record(
            kind=ReconciliationKind.PLANNED_VS_OBSERVED,
            outcome=ReconciliationOutcome(classified["outcome"]),
            confidence=ReconciliationConfidence(classified["confidence"]),
            reasons=list(classified["reason_codes"]),
            now=now,
            action=action,
            session=session,
            start_delta=classified["start_delta_seconds"],
            runtime_delta=classified["runtime_delta_seconds"],
        )

    def _unexpected(
        self, session: WateringSession, now: datetime
    ) -> ActualVsShadowRecord:
        confidence = (
            ReconciliationConfidence.LOW
            if session.incomplete or session.observation_quality is ObservationQuality.PARTIAL
            else ReconciliationConfidence.MEDIUM
        )
        return self._record(
            kind=ReconciliationKind.UNEXPECTED_OBSERVED_WATERING,
            outcome=ReconciliationOutcome.DISAGREEMENT,
            confidence=confidence,
            reasons=["observed_watering_without_matching_shadow_action"],
            now=now,
            session=session,
        )

    def _unmatched_without_shadow(
        self, session: WateringSession, now: datetime
    ) -> ActualVsShadowRecord:
        return self._record(
            kind=ReconciliationKind.UNMATCHED_WITHOUT_SHADOW,
            outcome=ReconciliationOutcome.INSUFFICIENT_EVIDENCE,
            confidence=ReconciliationConfidence.NONE,
            reasons=["no_preceding_shadow_evaluation"],
            now=now,
            session=session,
        )

    def _skipped(
        self,
        action: _PendingAction,
        now: datetime,
        *,
        observation_quality: ObservationQuality | None,
    ) -> ActualVsShadowRecord:
        if observation_quality is not ObservationQuality.CONFIRMED:
            outcome = ReconciliationOutcome.INSUFFICIENT_EVIDENCE
            confidence = ReconciliationConfidence.LOW
            reasons = ["planned_watering_not_observed", "observation_quality_not_confirmed"]
        else:
            outcome = ReconciliationOutcome.DISAGREEMENT
            confidence = ReconciliationConfidence.MEDIUM
            reasons = ["planned_watering_not_observed_after_grace_window"]
        return self._record(
            kind=ReconciliationKind.SKIPPED_PLANNED_WATERING,
            outcome=outcome,
            confidence=confidence,
            reasons=reasons,
            now=now,
            action=action,
        )

    def _record(
        self,
        *,
        kind: ReconciliationKind,
        outcome: ReconciliationOutcome,
        confidence: ReconciliationConfidence,
        reasons: list[str],
        now: datetime,
        action: _PendingAction | None = None,
        session: WateringSession | None = None,
        start_delta: int | None = None,
        runtime_delta: int | None = None,
    ) -> ActualVsShadowRecord:
        seed = "|".join(
            (
                kind.value,
                "" if action is None else action.key,
                "" if session is None else session.session_id,
            )
        )
        comparison_id = hashlib.sha256(seed.encode()).hexdigest()
        local = now.astimezone(self._timezone)
        return ActualVsShadowRecord(
            comparison_id=comparison_id,
            kind=kind,
            outcome=outcome,
            confidence=confidence,
            reason_codes=tuple(sorted(set(reasons))),
            reconciled_at_utc=now,
            reconciled_at_local=local,
            evaluation_id=None if action is None else action.evaluation_id,
            scheduled_action_id=None if action is None else action.scheduled_action_id,
            session_id=None if session is None else session.session_id,
            target_id=(
                action.target_id
                if action is not None
                else (session.area_id if session else None)
            ),
            planned_start_utc=None if action is None else action.starts_at,
            planned_end_utc=None if action is None else action.ends_at,
            planned_runtime_seconds=None if action is None else action.runtime_seconds,
            observed_start_utc=None if session is None else session.started_at,
            observed_end_utc=None if session is None else session.ended_at,
            observed_runtime_seconds=None if session is None else session.duration_seconds,
            start_delta_seconds=start_delta,
            runtime_delta_seconds=runtime_delta,
            observation_source=None if session is None else session.observation_source.value,
            observation_quality=None if session is None else session.observation_quality.value,
            timestamp_precision=None if session is None else session.timestamp_precision.value,
            observation_incomplete=None if session is None else session.incomplete,
        )

    def _write_record(self, record: ActualVsShadowRecord) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            self._cleanup(record.reconciled_at_local.date())
            path = self._root / (
                f"irrigationos_reconciliation_{record.reconciled_at_local.date().isoformat()}.jsonl"
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")))
                handle.write("\n")
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "reconciliation_log_write_failed"
            return False

    def _cleanup(self, local_date: date) -> None:
        if self._last_cleanup_date == local_date:
            return
        self._last_cleanup_date = local_date
        oldest = local_date - timedelta(days=RECONCILIATION_LOG_RETENTION_DAYS - 1)
        for path in self._root.glob("irrigationos_reconciliation_????-??-??.jsonl"):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_reconciliation_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    async def _async_persist(self) -> None:
        try:
            await self._store.async_save(
                {
                    "pending_actions": [
                        action.to_dict()
                        for action in sorted(self._pending.values(), key=lambda item: item.key)
                    ],
                    "processed_sessions": sorted(self._processed_sessions)[
                        -MAX_PROCESSED_IDENTIFIERS:
                    ],
                    "processed_actions": sorted(self._processed_actions)[
                        -MAX_PROCESSED_IDENTIFIERS:
                    ],
                }
            )
        except Exception:
            self.last_error = "reconciliation_store_save_failed"

    def diagnostics(self) -> dict[str, object]:
        """Return privacy-safe reconciliation health and latest outcome."""

        return {
            "record_count": self.record_count,
            "pending_action_count": len(self._pending),
            "superseded_action_count": self.superseded_action_count,
            "last_error": self.last_error,
            "last_comparison_id": (
                None if self.last_record is None else self.last_record.comparison_id
            ),
            "last_kind": None if self.last_record is None else self.last_record.kind.value,
            "last_outcome": None if self.last_record is None else self.last_record.outcome.value,
            "last_confidence": (
                None if self.last_record is None else self.last_record.confidence.value
            ),
            "retention_days": RECONCILIATION_LOG_RETENTION_DAYS,
        }


def _shadow_record_dict(record: object) -> dict[str, Any]:
    if isinstance(record, dict):
        return record
    payload = getattr(record, "payload", None)
    timestamp = getattr(record, "timestamp_utc", None)
    return {
        "evaluation_id": getattr(record, "evaluation_id", ""),
        "timestamp_utc": timestamp.isoformat() if isinstance(timestamp, datetime) else None,
        "payload": payload if isinstance(payload, dict) else {},
    }


def _shadow_timestamp(record: dict[str, Any]) -> datetime:
    value = record.get("timestamp_utc")
    try:
        return parse_time(value)
    except ValueError:
        return datetime.max.replace(tzinfo=UTC)
