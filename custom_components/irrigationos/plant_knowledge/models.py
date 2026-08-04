"""Canonical immutable models for the Plant Knowledge Framework."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any

PLANT_KNOWLEDGE_SCHEMA_VERSION = 1
PLANT_KNOWLEDGE_RESOLUTION_ALGORITHM_VERSION = "1.0.0"
MAX_FUNCTIONAL_GROUP_DEPTH = 8
MAX_PROFILE_INHERITANCE_DEPTH = 8

_CANONICAL_ID_PATTERN = re.compile(r"^pk\.[a-z][a-z0-9_]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
_FIELD_PATH_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_METADATA_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_USDA_ZONE_PATTERN = re.compile(r"^(?P<number>[1-9]|1[0-3])(?P<suffix>[ab])$")


class SourceType(StrEnum):
    """Canonical types of plant-knowledge evidence source."""

    UNIVERSITY_EXTENSION = "university_extension"
    GOVERNMENT_DATABASE = "government_database"
    PEER_REVIEWED_LITERATURE = "peer_reviewed_literature"
    PROFESSIONAL_SOCIETY = "professional_society"
    BOTANICAL_INSTITUTION = "botanical_institution"
    EXPERT_REVIEWED_INTERNAL = "expert_reviewed_internal"
    PROVISIONAL_INTERNAL = "provisional_internal"


class ReviewState(StrEnum):
    """Review state shared by sources and claims."""

    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class EvidenceGrade(StrEnum):
    """Qualitative strength of evidence, separate from confidence."""

    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    EXPERT_CONSENSUS = "expert_consensus"
    PROVISIONAL = "provisional"


class ConsumerCapability(StrEnum):
    """Descriptive consumers of plant knowledge."""

    VISUAL_IDENTIFICATION = "visual_identification"
    WATER_DEMAND = "water_demand"
    PLANT_HEALTH = "plant_health"
    DISEASE_DIAGNOSTICS = "disease_diagnostics"
    IRRIGATION_PLANNING = "irrigation_planning"
    LEARNING = "learning"
    RECOMMENDATIONS = "recommendations"


class CoastalApplicability(StrEnum):
    """Applicability to coastal context."""

    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    UNSPECIFIED = "unspecified"


class InlandApplicability(StrEnum):
    """Applicability to inland context."""

    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    UNSPECIFIED = "unspecified"


class Season(StrEnum):
    """Canonical seasonal applicability."""

    YEAR_ROUND = "year_round"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class RegionalScope(StrEnum):
    """Whether applicability is explicitly broad or region-constrained."""

    UNRESTRICTED = "unrestricted"
    REGIONAL = "regional"


class KnowledgeUnit(StrEnum):
    """Stable canonical units supported by the initial field contracts."""

    METERS = "meters"
    MONTHS = "months"
    RATIO = "ratio"
    CELSIUS = "celsius"


class ClaimValueKind(StrEnum):
    """Allowed value kinds in a field contract."""

    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    ENUM = "enum"


class WaterStressSensitivity(StrEnum):
    """Canonical qualitative water-stress sensitivity."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class HeatTolerance(StrEnum):
    """Canonical qualitative heat tolerance."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class DrainagePreference(StrEnum):
    """Canonical qualitative soil-drainage preference."""

    WELL_DRAINED = "well_drained"
    MOISTURE_RETENTIVE = "moisture_retentive"
    ADAPTABLE = "adaptable"
    UNKNOWN = "unknown"


class Susceptibility(StrEnum):
    """Canonical qualitative susceptibility."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class LeafShape(StrEnum):
    """Broad canonical leaf-shape vocabulary for future visual consumers."""

    BROAD = "broad"
    NEEDLE = "needle"
    LINEAR = "linear"
    COMPOUND = "compound"
    UNKNOWN = "unknown"


class HydrozoneCompatibility(StrEnum):
    """Canonical qualitative hydrozone compatibility."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class PlantCategory(StrEnum):
    """Broad plant categories without property-specific meaning."""

    TREE = "tree"
    SHRUB = "shrub"
    TURF = "turf"
    GROUNDCOVER = "groundcover"
    VINE = "vine"
    SUCCULENT = "succulent"
    HERBACEOUS = "herbaceous"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ProfileResolutionLevel(StrEnum):
    """Specificity of a plant-knowledge profile."""

    CULTIVAR = "cultivar"
    SPECIES = "species"
    GENUS = "genus"
    FUNCTIONAL_GROUP = "functional_group"
    CATEGORY_FALLBACK = "category_fallback"
    UNKNOWN_FALLBACK = "unknown_fallback"


class LifecycleState(StrEnum):
    """Lifecycle of profiles and functional groups."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class ClaimResolutionMethod(StrEnum):
    """Method used to resolve competing immutable claims."""

    SELECTED_CLAIM = "selected_claim"
    RESOLVED_RANGE = "resolved_range"
    REVIEWER_DECISION = "reviewer_decision"
    UNRESOLVED = "unresolved"


class ClaimTraceDisposition(StrEnum):
    """Disposition of a claim in an inheritance resolution trace."""

    EFFECTIVE = "effective"
    OVERRIDDEN = "overridden"
    CONFLICT_RETAINED = "conflict_retained"


class ResolutionReasonCode(StrEnum):
    """Machine-readable deterministic profile-resolution outcomes."""

    USER_CONFIRMED_OVERRIDE = "user_confirmed_override"
    EXACT_CULTIVAR_MATCH = "exact_cultivar_match"
    EXACT_SPECIES_MATCH = "exact_species_match"
    EXACT_GENUS_MATCH = "exact_genus_match"
    FUNCTIONAL_GROUP_MATCH = "functional_group_match"
    CATEGORY_FALLBACK = "category_fallback"
    UNKNOWN_FALLBACK = "unknown_fallback"
    AMBIGUOUS_MATCH = "ambiguous_match"
    NO_ELIGIBLE_PROFILE = "no_eligible_profile"


