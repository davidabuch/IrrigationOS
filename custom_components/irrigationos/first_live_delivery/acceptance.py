"""Persistent structured acceptance evidence for supervised first-live trials."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

FIRST_LIVE_ACCEPTANCE_RECORD_SCHEMA_VERSION = 1
FIRST_LIVE_ACCEPTANCE_STORE_VERSION = 1


class FirstLiveAcceptanceStatus(StrEnum):
    """Overall acceptance outcome for one supervised physical trial."""

    NOT_AVAILABLE = "not_available"
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class FirstLiveCriterionStatus(StrEnum):
    """Outcome for one deterministic acceptance criterion."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class FirstLiveAcceptanceCriterion:
    """One explicit criterion and its evidence state."""

    code: str
    status: FirstLiveCriterionStatus
    detail_code: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "status": self.status.value,
            "detail_code": self.detail_code,
        }


@dataclass(frozen=True, slots=True)
class FirstLiveAcceptanceRecord:
    """Privacy-safe structured terminal evidence for one supervised trial."""

    attempt_id: str
    status: FirstLiveAcceptanceStatus
    recorded_at: datetime
    controller_slot: int
    area_slot: int
    requested_runtime_seconds: int
    observed_watering_at: datetime | None
    observed_idle_at: datetime | None
    observed_runtime_seconds: int | None
    observation_precision: str
    refresh_error_count: int
    criteria: tuple[FirstLiveAcceptanceCriterion, ...]
    terminal_detail_code: str
    schema_version: int = FIRST_LIVE_ACCEPTANCE_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe persistence and entity data."""

        return {
            "attempt_id": self.attempt_id,
            "status": self.status.value,
            "recorded_at": self.recorded_at.isoformat(),
            "controller_slot": self.controller_slot,
            "area_slot": self.area_slot,
            "requested_runtime_seconds": self.requested_runtime_seconds,
            "observed_watering_at": (
                None if self.observed_watering_at is None else self.observed_watering_at.isoformat()
            ),
            "observed_idle_at": (
                None if self.observed_idle_at is None else self.observed_idle_at.isoformat()
            ),
            "observed_runtime_seconds": self.observed_runtime_seconds,
            "observation_precision": self.observation_precision,
            "refresh_error_count": self.refresh_error_count,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "criteria_passed_count": sum(
                criterion.status is FirstLiveCriterionStatus.PASS
                for criterion in self.criteria
            ),
            "criteria_total_count": len(self.criteria),
            "terminal_detail_code": self.terminal_detail_code,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: object) -> FirstLiveAcceptanceRecord:
        """Restore one validated record from Home Assistant storage."""

        if not isinstance(value, dict):
            raise ValueError("acceptance record must be a mapping")
        raw_criteria = value.get("criteria")
        if not isinstance(raw_criteria, list):
            raise ValueError("acceptance criteria must be a list")
        criteria = tuple(
            FirstLiveAcceptanceCriterion(
                code=str(item["code"]),
                status=FirstLiveCriterionStatus(str(item["status"])),
                detail_code=str(item["detail_code"]),
            )
            for item in raw_criteria
            if isinstance(item, dict)
        )
        if len(criteria) != len(raw_criteria):
            raise ValueError("acceptance criteria contain invalid entries")
        return cls(
            attempt_id=str(value["attempt_id"]),
            status=FirstLiveAcceptanceStatus(str(value["status"])),
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


class FirstLiveAcceptanceManager:
    """Persist and expose the latest structured supervised-trial result."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store[dict[str, Any]](
            hass,
            FIRST_LIVE_ACCEPTANCE_STORE_VERSION,
            f"irrigationos.{entry_id}.first_live_acceptance",
        )
        self.latest: FirstLiveAcceptanceRecord | None = None
        self.last_persistence_error: str | None = None

    async def async_initialize(self) -> None:
        """Restore the latest accepted structured record after restart."""

        try:
            stored = await self._store.async_load()
        except Exception:
            self.last_persistence_error = "acceptance_record_load_failed"
            return
        if stored is None:
            return
        try:
            self.latest = FirstLiveAcceptanceRecord.from_dict(stored)
            self.last_persistence_error = None
        except (KeyError, TypeError, ValueError):
            self.latest = None
            self.last_persistence_error = "acceptance_record_restore_failed"

    async def async_record(self, record: FirstLiveAcceptanceRecord) -> bool:
        """Persist one terminal record before exposing it as current state."""

        try:
            await self._store.async_save(record.to_dict())
        except Exception:
            self.latest = None
            self.last_persistence_error = "acceptance_record_save_failed"
            return False
        self.latest = record
        self.last_persistence_error = None
        return True

    @property
    def status(self) -> FirstLiveAcceptanceStatus:
        """Return the latest structured acceptance status."""

        if self.latest is None:
            return FirstLiveAcceptanceStatus.NOT_AVAILABLE
        return self.latest.status

    def diagnostics(self) -> dict[str, Any]:
        """Return privacy-safe latest acceptance evidence."""

        return {
            "status": self.status.value,
            "latest": None if self.latest is None else self.latest.to_dict(),
            "last_persistence_error": self.last_persistence_error,
            "schema_version": FIRST_LIVE_ACCEPTANCE_RECORD_SCHEMA_VERSION,
        }


