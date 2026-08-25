"""Pure mapping from approved onboarding inputs to commissioned zone knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .commissioning import (
    ZONE_COMMISSIONING_SCHEMA_VERSION,
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    CommissioningConflictCandidate,
    CommissioningEvidenceConflict,
    CommissioningEvidenceSource,
    DeliveryLinkStatus,
    IrrigationDeliveryLink,
    LandscapeChangeEvent,
    LandscapeEventType,
    LandscapePlantSnapshot,
    PlantCommissioningDetails,
    UserCalibratedBaseline,
    ZoneDemandSource,
    ZoneDemandSourceMode,
)
from .models import (
    Confidence,
    EstablishmentState,
    HydrozoneQuality,
    HydrozoneType,
    IrrigationRole,
    LandscapeIntelligenceProfile,
    PlantGroup,
)


@dataclass(frozen=True, slots=True)
class ManualPlantOnboardingInput:
    """User-confirmed plant facts accepted without photo evidence."""

    plant_group_id: str
    common_name: str
    botanical_name: str | None
    establishment_state: EstablishmentState
    observed_at: datetime
    planted_at: datetime | None = None
    source_container_gallons: float | None = None
    current_height_meters: float | None = None
    irrigation_role: IrrigationRole = IrrigationRole.PRIMARY_TARGET
    direct_irrigation: bool = True
    dedicated_emitter: bool = False
    emitter_type: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("plant_group_id", self.plant_group_id),
            ("common_name", self.common_name),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank text")
        for optional_name, optional_value in (
            ("botanical_name", self.botanical_name),
            ("emitter_type", self.emitter_type),
        ):
            if optional_value is not None and (
                not isinstance(optional_value, str) or not optional_value.strip()
            ):
                raise ValueError(
                    f"{optional_name} must be nonblank text when supplied"
                )


@dataclass(frozen=True, slots=True)
class ApprovedVisualPlantFinding:
    """Approved provider-neutral structured finding; never raw image content."""

    plant_group_id: str
    assessment_id: str
    evidence_ids: tuple[str, ...]
    likely_common_name: str
    likely_botanical_name: str | None
    confidence: Confidence
    establishment_state: EstablishmentState
    approved_at: datetime
    irrigation_role: IrrigationRole = IrrigationRole.PRIMARY_TARGET
    visible_irrigation_method: str | None = None
    delivery_profile_id: str | None = None
    delivery_component_ids: tuple[str, ...] = ()
    dedicated_delivery: bool | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("plant_group_id", self.plant_group_id),
            ("assessment_id", self.assessment_id),
            ("likely_common_name", self.likely_common_name),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank text")
        if any(not isinstance(value, str) or not value for value in self.evidence_ids):
            raise ValueError("evidence_ids must contain stable text identifiers")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must not contain duplicates")
        if self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")
        if self.likely_botanical_name is not None and (
            not isinstance(self.likely_botanical_name, str)
            or not self.likely_botanical_name.strip()
        ):
            raise ValueError("likely_botanical_name must be nonblank text when supplied")


@dataclass(frozen=True, slots=True)
class ZoneOnboardingRequest:
    """Complete typed input for one generic onboarding operation."""

    identity: CanonicalZoneIdentity
    display_name: str
    mode: ZoneDemandSourceMode
    observed_at: datetime
    manual_plants: tuple[ManualPlantOnboardingInput, ...] = ()
    visual_findings: tuple[ApprovedVisualPlantFinding, ...] = ()
    calibrated_baseline: UserCalibratedBaseline | None = None
    delivery_links: tuple[IrrigationDeliveryLink, ...] = ()


@dataclass(frozen=True, slots=True)
class PlantRemovalInput:
    """Structured request to remove one current plant group."""

    event_id: str
    plant_group_id: str
    effective_at: datetime


@dataclass(frozen=True, slots=True)
class PlantAdditionInput:
    """Structured request to add one user-confirmed plant group."""

    event_id: str
    plant: ManualPlantOnboardingInput
    effective_at: datetime
    delivery_link: IrrigationDeliveryLink | None = None


def _manual_group(value: ManualPlantOnboardingInput) -> PlantGroup:
    return PlantGroup(
        plant_group_id=value.plant_group_id,
        common_name=value.common_name,
        botanical_name=value.botanical_name,
        identification_confidence=Confidence.HIGH,
        irrigation_role=value.irrigation_role,
        establishment_state=value.establishment_state,
        direct_irrigation=value.direct_irrigation,
        dedicated_emitter=value.dedicated_emitter,
        emitter_type=value.emitter_type,
        controls_zone_demand=(
            False if value.irrigation_role is IrrigationRole.INCIDENTAL else None
        ),
    )


def _visual_group(value: ApprovedVisualPlantFinding) -> PlantGroup:
    return PlantGroup(
        plant_group_id=value.plant_group_id,
        common_name=value.likely_common_name,
        botanical_name=value.likely_botanical_name,
        identification_confidence=value.confidence,
        irrigation_role=value.irrigation_role,
        establishment_state=value.establishment_state,
        direct_irrigation=value.visible_irrigation_method is not None,
        dedicated_emitter=value.dedicated_delivery is True,
        emitter_type=value.visible_irrigation_method,
        controls_zone_demand=(
            False if value.irrigation_role is IrrigationRole.INCIDENTAL else None
        ),
    )


def _manual_details(value: ManualPlantOnboardingInput) -> PlantCommissioningDetails:
    return PlantCommissioningDetails(
        plant_group_id=value.plant_group_id,
        source=CommissioningEvidenceSource.USER_CONFIRMED,
        confidence=Confidence.HIGH,
        observed_at=value.observed_at,
        planted_at=value.planted_at,
        source_container_gallons=value.source_container_gallons,
        current_height_meters=value.current_height_meters,
    )


def _visual_details(value: ApprovedVisualPlantFinding) -> PlantCommissioningDetails:
    return PlantCommissioningDetails(
        plant_group_id=value.plant_group_id,
        source=CommissioningEvidenceSource.AI_INFERRED,
        confidence=value.confidence,
        observed_at=value.approved_at,
        structured_evidence_ids=value.evidence_ids,
    )


def _visual_link(value: ApprovedVisualPlantFinding) -> IrrigationDeliveryLink:
    if value.delivery_profile_id is None:
        return IrrigationDeliveryLink(
            link_id=f"{value.plant_group_id}.delivery",
            plant_group_id=value.plant_group_id,
            status=DeliveryLinkStatus.UNRESOLVED,
        )
    return IrrigationDeliveryLink(
        link_id=f"{value.plant_group_id}.delivery",
        plant_group_id=value.plant_group_id,
        status=DeliveryLinkStatus.REVIEW_REQUIRED,
        delivery_profile_id=value.delivery_profile_id,
        component_ids=value.delivery_component_ids,
        dedicated_delivery=value.dedicated_delivery,
    )


def _identity_conflict(
    manual: ManualPlantOnboardingInput,
    visual: ApprovedVisualPlantFinding,
) -> CommissioningEvidenceConflict | None:
    manual_value = manual.botanical_name or manual.common_name
    visual_value = visual.likely_botanical_name or visual.likely_common_name
    if manual_value.strip().casefold() == visual_value.strip().casefold():
        return None
    return CommissioningEvidenceConflict(
        conflict_id=f"{manual.plant_group_id}.conflict.identity",
        plant_group_id=manual.plant_group_id,
        field_path="plant.identity",
        candidates=(
            CommissioningConflictCandidate(
                CommissioningEvidenceSource.USER_CONFIRMED,
                manual_value,
                Confidence.HIGH,
            ),
            CommissioningConflictCandidate(
                CommissioningEvidenceSource.AI_INFERRED,
                visual_value,
                visual.confidence,
                visual.evidence_ids,
            ),
        ),
        detail="User-confirmed and structured visual plant identities disagree.",
    )


def map_zone_onboarding(request: ZoneOnboardingRequest) -> CommissionedZoneProfile:
    """Normalize one onboarding request without inference, scaling, or authority."""
    manual_by_id = {item.plant_group_id: item for item in request.manual_plants}
    visual_by_id = {item.plant_group_id: item for item in request.visual_findings}
    if len(manual_by_id) != len(request.manual_plants):
        raise ValueError("manual plant identities must be unique")
    if len(visual_by_id) != len(request.visual_findings):
        raise ValueError("visual plant identities must be unique")

    all_ids = tuple(sorted(set(manual_by_id) | set(visual_by_id)))
    groups: list[PlantGroup] = []
    details: list[PlantCommissioningDetails] = []
    conflicts: list[CommissioningEvidenceConflict] = []
    for plant_group_id in all_ids:
        manual = manual_by_id.get(plant_group_id)
        visual = visual_by_id.get(plant_group_id)
        if manual is not None:
            groups.append(_manual_group(manual))
            details.append(_manual_details(manual))
        elif visual is not None:
            groups.append(_visual_group(visual))
            details.append(_visual_details(visual))
        if manual is not None and visual is not None:
            conflict = _identity_conflict(manual, visual)
            if conflict is not None:
                conflicts.append(conflict)

    assessment_ids = tuple(
        sorted({item.assessment_id for item in request.visual_findings})
    )
    source = ZoneDemandSource(
        source_id=f"{request.identity.zone_id}.source.{request.mode.value}",
        mode=request.mode,
        plant_group_ids=all_ids,
        structured_visual_assessment_ids=assessment_ids,
        calibrated_baseline=request.calibrated_baseline,
    )

    supplied_links = {item.plant_group_id: item for item in request.delivery_links}
    if len(supplied_links) != len(request.delivery_links):
        raise ValueError("delivery-link plant identities must be unique")
    links: list[IrrigationDeliveryLink] = []
    for plant_group_id in all_ids:
        link = supplied_links.get(plant_group_id)
        if link is None and plant_group_id in visual_by_id:
            link = _visual_link(visual_by_id[plant_group_id])
        if link is None:
            link = IrrigationDeliveryLink(
                link_id=f"{plant_group_id}.delivery",
                plant_group_id=plant_group_id,
                status=DeliveryLinkStatus.UNRESOLVED,
            )
        links.append(link)

    hydrozone_type = (
        HydrozoneType.UNRESOLVED
        if not groups
        else HydrozoneType.UNIFORM
        if len(groups) == 1
        else HydrozoneType.MIXED
    )
    emitter_types = {group.emitter_type for group in groups if group.emitter_type}
    irrigation_method = (
        next(iter(emitter_types)) if len(emitter_types) == 1 else "unresolved"
    )
    landscape = LandscapeIntelligenceProfile(
        schema_version=1,
        area_slot=request.identity.area_slot,
        profile_status="onboarded",
        hydrozone_type=hydrozone_type,
        hydrozone_quality=HydrozoneQuality.UNRESOLVED,
        irrigation_method=irrigation_method,
        emitter_family=irrigation_method,
        predominant_radius_ft=None,
        predominant_emitter_color=None,
        application_rate_status="unresolved",
        plant_groups=tuple(groups),
        health_observations=(),
        plant_factor_status="unresolved",
        landscape_factor_status="unresolved",
    )
    return CommissionedZoneProfile(
        schema_version=ZONE_COMMISSIONING_SCHEMA_VERSION,
        identity=request.identity,
        display_name=request.display_name,
        landscape_profile=landscape,
        plant_details=tuple(details),
        demand_sources=(source,),
        delivery_links=tuple(links),
        conflicts=tuple(conflicts),
    )


def _updated_source(
    source: ZoneDemandSource,
    removed_ids: set[str],
) -> ZoneDemandSource | None:
    plant_ids = tuple(item for item in source.plant_group_ids if item not in removed_ids)
    has_plants = bool(plant_ids)
    has_visual = bool(source.structured_visual_assessment_ids)
    has_baseline = source.calibrated_baseline is not None
    kind_count = sum((has_plants, has_visual, has_baseline))
    if kind_count == 0:
        return ZoneDemandSource(
            source.source_id,
            ZoneDemandSourceMode.UNRESOLVED,
        )
    if kind_count >= 2:
        mode = ZoneDemandSourceMode.HYBRID
    elif has_visual:
        mode = ZoneDemandSourceMode.PHOTO_AI_DERIVED
    elif has_baseline:
        mode = ZoneDemandSourceMode.USER_CALIBRATED_BASELINE
    else:
        mode = ZoneDemandSourceMode.MANUAL_PLANT_PROFILE
    return ZoneDemandSource(
        source.source_id,
        mode,
        plant_ids,
        source.structured_visual_assessment_ids,
        source.calibrated_baseline,
    )


def map_landscape_changes(
    profile: CommissionedZoneProfile,
    *,
    removals: tuple[PlantRemovalInput, ...] = (),
    additions: tuple[PlantAdditionInput, ...] = (),
) -> CommissionedZoneProfile:
    """Apply immutable add/remove inputs while retaining event snapshots."""
    groups = {item.plant_group_id: item for item in profile.landscape_profile.plant_groups}
    details = {item.plant_group_id: item for item in profile.plant_details}
    links = {item.plant_group_id: item for item in profile.delivery_links}
    events = list(profile.landscape_events)
    removed_ids: set[str] = set()

    for removal in removals:
        group = groups.get(removal.plant_group_id)
        detail = details.get(removal.plant_group_id)
        if group is None or detail is None:
            raise ValueError("cannot remove an unknown current plant group")
        events.append(
            LandscapeChangeEvent(
                removal.event_id,
                LandscapeEventType.PLANT_GROUP_REMOVED,
                removal.effective_at,
                LandscapePlantSnapshot(group, detail),
            )
        )
        removed_ids.add(removal.plant_group_id)
        groups.pop(removal.plant_group_id)
        details.pop(removal.plant_group_id)
        links.pop(removal.plant_group_id, None)

    sources = tuple(
        updated
        for source in profile.demand_sources
        if (updated := _updated_source(source, removed_ids)) is not None
    )
    for addition in additions:
        group = _manual_group(addition.plant)
        detail = _manual_details(addition.plant)
        if group.plant_group_id in groups:
            raise ValueError("cannot add an existing plant group")
        groups[group.plant_group_id] = group
        details[group.plant_group_id] = detail
        link = addition.delivery_link or IrrigationDeliveryLink(
            f"{group.plant_group_id}.delivery",
            group.plant_group_id,
            DeliveryLinkStatus.UNRESOLVED,
        )
        links[group.plant_group_id] = link
        sources = (
            *(source for source in sources if source.mode is not ZoneDemandSourceMode.UNRESOLVED),
            ZoneDemandSource(
                f"{addition.event_id}.source.manual",
                ZoneDemandSourceMode.MANUAL_PLANT_PROFILE,
                (group.plant_group_id,),
            ),
        )
        events.append(
            LandscapeChangeEvent(
                addition.event_id,
                LandscapeEventType.PLANT_GROUP_ADDED,
                addition.effective_at,
                LandscapePlantSnapshot(group, detail),
            )
        )
    ordered_groups = tuple(groups[key] for key in sorted(groups))
    landscape = profile.landscape_profile
    updated_landscape = LandscapeIntelligenceProfile(
        landscape.schema_version,
        landscape.area_slot,
        landscape.profile_status,
        (
            HydrozoneType.UNRESOLVED
            if not ordered_groups
            else HydrozoneType.UNIFORM
            if len(ordered_groups) == 1
            else HydrozoneType.MIXED
        ),
        HydrozoneQuality.UNRESOLVED,
        landscape.irrigation_method,
        landscape.emitter_family,
        landscape.predominant_radius_ft,
        landscape.predominant_emitter_color,
        landscape.application_rate_status,
        ordered_groups,
        tuple(
            observation
            for observation in landscape.health_observations
            if observation.plant_group_id in groups
        ),
        "unresolved",
        "unresolved",
    )
    retained_conflicts = tuple(
        conflict
        for conflict in profile.conflicts
        if conflict.plant_group_id in groups
    )
    retained_conflict_ids = {conflict.conflict_id for conflict in retained_conflicts}
    return CommissionedZoneProfile(
        schema_version=ZONE_COMMISSIONING_SCHEMA_VERSION,
        identity=profile.identity,
        display_name=profile.display_name,
        landscape_profile=updated_landscape,
        plant_details=tuple(details[key] for key in sorted(details)),
        demand_sources=tuple(sorted(sources, key=lambda source: source.source_id)),
        delivery_links=tuple(links[key] for key in sorted(links)),
        landscape_events=tuple(
            sorted(
                events,
                key=lambda event: (
                    event.effective_at,
                    0
                    if event.event_type is LandscapeEventType.PLANT_GROUP_REMOVED
                    else 1,
                    event.event_id,
                ),
            )
        ),
        conflicts=retained_conflicts,
        conflict_resolutions=tuple(
            resolution
            for resolution in profile.conflict_resolutions
            if resolution.conflict_id in retained_conflict_ids
        ),
    )
