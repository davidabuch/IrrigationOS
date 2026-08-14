"""Structured terminal acceptance for one bounded unattended canary."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

UNATTENDED_CANARY_ACCEPTANCE_SCHEMA_VERSION = 1
UNATTENDED_CANARY_ACCEPTANCE_STORE_VERSION = 1


class UnattendedCanaryAcceptanceStatus(StrEnum):
    """Terminal acceptance state."""

    NOT_AVAILABLE = "not_available"
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class UnattendedCanaryCriterionStatus(StrEnum):
    """State of one explicit acceptance criterion."""

    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class UnattendedCanaryAcceptanceCriterion:
    """One immutable canary criterion."""

    code: str
    status: UnattendedCanaryCriterionStatus
    detail_code: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "status": self.status.value,
            "detail_code": self.detail_code,
        }


@dataclass(frozen=True, slots=True)
class UnattendedCanaryAcceptanceRecord:
    """Privacy-safe terminal evidence for one canary."""

    canary_id: str
    approval_id: str
    status: UnattendedCanaryAcceptanceStatus
    recorded_at: datetime
    controller_slot: int
    area_slot: int
    requested_runtime_seconds: int
    observed_watering_at: datetime | None
    observed_idle_at: datetime | None
    observed_runtime_seconds: int | None
    observation_precision: str
    refresh_error_count: int
    criteria: tuple[UnattendedCanaryAcceptanceCriterion, ...]
    terminal_detail_code: str
    schema_version: int = UNATTENDED_CANARY_ACCEPTANCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "canary_id": self.canary_id,
            "approval_id": self.approval_id,
            "status": self.status.value,
            "recorded_at": self.recorded_at.isoformat(),
            "controller_slot": self.controller_slot,
            "area_slot": self.area_slot,
            "requested_runtime_seconds": self.requested_runtime_seconds,
            "observed_watering_at": _iso_or_none(self.observed_watering_at),
            "observed_idle_at": _iso_or_none(self.observed_idle_at),
            "observed_runtime_seconds": self.observed_runtime_seconds,
            "observation_precision": self.observation_precision,
            "refresh_error_count": self.refresh_error_count,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "criteria_passed_count": sum(
                criterion.status is UnattendedCanaryCriterionStatus.PASS
                for criterion in self.criteria
            ),
            "criteria_total_count": len(self.criteria),
            "terminal_detail_code": self.terminal_detail_code,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: object) -> UnattendedCanaryAcceptanceRecord:
        if not isinstance(value, dict):
            raise ValueError("canary acceptance must be a mapping")
        raw_criteria = value.get("criteria")
        if not isinstance(raw_criteria, list):
            raise ValueError("canary criteria must be a list")
        criteria = tuple(
            UnattendedCanaryAcceptanceCriterion(
                code=str(item["code"]),
                status=UnattendedCanaryCriterionStatus(str(item["status"])),
                detail_code=str(item["detail_code"]),
            )
            for item in raw_criteria
            if isinstance(item, dict)
        )
        if len(criteria) != len(raw_criteria):
            raise ValueError("canary criteria contain invalid entries")
        return cls(
            canary_id=str(value["canary_id"]),
            approval_id=str(value["approval_id"]),
            status=UnattendedCanaryAcceptanceStatus(str(value["status"])),
            recorded_at=_parse_utc(value["recorded_at"]),
            controller_slot=int(value["controller_slot"]),
            area_slot=int(value["area_slot"]),
            requested_runtime_seconds=int(value["requested_runtime_seconds"]),
            observed_watering_at=_optional_utc(value.get("observed_watering_at")),
            observed_idle_at=_optional_utc(value.get("observed_idle_at")),
            observed_runtime_seconds=(
                None
                if value.get("observed_runtime_seconds") is None
                else int(value["observed_runtime_seconds"])
            ),
            observation_precision=str(value["observation_precision"]),
            refresh_error_count=int(value["refresh_error_count"]),
            criteria=criteria,
            terminal_detail_code=str(value["terminal_detail_code"]),
            schema_version=int(value.get("schema_version", 0)),
        )


def build_canary_acceptance_record(
    *,
    canary_id: str,
    approval_id: str,
    controller_slot: int,
    area_slot: int,
    requested_runtime_seconds: int,
    observed_watering_at: datetime | None,
    observed_idle_at: datetime | None,
    refresh_error_count: int,
    concurrent_watering_observed: bool,
    safety_preemption_observed: bool,
    terminal_detail_code: str,
    explicit_approval_recorded: bool = True,
    approval_matched_exact_target: bool = True,
    approval_matched_runtime: bool = True,
    production_readiness_passed: bool = True,
    command_intent_recorded: bool = True,
    approval_consumed: bool = True,
    target_preflight_observed: bool = True,
    start_acknowledged: bool = True,
    terminal_acceptance_audit_recorded: bool = True,
    audit_chain_complete: bool = True,
    recorded_at: datetime | None = None,
) -> UnattendedCanaryAcceptanceRecord:
    """Build a deterministic PASS, FAIL, or INDETERMINATE result."""

    completion_observed = observed_watering_at is not None and observed_idle_at is not None
    if completion_observed:
        watering_at = observed_watering_at
        idle_at = observed_idle_at
        assert watering_at is not None
        assert idle_at is not None
        observed_runtime_seconds = max(
            0,
            round((idle_at - watering_at).total_seconds()),
        )
    else:
        observed_runtime_seconds = None
    criteria = (
        _criterion("explicit_approval_recorded", explicit_approval_recorded),
        _criterion("approval_matched_exact_target", approval_matched_exact_target),
        _criterion("approval_matched_runtime", approval_matched_runtime),
        _criterion("production_readiness_passed", production_readiness_passed),
        _criterion("command_intent_recorded", command_intent_recorded),
        _criterion("approval_consumed", approval_consumed),
        _criterion("target_preflight_observed", target_preflight_observed),
        _criterion("start_acknowledged", start_acknowledged),
        _criterion("target_watering_observed", observed_watering_at is not None),
        _criterion(
            "runtime_within_canary_ceiling",
            15 <= requested_runtime_seconds <= 60,
        ),
        _criterion("target_returned_idle", completion_observed),
        _criterion("no_concurrent_watering_observed", not concurrent_watering_observed),
        _criterion("no_safety_preemption", not safety_preemption_observed),
        _criterion("post_run_reconciliation_passed", completion_observed),
        _criterion(
            "terminal_acceptance_audit_recorded",
            terminal_acceptance_audit_recorded,
        ),
        _criterion("audit_chain_complete", audit_chain_complete),
    )
    critical_codes = {
        "explicit_approval_recorded",
        "approval_matched_exact_target",
        "approval_matched_runtime",
        "production_readiness_passed",
        "command_intent_recorded",
        "approval_consumed",
        "target_preflight_observed",
        "start_acknowledged",
        "target_watering_observed",
        "runtime_within_canary_ceiling",
        "no_concurrent_watering_observed",
        "no_safety_preemption",
        "terminal_acceptance_audit_recorded",
        "audit_chain_complete",
    }
    if all(item.status is UnattendedCanaryCriterionStatus.PASS for item in criteria):
        status = UnattendedCanaryAcceptanceStatus.PASS
    elif any(
        item.code in critical_codes
        and item.status is UnattendedCanaryCriterionStatus.FAIL
        for item in criteria
    ):
        status = UnattendedCanaryAcceptanceStatus.FAIL
    else:
        status = UnattendedCanaryAcceptanceStatus.INDETERMINATE
    return UnattendedCanaryAcceptanceRecord(
        canary_id=canary_id,
        approval_id=approval_id,
        status=status,
        recorded_at=recorded_at or datetime.now(UTC),
        controller_slot=controller_slot,
        area_slot=area_slot,
        requested_runtime_seconds=requested_runtime_seconds,
        observed_watering_at=observed_watering_at,
        observed_idle_at=observed_idle_at,
        observed_runtime_seconds=observed_runtime_seconds,
        observation_precision="polling_bounded",
        refresh_error_count=refresh_error_count,
        criteria=criteria,
        terminal_detail_code=terminal_detail_code,
    )


class UnattendedCanaryAcceptanceSink(Protocol):
    async def async_record(self, record: UnattendedCanaryAcceptanceRecord) -> bool:
        """Persist one terminal record."""
        ...


class JsonlUnattendedCanaryAcceptanceSink:
    """Append terminal canary evidence to independent JSONL history."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def async_record(self, record: UnattendedCanaryAcceptanceRecord) -> bool:
        return await asyncio.to_thread(self._write, record)

    def _write(self, record: UnattendedCanaryAcceptanceRecord) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            return True
        except (OSError, TypeError, ValueError):
            return False


