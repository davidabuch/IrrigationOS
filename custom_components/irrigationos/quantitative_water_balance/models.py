"""Immutable quantitative water-balance and forecast-reconciliation contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from ..production_targets import ProductionTarget

WATER_BALANCE_SCHEMA_VERSION = 2
WATER_BALANCE_POLICY_VERSION = "2.0.0"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class WaterBalanceState(StrEnum):
    """Availability of a quantitative actual-water calculation."""

    NOT_AVAILABLE = "not_available"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AVAILABLE = "available"


class ForecastReconciliationState(StrEnum):
    """Relationship between provisional forecast cover and observed rain."""

    NO_FORECAST_ADJUSTMENT = "no_forecast_adjustment"
    FORECAST_PENDING = "forecast_pending"
    DEFERRED_FOR_FORECAST = "deferred_for_forecast"
    FORECAST_REALIZED = "forecast_realized"
    FORECAST_PARTIALLY_REALIZED = "forecast_partially_realized"
    FORECAST_NOT_REALIZED = "forecast_not_realized"
    RECONCILIATION_INCOMPLETE = "reconciliation_incomplete"


class WaterBalanceLedgerEventKind(StrEnum):
    """Immutable decision evidence retained across restart."""

    FORECAST_DEFERRAL = "forecast_deferral"
    FORECAST_RECONCILIATION = "forecast_reconciliation"


class WaterBalanceEvidenceKind(StrEnum):
    """Provider-neutral evidence categories used by the balance."""

    REFERENCE_ET = "reference_et"
    PLANT_FACTOR = "plant_factor"
    OBSERVED_PRECIPITATION = "observed_precipitation"
    OBSERVED_IRRIGATION = "observed_irrigation"
    FORECAST_PRECIPITATION = "forecast_precipitation"
    FORECAST_LEDGER = "forecast_ledger"
    EFFECTIVE_PRECIPITATION_POLICY = "effective_precipitation_policy"
    ROOT_ZONE_POLICY = "root_zone_policy"


class OpeningBalanceState(StrEnum):
    """Truthful provenance of the opening deficit for one window."""

    UNKNOWN = "unknown"
    RECONSTRUCTED = "reconstructed"
    DURABLE_CARRY_FORWARD = "durable_carry_forward"
    INVALIDATED_BY_UNQUANTIFIED_IRRIGATION = "invalidated_by_unquantified_irrigation"


class AccountingIntervalState(StrEnum):
    """Whether an exact new scientific interval can be consumed."""

    COMPLETE = "complete"
    NO_NEW_EVIDENCE = "no_new_evidence"
    GAP = "gap"
    OVERLAP = "overlap"
    REPLAY = "replay"


class DemandFactorSource(StrEnum):
    """Precedence-selected source of landscape demand evidence."""

    UNRESOLVED = "unresolved"
    CURATED_PLANT_KNOWLEDGE = "curated_plant_knowledge"
    GENERIC_LANDSCAPE_CLASS = "generic_landscape_class"


class IrrigationTriggerState(StrEnum):
    """Relationship of current deficit to the allowable-depletion threshold."""

    UNAVAILABLE = "unavailable"
    BELOW_TRIGGER = "below_trigger"
    AT_OR_ABOVE_TRIGGER = "at_or_above_trigger"
    UNCERTAIN_RANGE = "uncertain_range"


@dataclass(frozen=True, slots=True)
class WaterQuantity:
    """A millimetre scalar or closed range that preserves uncertainty."""

    scalar: float | None = None
    minimum: float | None = None
    typical: float | None = None
    maximum: float | None = None
    unit: str = "mm"

    def __post_init__(self) -> None:
        if self.unit != "mm":
            raise ValueError("water quantities must use millimetres")
        values = (self.scalar, self.minimum, self.typical, self.maximum)
        if any(value is not None and not _nonnegative(value) for value in values):
            raise ValueError("water quantity values must be finite and non-negative")
        range_present = self.minimum is not None or self.maximum is not None
        if (self.scalar is None) == (not range_present):
            raise ValueError("water quantity requires exactly one scalar or range")
        if range_present:
            if self.minimum is None or self.maximum is None:
                raise ValueError("water quantity ranges require minimum and maximum")
            if self.minimum > self.maximum:
                raise ValueError("water quantity minimum cannot exceed maximum")
            if self.typical is not None and not self.minimum <= self.typical <= self.maximum:
                raise ValueError("water quantity typical must be inside the range")
        elif self.typical is not None:
            raise ValueError("scalar water quantities cannot have a typical value")

    @classmethod
    def millimeters(cls, value: float) -> WaterQuantity:
        """Construct a scalar millimetre quantity."""

        return cls(scalar=value)


@dataclass(frozen=True, slots=True)
class RatioQuantity:
    """A scalar or closed ratio range, used for plant factor."""

    scalar: float | None = None
    minimum: float | None = None
    typical: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        values = (self.scalar, self.minimum, self.typical, self.maximum)
        if any(value is not None and not _bounded(value, 0, 2) for value in values):
            raise ValueError("ratio values must be finite and between zero and two")
        range_present = self.minimum is not None or self.maximum is not None
        if (self.scalar is None) == (not range_present):
            raise ValueError("ratio requires exactly one scalar or range")
        if range_present:
            if self.minimum is None or self.maximum is None:
                raise ValueError("ratio ranges require minimum and maximum")
            if self.minimum > self.maximum:
                raise ValueError("ratio minimum cannot exceed maximum")
            if self.typical is not None and not self.minimum <= self.typical <= self.maximum:
                raise ValueError("ratio typical must be inside the range")
        elif self.typical is not None:
            raise ValueError("scalar ratios cannot have a typical value")


@dataclass(frozen=True, slots=True)
class EffectivePrecipitationPolicy:
    """Explicit admitted fraction; never inferred from unknown site properties."""

    policy_id: str
    effective_fraction: float
    confidence: float
    rationale_code: str

    def __post_init__(self) -> None:
        _identifier("policy_id", self.policy_id)
        _fraction("effective_fraction", self.effective_fraction)
        _fraction("confidence", self.confidence)
        _code("rationale_code", self.rationale_code)


@dataclass(frozen=True, slots=True)
class ForecastAdjustmentPolicy:
    """Conservative, versioned admission policy for forecast deferral."""

    minimum_effective_precipitation_mm: float = 5.0
    maximum_horizon_hours: int = 48
    maximum_deficit_cover_fraction: float = 0.8
    minimum_source_confidence: float = 0.6
    maximum_forecast_age_hours: int = 6
    policy_version: str = WATER_BALANCE_POLICY_VERSION

    def __post_init__(self) -> None:
        if not _nonnegative(self.minimum_effective_precipitation_mm):
            raise ValueError("minimum forecast precipitation must be non-negative")
        if self.maximum_horizon_hours < 1 or self.maximum_forecast_age_hours < 1:
            raise ValueError("forecast hour limits must be positive")
        _fraction("maximum_deficit_cover_fraction", self.maximum_deficit_cover_fraction)
        _fraction("minimum_source_confidence", self.minimum_source_confidence)
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.policy_version):
            raise ValueError("policy_version must use MAJOR.MINOR.PATCH")


@dataclass(frozen=True, slots=True)
class ForecastPrecipitationEvidence:
    """One bounded future precipitation estimate; probability may be unavailable."""

    forecast_id: str
    issued_at: datetime
    window_start: datetime
    window_end: datetime
    precipitation_mm: WaterQuantity
    probability_percent: float | None
    confidence: float
    quality: str
    source: str

    def __post_init__(self) -> None:
        _identifier("forecast_id", self.forecast_id)
        for name, value in (
            ("issued_at", self.issued_at),
            ("window_start", self.window_start),
            ("window_end", self.window_end),
        ):
            _aware(name, value)
        if self.window_end <= self.window_start or self.issued_at > self.window_end:
            raise ValueError("forecast timestamps are inconsistent")
        if self.probability_percent is not None and not _bounded(self.probability_percent, 0, 100):
            raise ValueError("forecast probability must be between zero and 100")
        _fraction("confidence", self.confidence)
        if not self.quality.strip() or not self.source.strip():
            raise ValueError("forecast quality and source must not be blank")


@dataclass(frozen=True, slots=True)
class WaterBalanceEvidence:
    """Privacy-safe provenance retained in a result."""

    evidence_id: str
    kind: WaterBalanceEvidenceKind
    source: str
    observed_at: datetime
    confidence: float
    quality: str

    def __post_init__(self) -> None:
        _identifier("evidence_id", self.evidence_id)
        if not isinstance(self.kind, WaterBalanceEvidenceKind):
            raise ValueError("evidence kind must be canonical")
        if not self.source.strip() or not self.quality.strip():
            raise ValueError("evidence source and quality must not be blank")
        _aware("observed_at", self.observed_at)
        _fraction("confidence", self.confidence)


@dataclass(frozen=True, slots=True)
class WaterBalanceLedgerEvent:
    """Immutable deferral/reconciliation fact; never execution authority."""

    event_id: str
    kind: WaterBalanceLedgerEventKind
    target: ProductionTarget
    recorded_at: datetime
    accounted_through: datetime
    carry_forward_deficit_mm: WaterQuantity
    window_start: datetime | None = None
    forecast_id: str | None = None
    forecast_window_start: datetime | None = None
    forecast_window_end: datetime | None = None
    deferred_deficit_mm: WaterQuantity | None = None
    realized_effective_precipitation_mm: WaterQuantity | None = None
    schema_version: int = WATER_BALANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("event_id", self.event_id)
        if not isinstance(self.kind, WaterBalanceLedgerEventKind):
            raise ValueError("ledger event kind must be canonical")
        for name, value in (
            ("recorded_at", self.recorded_at),
            ("accounted_through", self.accounted_through),
        ):
            _aware(name, value)
        if self.accounted_through > self.recorded_at:
            raise ValueError("accounted_through cannot follow recorded_at")
        if self.window_start is not None:
            _aware("window_start", self.window_start)
            if self.accounted_through <= self.window_start:
                raise ValueError("ledger accounting window must advance")
        if self.forecast_id is None:
            raise ValueError("forecast ledger events require forecast_id")
        _identifier("forecast_id", self.forecast_id)
        if self.forecast_window_start is None or self.forecast_window_end is None:
            raise ValueError("forecast ledger events require a forecast window")
        _aware("forecast_window_start", self.forecast_window_start)
        _aware("forecast_window_end", self.forecast_window_end)
        if self.forecast_window_end <= self.forecast_window_start:
            raise ValueError("ledger forecast window is invalid")
        if self.deferred_deficit_mm is None:
            raise ValueError("forecast ledger events require deferred deficit")
        if self.kind is WaterBalanceLedgerEventKind.FORECAST_DEFERRAL:
            if self.realized_effective_precipitation_mm is not None:
                raise ValueError("deferral events cannot contain realized precipitation")
        elif self.kind is WaterBalanceLedgerEventKind.FORECAST_RECONCILIATION and (
            self.realized_effective_precipitation_mm is None
        ):
            raise ValueError("reconciliation requires realized and carry-forward water")
        if self.schema_version != WATER_BALANCE_SCHEMA_VERSION:
            raise ValueError("unsupported water-balance ledger schema")

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, value: object) -> WaterBalanceLedgerEvent:
        """Restore one strictly validated ledger event."""

        if not isinstance(value, dict):
            raise ValueError("ledger event must be a mapping")
        target = value.get("target")
        if not isinstance(target, dict):
            raise ValueError("ledger target must be a mapping")
        source_schema = int(value.get("schema_version", 0))
        if source_schema not in {1, WATER_BALANCE_SCHEMA_VERSION}:
            raise ValueError("unsupported water-balance ledger schema")
        realized = value.get("realized_effective_precipitation_mm")
        carry_forward = value.get("carry_forward_deficit_mm")
        if carry_forward is None:
            raise ValueError("ledger event requires carry-forward deficit")
        window_start = value.get("window_start")
        forecast_start = value.get("forecast_window_start")
        forecast_end = value.get("forecast_window_end")
        return cls(
            event_id=str(value.get("event_id", "")),
            kind=WaterBalanceLedgerEventKind(str(value.get("kind", ""))),
            target=ProductionTarget(int(target["controller_slot"]), int(target["area_slot"])),
            recorded_at=_parse_time(value.get("recorded_at")),
            accounted_through=_parse_time(value.get("accounted_through")),
            carry_forward_deficit_mm=_water_quantity(carry_forward),
            window_start=None if window_start is None else _parse_time(window_start),
            forecast_id=(
                None if value.get("forecast_id") is None else str(value.get("forecast_id"))
            ),
            forecast_window_start=(None if forecast_start is None else _parse_time(forecast_start)),
            forecast_window_end=(None if forecast_end is None else _parse_time(forecast_end)),
            deferred_deficit_mm=(
                None
                if value.get("deferred_deficit_mm") is None
                else _water_quantity(value.get("deferred_deficit_mm"))
            ),
            realized_effective_precipitation_mm=(
                None if realized is None else _water_quantity(realized)
            ),
            schema_version=WATER_BALANCE_SCHEMA_VERSION,
        )


@dataclass(frozen=True, slots=True)
class WaterBalanceTargetState:
    """Latest bounded scientific carry state for one production target."""

    target: ProductionTarget
    state: OpeningBalanceState
    window_start: datetime
    accounted_through: datetime
    recorded_at: datetime
    deficit_mm: WaterQuantity | None = None
    invalidated_session_ids: tuple[str, ...] = ()
    reason_code: str = "opening_balance_unknown"
    schema_version: int = WATER_BALANCE_SCHEMA_VERSION
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("window_start", self.window_start),
            ("accounted_through", self.accounted_through),
            ("recorded_at", self.recorded_at),
        ):
            _aware(name, value)
        if self.accounted_through <= self.window_start:
            raise ValueError("target-state accounting window must advance")
        if self.accounted_through > self.recorded_at:
            raise ValueError("target-state boundary cannot follow recorded_at")
        _sorted_ids("invalidated_session_ids", self.invalidated_session_ids)
        _code("reason_code", self.reason_code)
        numeric = self.state in {
            OpeningBalanceState.RECONSTRUCTED,
            OpeningBalanceState.DURABLE_CARRY_FORWARD,
        }
        if numeric != (self.deficit_mm is not None):
            raise ValueError("only numeric target states may carry a deficit")
        invalidated = self.state is OpeningBalanceState.INVALIDATED_BY_UNQUANTIFIED_IRRIGATION
        if invalidated != bool(self.invalidated_session_ids):
            raise ValueError("invalidation state requires exact session evidence")
        if self.schema_version != WATER_BALANCE_SCHEMA_VERSION or self.execution_authorized:
            raise ValueError("invalid water-balance target state")

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, value: object) -> WaterBalanceTargetState:
        if not isinstance(value, dict) or not isinstance(value.get("target"), dict):
            raise ValueError("target state must contain a target mapping")
        target = value["target"]
        invalidated = value.get("invalidated_session_ids", [])
        if not isinstance(invalidated, list):
            raise ValueError("invalidated session IDs must be a list")
        deficit = value.get("deficit_mm")
        return cls(
            target=ProductionTarget(int(target["controller_slot"]), int(target["area_slot"])),
            state=OpeningBalanceState(str(value.get("state", ""))),
            window_start=_parse_time(value.get("window_start")),
            accounted_through=_parse_time(value.get("accounted_through")),
            recorded_at=_parse_time(value.get("recorded_at")),
            deficit_mm=None if deficit is None else _water_quantity(deficit),
            invalidated_session_ids=tuple(str(item) for item in invalidated),
            reason_code=str(value.get("reason_code", "")),
        )


@dataclass(frozen=True, slots=True)
class ProductionAreaWaterBalanceRequest:
    """Complete explicit evidence for one deterministic evaluation."""

    target: ProductionTarget
    window_start: datetime
    window_end: datetime
    calculated_at: datetime
    reference_et_mm: WaterQuantity | None
    plant_factor: RatioQuantity | None
    observed_precipitation_mm: WaterQuantity | None
    quantified_irrigation_credit_mm: WaterQuantity | None
    unquantified_irrigation_session_ids: tuple[str, ...]
    effective_precipitation_policy: EffectivePrecipitationPolicy | None
    forecast: ForecastPrecipitationEvidence | None
    accounting_interval_state: AccountingIntervalState = AccountingIntervalState.COMPLETE
    opening_balance_state: OpeningBalanceState = OpeningBalanceState.UNKNOWN
    opening_deficit_mm: WaterQuantity | None = None
    demand_factor_source: DemandFactorSource = DemandFactorSource.UNRESOLVED
    demand_factor_confidence: float | None = None
    root_zone_available_water_mm: WaterQuantity | None = None
    root_zone_confidence: float | None = None
    allowable_depletion_fraction: RatioQuantity | None = None
    ledger_healthy: bool = True
    forecast_window_observed_precipitation_mm: WaterQuantity | None = None
    ledger_events: tuple[WaterBalanceLedgerEvent, ...] = ()
    evidence: tuple[WaterBalanceEvidence, ...] = ()
    forecast_policy: ForecastAdjustmentPolicy = field(default_factory=ForecastAdjustmentPolicy)

    def __post_init__(self) -> None:
        for name, value in (
            ("window_start", self.window_start),
            ("window_end", self.window_end),
            ("calculated_at", self.calculated_at),
        ):
            _aware(name, value)
        for name, confidence_value in (
            ("demand_factor_confidence", self.demand_factor_confidence),
            ("root_zone_confidence", self.root_zone_confidence),
        ):
            if confidence_value is not None:
                _fraction(name, confidence_value)
        if self.window_end < self.window_start or self.calculated_at < self.window_end:
            raise ValueError("water-balance evaluation timestamps are inconsistent")
        if (
            self.accounting_interval_state is AccountingIntervalState.COMPLETE
            and self.window_end <= self.window_start
        ):
            raise ValueError("complete accounting intervals must advance")
        _sorted_ids("unquantified_irrigation_session_ids", self.unquantified_irrigation_session_ids)
        event_keys = tuple((event.recorded_at, event.event_id) for event in self.ledger_events)
        if event_keys != tuple(sorted(set(event_keys))):
            raise ValueError("ledger events must be unique and deterministic")
        evidence_keys = tuple(item.evidence_id for item in self.evidence)
        if evidence_keys != tuple(sorted(set(evidence_keys))):
            raise ValueError("evidence must be unique and deterministic")
        numeric_opening = self.opening_balance_state in {
            OpeningBalanceState.RECONSTRUCTED,
            OpeningBalanceState.DURABLE_CARRY_FORWARD,
        }
        if numeric_opening != (self.opening_deficit_mm is not None):
            raise ValueError("only reconstructed or durable openings may be numeric")


@dataclass(frozen=True, slots=True)
class ProductionAreaWaterBalance:
    """Actual balance plus separate provisional forecast adjustment."""

    target: ProductionTarget
    state: WaterBalanceState
    window_start: datetime
    window_end: datetime
    calculated_at: datetime
    valid_until: datetime
    reference_et_mm: WaterQuantity | None
    plant_factor: RatioQuantity | None
    gross_landscape_demand_mm: WaterQuantity | None
    observed_precipitation_mm: WaterQuantity | None
    effective_observed_precipitation_mm: WaterQuantity | None
    quantified_irrigation_credit_mm: WaterQuantity | None
    unquantified_irrigation_session_ids: tuple[str, ...]
    actual_net_deficit_mm: WaterQuantity | None
    forecast_precipitation_mm: WaterQuantity | None
    effective_forecast_precipitation_mm: WaterQuantity | None
    forecast_window_observed_precipitation_mm: WaterQuantity | None
    effective_forecast_window_observed_precipitation_mm: WaterQuantity | None
    forecast_window_start: datetime | None
    forecast_window_end: datetime | None
    forecast_covered_deficit_mm: WaterQuantity | None
    residual_uncovered_deficit_mm: WaterQuantity | None
    deferred_deficit_mm: WaterQuantity | None
    forecast_reconciliation_state: ForecastReconciliationState
    accounting_interval_state: AccountingIntervalState
    opening_balance_state: OpeningBalanceState
    demand_factor_source: DemandFactorSource
    root_zone_available_water_mm: WaterQuantity | None
    allowable_depletion_fraction: RatioQuantity | None
    irrigation_trigger_deficit_mm: WaterQuantity | None
    trigger_state: IrrigationTriggerState
    irrigation_indicated: bool | None
    target_replenishment_depth_mm: WaterQuantity | None
    baseline_water_budget_policy_version: str
    confidence: float
    completeness: float
    evidence: tuple[WaterBalanceEvidence, ...]
    reason_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    schema_version: int = WATER_BALANCE_SCHEMA_VERSION
    policy_version: str = WATER_BALANCE_POLICY_VERSION
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("window_start", self.window_start),
            ("window_end", self.window_end),
            ("calculated_at", self.calculated_at),
            ("valid_until", self.valid_until),
        ):
            _aware(name, value)
        if self.valid_until <= self.calculated_at:
            raise ValueError("water-balance validity must extend beyond calculation")
        _fraction("confidence", self.confidence)
        _fraction("completeness", self.completeness)
        _sorted_ids("unquantified_irrigation_session_ids", self.unquantified_irrigation_session_ids)
        _sorted_codes("reason_codes", self.reason_codes)
        _sorted_codes("blocker_codes", self.blocker_codes)
        if self.execution_authorized:
            raise ValueError("water balances never authorize execution")
        if self.state is not WaterBalanceState.AVAILABLE and self.actual_net_deficit_mm is not None:
            raise ValueError("unavailable balances cannot expose a numeric deficit")

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(frozen=True, slots=True)
class WaterBalanceSnapshot:
    """Coordinator-owned current balances for canonical production targets."""

    state: WaterBalanceState
    calculated_at: datetime | None
    balances: tuple[ProductionAreaWaterBalance, ...]
    reason_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    schema_version: int = WATER_BALANCE_SCHEMA_VERSION
    policy_version: str = WATER_BALANCE_POLICY_VERSION
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if self.calculated_at is not None:
            _aware("calculated_at", self.calculated_at)
        targets = tuple(item.target for item in self.balances)
        if targets != tuple(sorted(set(targets))):
            raise ValueError("water balances must use deterministic unique targets")
        _sorted_codes("reason_codes", self.reason_codes)
        _sorted_codes("blocker_codes", self.blocker_codes)
        if self.execution_authorized:
            raise ValueError("water-balance snapshots never authorize execution")

    @classmethod
    def not_available(cls) -> WaterBalanceSnapshot:
        return cls(
            state=WaterBalanceState.NOT_AVAILABLE,
            calculated_at=None,
            balances=(),
            reason_codes=("fresh_recomputation_required",),
            blocker_codes=("water_balance_not_evaluated",),
        )

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


def _serialize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value


def _water_quantity(value: object) -> WaterQuantity:
    if not isinstance(value, dict):
        raise ValueError("water quantity must be a mapping")
    return WaterQuantity(
        scalar=value.get("scalar"),
        minimum=value.get("minimum"),
        typical=value.get("typical"),
        maximum=value.get("maximum"),
        unit=str(value.get("unit", "")),
    )


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO text")
    parsed = datetime.fromisoformat(value)
    _aware("timestamp", parsed)
    return parsed


def _latest_carried_event(
    events: tuple[WaterBalanceLedgerEvent, ...], target: ProductionTarget
) -> WaterBalanceLedgerEvent | None:
    carried = [
        event
        for event in events
        if event.target == target and event.carry_forward_deficit_mm is not None
    ]
    return (
        None
        if not carried
        else max(carried, key=lambda item: (item.accounted_through, item.event_id))
    )


def _aware(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a stable identifier")


def _code(name: str, value: str) -> None:
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        raise ValueError(f"{name} must be lower_snake_case")


def _fraction(name: str, value: float) -> None:
    if not _bounded(value, 0, 1):
        raise ValueError(f"{name} must be between zero and one")


def _nonnegative(value: object) -> bool:
    return _bounded(value, 0, float("inf"))


def _bounded(value: object, minimum: float, maximum: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
        and minimum <= value <= maximum
    )


def _sorted_codes(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must be a deterministic unique tuple")
    for value in values:
        _code(name, value)


def _sorted_ids(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must be a deterministic unique tuple")
    for value in values:
        _identifier(name, value)
