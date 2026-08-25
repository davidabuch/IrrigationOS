"""Deterministic persistence and additive migration for commissioned zones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..water_delivery import WaterDeliveryProfile
from ..water_delivery.persistence import water_delivery_profile_from_dict
from .commissioning import (
    ZONE_COMMISSIONING_SCHEMA_VERSION,
    BaselineEnvironmentalReference,
    BaselineReferenceSource,
    CanonicalZoneIdentity,
    CommissionedZoneProfile,
    CommissioningConflictCandidate,
    CommissioningConflictResolution,
    CommissioningEvidenceConflict,
    CommissioningEvidenceSource,
    DeactivatedCommissionedZone,
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
    HealthState,
    HydrozoneQuality,
    HydrozoneType,
    IrrigationRole,
    LandscapeIntelligenceProfile,
    ObservationSource,
    PlantGroup,
    PlantHealthObservation,
)

COMMISSIONING_STORE_SCHEMA_VERSION = 6


@dataclass(frozen=True, slots=True)
class CommissioningStoreSnapshot:
    """Validated in-memory representation of one Store payload."""

    zones: tuple[CommissionedZoneProfile, ...]
    deactivated_zones: tuple[DeactivatedCommissionedZone, ...]
    delivery_profiles: tuple[WaterDeliveryProfile, ...]
    legacy_zone1: dict[str, Any]
    migration_required: bool


def _mapping(name: str, value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _sequence(name: str, value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def _strings(name: str, value: object) -> tuple[str, ...]:
    values = _sequence(name, value)
    if any(not isinstance(item, str) for item in values):
        raise ValueError(f"{name} must contain strings")
    return tuple(str(item) for item in values)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text must be a string")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("optional number must be numeric")
    return float(value)


def _boolean(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO 8601 string")
    return datetime.fromisoformat(value)


def _plant_group(value: object) -> PlantGroup:
    item = _mapping("plant group", value)
    controls = item.get("controls_zone_demand")
    if controls is not None and not isinstance(controls, bool):
        raise ValueError("controls_zone_demand must be boolean or null")
    return PlantGroup(
        plant_group_id=str(item["plant_group_id"]),
        common_name=str(item["common_name"]),
        botanical_name=_optional_string(item.get("botanical_name")),
        identification_confidence=Confidence(str(item["identification_confidence"])),
        irrigation_role=IrrigationRole(str(item["irrigation_role"])),
        establishment_state=EstablishmentState(str(item["establishment_state"])),
        direct_irrigation=_boolean("direct_irrigation", item["direct_irrigation"]),
        dedicated_emitter=_boolean("dedicated_emitter", item["dedicated_emitter"]),
        emitter_type=_optional_string(item.get("emitter_type")),
        approximate_age_years=_optional_string(item.get("approximate_age_years")),
        emitter_relationship=_optional_string(item.get("emitter_relationship")),
        expected_water_use_class=_optional_string(item.get("expected_water_use_class")),
        scientific_source=_optional_string(item.get("scientific_source")),
        controls_zone_demand=controls,
    )


def _health_observation(value: object) -> PlantHealthObservation:
    item = _mapping("health observation", value)
    return PlantHealthObservation(
        observation_id=str(item["observation_id"]),
        plant_group_id=str(item["plant_group_id"]),
        observed_at=_datetime(item["observed_at"]),
        source=ObservationSource(str(item["source"])),
        confidence=Confidence(str(item["confidence"])),
        overall_state=HealthState(str(item["overall_state"])),
        findings=_strings("findings", item["findings"]),
        direct_irrigation=_boolean("direct_irrigation", item["direct_irrigation"]),
        visible_coverage_problem=item.get("visible_coverage_problem"),
        application_adequacy=str(item["application_adequacy"]),
        suspected_water_stress=str(item["suspected_water_stress"]),
        diagnosis=str(item["diagnosis"]),
        automatic_runtime_adjustment=_boolean(
            "automatic_runtime_adjustment",
            item.get("automatic_runtime_adjustment", False),
        ),
    )


def _landscape_profile(value: object) -> LandscapeIntelligenceProfile:
    item = _mapping("landscape profile", value)
    return LandscapeIntelligenceProfile(
        schema_version=int(item["schema_version"]),
        area_slot=int(item["area_slot"]),
        profile_status=str(item["profile_status"]),
        hydrozone_type=HydrozoneType(str(item["hydrozone_type"])),
        hydrozone_quality=HydrozoneQuality(str(item["hydrozone_quality"])),
        irrigation_method=str(item["irrigation_method"]),
        emitter_family=str(item["emitter_family"]),
        predominant_radius_ft=_optional_float(item.get("predominant_radius_ft")),
        predominant_emitter_color=_optional_string(
            item.get("predominant_emitter_color")
        ),
        application_rate_status=str(item["application_rate_status"]),
        plant_groups=tuple(
            _plant_group(group) for group in _sequence("plant_groups", item["plant_groups"])
        ),
        health_observations=tuple(
            _health_observation(observation)
            for observation in _sequence(
                "health_observations", item["health_observations"]
            )
        ),
        plant_factor_status=str(item.get("plant_factor_status", "unresolved")),
        landscape_factor_status=str(item.get("landscape_factor_status", "unresolved")),
        execution_authorized=_boolean(
            "execution_authorized", item.get("execution_authorized", False)
        ),
        live_control_authorized=_boolean(
            "live_control_authorized", item.get("live_control_authorized", False)
        ),
    )


def _plant_details(value: object) -> PlantCommissioningDetails:
    item = _mapping("plant commissioning details", value)
    return PlantCommissioningDetails(
        plant_group_id=str(item["plant_group_id"]),
        source=CommissioningEvidenceSource(str(item["source"])),
        confidence=Confidence(str(item["confidence"])),
        observed_at=_datetime(item["observed_at"]),
        planted_at=(None if item.get("planted_at") is None else _datetime(item["planted_at"])),
        source_container_gallons=_optional_float(item.get("source_container_gallons")),
        current_height_meters=_optional_float(item.get("current_height_meters")),
        structured_evidence_ids=_strings(
            "structured_evidence_ids", item.get("structured_evidence_ids", [])
        ),
    )


def _baseline(value: object) -> UserCalibratedBaseline:
    item = _mapping("calibrated baseline", value)
    environmental_reference = item.get("environmental_reference")
    return UserCalibratedBaseline(
        runtime_seconds=int(item["runtime_seconds"]),
        reference_air_temperature_celsius=float(
            item["reference_air_temperature_celsius"]
        ),
        reference_recent_precipitation_mm=float(
            item["reference_recent_precipitation_mm"]
        ),
        reference_condition=str(item["reference_condition"]),
        calibrated_at=_datetime(item["calibrated_at"]),
        confidence=Confidence(str(item["confidence"])),
        environmental_reference=(
            None
            if environmental_reference is None
            else _baseline_environmental_reference(environmental_reference)
        ),
        reference_history=tuple(
            _baseline_environmental_reference(reference)
            for reference in _sequence(
                "baseline reference history", item.get("reference_history", [])
            )
        ),
    )


def _baseline_environmental_reference(value: object) -> BaselineEnvironmentalReference:
    item = _mapping("baseline environmental reference", value)
    return BaselineEnvironmentalReference(
        reference_et0_mm=float(item["reference_et0_mm"]),
        period_hours=int(item["period_hours"]),
        observed_at=_datetime(item["observed_at"]),
        source=str(item["source"]),
        confidence=Confidence(str(item["confidence"])),
        observed_air_temperature_celsius=_optional_float(
            item.get("observed_air_temperature_celsius")
        ),
        quality=str(item.get("quality", "user_confirmed")),
        capture_method=BaselineReferenceSource(
            str(item.get("capture_method", "manually_entered_reference"))
        ),
        captured_at=(
            None if item.get("captured_at") is None else _datetime(item["captured_at"])
        ),
        evidence_ids=_strings("baseline reference evidence_ids", item.get("evidence_ids", [])),
    )


def _demand_source(value: object) -> ZoneDemandSource:
    item = _mapping("zone demand source", value)
    baseline = item.get("calibrated_baseline")
    return ZoneDemandSource(
        source_id=str(item["source_id"]),
        mode=ZoneDemandSourceMode(str(item["mode"])),
        plant_group_ids=_strings("plant_group_ids", item.get("plant_group_ids", [])),
        structured_visual_assessment_ids=_strings(
            "structured_visual_assessment_ids",
            item.get("structured_visual_assessment_ids", []),
        ),
        calibrated_baseline=None if baseline is None else _baseline(baseline),
    )


def _delivery_link(value: object) -> IrrigationDeliveryLink:
    item = _mapping("irrigation delivery link", value)
    dedicated = item.get("dedicated_delivery")
    if dedicated is not None and not isinstance(dedicated, bool):
        raise ValueError("dedicated_delivery must be boolean or null")
    return IrrigationDeliveryLink(
        link_id=str(item["link_id"]),
        plant_group_id=str(item["plant_group_id"]),
        status=DeliveryLinkStatus(str(item["status"])),
        delivery_profile_id=_optional_string(item.get("delivery_profile_id")),
        component_ids=_strings("component_ids", item.get("component_ids", [])),
        dedicated_delivery=dedicated,
    )


def _plant_snapshot(value: object) -> LandscapePlantSnapshot:
    item = _mapping("landscape plant snapshot", value)
    return LandscapePlantSnapshot(
        plant_group=_plant_group(item["plant_group"]),
        commissioning_details=_plant_details(item["commissioning_details"]),
    )


def _landscape_event(value: object) -> LandscapeChangeEvent:
    item = _mapping("landscape change event", value)
    return LandscapeChangeEvent(
        event_id=str(item["event_id"]),
        event_type=LandscapeEventType(str(item["event_type"])),
        effective_at=_datetime(item["effective_at"]),
        plant_snapshot=_plant_snapshot(item["plant_snapshot"]),
    )


def _conflict_candidate(value: object) -> CommissioningConflictCandidate:
    item = _mapping("commissioning conflict candidate", value)
    return CommissioningConflictCandidate(
        source=CommissioningEvidenceSource(str(item["source"])),
        value=str(item["value"]),
        confidence=Confidence(str(item["confidence"])),
        evidence_ids=_strings("evidence_ids", item.get("evidence_ids", [])),
    )


def _conflict(value: object) -> CommissioningEvidenceConflict:
    item = _mapping("commissioning conflict", value)
    return CommissioningEvidenceConflict(
        conflict_id=str(item["conflict_id"]),
        plant_group_id=str(item["plant_group_id"]),
        field_path=str(item["field_path"]),
        candidates=tuple(
            _conflict_candidate(candidate)
            for candidate in _sequence("conflict candidates", item["candidates"])
        ),
        detail=str(item["detail"]),
        unresolved=_boolean("unresolved", item.get("unresolved", True)),
    )


def _conflict_resolution(value: object) -> CommissioningConflictResolution:
    item = _mapping("commissioning conflict resolution", value)
    return CommissioningConflictResolution(
        resolution_id=str(item["resolution_id"]),
        conflict_id=str(item["conflict_id"]),
        selected_value=str(item["selected_value"]),
        resolved_at=_datetime(item["resolved_at"]),
        source=CommissioningEvidenceSource(str(item["source"])),
        confidence=Confidence(str(item["confidence"])),
        note=_optional_string(item.get("note")),
    )


def commissioned_zone_from_dict(value: object) -> CommissionedZoneProfile:
    """Restore supported commissioned-zone data through additive migration."""
    item = _mapping("commissioned zone", value)
    source_schema = int(item["schema_version"])
    if source_schema not in {1, 2, 3, 4, ZONE_COMMISSIONING_SCHEMA_VERSION}:
        raise ValueError("commissioned zone schema is unsupported")
    identity = _mapping("canonical zone identity", item["identity"])
    return CommissionedZoneProfile(
        schema_version=ZONE_COMMISSIONING_SCHEMA_VERSION,
        identity=CanonicalZoneIdentity(
            property_id=str(identity["property_id"]),
            zone_id=str(identity["zone_id"]),
            controller_slot=(
                None
                if identity.get("controller_slot") is None
                else int(identity["controller_slot"])
            ),
            area_slot=int(identity["area_slot"]),
        ),
        display_name=str(item["display_name"]),
        landscape_profile=_landscape_profile(item["landscape_profile"]),
        plant_details=tuple(
            _plant_details(details)
            for details in _sequence("plant_details", item["plant_details"])
        ),
        demand_sources=tuple(
            _demand_source(source)
            for source in _sequence("demand_sources", item["demand_sources"])
        ),
        delivery_links=tuple(
            _delivery_link(link)
            for link in _sequence("delivery_links", item["delivery_links"])
        ),
        landscape_events=tuple(
            _landscape_event(event)
            for event in _sequence("landscape_events", item.get("landscape_events", []))
        ),
        conflicts=tuple(
            _conflict(conflict)
            for conflict in _sequence("conflicts", item.get("conflicts", []))
        ),
        conflict_resolutions=tuple(
            _conflict_resolution(resolution)
            for resolution in _sequence(
                "conflict_resolutions", item.get("conflict_resolutions", [])
            )
        ),
        execution_authorized=_boolean(
            "execution_authorized", item.get("execution_authorized", False)
        ),
        live_control_authorized=_boolean(
            "live_control_authorized", item.get("live_control_authorized", False)
        ),
    )


def deactivated_zone_from_dict(value: object) -> DeactivatedCommissionedZone:
    """Restore one evidence-preserving zone tombstone."""
    item = _mapping("deactivated commissioned zone", value)
    return DeactivatedCommissionedZone(
        profile=commissioned_zone_from_dict(item["profile"]),
        deactivated_at=_datetime(item["deactivated_at"]),
        reason=str(item["reason"]),
    )


def _zone_key(profile: CommissionedZoneProfile) -> tuple[str, str]:
    return profile.identity.property_id, profile.identity.zone_id


def _validate_order(zones: tuple[CommissionedZoneProfile, ...]) -> None:
    keys = tuple(_zone_key(zone) for zone in zones)
    if len(keys) != len(set(keys)):
        raise ValueError("commissioned zone identities must be unique")
    if keys != tuple(sorted(keys)):
        raise ValueError("commissioned zones must be deterministically ordered")
    bindings = tuple(
        (zone.identity.controller_slot, zone.identity.area_slot)
        for zone in zones
        if zone.identity.controller_slot is not None
    )
    if len(bindings) != len(set(bindings)):
        raise ValueError("one canonical controller area cannot bind multiple active zones")


def restore_store_payload(
    stored: object,
    *,
    fallback_zone1: CommissionedZoneProfile,
) -> CommissioningStoreSnapshot:
    """Restore legacy or current Store data through additive migration."""
    item = _mapping("landscape intelligence store", stored)
    if int(item.get("schema_version", 1)) != 1:
        raise ValueError("legacy landscape intelligence schema is unsupported")
    payload_schema = int(item.get("commissioning_store_schema_version", 1))
    if payload_schema not in {1, 2, 3, 4, 5, COMMISSIONING_STORE_SCHEMA_VERSION}:
        raise ValueError("commissioning Store schema is unsupported")
    if (
        payload_schema == COMMISSIONING_STORE_SCHEMA_VERSION
        and "water_delivery_profiles" not in item
    ):
        raise ValueError("current commissioning Store is missing delivery profiles")
    legacy_zone1 = _mapping("legacy zone_1", item["zone_1"])
    raw_zones = item.get("commissioned_zones")
    zones: tuple[CommissionedZoneProfile, ...]
    if raw_zones is None:
        zones = (fallback_zone1,)
        migration_required = True
    else:
        zones = tuple(
            commissioned_zone_from_dict(zone)
            for zone in _sequence("commissioned_zones", raw_zones)
        )
        missing_zone1 = not any(
            _zone_key(zone) == _zone_key(fallback_zone1) for zone in zones
        )
        if missing_zone1:
            zones = (*zones, fallback_zone1)
        zones = tuple(sorted(zones, key=_zone_key))
        migration_required = (
            payload_schema != COMMISSIONING_STORE_SCHEMA_VERSION
            or missing_zone1
            or any(
                int(_mapping("commissioned zone", zone)["schema_version"])
                != ZONE_COMMISSIONING_SCHEMA_VERSION
                for zone in _sequence("commissioned_zones", raw_zones)
            )
        )
    deactivated = tuple(
        deactivated_zone_from_dict(zone)
        for zone in _sequence("deactivated_zones", item.get("deactivated_zones", []))
    )
    deactivated = tuple(
        sorted(deactivated, key=lambda value: _zone_key(value.profile))
    )
    _validate_order(zones)
    delivery_profiles = tuple(
        sorted(
            (
                water_delivery_profile_from_dict(profile)
                for profile in _sequence(
                    "water_delivery_profiles", item.get("water_delivery_profiles", [])
                )
            ),
            key=lambda profile: profile.profile_id,
        )
    )
    profile_ids = tuple(profile.profile_id for profile in delivery_profiles)
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("water delivery profile IDs must be unique")
    return CommissioningStoreSnapshot(
        zones=zones,
        deactivated_zones=deactivated,
        delivery_profiles=delivery_profiles,
        legacy_zone1=legacy_zone1,
        migration_required=migration_required,
    )


def build_store_payload(
    zones: tuple[CommissionedZoneProfile, ...],
    deactivated_zones: tuple[DeactivatedCommissionedZone, ...],
    *,
    legacy_zone1: dict[str, Any],
    delivery_profiles: tuple[WaterDeliveryProfile, ...] = (),
) -> dict[str, Any]:
    """Build deterministic current Store data while retaining legacy Zone 1."""
    ordered = tuple(sorted(zones, key=_zone_key))
    _validate_order(ordered)
    ordered_deactivated = tuple(
        sorted(deactivated_zones, key=lambda value: _zone_key(value.profile))
    )
    ordered_delivery = tuple(
        sorted(delivery_profiles, key=lambda profile: profile.profile_id)
    )
    profile_ids = tuple(profile.profile_id for profile in ordered_delivery)
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("water delivery profile IDs must be unique")
    return {
        "schema_version": 1,
        "commissioning_store_schema_version": COMMISSIONING_STORE_SCHEMA_VERSION,
        "zone_1": legacy_zone1,
        "commissioned_zones": [zone.to_dict() for zone in ordered],
        "deactivated_zones": [zone.to_dict() for zone in ordered_deactivated],
        "water_delivery_profiles": [profile.to_dict() for profile in ordered_delivery],
    }