def _validate_canonical_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not _CANONICAL_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must use the stable pk.<namespace>.<identity> format")


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validate_confidence(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("confidence must be between 0.0 and 1.0")


def _validate_positive_version(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_semantic_version(name: str, value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must use MAJOR.MINOR.PATCH")


def _validate_enum(name: str, value: object, enum_type: type[StrEnum]) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{name} must use a canonical {enum_type.__name__} value")


def _validate_boolean(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validate_tuple(name: str, values: object) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be an immutable tuple")


def _validate_sorted_unique_text(name: str, values: tuple[str, ...]) -> None:
    _validate_tuple(name, values)
    normalized: list[str] = []
    for value in values:
        _validate_text(name, value)
        normalized.append(_normalize_text(value))
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} must not contain normalized duplicates")
    if normalized != sorted(normalized):
        raise ValueError(f"{name} must use deterministic normalized ordering")


def _validate_sorted_unique_enums(name: str, values: tuple[StrEnum, ...]) -> None:
    _validate_tuple(name, values)
    if any(not isinstance(value, StrEnum) for value in values):
        raise ValueError(f"{name} must be an immutable tuple of canonical enum values")
    serialized = [value.value for value in values]
    if len(serialized) != len(set(serialized)):
        raise ValueError(f"{name} must not contain duplicates")
    if serialized != sorted(serialized):
        raise ValueError(f"{name} must use deterministic ordering")


def _validate_id_tuple(name: str, values: tuple[str, ...]) -> None:
    _validate_tuple(name, values)
    for value in values:
        _validate_canonical_id(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    if tuple(sorted(values)) != values:
        raise ValueError(f"{name} must use deterministic ordering")


def _validate_unique_id_tuple(name: str, values: tuple[str, ...]) -> None:
    _validate_tuple(name, values)
    for value in values:
        _validate_canonical_id(name, value)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")


def _serialize(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, type) and issubclass(value, StrEnum):
        return value.__name__
    if isinstance(value, datetime | date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError("raw bytes are not permitted in plant-knowledge records")
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"unsupported plant-knowledge serialization type: {type(value).__name__}")


class SerializableKnowledgeModel:
    """Mixin for deterministic plain-dictionary serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic plain data suitable for audit and checksums."""
        serialized = _serialize(self)
        if not isinstance(serialized, dict):  # pragma: no cover - mixin contract
            raise TypeError("plant-knowledge model did not serialize to a dictionary")
        return serialized


@dataclass(frozen=True, slots=True)
class SourceReviewRecord(SerializableKnowledgeModel):
    """One immutable transition in source review history."""

    state: ReviewState
    changed_at: datetime
    reviewer: str
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_enum("state", self.state, ReviewState)
        _validate_timestamp("changed_at", self.changed_at)
        _validate_text("reviewer", self.reviewer)
        if self.notes is not None:
            _validate_text("notes", self.notes)


@dataclass(frozen=True, slots=True)
class PlantKnowledgeSource(SerializableKnowledgeModel):
    """Structured bibliographic source for plant-knowledge claims."""

    source_id: str
    organization: str
    title: str
    authors: tuple[str, ...]
    publication_date: date | None
    accessed_date: date
    citation: str
    source_type: SourceType
    geographic_scope: tuple[str, ...]
    review_state: ReviewState
    review_history: tuple[SourceReviewRecord, ...]
    url: str | None = None
    licensing_notes: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_canonical_id("source_id", self.source_id)
        _validate_text("organization", self.organization)
        _validate_text("title", self.title)
        _validate_sorted_unique_text("authors", self.authors)
        _validate_text("citation", self.citation)
        _validate_sorted_unique_text("geographic_scope", self.geographic_scope)
        if not isinstance(self.accessed_date, date) or isinstance(self.accessed_date, datetime):
            raise ValueError("accessed_date must be a date")
        if self.publication_date is not None and (
            not isinstance(self.publication_date, date)
            or isinstance(self.publication_date, datetime)
        ):
            raise ValueError("publication_date must be a date")
        _validate_enum("source_type", self.source_type, SourceType)
        _validate_enum("review_state", self.review_state, ReviewState)
        if self.publication_date is not None and self.publication_date > self.accessed_date:
            raise ValueError("publication_date cannot follow accessed_date")
        if self.url is not None:
            _validate_text("url", self.url)
            if self.url.lstrip().lower().startswith("data:"):
                raise ValueError("source URL must not embed document data")
            if not self.url.startswith(("https://", "http://")):
                raise ValueError("source URL must use http or https")
        for name, value in (
            ("licensing_notes", self.licensing_notes),
            ("notes", self.notes),
        ):
            if value is not None:
                _validate_text(name, value)
        if not self.review_history:
            raise ValueError("source requires immutable review history")
        _validate_tuple("review_history", self.review_history)
        if any(not isinstance(record, SourceReviewRecord) for record in self.review_history):
            raise ValueError("review_history must contain SourceReviewRecord values")
        if self.review_history[0].state is not ReviewState.UNREVIEWED:
            raise ValueError("source review history must begin unreviewed")
        if self.review_history[-1].state is not self.review_state:
            raise ValueError("source review_state must match its final review record")
        timestamps = tuple(record.changed_at for record in self.review_history)
        if timestamps != tuple(sorted(timestamps)):
            raise ValueError("source review history must be chronological")
        allowed = {
            ReviewState.UNREVIEWED: {ReviewState.REVIEWED, ReviewState.REJECTED},
            ReviewState.REVIEWED: {
                ReviewState.APPROVED,
                ReviewState.REJECTED,
                ReviewState.DEPRECATED,
            },
            ReviewState.APPROVED: {ReviewState.DEPRECATED},
            ReviewState.REJECTED: {ReviewState.REVIEWED, ReviewState.DEPRECATED},
            ReviewState.DEPRECATED: set(),
        }
        for previous, current in zip(self.review_history, self.review_history[1:], strict=False):
            if current.state not in allowed[previous.state]:
                raise ValueError(
                    f"invalid source review transition: {previous.state} -> {current.state}"
                )


@dataclass(frozen=True, slots=True)
class KnowledgeRange(SerializableKnowledgeModel):
    """Bounded knowledge value without implied precision beyond its inputs."""

    minimum: float
    maximum: float
    unit: KnowledgeUnit
    typical: float | None = None

    def __post_init__(self) -> None:
        _validate_enum("unit", self.unit, KnowledgeUnit)
        for name, value in (("minimum", self.minimum), ("maximum", self.maximum)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number")
        if self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        if self.typical is not None:
            if (
                isinstance(self.typical, bool)
                or not isinstance(self.typical, (int, float))
                or not isfinite(self.typical)
            ):
                raise ValueError("typical must be a finite number")
            if not self.minimum <= self.typical <= self.maximum:
                raise ValueError("typical must fall between minimum and maximum")


def _usda_zone_key(value: str) -> tuple[int, int]:
    match = _USDA_ZONE_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("USDA hardiness zone must use 1a through 13b")
    return int(match.group("number")), 0 if match.group("suffix") == "a" else 1


@dataclass(frozen=True, slots=True)
class RegionalApplicability(SerializableKnowledgeModel):
    """Explicit geographic, climatic, and seasonal scope of knowledge."""

    scope: RegionalScope
    countries: tuple[str, ...] = ()
    states_or_provinces: tuple[str, ...] = ()
    climate_zone_ids: tuple[str, ...] = ()
    wucols_regions: tuple[str, ...] = ()
    usda_zone_minimum: str | None = None
    usda_zone_maximum: str | None = None
    coastal: CoastalApplicability = CoastalApplicability.UNSPECIFIED
    inland: InlandApplicability = InlandApplicability.UNSPECIFIED
    elevation_minimum_meters: float | None = None
    elevation_maximum_meters: float | None = None
    seasons: tuple[Season, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_enum("scope", self.scope, RegionalScope)
        _validate_enum("coastal", self.coastal, CoastalApplicability)
        _validate_enum("inland", self.inland, InlandApplicability)
        _validate_tuple("countries", self.countries)
        for country in self.countries:
            if not re.fullmatch(r"[A-Z]{2}", country):
                raise ValueError("countries must use uppercase two-letter identifiers")
        if tuple(sorted(self.countries)) != self.countries or len(self.countries) != len(
            set(self.countries)
        ):
            raise ValueError("countries must be unique and deterministically ordered")
        for name, values in (
            ("states_or_provinces", self.states_or_provinces),
            ("climate_zone_ids", self.climate_zone_ids),
            ("wucols_regions", self.wucols_regions),
        ):
            _validate_sorted_unique_text(name, values)
        if (self.usda_zone_minimum is None) != (self.usda_zone_maximum is None):
            raise ValueError("USDA applicability requires both minimum and maximum")
        if (
            self.usda_zone_minimum is not None
            and self.usda_zone_maximum is not None
            and _usda_zone_key(self.usda_zone_minimum) > _usda_zone_key(self.usda_zone_maximum)
        ):
            raise ValueError("USDA minimum cannot exceed maximum")
        for name, value in (
            ("elevation_minimum_meters", self.elevation_minimum_meters),
            ("elevation_maximum_meters", self.elevation_maximum_meters),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number")
        if (
            self.elevation_minimum_meters is not None
            and self.elevation_maximum_meters is not None
            and self.elevation_minimum_meters > self.elevation_maximum_meters
        ):
            raise ValueError("elevation minimum cannot exceed maximum")
        _validate_sorted_unique_enums("seasons", self.seasons)
        if any(not isinstance(season, Season) for season in self.seasons):
            raise ValueError("seasons must contain canonical Season values")
        if self.notes is not None:
            _validate_text("notes", self.notes)
        has_constraints = any(
            (
                self.countries,
                self.states_or_provinces,
                self.climate_zone_ids,
                self.wucols_regions,
                self.usda_zone_minimum,
                self.usda_zone_maximum,
                self.elevation_minimum_meters is not None,
                self.elevation_maximum_meters is not None,
                self.seasons,
                self.coastal is not CoastalApplicability.UNSPECIFIED,
                self.inland is not InlandApplicability.UNSPECIFIED,
            )
        )
        if self.scope is RegionalScope.UNRESTRICTED and has_constraints:
            raise ValueError("unrestricted applicability cannot contain regional constraints")
        if self.scope is RegionalScope.REGIONAL and not has_constraints:
            raise ValueError("regional applicability requires at least one explicit constraint")

    @property
    def is_unrestricted(self) -> bool:
        """Return whether this object explicitly represents broad scope."""
        return self.scope is RegionalScope.UNRESTRICTED


@dataclass(frozen=True, slots=True)
class PlantKnowledgeFieldContract(SerializableKnowledgeModel):
    """Stable value and unit contract for one canonical claim field."""

    field_path: str
    value_kind: ClaimValueKind
    allowed_units: tuple[KnowledgeUnit, ...]
    negative_values_permitted: bool
    range_permitted: bool
    enum_type: type[StrEnum] | None = None
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not _FIELD_PATH_PATTERN.fullmatch(self.field_path):
            raise ValueError("field_path must use canonical lower_snake_case segments")
        _validate_sorted_unique_enums("allowed_units", self.allowed_units)
        if any(not isinstance(unit, KnowledgeUnit) for unit in self.allowed_units):
            raise ValueError("allowed_units must contain canonical KnowledgeUnit values")
        _validate_enum("value_kind", self.value_kind, ClaimValueKind)
        for name, value in (("minimum", self.minimum), ("maximum", self.maximum)):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("field-contract minimum cannot exceed maximum")
        if self.value_kind is ClaimValueKind.ENUM and self.enum_type is None:
            raise ValueError("enum field contracts require enum_type")
        if self.value_kind is not ClaimValueKind.ENUM and self.enum_type is not None:
            raise ValueError("enum_type is only valid for enum field contracts")


_FIELD_CONTRACTS = MappingProxyType(
    {
        contract.field_path: contract
        for contract in (
            PlantKnowledgeFieldContract(
                "identity.scientific_name",
                ClaimValueKind.STRING,
                (),
                False,
                False,
            ),
            PlantKnowledgeFieldContract(
                "identity.preferred_common_name",
                ClaimValueKind.STRING,
                (),
                False,
                False,
            ),
            PlantKnowledgeFieldContract(
                "growth.typical_root_depth_meters",
                ClaimValueKind.FLOAT,
                (KnowledgeUnit.METERS,),
                False,
                True,
                minimum=0,
            ),
            PlantKnowledgeFieldContract(
                "growth.establishment_duration_months",
                ClaimValueKind.INTEGER,
                (KnowledgeUnit.MONTHS,),
                False,
                True,
                minimum=0,
            ),
            PlantKnowledgeFieldContract(
                "water.landscape_coefficient",
                ClaimValueKind.FLOAT,
                (KnowledgeUnit.RATIO,),
                False,
                True,
                minimum=0,
                maximum=2,
            ),
            PlantKnowledgeFieldContract(
                "water.plant_factor",
                ClaimValueKind.FLOAT,
                (KnowledgeUnit.RATIO,),
                False,
                True,
                minimum=0,
                maximum=2,
            ),
            PlantKnowledgeFieldContract(
                "water.water_stress_sensitivity",
                ClaimValueKind.ENUM,
                (),
                False,
                False,
                enum_type=WaterStressSensitivity,
            ),
            PlantKnowledgeFieldContract(
                "environment.minimum_temperature_celsius",
                ClaimValueKind.FLOAT,
                (KnowledgeUnit.CELSIUS,),
                True,
                True,
                minimum=-100,
                maximum=70,
            ),
            PlantKnowledgeFieldContract(
                "environment.heat_tolerance",
                ClaimValueKind.ENUM,
                (),
                False,
                False,
                enum_type=HeatTolerance,
            ),
            PlantKnowledgeFieldContract(
                "soil.preferred_drainage",
                ClaimValueKind.ENUM,
                (),
                False,
                False,
                enum_type=DrainagePreference,
            ),
            PlantKnowledgeFieldContract(
                "health.root_rot_susceptibility",
                ClaimValueKind.ENUM,
                (),
                False,
                False,
                enum_type=Susceptibility,
            ),
            PlantKnowledgeFieldContract(
                "visual.leaf_shape",
                ClaimValueKind.ENUM,
                (),
                False,
                False,
                enum_type=LeafShape,
            ),
            PlantKnowledgeFieldContract(
                "planning.hydrozone_compatibility",
                ClaimValueKind.ENUM,
                (),
                False,
                False,
                enum_type=HydrozoneCompatibility,
            ),
        )
    }
)


def get_field_contract(field_path: str) -> PlantKnowledgeFieldContract:
    """Return the stable contract for a supported canonical field path."""
    try:
        return _FIELD_CONTRACTS[field_path]
    except KeyError as err:
        raise KeyError(f"unsupported plant-knowledge field path: {field_path}") from err


def supported_field_paths() -> tuple[str, ...]:
    """Return supported field paths in deterministic order."""
    return tuple(sorted(_FIELD_CONTRACTS))


def _validate_numeric_against_contract(
    value: int | float,
    contract: PlantKnowledgeFieldContract,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("numeric claim value must be finite")
    if not contract.negative_values_permitted and value < 0:
        raise ValueError(f"negative values are not permitted for {contract.field_path}")
    if contract.minimum is not None and value < contract.minimum:
        raise ValueError(f"claim value is below the minimum for {contract.field_path}")
    if contract.maximum is not None and value > contract.maximum:
        raise ValueError(f"claim value exceeds the maximum for {contract.field_path}")


def _validate_claim_value(
    value: str | bool | int | float | StrEnum | KnowledgeRange,
    unit: KnowledgeUnit | None,
    contract: PlantKnowledgeFieldContract,
) -> None:
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError("claim value cannot contain raw bytes or embedded documents")
    if isinstance(value, KnowledgeRange):
        if not contract.range_permitted:
            raise ValueError(f"KnowledgeRange is not permitted for {contract.field_path}")
        if value.unit not in contract.allowed_units or unit is not value.unit:
            raise ValueError("claim unit is incompatible with its field contract")
        for bound in (value.minimum, value.maximum):
            _validate_numeric_against_contract(bound, contract)
        if value.typical is not None:
            _validate_numeric_against_contract(value.typical, contract)
        if contract.value_kind is ClaimValueKind.INTEGER and any(
            not float(bound).is_integer()
            for bound in (value.minimum, value.maximum)
            if bound is not None
        ):
            raise ValueError("integer field ranges require whole-number bounds")
        return
    if contract.allowed_units:
        if unit not in contract.allowed_units:
            raise ValueError("claim unit is incompatible with its field contract")
    elif unit is not None:
        raise ValueError("unit is not permitted for this field contract")
    if contract.value_kind is ClaimValueKind.STRING:
        if not isinstance(value, str) or isinstance(value, StrEnum):
            raise ValueError("claim requires a string value")
        _validate_text("claim value", value)
    elif contract.value_kind is ClaimValueKind.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("claim requires a boolean value")
    elif contract.value_kind is ClaimValueKind.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("claim requires an integer value")
        _validate_numeric_against_contract(value, contract)
    elif contract.value_kind is ClaimValueKind.FLOAT:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("claim requires a numeric value")
        _validate_numeric_against_contract(value, contract)
    elif contract.value_kind is ClaimValueKind.ENUM:
        if contract.enum_type is None or not isinstance(value, contract.enum_type):
            raise ValueError("claim requires the canonical enum for its field contract")


@dataclass(frozen=True, slots=True)
class PlantKnowledgeClaim(SerializableKnowledgeModel):
    """Central immutable evidence-backed plant-knowledge record."""

    claim_id: str
    field_path: str
    value: str | bool | int | float | StrEnum | KnowledgeRange
    unit: KnowledgeUnit | None
    regional_applicability: RegionalApplicability
    confidence: float
    evidence_grade: EvidenceGrade
    source_ids: tuple[str, ...]
    created_at: datetime
    review_state: ReviewState
    intended_consumer_capabilities: tuple[ConsumerCapability, ...]
    claim_version: int
    reviewed_at: datetime | None = None
    notes: str | None = None
    superseded_claim_id: str | None = None
    unresolved_conflict: bool = False

    def __post_init__(self) -> None:
        _validate_canonical_id("claim_id", self.claim_id)
        contract = get_field_contract(self.field_path)
        _validate_claim_value(self.value, self.unit, contract)
        _validate_confidence(self.confidence)
        _validate_enum("evidence_grade", self.evidence_grade, EvidenceGrade)
        _validate_enum("review_state", self.review_state, ReviewState)
        _validate_id_tuple("source_ids", self.source_ids)
        _validate_timestamp("created_at", self.created_at)
        if self.reviewed_at is not None:
            _validate_timestamp("reviewed_at", self.reviewed_at)
            if self.reviewed_at < self.created_at:
                raise ValueError("reviewed_at cannot precede created_at")
        if self.review_state in {ReviewState.REVIEWED, ReviewState.APPROVED}:
            if not self.source_ids:
                raise ValueError("reviewed and approved claims require source IDs")
            if self.reviewed_at is None:
                raise ValueError("reviewed and approved claims require reviewed_at")
        _validate_sorted_unique_enums(
            "intended_consumer_capabilities", self.intended_consumer_capabilities
        )
        if any(
            not isinstance(capability, ConsumerCapability)
            for capability in self.intended_consumer_capabilities
        ):
            raise ValueError("consumer capabilities must use canonical values")
        _validate_positive_version("claim_version", self.claim_version)
        if self.notes is not None:
            _validate_text("notes", self.notes)
        if self.superseded_claim_id is not None:
            _validate_canonical_id("superseded_claim_id", self.superseded_claim_id)
            if self.superseded_claim_id == self.claim_id:
                raise ValueError("a claim cannot supersede itself")


@dataclass(frozen=True, slots=True)
class PlantFunctionalGroup(SerializableKnowledgeModel):
    """Descriptive functional-group hierarchy node, separate from inheritance."""

    group_id: str
    display_name: str
    description: str
    intended_consumer_capabilities: tuple[ConsumerCapability, ...]
    lifecycle_state: LifecycleState
    version: int
    parent_group_id: str | None = None

    def __post_init__(self) -> None:
        _validate_canonical_id("group_id", self.group_id)
        _validate_text("display_name", self.display_name)
        _validate_text("description", self.description)
        _validate_sorted_unique_enums(
            "intended_consumer_capabilities", self.intended_consumer_capabilities
        )
        if any(
            not isinstance(capability, ConsumerCapability)
            for capability in self.intended_consumer_capabilities
        ):
            raise ValueError("consumer capabilities must use canonical values")
        _validate_enum("lifecycle_state", self.lifecycle_state, LifecycleState)
        _validate_positive_version("version", self.version)
        if self.parent_group_id is not None:
            _validate_canonical_id("parent_group_id", self.parent_group_id)
            if self.parent_group_id == self.group_id:
                raise ValueError("a functional group cannot parent itself")


@dataclass(frozen=True, slots=True)
class ProfileExplanationMetadata(SerializableKnowledgeModel):
    """One deterministic non-payload explanation metadata item."""

    key: str
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not _METADATA_KEY_PATTERN.fullmatch(self.key):
            raise ValueError("metadata key must use stable lower_snake_case")
        _validate_text("metadata value", self.value)


@dataclass(frozen=True, slots=True)
class PlantKnowledgeProfile(SerializableKnowledgeModel):
    """Versioned general plant-knowledge profile with explicit inheritance."""

    profile_id: str
    preferred_common_name: str
    scientific_name: str | None
    aliases: tuple[str, ...]
    cultivar: str | None
    broad_category: PlantCategory
    resolution_level: ProfileResolutionLevel
    parent_profile_id: str | None
    functional_group_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    regional_applicability: RegionalApplicability
    intended_consumer_capabilities: tuple[ConsumerCapability, ...]
    schema_version: int
    profile_version: int
    lifecycle_state: LifecycleState
    created_at: datetime
    reviewed_at: datetime | None = None
    superseded_profile_id: str | None = None
    explanation_metadata: tuple[ProfileExplanationMetadata, ...] = ()

    def __post_init__(self) -> None:
        _validate_canonical_id("profile_id", self.profile_id)
        _validate_text("preferred_common_name", self.preferred_common_name)
        if self.scientific_name is not None:
            _validate_text("scientific_name", self.scientific_name)
        _validate_sorted_unique_text("aliases", self.aliases)
        if _normalize_text(self.preferred_common_name) in {
            _normalize_text(alias) for alias in self.aliases
        }:
            raise ValueError("aliases must not duplicate the preferred common name")
        if self.scientific_name is not None and _normalize_text(self.scientific_name) in {
            _normalize_text(alias) for alias in self.aliases
        }:
            raise ValueError("aliases must not duplicate the scientific name")
        if self.cultivar is not None:
            _validate_text("cultivar", self.cultivar)
        _validate_enum("broad_category", self.broad_category, PlantCategory)
        _validate_enum("resolution_level", self.resolution_level, ProfileResolutionLevel)
        _validate_enum("lifecycle_state", self.lifecycle_state, LifecycleState)
        _validate_id_tuple("functional_group_ids", self.functional_group_ids)
        _validate_id_tuple("claim_ids", self.claim_ids)
        _validate_sorted_unique_enums(
            "intended_consumer_capabilities", self.intended_consumer_capabilities
        )
        if any(
            not isinstance(capability, ConsumerCapability)
            for capability in self.intended_consumer_capabilities
        ):
            raise ValueError("consumer capabilities must use canonical values")
        _validate_positive_version("schema_version", self.schema_version)
        _validate_positive_version("profile_version", self.profile_version)
        _validate_timestamp("created_at", self.created_at)
        if self.reviewed_at is not None:
            _validate_timestamp("reviewed_at", self.reviewed_at)
            if self.reviewed_at < self.created_at:
                raise ValueError("reviewed_at cannot precede created_at")
        if (
            self.lifecycle_state in {LifecycleState.REVIEWED, LifecycleState.PUBLISHED}
            and self.reviewed_at is None
        ):
            raise ValueError("reviewed and published profiles require reviewed_at")
        if self.parent_profile_id is not None:
            _validate_canonical_id("parent_profile_id", self.parent_profile_id)
            if self.parent_profile_id == self.profile_id:
                raise ValueError("a profile cannot parent itself")
        if self.superseded_profile_id is not None:
            _validate_canonical_id("superseded_profile_id", self.superseded_profile_id)
            if self.superseded_profile_id == self.profile_id:
                raise ValueError("a profile cannot supersede itself")
        if self.lifecycle_state is LifecycleState.SUPERSEDED:
            if self.superseded_profile_id is None:
                raise ValueError("superseded profiles require superseded_profile_id")
        elif self.superseded_profile_id is not None:
            raise ValueError("superseded_profile_id is only valid for superseded profiles")
        prefixes = {
            ProfileResolutionLevel.CULTIVAR: "pk.cultivar.",
            ProfileResolutionLevel.SPECIES: "pk.species.",
            ProfileResolutionLevel.GENUS: "pk.genus.",
            ProfileResolutionLevel.FUNCTIONAL_GROUP: "pk.group.",
            ProfileResolutionLevel.CATEGORY_FALLBACK: "pk.category.",
            ProfileResolutionLevel.UNKNOWN_FALLBACK: "pk.fallback.",
        }
        if not self.profile_id.startswith(prefixes[self.resolution_level]):
            raise ValueError("profile ID namespace must match resolution level")
        if self.resolution_level is ProfileResolutionLevel.CULTIVAR:
            if self.cultivar is None or self.scientific_name is None:
                raise ValueError("cultivar profiles require cultivar and scientific_name")
        elif self.cultivar is not None:
            raise ValueError("cultivar is only valid for cultivar profiles")
        if (
            self.resolution_level
            in {
                ProfileResolutionLevel.SPECIES,
                ProfileResolutionLevel.GENUS,
            }
            and self.scientific_name is None
        ):
            raise ValueError("species and genus profiles require scientific_name")
        if (
            self.resolution_level is ProfileResolutionLevel.FUNCTIONAL_GROUP
            and not self.functional_group_ids
        ):
            raise ValueError("functional-group profiles require functional_group_ids")
        if (
            self.resolution_level is ProfileResolutionLevel.CATEGORY_FALLBACK
            and self.broad_category is PlantCategory.UNKNOWN
        ):
            raise ValueError("category fallback requires a known broad category")
        _validate_tuple("explanation_metadata", self.explanation_metadata)
        if any(
            not isinstance(item, ProfileExplanationMetadata) for item in self.explanation_metadata
        ):
            raise ValueError("explanation_metadata must contain canonical metadata records")
        metadata_keys = tuple(item.key for item in self.explanation_metadata)
        if len(metadata_keys) != len(set(metadata_keys)):
            raise ValueError("explanation metadata keys must be unique")
        if metadata_keys != tuple(sorted(metadata_keys)):
            raise ValueError("explanation metadata must use deterministic key ordering")


@dataclass(frozen=True, slots=True)
class RegionalWeight(SerializableKnowledgeModel):
    """Explainable regional weighting used in a claim resolution."""

    attribute: str
    weight: float
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.attribute, str) or not _METADATA_KEY_PATTERN.fullmatch(
            self.attribute
        ):
            raise ValueError("regional weight attribute must use lower_snake_case")
        _validate_confidence(self.weight)
        _validate_text("regional weight reason", self.reason)


@dataclass(frozen=True, slots=True)
class ClaimResolution(SerializableKnowledgeModel):
    """Immutable resolution of competing claims without deleting originals."""

    resolution_id: str
    field_path: str
    competing_claim_ids: tuple[str, ...]
    selected_claim_id: str | None
    resolved_range: KnowledgeRange | None
    regional_weights: tuple[RegionalWeight, ...]
    resolution_method: ClaimResolutionMethod
    resolver_identity: str
    confidence: float
    unresolved_issues: tuple[str, ...]
    version: int
    created_at: datetime
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_canonical_id("resolution_id", self.resolution_id)
        get_field_contract(self.field_path)
        _validate_id_tuple("competing_claim_ids", self.competing_claim_ids)
        if len(self.competing_claim_ids) < 2:
            raise ValueError("claim resolution requires at least two competing claims")
        if self.selected_claim_id is None and self.resolved_range is None:
            raise ValueError("claim resolution requires a selected claim or resolved range")
        if self.selected_claim_id is not None:
            _validate_canonical_id("selected_claim_id", self.selected_claim_id)
            if self.selected_claim_id not in self.competing_claim_ids:
                raise ValueError("selected claim must be one of the competing claims")
        if self.resolved_range is not None:
            contract = get_field_contract(self.field_path)
            _validate_claim_value(
                self.resolved_range,
                self.resolved_range.unit,
                contract,
            )
        _validate_enum("resolution_method", self.resolution_method, ClaimResolutionMethod)
        if (
            self.resolution_method is ClaimResolutionMethod.SELECTED_CLAIM
            and self.selected_claim_id is None
        ):
            raise ValueError("selected-claim resolution method requires selected_claim_id")
        if (
            self.resolution_method is ClaimResolutionMethod.RESOLVED_RANGE
            and self.resolved_range is None
        ):
            raise ValueError("resolved-range resolution method requires resolved_range")
        if (
            self.resolution_method is ClaimResolutionMethod.UNRESOLVED
            and not self.unresolved_issues
        ):
            raise ValueError("unresolved resolution method requires unresolved issues")
        _validate_tuple("regional_weights", self.regional_weights)
        if any(not isinstance(item, RegionalWeight) for item in self.regional_weights):
            raise ValueError("regional_weights must contain RegionalWeight values")
        attributes = tuple(item.attribute for item in self.regional_weights)
        if len(attributes) != len(set(attributes)):
            raise ValueError("regional weights must use unique attributes")
        if attributes != tuple(sorted(attributes)):
            raise ValueError("regional weights must use deterministic ordering")
        _validate_text("resolver_identity", self.resolver_identity)
        _validate_confidence(self.confidence)
        _validate_sorted_unique_text("unresolved_issues", self.unresolved_issues)
        _validate_positive_version("version", self.version)
        _validate_timestamp("created_at", self.created_at)
        if self.reviewed_at is not None:
            _validate_timestamp("reviewed_at", self.reviewed_at)
            if self.reviewed_at < self.created_at:
                raise ValueError("reviewed_at cannot precede created_at")


@dataclass(frozen=True, slots=True)
class ClaimConfidenceStatistics(SerializableKnowledgeModel):
    """Manifest confidence statistics over all immutable claims."""

    claim_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None

    def __post_init__(self) -> None:
        if isinstance(self.claim_count, bool) or not isinstance(self.claim_count, int):
            raise ValueError("claim_count must be a non-negative integer")
        if self.claim_count < 0:
            raise ValueError("claim_count must be a non-negative integer")
        values = (self.minimum, self.maximum, self.mean)
        if self.claim_count == 0:
            if any(value is not None for value in values):
                raise ValueError("empty confidence statistics must use None values")
            return
        if any(value is None for value in values):
            raise ValueError("non-empty confidence statistics require all values")
        for value in values:
            if value is not None:
                _validate_confidence(value)
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.mean is not None
            and not self.minimum <= self.mean <= self.maximum
        ):
            raise ValueError("mean confidence must fall between minimum and maximum")


@dataclass(frozen=True, slots=True)
class PlantKnowledgeManifest(SerializableKnowledgeModel):
    """Immutable version and validation summary for one complete library."""

    schema_version: int
    library_version: str
    generated_at: datetime
    supported_climate_regions: tuple[str, ...]
    usda_zone_minimum: str | None
    usda_zone_maximum: str | None
    profile_count: int
    category_count: int
    functional_group_count: int
    genus_count: int
    species_count: int
    cultivar_count: int
    source_count: int
    claim_count: int
    claim_resolution_count: int
    published_profile_count: int
    confidence_statistics: ClaimConfidenceStatistics
    validation_checksum: str
    previous_library_version: str | None = None

    def __post_init__(self) -> None:
        _validate_positive_version("schema_version", self.schema_version)
        _validate_semantic_version("library_version", self.library_version)
        _validate_timestamp("generated_at", self.generated_at)
        _validate_sorted_unique_text("supported_climate_regions", self.supported_climate_regions)
        if (self.usda_zone_minimum is None) != (self.usda_zone_maximum is None):
            raise ValueError("manifest USDA summary requires both minimum and maximum")
        if (
            self.usda_zone_minimum is not None
            and self.usda_zone_maximum is not None
            and _usda_zone_key(self.usda_zone_minimum) > _usda_zone_key(self.usda_zone_maximum)
        ):
            raise ValueError("manifest USDA minimum cannot exceed maximum")
        count_fields = (
            "profile_count",
            "category_count",
            "functional_group_count",
            "genus_count",
            "species_count",
            "cultivar_count",
            "source_count",
            "claim_count",
            "claim_resolution_count",
            "published_profile_count",
        )
        for name in count_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.confidence_statistics.claim_count != self.claim_count:
            raise ValueError("confidence statistics claim count must match manifest")
        if not re.fullmatch(r"[0-9a-f]{64}", self.validation_checksum):
            raise ValueError("validation_checksum must be a lowercase SHA-256 digest")
        if self.previous_library_version is not None:
            _validate_semantic_version("previous_library_version", self.previous_library_version)
            if self.previous_library_version == self.library_version:
                raise ValueError("previous library version must differ from current version")


@dataclass(frozen=True, slots=True)
class PlantKnowledgeResolutionRequest(SerializableKnowledgeModel):
    """Deterministic exact-match request for a general plant profile."""

    request_id: str
    user_confirmed_profile_id: str | None = None
    scientific_name: str | None = None
    common_name: str | None = None
    cultivar: str | None = None
    broad_category: PlantCategory | None = None
    functional_group_hints: tuple[str, ...] = ()
    country: str | None = None
    state_or_province: str | None = None
    climate_zone_ids: tuple[str, ...] = ()
    wucols_region: str | None = None
    usda_hardiness_zone: str | None = None
    coastal: bool | None = None
    inland: bool | None = None

    def __post_init__(self) -> None:
        _validate_canonical_id("request_id", self.request_id)
        if self.user_confirmed_profile_id is not None:
            _validate_canonical_id("user_confirmed_profile_id", self.user_confirmed_profile_id)
        for name, value in (
            ("scientific_name", self.scientific_name),
            ("common_name", self.common_name),
            ("cultivar", self.cultivar),
            ("state_or_province", self.state_or_province),
            ("wucols_region", self.wucols_region),
        ):
            if value is not None:
                _validate_text(name, value)
        _validate_id_tuple("functional_group_hints", self.functional_group_hints)
        _validate_sorted_unique_text("climate_zone_ids", self.climate_zone_ids)
        if self.broad_category is not None:
            _validate_enum("broad_category", self.broad_category, PlantCategory)
        if self.country is not None and not re.fullmatch(r"[A-Z]{2}", self.country):
            raise ValueError("country must use an uppercase two-letter identifier")
        if self.usda_hardiness_zone is not None:
            _usda_zone_key(self.usda_hardiness_zone)
        for context_name, context_value in (
            ("coastal", self.coastal),
            ("inland", self.inland),
        ):
            if context_value is not None:
                _validate_boolean(context_name, context_value)


@dataclass(frozen=True, slots=True)
class PlantKnowledgeResolutionCandidate(SerializableKnowledgeModel):
    """One profile considered by the deterministic resolution algorithm."""

    profile_id: str
    resolution_level: ProfileResolutionLevel
    identity_score: int
    regional_score: int
    total_score: int
    matched_aliases: tuple[str, ...]
    matched_regional_attributes: tuple[str, ...]
    unavailable_regional_attributes: tuple[str, ...]
    mismatched_regional_attributes: tuple[str, ...]
    eligible: bool
    reason_code: str

    def __post_init__(self) -> None:
        _validate_canonical_id("profile_id", self.profile_id)
        _validate_enum("resolution_level", self.resolution_level, ProfileResolutionLevel)
        for name, value in (
            ("identity_score", self.identity_score),
            ("regional_score", self.regional_score),
            ("total_score", self.total_score),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        _validate_sorted_unique_text("matched_aliases", self.matched_aliases)
        for name, values in (
            ("matched_regional_attributes", self.matched_regional_attributes),
            ("unavailable_regional_attributes", self.unavailable_regional_attributes),
            ("mismatched_regional_attributes", self.mismatched_regional_attributes),
        ):
            _validate_sorted_unique_text(name, values)
        _validate_text("reason_code", self.reason_code)
        _validate_boolean("eligible", self.eligible)
        if self.total_score != self.identity_score + self.regional_score:
            raise ValueError("total_score must equal identity_score plus regional_score")


@dataclass(frozen=True, slots=True)
class EffectivePlantKnowledgeClaim(SerializableKnowledgeModel):
    """Effective claim with its originating profile and inheritance status."""

    claim_id: str
    field_path: str
    originating_profile_id: str
    inherited: bool
    claim_resolution_id: str | None = None
    resolved_range: KnowledgeRange | None = None

    def __post_init__(self) -> None:
        _validate_canonical_id("claim_id", self.claim_id)
        contract = get_field_contract(self.field_path)
        _validate_canonical_id("originating_profile_id", self.originating_profile_id)
        _validate_boolean("inherited", self.inherited)
        if self.claim_resolution_id is not None:
            _validate_canonical_id("claim_resolution_id", self.claim_resolution_id)
        if self.resolved_range is not None:
            if self.claim_resolution_id is None:
                raise ValueError("resolved effective ranges require a claim resolution ID")
            _validate_claim_value(self.resolved_range, self.resolved_range.unit, contract)


@dataclass(frozen=True, slots=True)
class InheritedClaimTrace(SerializableKnowledgeModel):
    """Preserved inheritance and override disposition for one claim."""

    claim_id: str
    field_path: str
    originating_profile_id: str
    disposition: ClaimTraceDisposition
    overridden_by_claim_id: str | None = None

    def __post_init__(self) -> None:
        _validate_canonical_id("claim_id", self.claim_id)
        get_field_contract(self.field_path)
        _validate_canonical_id("originating_profile_id", self.originating_profile_id)
        _validate_enum("disposition", self.disposition, ClaimTraceDisposition)
        if self.overridden_by_claim_id is not None:
            _validate_canonical_id("overridden_by_claim_id", self.overridden_by_claim_id)
        if self.disposition is ClaimTraceDisposition.OVERRIDDEN:
            if self.overridden_by_claim_id is None:
                raise ValueError("overridden traces require overridden_by_claim_id")
        elif self.overridden_by_claim_id is not None:
            raise ValueError("overridden_by_claim_id is only valid for overridden traces")


@dataclass(frozen=True, slots=True)
class PlantKnowledgeExplanation(SerializableKnowledgeModel):
    """Machine- and human-readable explanation of profile resolution."""

    reason_code: ResolutionReasonCode
    summary: str
    algorithm_version: str
    candidate_profile_ids: tuple[str, ...]
    evidence_source_ids: tuple[str, ...]
    matched_regional_attributes: tuple[str, ...]
    unavailable_regional_attributes: tuple[str, ...]
    mismatched_regional_attributes: tuple[str, ...]
    inherited_claim_ids: tuple[str, ...]
    overridden_claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_enum("reason_code", self.reason_code, ResolutionReasonCode)
        _validate_text("summary", self.summary)
        _validate_semantic_version("algorithm_version", self.algorithm_version)
        for name, values in (
            ("candidate_profile_ids", self.candidate_profile_ids),
            ("evidence_source_ids", self.evidence_source_ids),
            ("inherited_claim_ids", self.inherited_claim_ids),
            ("overridden_claim_ids", self.overridden_claim_ids),
        ):
            _validate_id_tuple(name, values)
        for name, values in (
            ("matched_regional_attributes", self.matched_regional_attributes),
            ("unavailable_regional_attributes", self.unavailable_regional_attributes),
            ("mismatched_regional_attributes", self.mismatched_regional_attributes),
        ):
            _validate_sorted_unique_text(name, values)


@dataclass(frozen=True, slots=True)
class PlantKnowledgeResolution(SerializableKnowledgeModel):
    """Complete deterministic profile-resolution result."""

    request_id: str
    selected_profile_id: str | None
    selected_resolution_level: ProfileResolutionLevel | None
    candidates: tuple[PlantKnowledgeResolutionCandidate, ...]
    matched_aliases: tuple[str, ...]
    fallback_chain: tuple[ProfileResolutionLevel, ...]
    profile_inheritance_chain: tuple[str, ...]
    effective_claims: tuple[EffectivePlantKnowledgeClaim, ...]
    claim_traces: tuple[InheritedClaimTrace, ...]
    resolution_confidence: float
    unresolved_ambiguity: bool
    suggested_verification_action: str | None
    reason_code: ResolutionReasonCode
    explanation: PlantKnowledgeExplanation
    algorithm_version: str

    def __post_init__(self) -> None:
        _validate_canonical_id("request_id", self.request_id)
        if self.selected_profile_id is not None:
            _validate_canonical_id("selected_profile_id", self.selected_profile_id)
        if self.selected_resolution_level is not None:
            _validate_enum(
                "selected_resolution_level",
                self.selected_resolution_level,
                ProfileResolutionLevel,
            )
        if (self.selected_profile_id is None) != (self.selected_resolution_level is None):
            raise ValueError("selected profile ID and resolution level must be present together")
        _validate_tuple("candidates", self.candidates)
        if any(not isinstance(item, PlantKnowledgeResolutionCandidate) for item in self.candidates):
            raise ValueError("candidates must contain canonical candidate records")
        candidate_ids = tuple(item.profile_id for item in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("resolution candidates must have unique profile IDs")
        if candidate_ids != tuple(sorted(candidate_ids)):
            raise ValueError("resolution candidates must use canonical-ID ordering")
        _validate_sorted_unique_text("matched_aliases", self.matched_aliases)
        _validate_tuple("fallback_chain", self.fallback_chain)
        if any(not isinstance(item, ProfileResolutionLevel) for item in self.fallback_chain):
            raise ValueError("fallback_chain must contain canonical resolution levels")
        fallback_values = [item.value for item in self.fallback_chain]
        if len(fallback_values) != len(set(fallback_values)):
            raise ValueError("fallback chain must not contain duplicates")
        _validate_unique_id_tuple("profile_inheritance_chain", self.profile_inheritance_chain)
        _validate_tuple("effective_claims", self.effective_claims)
        if any(
            not isinstance(item, EffectivePlantKnowledgeClaim) for item in self.effective_claims
        ):
            raise ValueError("effective_claims must contain canonical effective claims")
        effective_fields = tuple(item.field_path for item in self.effective_claims)
        if len(effective_fields) != len(set(effective_fields)):
            raise ValueError("effective_claims must have unique field paths")
        if effective_fields != tuple(sorted(effective_fields)):
            raise ValueError("effective_claims must use canonical field-path ordering")
        _validate_tuple("claim_traces", self.claim_traces)
        if any(not isinstance(item, InheritedClaimTrace) for item in self.claim_traces):
            raise ValueError("claim_traces must contain canonical trace records")
        _validate_confidence(self.resolution_confidence)
        _validate_boolean("unresolved_ambiguity", self.unresolved_ambiguity)
        _validate_enum("reason_code", self.reason_code, ResolutionReasonCode)
        if self.suggested_verification_action is not None:
            _validate_text("suggested_verification_action", self.suggested_verification_action)
        _validate_semantic_version("algorithm_version", self.algorithm_version)
        if self.explanation.algorithm_version != self.algorithm_version:
            raise ValueError("explanation algorithm version must match resolution")
        if self.explanation.reason_code is not self.reason_code:
            raise ValueError("explanation reason code must match resolution")
