"""Immutable contracts for the fail-closed production-readiness gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

PRODUCTION_READINESS_SCHEMA_VERSION = 2
PRODUCTION_READINESS_POLICY_VERSION = 2


class ProductionReadinessState(StrEnum):
    """Advisory readiness states that grant no actuation authority."""

    NOT_READY = "not_ready"
    READY_FOR_SUPERVISED_PRODUCTION = "ready_for_supervised_production"
    READY_FOR_UNATTENDED_CANARY = "ready_for_unattended_canary"


@dataclass(frozen=True, slots=True, order=True)
class ProductionTarget:
    """One privacy-safe canonical configured irrigation target."""

    controller_slot: int
    area_slot: int

    def __post_init__(self) -> None:
        if self.controller_slot < 1 or self.area_slot < 1:
            raise ValueError("production target slots must be positive")

    def to_dict(self) -> dict[str, int]:
        return {
            "controller_slot": self.controller_slot,
            "area_slot": self.area_slot,
        }


@dataclass(frozen=True, slots=True)
class ProductionReadinessInputs:
    """Complete deterministic evidence consumed by the readiness engine."""

    evaluated_at: datetime
    health_state: str
    observation_age_seconds: int | None
    cloud_connection_healthy: bool
    realtime_observation_healthy: bool
    ownership_confirmed: bool
    boundary_review_acknowledged: bool
    topology_matches: bool
    ownership_persistence_healthy: bool
    production_targets: tuple[ProductionTarget, ...]
    validated_targets: tuple[ProductionTarget, ...]
    validated_target_persistence_healthy: bool
    first_live_persistence_healthy: bool
    supervised_operation_persistence_healthy: bool
    aggregate_persistence_healthy: bool
    operational_log_healthy: bool
    active_external_watering_count: int
    supervised_operation_in_progress: bool
    safety_prerequisites_met: bool
    unattended_canary_approval_present: bool = False
    unattended_canary_in_progress: bool = False
    unattended_canary_persistence_healthy: bool = True

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if self.observation_age_seconds is not None and self.observation_age_seconds < 0:
            raise ValueError("observation age must not be negative")
        if self.active_external_watering_count < 0:
            raise ValueError("active watering count must not be negative")


@dataclass(frozen=True, slots=True)
class ProductionReadinessSummary:
    """Privacy-safe advisory result; never controller authorization."""

    state: ProductionReadinessState
    evaluated_at: datetime
    blocker_codes: tuple[str, ...]
    unattended_canary_blocker_codes: tuple[str, ...]
    production_targets: tuple[ProductionTarget, ...]
    validated_targets: tuple[ProductionTarget, ...]
    health_state: str
    observation_age_seconds: int | None
    active_external_watering_count: int
    supervised_operation_in_progress: bool
    unattended_canary_in_progress: bool
    ownership_confirmed: bool
    topology_matches: bool
    persistence_health: dict[str, bool]
    policy_version: int = PRODUCTION_READINESS_POLICY_VERSION
    schema_version: int = PRODUCTION_READINESS_SCHEMA_VERSION
    live_control_authorized: bool = False

    @property
    def production_target_count(self) -> int:
        return len(self.production_targets)

    @property
    def validated_production_target_count(self) -> int:
        validated = set(self.validated_targets)
        return sum(target in validated for target in self.production_targets)

    @property
    def production_ready(self) -> bool:
        return self.state is not ProductionReadinessState.NOT_READY

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["evaluated_at"] = self.evaluated_at.isoformat()
        payload["blocker_codes"] = list(self.blocker_codes)
        payload["unattended_canary_blocker_codes"] = list(
            self.unattended_canary_blocker_codes
        )
        payload["production_targets"] = [
            target.to_dict() for target in self.production_targets
        ]
        payload["validated_targets"] = [
            target.to_dict() for target in self.validated_targets
        ]
        payload["production_target_count"] = self.production_target_count
        payload["validated_production_target_count"] = (
            self.validated_production_target_count
        )
        return payload