class UnattendedCanaryAcceptanceManager:
    """Persist only the latest terminal canary result through HA storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store[dict[str, Any]](
            hass,
            UNATTENDED_CANARY_ACCEPTANCE_STORE_VERSION,
            f"irrigationos.{entry_id}.unattended_canary_acceptance",
        )
        self.latest: UnattendedCanaryAcceptanceRecord | None = None
        self.last_persistence_error: str | None = None

    async def async_initialize(self) -> None:
        try:
            stored = await self._store.async_load()
        except Exception:
            self.last_persistence_error = "unattended_canary_acceptance_load_failed"
            return
        if stored is None:
            return
        try:
            self.latest = UnattendedCanaryAcceptanceRecord.from_dict(stored)
            self.last_persistence_error = None
        except (KeyError, TypeError, ValueError):
            self.latest = None
            self.last_persistence_error = "unattended_canary_acceptance_restore_failed"

    async def async_record(self, record: UnattendedCanaryAcceptanceRecord) -> bool:
        try:
            await self._store.async_save(record.to_dict())
        except Exception:
            self.latest = None
            self.last_persistence_error = "unattended_canary_acceptance_save_failed"
            return False
        self.latest = record
        self.last_persistence_error = None
        return True

    @property
    def status(self) -> UnattendedCanaryAcceptanceStatus:
        if self.latest is None:
            return UnattendedCanaryAcceptanceStatus.NOT_AVAILABLE
        return self.latest.status

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "latest": None if self.latest is None else self.latest.to_dict(),
            "last_persistence_error": self.last_persistence_error,
            "schema_version": UNATTENDED_CANARY_ACCEPTANCE_SCHEMA_VERSION,
        }


async def async_record_terminal_acceptance(
    record: UnattendedCanaryAcceptanceRecord,
    *,
    history: UnattendedCanaryAcceptanceSink,
    latest: UnattendedCanaryAcceptanceManager,
) -> tuple[bool, bool]:
    """Write append-only history and latest HA persistence independently."""

    return await history.async_record(record), await latest.async_record(record)


def _criterion(code: str, passed: bool) -> UnattendedCanaryAcceptanceCriterion:
    return UnattendedCanaryAcceptanceCriterion(
        code=code,
        status=(
            UnattendedCanaryCriterionStatus.PASS
            if passed
            else UnattendedCanaryCriterionStatus.FAIL
        ),
        detail_code=f"{code}_{'confirmed' if passed else 'not_confirmed'}",
    )


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _optional_utc(value: object) -> datetime | None:
    return None if value is None else _parse_utc(value)


def _iso_or_none(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()