def build_acceptance_record(
    *,
    attempt_id: str,
    controller_slot: int,
    area_slot: int,
    requested_runtime_seconds: int,
    observed_watering_at: datetime | None,
    observed_idle_at: datetime | None,
    refresh_error_count: int,
    concurrent_watering_observed: bool,
    terminal_detail_code: str,
    dispatch_intent_recorded: bool = True,
    operator_approval_recorded: bool = True,
    preflight_target_observed: bool = True,
    start_acknowledged: bool = True,
    terminal_audit_recorded: bool = True,
) -> FirstLiveAcceptanceRecord:
    """Build a deterministic PASS/FAIL/INDETERMINATE terminal record."""

    if observed_watering_at is not None and observed_idle_at is not None:
        completion_observed = True
        watering_at = observed_watering_at
        idle_at = observed_idle_at
        assert watering_at is not None
        assert idle_at is not None
        observed_runtime_seconds = max(
            0, round((idle_at - watering_at).total_seconds())
        )
    else:
        completion_observed = False
        observed_runtime_seconds = None
    criteria = (
        _criterion("command_intent_recorded", dispatch_intent_recorded),
        _criterion("operator_approval_recorded", operator_approval_recorded),
        _criterion("preflight_target_observed", preflight_target_observed),
        _criterion("start_acknowledged", start_acknowledged),
        _criterion("target_watering_observed", observed_watering_at is not None),
        _criterion("requested_runtime_within_ceiling", 1 <= requested_runtime_seconds <= 120),
        _criterion("target_returned_idle", completion_observed),
        _criterion("no_concurrent_watering_observed", not concurrent_watering_observed),
        _criterion("post_run_reconciliation_passed", completion_observed),
        _criterion("terminal_acceptance_audit_recorded", terminal_audit_recorded),
    )
    if all(item.status is FirstLiveCriterionStatus.PASS for item in criteria):
        status = FirstLiveAcceptanceStatus.PASS
    elif any(
        item.status is FirstLiveCriterionStatus.FAIL
        for item in criteria
        if item.code in {
            "command_intent_recorded",
            "operator_approval_recorded",
            "preflight_target_observed",
            "start_acknowledged",
            "target_watering_observed",
            "requested_runtime_within_ceiling",
            "no_concurrent_watering_observed",
            "terminal_acceptance_audit_recorded",
        }
    ):
        status = FirstLiveAcceptanceStatus.FAIL
    else:
        status = FirstLiveAcceptanceStatus.INDETERMINATE

    return FirstLiveAcceptanceRecord(
        attempt_id=attempt_id,
        status=status,
        recorded_at=datetime.now(UTC),
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


def _criterion(code: str, passed: bool) -> FirstLiveAcceptanceCriterion:
    return FirstLiveAcceptanceCriterion(
        code=code,
        status=(FirstLiveCriterionStatus.PASS if passed else FirstLiveCriterionStatus.FAIL),
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
