"""Observation-only shadow evaluation persistence and semantic deduplication."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import VERSION
from ..pipeline import PipelineEvaluation
from .models import (
    SHADOW_EVALUATION_SCHEMA_VERSION,
    ShadowEvaluationReason,
    ShadowEvaluationRecord,
    jsonable,
    semantic_value,
)

SHADOW_STORE_VERSION = 1
SHADOW_LOG_RETENTION_DAYS = 30


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _section_hash(value: Any) -> str:
    return hashlib.sha256(_canonical(semantic_value(value)).encode()).hexdigest()


def _decision_payload(pipeline: PipelineEvaluation) -> dict[str, Any]:
    return {
        "status": pipeline.status.value,
        "current_stage": pipeline.current_stage.value,
        "blocker_codes": list(pipeline.blocker_codes),
        "water_requirements": jsonable(pipeline.water_requirements),
        "plant_stress": jsonable(pipeline.plant_stress),
        "plant_health": jsonable(pipeline.plant_health),
        "recommendations": jsonable(pipeline.recommendations),
        "planning": jsonable(pipeline.planning),
        "scheduling": jsonable(pipeline.scheduling),
        "execution_simulation": jsonable(pipeline.execution),
    }


class ShadowEvaluationManager:
    """Persist decision-significant shadow evidence without actuating irrigation."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, root: Path, timezone: ZoneInfo
    ) -> None:
        self._hass = hass
        self._timezone = timezone
        self._root = root
        self._store = Store[dict[str, Any]](
            hass, SHADOW_STORE_VERSION, f"irrigationos.{entry_id}.shadow_evaluations"
        )
        self.last_record: ShadowEvaluationRecord | None = None
        self.last_decision_fingerprint: str | None = None
        self._section_hashes: dict[str, str] = {}
        self._completed_session_count = 0
        self.record_count = 0
        self.deduplicated_count = 0
        self.last_error: str | None = None
        self._last_cleanup_date: date | None = None

    async def async_initialize(self) -> None:
        """Restore only deduplication metadata; immutable evidence remains in JSONL."""
        try:
            stored = await self._store.async_load()
        except Exception:
            stored = None
            self.last_error = "shadow_store_load_failed"
        if isinstance(stored, dict):
            self.last_decision_fingerprint = stored.get("last_decision_fingerprint")
            hashes = stored.get("section_hashes", {})
            if isinstance(hashes, dict):
                self._section_hashes = {str(k): str(v) for k, v in hashes.items()}
            self._completed_session_count = int(
                stored.get("completed_session_count", 0)
            )

    async def async_consider(
        self,
        pipeline: PipelineEvaluation,
        *,
        completed_session_count: int,
        force_reason: ShadowEvaluationReason | None = None,
    ) -> ShadowEvaluationRecord | None:
        """Persist a full record only for nightly or semantically changed decisions."""
        reason = force_reason or self._reason_for_change(
            pipeline, completed_session_count
        )
        payload = self._build_payload(pipeline)
        fingerprint = _section_hash(_decision_payload(pipeline))
        should_write = (
            reason is ShadowEvaluationReason.NIGHTLY
            or fingerprint != self.last_decision_fingerprint
        )
        self._update_change_state(pipeline, completed_session_count)
        if not should_write:
            self.deduplicated_count += 1
            await self._async_persist_state()
            return None
        now_utc = pipeline.evaluated_at.astimezone(UTC)
        local = now_utc.astimezone(self._timezone)
        identity_seed = f"{now_utc.isoformat()}|{reason.value}|{fingerprint}"
        record = ShadowEvaluationRecord(
            schema_version=SHADOW_EVALUATION_SCHEMA_VERSION,
            evaluation_id=hashlib.sha256(identity_seed.encode()).hexdigest(),
            reason=reason,
            timestamp_utc=now_utc,
            timestamp_local=local,
            integration_version=VERSION,
            pipeline_algorithm_version=pipeline.algorithm_version,
            decision_fingerprint=fingerprint,
            payload=payload,
        )
        success = await self._hass.async_add_executor_job(self._write_record, record)
        if success:
            self.last_record = record
            self.last_decision_fingerprint = fingerprint
            self.record_count += 1
        await self._async_persist_state()
        return record if success else None

    def _reason_for_change(
        self, pipeline: PipelineEvaluation, completed_count: int
    ) -> ShadowEvaluationReason:
        if self.last_decision_fingerprint is None:
            return ShadowEvaluationReason.STARTUP_STALE_OR_MISSING
        if completed_count > self._completed_session_count:
            return ShadowEvaluationReason.WATERING_COMPLETED
        sections = {
            "profile": _section_hash(pipeline.landscape_profile),
            "scientific": _section_hash(pipeline.scientific_inputs),
            "observation": _section_hash(pipeline.observation_snapshot),
            "confidence": _section_hash((pipeline.status, pipeline.stages)),
        }
        if sections["profile"] != self._section_hashes.get("profile"):
            return ShadowEvaluationReason.PROFILE_CHANGE
        if sections["confidence"] != self._section_hashes.get("confidence"):
            return ShadowEvaluationReason.CONFIDENCE_CHANGE
        if sections["scientific"] != self._section_hashes.get("scientific"):
            return ShadowEvaluationReason.SCIENTIFIC_INPUT_CHANGE
        if sections["observation"] != self._section_hashes.get("observation"):
            return ShadowEvaluationReason.OBSERVATION_CHANGE
        return ShadowEvaluationReason.DECISION_CHANGE

    def _update_change_state(
        self, pipeline: PipelineEvaluation, completed_count: int
    ) -> None:
        self._section_hashes = {
            "profile": _section_hash(pipeline.landscape_profile),
            "scientific": _section_hash(pipeline.scientific_inputs),
            "observation": _section_hash(pipeline.observation_snapshot),
            "confidence": _section_hash((pipeline.status, pipeline.stages)),
        }
        self._completed_session_count = completed_count

    def _build_payload(self, pipeline: PipelineEvaluation) -> dict[str, Any]:
        return {
            "pipeline_status": pipeline.status.value,
            "current_stage": pipeline.current_stage.value,
            "stages": jsonable(pipeline.stages),
            "blockers": list(pipeline.blocker_codes),
            "scientific_inputs": jsonable(pipeline.scientific_inputs),
            "observation_snapshot": jsonable(pipeline.observation_snapshot),
            "landscape_profile": jsonable(pipeline.landscape_profile),
            **_decision_payload(pipeline),
        }

    def _write_record(self, record: ShadowEvaluationRecord) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            self._cleanup(record.timestamp_local.date())
            path = self._root / (
                f"irrigationos_shadow_{record.timestamp_local.date().isoformat()}.jsonl"
            )
            data = jsonable(record)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical(data) + "\n")
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError):
            self.last_error = "shadow_log_write_failed"
            return False

    def _cleanup(self, local_date: date) -> None:
        if self._last_cleanup_date == local_date:
            return
        self._last_cleanup_date = local_date
        oldest = local_date - timedelta(days=SHADOW_LOG_RETENTION_DAYS - 1)
        for path in self._root.glob("irrigationos_shadow_????-??-??.jsonl"):
            try:
                file_date = date.fromisoformat(
                    path.stem.removeprefix("irrigationos_shadow_")
                )
            except ValueError:
                continue
            if file_date < oldest:
                path.unlink()

    async def async_load_records(self) -> tuple[dict[str, Any], ...]:
        """Load preserved immutable shadow records in chronological order."""

        return await self._hass.async_add_executor_job(self._load_records)

    def _load_records(self) -> tuple[dict[str, Any], ...]:
        records: list[dict[str, Any]] = []
        try:
            for path in sorted(self._root.glob("irrigationos_shadow_????-??-??.jsonl")):
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        value = json.loads(line)
                        if isinstance(value, dict):
                            records.append(value)
        except (OSError, ValueError, json.JSONDecodeError):
            self.last_error = "shadow_log_read_failed"
        records.sort(key=lambda item: str(item.get("timestamp_utc", "")))
        return tuple(records)

    async def _async_persist_state(self) -> None:
        try:
            await self._store.async_save(
                {
                    "last_decision_fingerprint": self.last_decision_fingerprint,
                    "section_hashes": self._section_hashes,
                    "completed_session_count": self._completed_session_count,
                }
            )
        except Exception:
            self.last_error = "shadow_store_save_failed"

    def diagnostics(self) -> dict[str, Any]:
        return {
            "record_count": self.record_count,
            "deduplicated_count": self.deduplicated_count,
            "last_error": self.last_error,
            "last_evaluation_id": (
                None if self.last_record is None else self.last_record.evaluation_id
            ),
            "last_reason": (
                None if self.last_record is None else self.last_record.reason.value
            ),
            "last_timestamp_utc": (
                None
                if self.last_record is None
                else self.last_record.timestamp_utc.isoformat()
            ),
            "last_decision_fingerprint": self.last_decision_fingerprint,
            "retention_days": SHADOW_LOG_RETENTION_DAYS,
        }
