"""Pure review and editing operations for generic commissioned zones."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from ..water_delivery import WaterDeliveryProfile
from .admission import CommissioningAssessment, assess_commissioning
from .baseline_scaling import BaselineEnvironmentalScalingAssessment
from .commissioning import (
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    CommissioningConflictResolution,
    CommissioningEvidenceConflict,
    CommissioningEvidenceSource,
    DeliveryAdvisory,
    IrrigationDeliveryLink,
    LandscapeChangeEvent,
    LandscapeEventType,
    LandscapePlantSnapshot,
    LandscapeSetupSnapshot,
    PlantCommissioningDetails,
    SerializableCommissioningModel,
    UserCalibratedBaseline,
    ZoneDemandSource,
    ZoneDemandSourceMode,
    assess_delivery_compatibility,
)
from .models import (
    Confidence,
    HydrozoneQuality,
    HydrozoneType,
    IrrigationRole,
    LandscapeIntelligenceProfile,
    PlantGroup,
)
from .onboarding import (
    ManualPlantOnboardingInput,
    PlantAdditionInput,
    PlantRemovalInput,
    map_landscape_changes,
)


@dataclass(frozen=True, slots=True)
class PlantEditInput:
    """Explicit user-confirmed replacement facts for one current plant group."""

    event_id: str
    plant: ManualPlantOnboardingInput
    effective_at: datetime


@dataclass(frozen=True, slots=True)
class ConflictResolutionInput:
    """Explicit human correction of one preserved commissioning conflict."""

    resolution_id: str
    event_id: str
    conflict_id: str
    confirmed_common_name: str
    confirmed_botanical_name: str | None
    resolved_at: datetime
    confidence: Confidence = Confidence.HIGH
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CommissionedPlantReview(SerializableCommissioningModel):
    """One active plant with its provenance and delivery relationship."""

    plant_group: PlantGroup
    commissioning_details: PlantCommissioningDetails
    delivery_link: IrrigationDeliveryLink | None


@dataclass(frozen=True, slots=True)
class CommissionedZoneReview(SerializableCommissioningModel):
    """Detailed bounded review model kept outside Recorder-facing state."""

    identity: CanonicalZoneIdentity
    display_name: str
    plants: tuple[CommissionedPlantReview, ...]
    demand_source_modes: tuple[ZoneDemandSourceMode, ...]
    calibrated_baselines: tuple[UserCalibratedBaseline, ...]
    structured_visual_assessment_ids: tuple[str, ...]
    unresolved_conflicts: tuple[CommissioningEvidenceConflict, ...]
    conflict_resolutions: tuple[CommissioningConflictResolution, ...]
    advisories: tuple[DeliveryAdvisory, ...]
    recent_landscape_events: tuple[LandscapeChangeEvent, ...]
    commissioning_assessment: CommissioningAssessment
    baseline_scaling_assessment: BaselineEnvironmentalScalingAssessment | None = None
    execution_authorized: bool = False
    live_control_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized or self.live_control_authorized:
            raise ValueError("commissioning review is advisory only")


def _current_maps(
    profile: CommissionedZoneProfile,
) -> tuple[
    dict[str, PlantGroup],
    dict[str, PlantCommissioningDetails],
    dict[str, IrrigationDeliveryLink],
]:
    return (
        {item.plant_group_id: item for item in profile.landscape_profile.plant_groups},
        {item.plant_group_id: item for item in profile.plant_details},
        {item.plant_group_id: item for item in profile.delivery_links},
    )


def _rebuild_plant_profile(
    profile: CommissionedZoneProfile,
    *,
    groups: dict[str, PlantGroup],
    details: dict[str, PlantCommissioningDetails],
    events: tuple[LandscapeChangeEvent, ...],
    conflicts: tuple[CommissioningEvidenceConflict, ...] | None = None,
    resolutions: tuple[CommissioningConflictResolution, ...] | None = None,
) -> CommissionedZoneProfile:
    ordered_groups = tuple(groups[key] for key in sorted(groups))
    landscape = profile.landscape_profile
    updated_landscape = LandscapeIntelligenceProfile(
        schema_version=landscape.schema_version,
        area_slot=landscape.area_slot,
        profile_status=landscape.profile_status,
        hydrozone_type=(
            HydrozoneType.UNRESOLVED
            if not ordered_groups
            else HydrozoneType.UNIFORM
            if len(ordered_groups) == 1
            else HydrozoneType.MIXED
        ),
        hydrozone_quality=HydrozoneQuality.UNRESOLVED,
        irrigation_method=landscape.irrigation_method,
        emitter_family=landscape.emitter_family,
        predominant_radius_ft=landscape.predominant_radius_ft,
        predominant_emitter_color=landscape.predominant_emitter_color,
        application_rate_status=landscape.application_rate_status,
        plant_groups=ordered_groups,
        health_observations=tuple(
            item
            for item in landscape.health_observations
            if item.plant_group_id in groups
        ),
        plant_factor_status="unresolved",
        landscape_factor_status="unresolved",
    )
    return replace(
        profile,
        landscape_profile=updated_landscape,
        plant_details=tuple(details[key] for key in sorted(details)),
        landscape_events=tuple(
            sorted(
                events,
                key=lambda event: (
                    event.effective_at,
                    {
                        LandscapeEventType.PLANT_GROUP_REMOVED: 0,
                        LandscapeEventType.PLANT_GROUP_ADDED: 1,
                        LandscapeEventType.PLANT_GROUP_UPDATED: 2,
                        LandscapeEventType.ZONE_RECOMMISSIONED: 3,
                    }[event.event_type],
                    event.event_id,
                ),
            )
        ),
        conflicts=profile.conflicts if conflicts is None else conflicts,
        conflict_resolutions=(
            profile.conflict_resolutions if resolutions is None else resolutions
        ),
        execution_authorized=False,
        live_control_authorized=False,
    )


def build_commissioning_review(
    profile: CommissionedZoneProfile,
    *,
    recent_event_limit: int = 10,
    baseline_scaling_assessment: BaselineEnvironmentalScalingAssessment | None = None,
    delivery_profiles: tuple[WaterDeliveryProfile, ...] = (),
) -> CommissionedZoneReview:
    """Build one bounded deterministic review without mutating evidence."""
    if not 1 <= recent_event_limit <= 20:
        raise ValueError("recent_event_limit must be between 1 and 20")
    groups, details, links = _current_maps(profile)
    resolved_ids = {
        resolution.conflict_id for resolution in profile.conflict_resolutions
    }
    compatibility = assess_delivery_compatibility(profile, delivery_profiles)
    visual_ids = tuple(
        sorted(
            {
                assessment_id
                for source in profile.demand_sources
                for assessment_id in source.structured_visual_assessment_ids
            }
        )
    )
    return CommissionedZoneReview(
        identity=profile.identity,
        display_name=profile.display_name,
        plants=tuple(
            CommissionedPlantReview(groups[key], details[key], links.get(key))
            for key in sorted(groups)
        ),
        demand_source_modes=tuple(
            sorted({source.mode for source in profile.demand_sources}, key=str)
        ),
        calibrated_baselines=tuple(
            source.calibrated_baseline
            for source in profile.demand_sources
            if source.calibrated_baseline is not None
        ),
        structured_visual_assessment_ids=visual_ids,
        unresolved_conflicts=tuple(
            conflict
            for conflict in profile.conflicts
            if conflict.conflict_id not in resolved_ids
        ),
        conflict_resolutions=profile.conflict_resolutions,
        advisories=compatibility.advisories,
        recent_landscape_events=profile.landscape_events[-recent_event_limit:],
        commissioning_assessment=assess_commissioning(profile),
        baseline_scaling_assessment=baseline_scaling_assessment,
    )


def add_plant_group(
    profile: CommissionedZoneProfile,
    addition: PlantAdditionInput,
) -> CommissionedZoneProfile:
    """Add one plant and immutable addition event through existing semantics."""
    return map_landscape_changes(profile, additions=(addition,))


def remove_plant_group(
    profile: CommissionedZoneProfile,
    removal: PlantRemovalInput,
) -> CommissionedZoneProfile:
    """Remove one active plant while preserving its complete historical snapshot."""
    return map_landscape_changes(profile, removals=(removal,))


def edit_plant_group(
    profile: CommissionedZoneProfile,
    edit: PlantEditInput,
) -> CommissionedZoneProfile:
    """Replace scientifically relevant facts and retain the previous snapshot."""
    groups, details, _links = _current_maps(profile)
    plant_id = edit.plant.plant_group_id
    prior_group = groups.get(plant_id)
    prior_details = details.get(plant_id)
    if prior_group is None or prior_details is None:
        raise ValueError("cannot edit an unknown current plant group")
    updated_group = replace(
        prior_group,
        common_name=edit.plant.common_name,
        botanical_name=edit.plant.botanical_name,
        identification_confidence=Confidence.HIGH,
        irrigation_role=edit.plant.irrigation_role,
        establishment_state=edit.plant.establishment_state,
        direct_irrigation=edit.plant.direct_irrigation,
        dedicated_emitter=edit.plant.dedicated_emitter,
        emitter_type=edit.plant.emitter_type,
        controls_zone_demand=(
            False
            if edit.plant.irrigation_role is IrrigationRole.INCIDENTAL
            else prior_group.controls_zone_demand
        ),
    )
    updated_details = PlantCommissioningDetails(
        plant_group_id=plant_id,
        source=CommissioningEvidenceSource.USER_CONFIRMED,
        confidence=Confidence.HIGH,
        observed_at=edit.plant.observed_at,
        planted_at=edit.plant.planted_at,
        source_container_gallons=edit.plant.source_container_gallons,
        current_height_meters=edit.plant.current_height_meters,
        structured_evidence_ids=prior_details.structured_evidence_ids,
    )
    details_semantically_unchanged = (
        prior_details.source is CommissioningEvidenceSource.USER_CONFIRMED
        and prior_details.confidence is Confidence.HIGH
        and prior_details.planted_at == updated_details.planted_at
        and prior_details.source_container_gallons
        == updated_details.source_container_gallons
        and prior_details.current_height_meters == updated_details.current_height_meters
    )
    if updated_group == prior_group and details_semantically_unchanged:
        return profile
    groups[plant_id] = updated_group
    details[plant_id] = updated_details
    event = LandscapeChangeEvent(
        edit.event_id,
        LandscapeEventType.PLANT_GROUP_UPDATED,
        edit.effective_at,
        LandscapePlantSnapshot(prior_group, prior_details),
    )
    return _rebuild_plant_profile(
        profile,
        groups=groups,
        details=details,
        events=(*profile.landscape_events, event),
    )


def update_delivery_link(
    profile: CommissionedZoneProfile,
    link: IrrigationDeliveryLink,
) -> CommissionedZoneProfile:
    """Replace one delivery association without inferring hydraulic facts."""
    groups, _details, links = _current_maps(profile)
    if link.plant_group_id not in groups:
        raise ValueError("delivery link references an unknown current plant group")
    links[link.plant_group_id] = link
    return replace(
        profile,
        delivery_links=tuple(links[key] for key in sorted(links)),
        execution_authorized=False,
        live_control_authorized=False,
    )


def set_calibrated_baseline(
    profile: CommissionedZoneProfile,
    baseline: UserCalibratedBaseline,
) -> CommissionedZoneProfile:
    """Add or replace baseline evidence without calculating demand or runtime."""
    sources = tuple(
        stripped
        for source in profile.demand_sources
        if (stripped := _strip_calibrated_baseline(source)) is not None
        and stripped.mode is not ZoneDemandSourceMode.UNRESOLVED
    )
    baseline_source = ZoneDemandSource(
        source_id=f"{profile.identity.zone_id}.source.user_calibrated_baseline",
        mode=ZoneDemandSourceMode.USER_CALIBRATED_BASELINE,
        calibrated_baseline=baseline,
    )
    return replace(
        profile,
        demand_sources=tuple(
            sorted((*sources, baseline_source), key=lambda source: source.source_id)
        ),
        execution_authorized=False,
        live_control_authorized=False,
    )


def remove_calibrated_baseline(
    profile: CommissionedZoneProfile,
) -> CommissionedZoneProfile:
    """Remove baseline evidence only when another demand source remains."""
    sources = tuple(
        stripped
        for source in profile.demand_sources
        if (stripped := _strip_calibrated_baseline(source)) is not None
    )
    if not sources:
        sources = (
            ZoneDemandSource(
                source_id=f"{profile.identity.zone_id}.source.unresolved",
                mode=ZoneDemandSourceMode.UNRESOLVED,
            ),
        )
    return replace(
        profile,
        demand_sources=sources,
        execution_authorized=False,
        live_control_authorized=False,
    )


def zone_setup_is_unresolved(profile: CommissionedZoneProfile) -> bool:
    """Return whether a physical zone has no current replaceable setup evidence."""

    return bool(
        not profile.landscape_profile.plant_groups
        and not profile.plant_details
        and len(profile.demand_sources) == 1
        and profile.demand_sources[0].mode is ZoneDemandSourceMode.UNRESOLVED
        and not profile.delivery_links
        and not profile.conflicts
        and not profile.conflict_resolutions
    )


def recommission_zone(
    profile: CommissionedZoneProfile,
    *,
    event_id: str,
    effective_at: datetime,
) -> CommissionedZoneProfile:
    """Retire the active setup while preserving physical identity and full evidence."""

    if zone_setup_is_unresolved(profile):
        raise ValueError("zone setup is already unresolved")
    retired_setup = LandscapeSetupSnapshot(
        landscape_profile=profile.landscape_profile,
        plant_details=profile.plant_details,
        demand_sources=profile.demand_sources,
        delivery_links=profile.delivery_links,
        conflicts=profile.conflicts,
        conflict_resolutions=profile.conflict_resolutions,
    )
    event = LandscapeChangeEvent(
        event_id=event_id,
        event_type=LandscapeEventType.ZONE_RECOMMISSIONED,
        effective_at=effective_at,
        setup_snapshot=retired_setup,
    )
    landscape = profile.landscape_profile
    reset_landscape = LandscapeIntelligenceProfile(
        schema_version=landscape.schema_version,
        area_slot=landscape.area_slot,
        profile_status="not_set_up",
        hydrozone_type=HydrozoneType.UNRESOLVED,
        hydrozone_quality=HydrozoneQuality.UNRESOLVED,
        irrigation_method="unresolved",
        emitter_family="unresolved",
        predominant_radius_ft=None,
        predominant_emitter_color=None,
        application_rate_status="unresolved",
        plant_groups=(),
        health_observations=(),
        plant_factor_status="unresolved",
        landscape_factor_status="unresolved",
    )
    return replace(
        profile,
        landscape_profile=reset_landscape,
        plant_details=(),
        demand_sources=(
            ZoneDemandSource(
                source_id=f"{profile.identity.zone_id}.source.unresolved",
                mode=ZoneDemandSourceMode.UNRESOLVED,
            ),
        ),
        delivery_links=(),
        landscape_events=tuple(
            sorted(
                (*profile.landscape_events, event),
                key=lambda item: (item.effective_at, item.event_id),
            )
        ),
        conflicts=(),
        conflict_resolutions=(),
        execution_authorized=False,
        live_control_authorized=False,
    )


def _strip_calibrated_baseline(
    source: ZoneDemandSource,
) -> ZoneDemandSource | None:
    """Remove only baseline evidence while preserving plant/visual provenance."""
    if source.calibrated_baseline is None:
        return source
    has_plants = bool(source.plant_group_ids)
    has_visual = bool(source.structured_visual_assessment_ids)
    if not has_plants and not has_visual:
        return None
    mode = (
        ZoneDemandSourceMode.HYBRID
        if has_plants and has_visual
        else ZoneDemandSourceMode.MANUAL_PLANT_PROFILE
        if has_plants
        else ZoneDemandSourceMode.PHOTO_AI_DERIVED
    )
    return ZoneDemandSource(
        source_id=source.source_id,
        mode=mode,
        plant_group_ids=source.plant_group_ids,
        structured_visual_assessment_ids=source.structured_visual_assessment_ids,
    )


def resolve_identity_conflict(
    profile: CommissionedZoneProfile,
    resolution: ConflictResolutionInput,
) -> CommissionedZoneProfile:
    """Record explicit human confirmation while preserving original candidates."""
    conflict = next(
        (
            item
            for item in profile.conflicts
            if item.conflict_id == resolution.conflict_id
        ),
        None,
    )
    if conflict is None:
        raise ValueError("cannot resolve an unknown commissioning conflict")
    if any(
        item.conflict_id == resolution.conflict_id
        for item in profile.conflict_resolutions
    ):
        raise ValueError("commissioning conflict is already resolved")
    groups, details, _links = _current_maps(profile)
    prior_group = groups[conflict.plant_group_id]
    prior_details = details[conflict.plant_group_id]
    selected_value = (
        resolution.confirmed_botanical_name or resolution.confirmed_common_name
    )
    groups[conflict.plant_group_id] = replace(
        prior_group,
        common_name=resolution.confirmed_common_name,
        botanical_name=resolution.confirmed_botanical_name,
        identification_confidence=resolution.confidence,
    )
    details[conflict.plant_group_id] = replace(
        prior_details,
        source=CommissioningEvidenceSource.USER_CONFIRMED,
        confidence=resolution.confidence,
        observed_at=resolution.resolved_at,
    )
    record = CommissioningConflictResolution(
        resolution_id=resolution.resolution_id,
        conflict_id=resolution.conflict_id,
        selected_value=selected_value,
        resolved_at=resolution.resolved_at,
        source=CommissioningEvidenceSource.USER_CONFIRMED,
        confidence=resolution.confidence,
        note=resolution.note,
    )
    event = LandscapeChangeEvent(
        resolution.event_id,
        LandscapeEventType.PLANT_GROUP_UPDATED,
        resolution.resolved_at,
        LandscapePlantSnapshot(prior_group, prior_details),
    )
    return _rebuild_plant_profile(
        profile,
        groups=groups,
        details=details,
        events=(*profile.landscape_events, event),
        resolutions=tuple(
            sorted(
                (*profile.conflict_resolutions, record),
                key=lambda item: item.resolution_id,
            )
        ),
    )
