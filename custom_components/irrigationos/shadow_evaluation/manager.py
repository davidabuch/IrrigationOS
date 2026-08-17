"""Observation-only shadow evaluation persistence and semantic deduplication."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import VERSION
from ..pipeline import PipelineEvaluation
from ..production_recommendation import ProductionRecommendationSnapshot
from ..quantitative_water_balance import WaterBalanceSnapshot
from .models import (
    SHADOW_EVALUATION_SCHEMA_VERSION,
    ShadowEvaluationReason,
    ShadowEvaluationRecord,
    jsonable,
    semantic_decision_value,
    semantic_value,
)

SHADOW_STORE_VERSION = 1
SHADOW_LOG_RETENTION_DAYS = 30


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _section_hash(value: Any) -> str:
    return hashlib.sha256(_canonical(semantic_value(value)).encode()).hexdigest()


def _decision_hash(value: Any) -> str:
    return hashlib.sha256(
        _canonical(semantic_decision_value(value)).encode()
    ).hexdigest()


def _decision_payload(
    pipeline: PipelineEvaluation,
    production_recommendations: ProductionRecommendationSnapshot,
    water_balances: WaterBalanceSnapshot | None = None,
) -> dict[str, Any]:
    return {
        "status": pipeline.status.value,
        "current_stage": pipeline.current_stage.value,
        "blocker_codes": list(pipeline.blocker_codes),
        "water_requirements": jsonable(pipeline.water_requirements),
        "plant_stress": jsonable(pipeline.plant_stress),
        "plant_health": jsonable(pipeline.plant_health),
        "recommendations": jsonable(pipeline.recommendations),
        "planning": jsonable(pipeline.planning),
        "scheduling": {"area_evaluations": jsonable(pipeline.scheduling)},
        "execution_simulation": jsonable(pipeline.execution),
        "production_recommendations": production_recommendations.to_dict(),
        "quantitative_water_balances": (
            WaterBalanceSnapshot.not_available().to_dict()
            if water_balances is None
            else water_balances.to_dict()
        ),
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
        self.record_count_loaded = 0
        self.deduplicated_count = 0
        self.shadow_log_bytes = 0
        self.last_error: str | None = None
        self.last_shadow_write_reason: ShadowEvaluationReason | None = None
        self.last_shadow_write_at: datetime | None = None
        self.last_shadow_fingerprint_changed: bool | None = None
        self._last_cleanup_date: date | None = None
        self._last_persisted_state: dict[str, Any] | None = None

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
            self._last_persisted_state = self._state_payload()

    async def async_consider(
        self,
        pipeline: PipelineEvaluation,
        *,
        production_recommendations: ProductionRecommendationSnapshot,
        water_balances: WaterBalanceSnapshot | None = None,
        completed_session_count: int,
        force_reason: ShadowEvaluationReason | None = None,
    ) -> ShadowEvaluationRecord | None:
        """Persist a full record only for nightly or semantically changed decisions."""
        section_hashes = self._pipeline_section_hashes(pipeline)
        reason = force_reason or self._reason_for_change(
            section_hashes, completed_session_count
        )
        fingerprint = _decision_hash(
            _decision_payload(pipeline, production_recommendations, water_balances)
        )
        fingerprint_changed = fingerprint != self.last_decision_fingerprint
        self.last_shadow_fingerprint_changed = fingerprint_changed
        should_write = (
            reason is ShadowEvaluationReason.NIGHTLY
            or fingerprint_changed
        )
        self._section_hashes = section_hashes
        self._completed_session_count = completed_session_count
        if not should_write:
            self.deduplicated_count += 1
            await self._async_persist_state()
            return None
        payload = self._build_payload(pipeline, production_recommendations, water_balances)
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
        bytes_written = await self._hass.async_add_executor_job(self._write_record, record)
        if bytes_written is not None:
            self.last_record = record
            self.last_decision_fingerprint = fingerprint
            self.record_count += 1
            self.shadow_log_bytes += bytes_written
            self.last_shadow_write_reason = reason
            self.last_shadow_write_at = now_utc
        await self._async_persist_state()
        return record if bytes_written is not None else None

    def _reason_for_change(
        self, sections: dict[str, str], completed_count: int
    ) -> ShadowEvaluationReason:
        if self.last_decision_fingerprint is None:
            return ShadowEvaluationReason.STARTUP_STALE_OR_MISSING
        if completed_count > self._completed_session_count:
            return ShadowEvaluationReason.WATERING_COMPLETED
        if sections["profile"] != self._section_hashes.get("profile"):
            return ShadowEvaluationReason.PROFILE_CHANGE
        if sections["confidence"] != self._section_hashes.get("confidence"):
            return ShadowEvaluationReason.CONFIDENCE_CHANGE
        if sections["scientific"] != self._section_hashes.get("scientific"):
            return ShadowEvaluationReason.SCIENTIFIC_INPUT_CHANGE
        if sections["observation"] != self._section_hashes.get("observation"):
            return ShadowEvaluationReason.OBSERVATION_CHANGE
        return ShadowEvaluationReason.DECISION_CHANGE

    @staticmethod
    def _pipeline_section_hashes(pipeline: PipelineEvaluation) -> dict[str, str]:
        return {
            "profile": _section_hash(pipeline.landscape_profile),
            "scientific": _section_hash(pipeline.scientific_inputs),
            "observation": _section_hash(pipeline.observation_snapshot),
            "confidence": _section_hash((pipeline.status, pipeline.stages)),
        }

    def _build_payload(
        self,
        pipeline: PipelineEvaluation,
        production_recommendations: ProductionRecommendationSnapshot,
        water_balances: WaterBalanceSnapshot | None = None,
    ) -> dict[str, Any]:
        return {
            "pipeline_status": pipeline.status.value,
            "current_stage": pipeline.current_stage.value,
            "stages": jsonable(pipeline.stages),
            "blockers": list(pipeline.blocker_codes),
            "scientific_inputs": jsonable(pipeline.scientific_inputs),
            "observation_snapshot": jsonable(pipeline.observation_snapshot),
            "landscape_profile": jsonable(pipeline.landscape_profile),
            **_decision_payload(pipeline, production_recommendations, water_balances),
        }

    def _write_record(self, record: ShadowEvaluationRecord) -> int | None:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            self._cleanup(record.timestamp_local.date())
            path = self._root / (
                f"irrigationos_shadow_{record.timestamp_local.date().isoformat()}.jsonl"
            )
            data = jsonable(record)
            line = _canonical(data) + "\n"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
            self.last_error = None
            return len(line.encode("utf-8"))
        except (OSError, TypeError, ValueError):
            self.last_error = "shadow_log_write_failed"
            return None

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
        log_bytes = 0
        try:
            for path in sorted(self._root.glob("irrigationos_shadow_????-??-??.jsonl")):
                log_bytes += path.stat().st_size
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
        self.record_count_loaded = len(records)
        self.shadow_log_bytes = log_bytes
        if records:
            latest = records[-1]
            try:
                self.last_shadow_write_reason = ShadowEvaluationReason(
                    str(latest.get("reason", ""))
                )
                timestamp = latest.get("timestamp_utc")
                if isinstance(timestamp, str):
                    self.last_shadow_write_at = datetime.fromisoformat(timestamp)
            except ValueError:
                pass
        return tuple(records)

    async def _async_persist_state(self) -> None:
        payload = self._state_payload()
        if payload == self._last_persisted_state:
            return
        try:
            await self._store.async_save(payload)
            self._last_persisted_state = payload
        except Exception:
            self.last_error = "shadow_store_save_failed"

    def _state_payload(self) -> dict[str, Any]:
        return {
            "last_decision_fingerprint": self.last_decision_fingerprint,
            "section_hashes": dict(self._section_hashes),
            "completed_session_count": self._completed_session_count,
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "record_count": self.record_count,
            "shadow_record_count_loaded": self.record_count_loaded,
            "deduplicated_count": self.deduplicated_count,
            "shadow_log_bytes": self.shadow_log_bytes,
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
            "last_shadow_write_reason": (
                None
                if self.last_shadow_write_reason is None
                else self.last_shadow_write_reason.value
            ),
            "last_shadow_write_at": (
                None
                if self.last_shadow_write_at is None
                else self.last_shadow_write_at.isoformat()
            ),
            "last_shadow_fingerprint_changed": self.last_shadow_fingerprint_changed,
            "retention_days": SHADOW_LOG_RETENTION_DAYS,
        }
