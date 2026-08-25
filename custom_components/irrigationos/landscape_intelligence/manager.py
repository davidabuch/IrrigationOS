"""Durable generic Landscape Intelligence collection and compact summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .admission import assess_commissioning
from .commissioning import (
    CommissionedZoneProfile,
    DeactivatedCommissionedZone,
    assess_delivery_compatibility,
)
from .editing import CommissionedZoneReview, build_commissioning_review
from .factor_resolution import ZoneFactorResolution, resolve_zone_factor
from .models import HealthState, LandscapeIntelligenceProfile, summarize_health
from .persistence import (
    COMMISSIONING_STORE_SCHEMA_VERSION,
    build_store_payload,
    restore_store_payload,
)
from .zone1 import build_zone_1_commissioning_profile
from .zone1_factor_evidence import zone_1_factor_evidence

STORE_VERSION = 1
_ZONE1_KEY = ("property.primary", "zone.1")


def _key(profile: CommissionedZoneProfile) -> tuple[str, str]:
    return profile.identity.property_id, profile.identity.zone_id


class LandscapeIntelligenceManager:
    """Own the advisory generic commissioning persistence boundary."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            STORE_VERSION,
            f"irrigationos.{entry_id}.landscape_intelligence",
        )
        self._zones: tuple[CommissionedZoneProfile, ...] = ()
        self._deactivated_zones: tuple[DeactivatedCommissionedZone, ...] = ()
        self._legacy_zone1: dict[str, Any] = {}
        self._factor_resolutions: dict[tuple[str, str], ZoneFactorResolution] = {}
        self.last_persistence_error: str | None = None

    async def async_initialize(self, *, initial_observed_at: datetime) -> None:
        """Restore generic zones and additively migrate legacy Zone 1 storage."""
        zone1 = build_zone_1_commissioning_profile(initial_observed_at)
        self._zones = (zone1,)
        self._legacy_zone1 = zone1.to_landscape_intelligence_profile().to_dict()
        self._refresh_factor_resolutions()
        try:
            stored = await self._store.async_load()
        except Exception:
            self.last_persistence_error = "commissioning_store_load_failed"
            return
        if stored is None:
            await self._async_save(self._zones, self._deactivated_zones)
            return
        try:
            restored = restore_store_payload(stored, fallback_zone1=zone1)
        except (KeyError, TypeError, ValueError):
            self.last_persistence_error = "commissioning_store_restore_failed"
            return
        self._zones = restored.zones
        self._deactivated_zones = restored.deactivated_zones
        self._legacy_zone1 = restored.legacy_zone1
        self._refresh_factor_resolutions()
        self.last_persistence_error = None
        if restored.migration_required:
            await self._async_save(self._zones, self._deactivated_zones)

    @property
    def zone1(self) -> LandscapeIntelligenceProfile:
        """Return the commissioned Zone 1 profile through its legacy API."""
        zone = self.get_zone(*_ZONE1_KEY)
        if zone is None:
            raise RuntimeError("landscape intelligence not initialized")
        return zone.to_landscape_intelligence_profile()

    @property
    def commissioned_zones(self) -> tuple[CommissionedZoneProfile, ...]:
        """Return active generic zones in deterministic canonical order."""
        return self._zones

    @property
    def deactivated_zones(self) -> tuple[DeactivatedCommissionedZone, ...]:
        """Return evidence-preserving zone tombstones."""
        return self._deactivated_zones

    def get_zone(self, property_id: str, zone_id: str) -> CommissionedZoneProfile | None:
        """Look up one active zone by stable canonical identity."""
        return next(
            (zone for zone in self._zones if _key(zone) == (property_id, zone_id)),
            None,
        )

    def get_zone_by_slots(
        self, controller_slot: int, area_slot: int
    ) -> CommissionedZoneProfile | None:
        """Resolve one unambiguous active canonical controller/area binding."""
        matches = tuple(
            zone
            for zone in self._zones
            if zone.identity.controller_slot == controller_slot
            and zone.identity.area_slot == area_slot
        )
        return matches[0] if len(matches) == 1 else None

    def review_zone(
        self, property_id: str, zone_id: str
    ) -> CommissionedZoneReview | None:
        """Build a bounded detailed review for one active commissioned zone."""
        profile = self.get_zone(property_id, zone_id)
        return None if profile is None else build_commissioning_review(profile)

    async def async_add_zone(self, profile: CommissionedZoneProfile) -> bool:
        """Durably add a new canonical zone before exposing it in memory."""
        if self.get_zone(profile.identity.property_id, profile.identity.zone_id) is not None:
            return False
        return await self._async_save((*self._zones, profile), self._deactivated_zones)

    async def async_update_zone(self, profile: CommissionedZoneProfile) -> bool:
        """Durably replace one profile with the same immutable canonical identity."""
        key = _key(profile)
        if self.get_zone(*key) is None:
            return False
        zones = tuple(profile if _key(zone) == key else zone for zone in self._zones)
        return await self._async_save(zones, self._deactivated_zones)

    async def async_upsert_zone(self, profile: CommissionedZoneProfile) -> bool:
        """Durably add or update one mapped onboarding result."""
        if self.get_zone(profile.identity.property_id, profile.identity.zone_id) is None:
            return await self.async_add_zone(profile)
        return await self.async_update_zone(profile)

    async def async_deactivate_zone(
        self,
        property_id: str,
        zone_id: str,
        *,
        deactivated_at: datetime,
        reason: str,
    ) -> bool:
        """Deactivate a non-legacy zone while retaining its complete evidence."""
        key = (property_id, zone_id)
        if key == _ZONE1_KEY:
            return False
        profile = self.get_zone(*key)
        if profile is None:
            return False
        tombstone = DeactivatedCommissionedZone(profile, deactivated_at, reason)
        zones = tuple(zone for zone in self._zones if _key(zone) != key)
        tombstones = tuple(
            item for item in self._deactivated_zones if _key(item.profile) != key
        )
        return await self._async_save(zones, (*tombstones, tombstone))

    def compact_summary(self, area_slot: int) -> dict[str, Any] | None:
        """Return Recorder-safe summary data without longitudinal history."""
        matches = tuple(
            zone for zone in self._zones if zone.identity.area_slot == area_slot
        )
        if len(matches) != 1:
            return None
        commissioned = matches[0]
        profile = commissioned.to_landscape_intelligence_profile()
        summaries = [
            summarize_health(profile, group.plant_group_id)
            for group in profile.plant_groups
        ]
        exceptions = [
            summary
            for summary in summaries
            if summary.latest_state
            in {HealthState.STRESSED, HealthState.SEVERELY_STRESSED}
        ]
        resolution = self._factor_resolutions.get(_key(commissioned))
        compatibility = assess_delivery_compatibility(commissioned)
        assessment = assess_commissioning(commissioned)
        resolved_conflict_ids = {
            item.conflict_id for item in commissioned.conflict_resolutions
        }
        return {
            "schema_version": profile.schema_version,
            "hydrozone_type": profile.hydrozone_type.value,
            "hydrozone_quality": profile.hydrozone_quality.value,
            "plant_group_count": len(profile.plant_groups),
            "health_exception_count": len(exceptions),
            "plant_factor_status": profile.plant_factor_status,
            "factor_resolution_status": (
                None if resolution is None else resolution.status.value
            ),
            "landscape_factor_status": profile.landscape_factor_status,
            "commissioning_conflict_count": sum(
                conflict.conflict_id not in resolved_conflict_ids
                for conflict in commissioned.conflicts
            ),
            "delivery_compatibility_state": compatibility.state.value,
            "commissioning_assessment_status": assessment.status.value,
            "commissioning_ready_purpose_count": sum(
                item.state.value == "ready" for item in assessment.purpose_readiness
            ),
            "commissioning_follow_up_count": len(assessment.follow_up_requirements),
            "execution_authorized": False,
            "live_control_authorized": False,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return detailed evidence plus a bounded privacy-safe collection summary."""
        if not self._zones:
            return {}
        summaries = []
        for zone in self._zones:
            compatibility = assess_delivery_compatibility(zone)
            assessment = assess_commissioning(zone)
            resolved_conflict_ids = {
                item.conflict_id for item in zone.conflict_resolutions
            }
            unresolved_conflicts = tuple(
                item
                for item in zone.conflicts
                if item.conflict_id not in resolved_conflict_ids
            )
            summaries.append(
                {
                    "identity": zone.identity.to_dict(),
                    "demand_source_modes": [
                        source.mode.value for source in zone.demand_sources
                    ],
                    "conflict_count": len(unresolved_conflicts),
                    "conflict_ids": [
                        item.conflict_id for item in unresolved_conflicts
                    ],
                    "conflict_resolution_count": len(zone.conflict_resolutions),
                    "delivery_compatibility_state": compatibility.state.value,
                    "advisory_codes": [
                        advisory.code for advisory in compatibility.advisories
                    ],
                    "commissioning_assessment": assessment.to_dict(),
                }
            )
        zone1_resolution = self._factor_resolutions.get(_ZONE1_KEY)
        return {
            "zone_1": self.zone1.to_dict(),
            "commissioned_zones": [zone.to_dict() for zone in self._zones],
            "zone_1_factor_resolution": (
                None if zone1_resolution is None else zone1_resolution.to_dict()
            ),
            "commissioning_summary": {
                "store_schema_version": COMMISSIONING_STORE_SCHEMA_VERSION,
                "commissioned_zone_count": len(self._zones),
                "deactivated_zone_count": len(self._deactivated_zones),
                "zones": summaries,
                "legacy_zone_1_compatible": self.get_zone(*_ZONE1_KEY) is not None,
                "last_persistence_error": self.last_persistence_error,
            },
        }

    async def _async_save(
        self,
        zones: tuple[CommissionedZoneProfile, ...],
        deactivated_zones: tuple[DeactivatedCommissionedZone, ...],
    ) -> bool:
        try:
            payload = build_store_payload(
                zones,
                deactivated_zones,
                legacy_zone1=self._legacy_zone1,
            )
            await self._store.async_save(payload)
        except Exception:
            self.last_persistence_error = "commissioning_store_save_failed"
            return False
        self._zones = tuple(
            sorted(zones, key=lambda zone: (zone.identity.property_id, zone.identity.zone_id))
        )
        self._deactivated_zones = tuple(
            sorted(
                deactivated_zones,
                key=lambda item: (
                    item.profile.identity.property_id,
                    item.profile.identity.zone_id,
                ),
            )
        )
        self._refresh_factor_resolutions()
        self.last_persistence_error = None
        return True

    def _refresh_factor_resolutions(self) -> None:
        zone1 = self.get_zone(*_ZONE1_KEY)
        self._factor_resolutions = (
            {}
            if zone1 is None
            else {
                _ZONE1_KEY: resolve_zone_factor(
                    zone1.to_landscape_intelligence_profile(), zone_1_factor_evidence()
                )
            }
        )
