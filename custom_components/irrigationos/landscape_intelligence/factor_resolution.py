"""Deterministic advisory landscape-factor resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .models import EstablishmentState, IrrigationRole, LandscapeIntelligenceProfile

FACTOR_RESOLUTION_ALGORITHM_VERSION = "1.1.0"


class EvidenceClass(StrEnum):
    """Evidence classes in descending directness for landscape demand."""

    LANDSCAPE_PLANT_FACTOR = "landscape_plant_factor"
    URBAN_HORTICULTURE = "urban_horticulture"
    AGRICULTURAL_CROP_COEFFICIENT = "agricultural_crop_coefficient"
    QUALITATIVE_HORTICULTURE = "qualitative_horticulture"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


class FactorResolutionStatus(StrEnum):
    """Whether a factor is safe to admit into quantitative accounting."""

    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    UNRESOLVED = "unresolved"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class FactorRange:
    """A source-supported factor range; no midpoint is synthesized."""

    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not 0 <= self.minimum <= self.maximum <= 2:
            raise ValueError("factor range must be ordered and within 0..2")

    def to_dict(self) -> dict[str, float]:
        return {"minimum": self.minimum, "maximum": self.maximum}


@dataclass(frozen=True, slots=True)
class PlantFactorEvidence:
    """Reviewed evidence attached to one commissioned plant group."""

    plant_group_id: str
    evidence_class: EvidenceClass
    factor: float | FactorRange | None
    water_use_class: str | None
    source_id: str
    source_title: str
    source_url: str
    confidence: str
    authoritative_for_landscape_factor: bool
    notes: str

    def __post_init__(self) -> None:
        if not self.plant_group_id or not self.source_id:
            raise ValueError("factor evidence identity is required")
        if isinstance(self.factor, float) and not 0 <= self.factor <= 2:
            raise ValueError("factor must be within 0..2")
        if self.authoritative_for_landscape_factor and self.factor is None:
            raise ValueError("authoritative evidence requires a numeric factor")
        if (
            self.evidence_class is EvidenceClass.AGRICULTURAL_CROP_COEFFICIENT
            and self.authoritative_for_landscape_factor
        ):
            raise ValueError("agricultural Kc cannot directly authorize landscape PF")

    def to_dict(self) -> dict[str, Any]:
        factor: float | dict[str, float] | None = (
            self.factor.to_dict() if isinstance(self.factor, FactorRange) else self.factor
        )
        return {
            "plant_group_id": self.plant_group_id,
            "evidence_class": self.evidence_class.value,
            "factor": factor,
            "water_use_class": self.water_use_class,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "authoritative_for_landscape_factor": self.authoritative_for_landscape_factor,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class PlantGroupFactorResolution:
    """Factor-resolution result for one commissioned plant group."""

    plant_group_id: str
    status: FactorResolutionStatus
    admitted_factor: float | FactorRange | None
    evidence_class: EvidenceClass
    blocker_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    controls_zone_demand: bool

    def to_dict(self) -> dict[str, Any]:
        factor: float | dict[str, float] | None
        if isinstance(self.admitted_factor, FactorRange):
            factor = self.admitted_factor.to_dict()
        else:
            factor = self.admitted_factor
        return {
            "plant_group_id": self.plant_group_id,
            "status": self.status.value,
            "admitted_factor": factor,
            "evidence_class": self.evidence_class.value,
            "blocker_codes": list(self.blocker_codes),
            "source_ids": list(self.source_ids),
            "controls_zone_demand": self.controls_zone_demand,
        }


@dataclass(frozen=True, slots=True)
class ZoneFactorResolution:
    """Advisory mixed-hydrozone factor resolution."""

    algorithm_version: str
    area_slot: int
    status: FactorResolutionStatus
    plant_factor: float | FactorRange | None
    controlling_group_id: str | None
    group_resolutions: tuple[PlantGroupFactorResolution, ...]
    blocker_codes: tuple[str, ...]
    density_factor_status: str
    microclimate_factor_status: str
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("factor resolution is advisory only")
        if self.status is FactorResolutionStatus.RESOLVED and self.plant_factor is None:
            raise ValueError("resolved zone requires a plant factor")

    def to_dict(self) -> dict[str, Any]:
        factor: float | dict[str, float] | None
        if isinstance(self.plant_factor, FactorRange):
            factor = self.plant_factor.to_dict()
        else:
            factor = self.plant_factor
        return {
            "algorithm_version": self.algorithm_version,
            "area_slot": self.area_slot,
            "status": self.status.value,
            "plant_factor": factor,
            "controlling_group_id": self.controlling_group_id,
            "group_resolutions": [item.to_dict() for item in self.group_resolutions],
            "blocker_codes": list(self.blocker_codes),
            "density_factor_status": self.density_factor_status,
            "microclimate_factor_status": self.microclimate_factor_status,
            "execution_authorized": False,
            "live_control_authorized": False,
        }


def resolve_zone_factor(
    profile: LandscapeIntelligenceProfile,
    evidence: tuple[PlantFactorEvidence, ...],
) -> ZoneFactorResolution:
    """Resolve only directly admissible evidence; never invent missing precision."""
    by_group: dict[str, list[PlantFactorEvidence]] = {}
    for item in evidence:
        by_group.setdefault(item.plant_group_id, []).append(item)

    results: list[PlantGroupFactorResolution] = []
    for group in profile.plant_groups:
        if group.irrigation_role is IrrigationRole.INCIDENTAL:
            results.append(
                PlantGroupFactorResolution(
                    group.plant_group_id,
                    FactorResolutionStatus.EXCLUDED,
                    None,
                    EvidenceClass.UNKNOWN,
                    (),
                    (),
                    False,
                )
            )
            continue

        candidates = by_group.get(group.plant_group_id, [])
        authoritative = next(
            (item for item in candidates if item.authoritative_for_landscape_factor), None
        )
        group_blockers: list[str] = []
        admitted: float | FactorRange | None = None
        status = FactorResolutionStatus.UNRESOLVED
        evidence_class = EvidenceClass.UNKNOWN
        source_ids = tuple(item.source_id for item in candidates)
        if authoritative is not None:
            admitted = authoritative.factor
            evidence_class = authoritative.evidence_class
            status = FactorResolutionStatus.RESOLVED
        elif candidates:
            evidence_class = candidates[0].evidence_class
            status = FactorResolutionStatus.PARTIALLY_RESOLVED
            group_blockers.append("plant_group_factor_unresolved")
        else:
            group_blockers.append("plant_group_factor_unresolved")

        if group.establishment_state in {
            EstablishmentState.NEWLY_PLANTED,
            EstablishmentState.ESTABLISHING,
        }:
            # Keep any source-supported baseline PF, but do not pretend that the
            # establishment-stage irrigation management policy is resolved.
            status = FactorResolutionStatus.PARTIALLY_RESOLVED
            group_blockers.append("establishment_management_unresolved")

        results.append(
            PlantGroupFactorResolution(
                group.plant_group_id,
                status,
                admitted,
                evidence_class,
                tuple(sorted(set(group_blockers))),
                source_ids,
                True,
            )
        )

    admitted_candidates = [
        item
        for item in results
        if item.controls_zone_demand and item.admitted_factor is not None
    ]
    unresolved_factor_controllers = [
        item
        for item in results
        if item.controls_zone_demand and item.admitted_factor is None
    ]
    zone_blockers: set[str] = {code for item in results for code in item.blocker_codes}
    if unresolved_factor_controllers:
        zone_blockers.add("hydrozone_controlling_group_unresolved")

    # Plant Factor v2 does not synthesize a density coefficient. UC landscape
    # guidance uses projected canopy/planted area separately from PF; geometry
    # belongs to a future quantitative area/delivery model.
    density_factor_status = "not_required_for_plant_factor_v2"

    # A zone PF is admitted only when every controlling group has an admitted
    # factor. Establishment-management blockers may still keep the overall zone
    # partially resolved even when the baseline PF is known.
    if unresolved_factor_controllers or not admitted_candidates:
        status = (
            FactorResolutionStatus.PARTIALLY_RESOLVED
            if admitted_candidates
            else FactorResolutionStatus.UNRESOLVED
        )
        plant_factor = None
        controlling_group_id = None
    else:
        scalar_candidates = [
            (item, item.admitted_factor)
            for item in admitted_candidates
            if isinstance(item.admitted_factor, float)
        ]
        if len(scalar_candidates) != len(admitted_candidates):
            status = FactorResolutionStatus.PARTIALLY_RESOLVED
            plant_factor = None
            controlling_group_id = None
            zone_blockers.add("hydrozone_controlling_group_unresolved")
        else:
            controlling, plant_factor = max(
                scalar_candidates,
                key=lambda candidate: candidate[1],
            )
            controlling_group_id = controlling.plant_group_id
            status = (
                FactorResolutionStatus.PARTIALLY_RESOLVED
                if zone_blockers
                else FactorResolutionStatus.RESOLVED
            )

    return ZoneFactorResolution(
        FACTOR_RESOLUTION_ALGORITHM_VERSION,
        profile.area_slot,
        status,
        plant_factor,
        controlling_group_id,
        tuple(results),
        tuple(sorted(zone_blockers)),
        density_factor_status,
        "not_required_for_plant_factor_v2",
    )
