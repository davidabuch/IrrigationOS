"""Durable privacy-safe registry of first-live validated canonical targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .acceptance import FirstLiveAcceptanceRecord, FirstLiveAcceptanceStatus

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

VALIDATED_TARGET_REGISTRY_SCHEMA_VERSION = 1
VALIDATED_TARGET_STORE_VERSION = 1


@dataclass(frozen=True, slots=True)
class ValidatedTargetRecord:
    """Durable evidence that one canonical target passed first-live validation."""

    controller_slot: int
    area_slot: int
    validated_at: datetime
    source_attempt_id: str
    requested_runtime_seconds: int
    observed_runtime_seconds: int | None
    acceptance_status: FirstLiveAcceptanceStatus
    acceptance_schema_version: int
    registry_schema_version: int = VALIDATED_TARGET_REGISTRY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.controller_slot < 1 or self.area_slot < 1:
            raise ValueError("validated target slots must be positive")
        if self.validated_at.tzinfo is None or self.validated_at.utcoffset() is None:
            raise ValueError("validated_at must be timezone-aware")
        if re.fullmatch(r"first_live_[a-z0-9_]+", self.source_attempt_id) is None:
            raise ValueError("source_attempt_id must be a privacy-safe first-live ID")
        if not 1 <= self.requested_runtime_seconds <= 120:
            raise ValueError("requested runtime must be between 1 and 120 seconds")
        if self.observed_runtime_seconds is not None and self.observed_runtime_seconds < 0:
            raise ValueError("observed runtime must not be negative")
        if self.acceptance_status is not FirstLiveAcceptanceStatus.PASS:
            raise ValueError("only PASS acceptance may validate a target")
        if self.acceptance_schema_version < 1 or self.registry_schema_version != 1:
            raise ValueError("validated target schema version is unsupported")

    @property
    def key(self) -> tuple[int, int]:
        """Return stable canonical registry identity."""

        return self.controller_slot, self.area_slot

    def to_dict(self) -> dict[str, object]:
        """Return deterministic privacy-safe persistence data."""

        return {
            "controller_slot": self.controller_slot,
            "area_slot": self.area_slot,
            "validated_at": self.validated_at.astimezone(UTC).isoformat(),
            "source_attempt_id": self.source_attempt_id,
            "requested_runtime_seconds": self.requested_runtime_seconds,
            "observed_runtime_seconds": self.observed_runtime_seconds,
            "acceptance_status": self.acceptance_status.value,
            "acceptance_schema_version": self.acceptance_schema_version,
            "registry_schema_version": self.registry_schema_version,
        }

    @classmethod
    def from_dict(cls, value: object) -> ValidatedTargetRecord:
        """Restore one validated canonical target record."""

        if not isinstance(value, dict):
            raise ValueError("validated target must be a mapping")
        validated_at = datetime.fromisoformat(str(value["validated_at"]))
        return cls(
            controller_slot=int(value["controller_slot"]),
            area_slot=int(value["area_slot"]),
            validated_at=validated_at,
            source_attempt_id=str(value["source_attempt_id"]),
            requested_runtime_seconds=int(value["requested_runtime_seconds"]),
            observed_runtime_seconds=(
                None
                if value.get("observed_runtime_seconds") is None
                else int(value["observed_runtime_seconds"])
            ),
            acceptance_status=FirstLiveAcceptanceStatus(
                str(value["acceptance_status"])
            ),
            acceptance_schema_version=int(value["acceptance_schema_version"]),
            registry_schema_version=int(value["registry_schema_version"]),
        )

    @classmethod
    def from_acceptance(cls, record: FirstLiveAcceptanceRecord) -> ValidatedTargetRecord:
        """Create canonical registry evidence from an exact PASS record."""

        if record.status is not FirstLiveAcceptanceStatus.PASS:
            raise ValueError("only PASS acceptance may validate a target")
        return cls(
            controller_slot=record.controller_slot,
            area_slot=record.area_slot,
            validated_at=record.recorded_at,
            source_attempt_id=record.attempt_id,
            requested_runtime_seconds=record.requested_runtime_seconds,
            observed_runtime_seconds=record.observed_runtime_seconds,
            acceptance_status=record.status,
            acceptance_schema_version=record.schema_version,
        )


class ValidatedTargetRegistry:
    """Persist exact canonical targets that passed first-live commissioning."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store[dict[str, Any]](
            hass,
            VALIDATED_TARGET_STORE_VERSION,
            f"irrigationos.{entry_id}.validated_targets",
        )
        self._targets: tuple[ValidatedTargetRecord, ...] = ()
        self._migration_completed = False
        self.last_persistence_error: str | None = None

    @property
    def targets(self) -> tuple[ValidatedTargetRecord, ...]:
        """Return deterministically ordered immutable registry contents."""

        return self._targets

    def contains(self, controller_slot: int, area_slot: int) -> bool:
        """Return whether this exact canonical target is durably validated."""

        return any(
            target.key == (controller_slot, area_slot) for target in self._targets
        )

    async def async_initialize(
        self, latest_first_live: FirstLiveAcceptanceRecord | None
    ) -> None:
        """Restore registry and perform one idempotent v1.0.40 PASS backfill."""

        try:
            stored = await self._store.async_load()
        except Exception:
            self.last_persistence_error = "validated_target_registry_load_failed"
            return
        if stored is not None:
            try:
                self._restore(stored)
            except (KeyError, TypeError, ValueError):
                self._targets = ()
                self.last_persistence_error = "validated_target_registry_restore_failed"
                return
        if self._migration_completed:
            self.last_persistence_error = None
            return

        targets = self._targets
        if (
            not targets
            and latest_first_live is not None
            and latest_first_live.status is FirstLiveAcceptanceStatus.PASS
        ):
            targets = (ValidatedTargetRecord.from_acceptance(latest_first_live),)
        await self._async_save(targets, migration_completed=True)

    async def async_register(self, acceptance: FirstLiveAcceptanceRecord) -> bool:
        """Durably add or refresh one exact PASS target before exposing eligibility."""

        if acceptance.status is not FirstLiveAcceptanceStatus.PASS:
            return False
        candidate = ValidatedTargetRecord.from_acceptance(acceptance)
        by_key = {target.key: target for target in self._targets}
        by_key[candidate.key] = candidate
        targets = tuple(by_key[key] for key in sorted(by_key))
        return await self._async_save(targets, migration_completed=True)

    async def async_revoke(self, controller_slot: int, area_slot: int) -> bool:
        """Durably revoke one canonical target without affecting other targets."""

        targets = tuple(
            target
            for target in self._targets
            if target.key != (controller_slot, area_slot)
        )
        if targets == self._targets:
            return True
        return await self._async_save(targets, migration_completed=True)

    def diagnostics(self) -> dict[str, object]:
        """Return provider-ID-free registry state."""

        return {
            "validated_target_count": len(self._targets),
            "validated_targets": [target.to_dict() for target in self._targets],
            "schema_version": VALIDATED_TARGET_REGISTRY_SCHEMA_VERSION,
            "last_persistence_error": self.last_persistence_error,
        }

    async def _async_save(
        self,
        targets: tuple[ValidatedTargetRecord, ...],
        *,
        migration_completed: bool,
    ) -> bool:
        payload = {
            "schema_version": VALIDATED_TARGET_REGISTRY_SCHEMA_VERSION,
            "migration_completed": migration_completed,
            "targets": [target.to_dict() for target in targets],
        }
        try:
            await self._store.async_save(payload)
        except Exception:
            self.last_persistence_error = "validated_target_registry_save_failed"
            return False
        self._targets = targets
        self._migration_completed = migration_completed
        self.last_persistence_error = None
        return True

    def _restore(self, stored: dict[str, Any]) -> None:
        if int(stored["schema_version"]) != VALIDATED_TARGET_REGISTRY_SCHEMA_VERSION:
            raise ValueError("validated target registry schema is unsupported")
        raw_targets = stored["targets"]
        if not isinstance(raw_targets, list):
            raise ValueError("validated targets must be a list")
        targets = tuple(ValidatedTargetRecord.from_dict(item) for item in raw_targets)
        ordered = tuple(sorted(targets, key=lambda target: target.key))
        if len({target.key for target in targets}) != len(targets) or targets != ordered:
            raise ValueError("validated targets must be unique and ordered")
        migration_completed = stored.get("migration_completed")
        if not isinstance(migration_completed, bool):
            raise ValueError("migration marker must be boolean")
        self._targets = targets
        self._migration_completed = migration_completed
        self.last_persistence_error = None
